import os
import subprocess
import shutil
from pathlib import Path
from config import ( SCENES_DIR, MANIM_QUALITY)

# Manim Quality Flags
# These map to Manim CLI flags
# Use low_quality during development — renders in seconds not minutes
# Switch to high_quality for final output

QUALITY_FLAGS ={
    "low_quality": "-ql",      # 480p, fast — use for testing
    "medium_quality": "-qm",   # 720p, moderate
    "high_quality": "-qh",     # 1080p, slow — use for final render
    "production_quality": "-qk" # 4K, very slow
}

# Animation durations
# How long each animation type takes to play
# These are subtracted from wait times to keep sync accurate
ANIM_DURATIONS = {
    "title": 1.0,      # FadeIn for titles
    "subtitle": 0.8,   # FadeIn for subtitles
    "bullet": 0.6,     # Write animation for bullets
    "diagram": 1.2,    # Create for diagrams
    "code": 0.8,       # Write for code blocks
    "equation": 1.0,   # Write for equations
    "arrow": 0.6,      # GrowArrow for arrows
    "highlight": 0.5,  # Indicate for highlights
}

def generate_manim_scene_code(
    scene_number : int,
    scene_title : str,
    visual_elements : list,
    actual_duration : float,
    style : str = "technical"
) -> str:
    """
    Generates a complete Manim Python script for one scene.

    Why generate code instead of calling Manim directly?
    Manim requires Python class definitions — there is no
    functional API to call programmatically. We generate
    the class definition as a string, write it to a file,
    and execute it. This is the standard approach for
    dynamic Manim usage.

    The generated code:
      1. Imports Manim
      2. Defines a Scene class with construct() method
      3. Adds each visual element at its appear_at time
      4. Fills remaining time with self.wait() to match audio duration
    """

    # Style configuration, Colors adapt to the video style
    style_config = {
        "technical": {
            "background": "\"#0D1117\"",   # dark GitHub-like background
            "title_color": "\"#58A6FF\"",  # blue
            "text_color": "WHITE",
            "bullet_color": "\"#3FB950\"", # green
            "diagram_color": "\"#F78166\"", # red/orange
            "code_color": "\"#FFA657\"",   # orange
        },
        "finance": {
            "background": "\"#FFFFFF\"",
            "title_color": "\"#1A1A2E\"",
            "text_color": "\"#16213E\"",
            "bullet_color": "\"#0F3460\"",
            "diagram_color": "\"#E94560\"",
            "code_color": "\"#533483\"",
        },
        "general": {
            "background": "\"#1A1A2E\"",
            "title_color": "\"#E94560\"",
            "text_color": "WHITE",
            "bullet_color": "\"#0F3460\"",
            "diagram_color": "\"#533483\"",
            "code_color": "\"#E94560\"",
        }
    }

    colors = style_config.get(style, style_config["technical"])

    # Build animation sequence,Each element becomes a block of Manim code, We track current_time to calculate wait() durations

    animation_blocks = []
    current_time = 0.0
    element_vars = []  # track variable names for cleanup
    
    # Sort elements by appear_at to ensure correct order
    sorted_elements = sorted(visual_elements, key=lambda e: e.get("appear_at", 0.0))

    for i,element in enumerate(sorted_elements):
        appear_at = element.get("appear_at" , 0.0)
        visual_type = element.get("visual_type", "bullet")
        text = element.get("text", "").replace('"', '\\"').replace("'", "\\'")
        position = element.get("position", "center")
        emphasis = element.get("emphasis", False)
        var_name = f"elem_{i}"
        element_vars.append(var_name)

        anim_duration = ANIM_DURATIONS.get(visual_type, 0.6)

        # Calculate wait time before this element
        wait_before = appear_at - current_time
        if wait_before > 0.05:
            animation_blocks.append(f"        self.wait({wait_before:.2f})")
        
        # Generate animation code based on visual type
        if visual_type == "title":
            animation_blocks.extend([
                f'        {var_name} = Text("{text}", font_size=56, color={colors["title_color"]})',
                f"        {var_name}.move_to(UP * 2.5)",
                f"        self.play(FadeIn({var_name}), run_time={anim_duration})",
            ])   
        elif visual_type == "subtitle":
            animation_blocks.extend([
                f'        {var_name} = Text("{text}", font_size=36, color={colors["text_color"]})',
                f"        {var_name}.move_to(UP * 1.5)",
                f"        self.play(FadeIn({var_name}), run_time={anim_duration})",
            ])
        elif visual_type == "bullet":
            # Stack bullets vertically based on how many have appeared
            bullet_index = sum(
                1 for e in sorted_elements[:i]
                if e.get("visual_type") == "bullet"
            )
            y_pos = 0.5 - (bullet_index * 0.8)
            animation_blocks.extend([
                f'        {var_name} = Text("• {text}", font_size=32, color={colors["bullet_color"]})',
                f"        {var_name}.move_to(LEFT * 2 + UP * {y_pos:.1f})",
                f"        {var_name}.align_to(LEFT * 5, LEFT)",
                f"        self.play(Write({var_name}), run_time={anim_duration})",
            ])

        elif visual_type == "diagram":
            animation_blocks.extend([
                f'        {var_name}_box = RoundedRectangle(corner_radius=0.2, width=4, height=1.5, color={colors["diagram_color"]})',
                f'        {var_name}_text = Text("{text}", font_size=28, color={colors["diagram_color"]})',
                f"        {var_name}_text.move_to({var_name}_box.get_center())",
                f"        {var_name} = VGroup({var_name}_box, {var_name}_text)",
                f"        {var_name}.move_to(ORIGIN)",
                f"        self.play(Create({var_name}_box), Write({var_name}_text), run_time={anim_duration})",
            ])
        elif visual_type == "code":
            # Code blocks use monospace styling
            animation_blocks.extend([
                f'        {var_name} = Code(code="{text}", language="python", font_size=24)',
                f"        {var_name}.move_to(DOWN * 0.5)",
                f"        self.play(Write({var_name}), run_time={anim_duration})",
            ])

        elif visual_type == "equation":
            animation_blocks.extend([
                f'        {var_name} = MathTex(r"{text}", color={colors["text_color"]})',
                f"        {var_name}.scale(1.2)",
                f"        {var_name}.move_to(ORIGIN)",
                f"        self.play(Write({var_name}), run_time={anim_duration})",
            ])
        elif visual_type == "arrow":
            animation_blocks.extend([
                f'        {var_name} = Arrow(LEFT * 2, RIGHT * 2, color={colors["diagram_color"]})',
                f'        {var_name}_label = Text("{text}", font_size=28, color={colors["text_color"]})',
                f"        {var_name}_label.next_to({var_name}, UP)",
                f"        self.play(GrowArrow({var_name}), Write({var_name}_label), run_time={anim_duration})",
            ])

        elif visual_type == "highlight":
            animation_blocks.extend([
                f'        {var_name} = Text("{text}", font_size=40, color=YELLOW)',
                f"        {var_name}.move_to(ORIGIN)",
                f"        self.play(FadeIn({var_name}, scale=1.3), run_time={anim_duration})",
            ])

        else:
            # Fallback for unknown types
            animation_blocks.extend([
                f'        {var_name} = Text("{text}", font_size=32, color={colors["text_color"]})',
                f"        self.play(FadeIn({var_name}), run_time={anim_duration})",
            ])
        # Add emphasis flash if requested
        if emphasis:
            animation_blocks.append(
                f"        self.play(Indicate({var_name}), run_time=0.5)"
            )
            anim_duration += 0.5

        current_time = appear_at + anim_duration

    # Fill remaining time with wait() to match actual audio duration
    remaining_time = actual_duration - current_time
    if remaining_time > 0.1:
        animation_blocks.append(
            f"        self.wait({remaining_time:.2f})"
        )
    
    # Assemble the full python file for the Manim script
    class_name = f"Scene{scene_number:02d}"
    animation_code = "\n".join(animation_blocks)

    code = f'''from manim import *

config.background_color = {colors["background"]}
config.pixel_height = 1080
config.pixel_width = 1920
config.frame_rate = 30

class {class_name}(Scene):
    """
    Auto-generated Manim scene for: {scene_title}
    Scene number: {scene_number}
    Duration: {actual_duration}s
    """
    def construct(self):
{animation_code}
'''
    
    return code

def render_manim_scene(
    scene_number: int,
    scene_title: str,
    visual_elements: list,
    actual_duration: float,
    style: str = "technical",
) -> dict:
    """
    Generates Manim code for a scene and renders it to MP4.

    Steps:
      1. Generate Python code with generate_manim_scene_code()
      2. Write to a temp file in outputs/scenes/
      3. Execute with subprocess: manim -ql scene.py ClassName
      4. Find the rendered MP4 in Manim's output directory
      5. Copy to our outputs/scenes/ folder
      6. Return result dict

    Why subprocess?
    Manim is designed as a CLI tool. While it has a Python API,
    the CLI approach is more stable across Manim versions and
    gives us full control over quality flags and output paths.

    Returns dict with:
      success: bool
      file_path: str (path to final MP4)
      error: str (if failed)
    """
    os.makedirs(SCENES_DIR, exist_ok=True)

    class_name = f"Scene{scene_number:02d}"
    script_filename = f"scene_{scene_number:02d}_manim.py"
    script_path = os.path.join(SCENES_DIR, script_filename)
    output_filename = f"scene_{scene_number:02d}.mp4"
    output_path = os.path.join(SCENES_DIR, output_filename)

    #Step 1 & 2 : Generate code and write to file
    manim_code = generate_manim_scene_code(
        scene_number=scene_number,
        scene_title=scene_title,
        visual_elements=visual_elements,
        actual_duration=actual_duration,
        style=style
    )

    with open(script_path, "w") as f:
        f.write(manim_code)
    
    print(f"  [Manim] Generated script: {script_filename}")

    #Step 3: Execute Manim CLI to render the scene
    quality_flag = QUALITY_FLAGS.get(MANIM_QUALITY, "-ql")

    cmd = [
        "manim",
        quality_flag,
        script_path,
        class_name,
        "--output_file", output_filename,
        "--media_dir", SCENES_DIR
    ]
    print(f"  [Manim] Rendering {class_name} ({MANIM_QUALITY})...")
    print(f"  [Manim] This may take 30-120 seconds per scene...")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode == 0:
            # Step 4: Find the rendered MP4 in Manim's output directory
            # Manim saves to: media_dir/videos/script_name/quality/ClassName.mp4
            rendered_path = find_rendered_mp4(
                SCENES_DIR, class_name, script_filename
            )

            if rendered_path and os.path.exists(rendered_path):
                # Step 5: Copy to our outputs/scenes/ folder
                shutil.copy2(rendered_path, output_path)
                print(f"  [Manim] ✅ Rendered: {output_filename}")
                return {"success": True, "file_path": output_path, "error": None}
            else:
                return {"success": False, "file_path": None, "error": f"Manim completed but MP4 not found. stdout: {result.stdout[-500:]}"}

        else:
            return {"success": False, "file_path": None, "error": f"Manim failed (code {result.returncode}): {result.stderr[-500:]}"}

    except subprocess.TimeoutExpired:
        return {
            "success": False, 
            "file_path": None, 
            "error": "Manim rendering timed out after 5 minutes."
        }
    
    except Exception as e:
        return {
            "success": False, 
            "file_path": None, 
            "error": f"Unexpected error: {str(e)}"
        }


def find_rendered_mp4(media_dir: str, class_name: str, script_filename: str) -> str:
    """
    Finds the final rendered MP4 in Manim's output directory.

    Manim saves to:
      media_dir/videos/script_stem/quality_folder/output_filename.mp4

    We exclude partial_movie_files — those are intermediate chunks
    Manim uses internally during rendering, not the final output.

    Search priority:
      1. Look for scene_XX.mp4 (our --output_file name)
      2. Look for ClassName.mp4 (Manim default naming)
    """
    script_stem = Path(script_filename).stem
    videos_dir = os.path.join(media_dir, "videos", script_stem)

    if not os.path.exists(videos_dir):
        videos_dir = os.path.join(media_dir, "videos")

    if not os.path.exists(videos_dir):
        videos_dir = media_dir

    for root, dirs, files in os.walk(videos_dir):
        # Skip partial_movie_files — intermediate chunks not final output
        if "partial_movie_files" in root:
            continue
        for file in files:
            if file.endswith(".mp4"):
                full_path = os.path.join(root, file)
                print(f"  [Manim] Found MP4: {full_path}")
                return full_path

    return None