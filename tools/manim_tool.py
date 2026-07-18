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
    scene_number: int,
    scene_title: str,
    visual_elements: list,
    actual_duration: float,
    style: str = "technical",
    narration: str = "",
) -> str:
    """
    Kinetic typography — clean professional word-by-word reveal.

    Technique:
      Each line is rendered as a single Text object.
      As each word is added, we replace the line Text with
      a longer version containing the new word.
      This gives natural font spacing — no cramming.

    Layout:
      Title: very top, small, stays throughout
      Lines: build from top of content zone downward
      When MAX_LINES reached: all lines fade, restart from top
    """

    style_config = {
        "technical": {
            "background":   "WHITE",
            "title_color":  "\"#7B1FA2\"",   # Bright Orange
            "line_colors":  [
                "\"#0F172A\"",   # Cyan
                "\"#0F172A\"",
                "\"#0F172A\"",
                "\"#0F172A\"",
            ],
            "title_bg":     "\"#F3E5F5\"",
        },
        "finance": {
            "background":   "\"#FFFDE7\"",
            "title_color":  "\"#1A237E\"",
            "line_colors":  [
                "\"#212121\"",
                "\"#1A237E\"",
                "\"#1B5E20\"",
                "\"#E65100\"",
            ],
            "title_bg":     "\"#FFF9C4\"",
        },
        "general": {
            "background":   "\"#0D1117\"",
            "title_color":  "\"#58A6FF\"",
            "line_colors":  [
                "WHITE",
                "\"#3FB950\"",
                "\"#FFA657\"",
                "YELLOW",
            ],
            "title_bg":     "\"#161B22\"",
        },
    }

    colors = style_config.get(style, style_config["technical"])

    # ── Layout ─────────────────────────────────────────────────────────────────
    WORDS_PER_SEC  = 1.9
    WORDS_PER_LINE = 6        # fewer words per line = more breathing room
    MAX_LINES      = 5
    FONT_SIZE      = 38       # large, readable
    TITLE_FONT    = 40
    LINE_GAP       = 0.9      # vertical space between lines
    FIRST_LINE_Y   = 1.7      # y position of first line (below title)
    WORD_TIME      = 0.15     # seconds per word appearance
    PAGE_FADE_T    = 0.5

    animation_blocks = []
    current_time = 0.0

    vcounter = [0]
    def nv(prefix="v"):
        vcounter[0] += 1
        return f"{prefix}{vcounter[0]}"

    def add_wait(until):
        nonlocal current_time
        gap = until - current_time
        if gap > 0.02:
            animation_blocks.append(f"        self.wait({gap:.2f})")
            current_time = until

    # ── Title bar at very top ──────────────────────────────────────────────────
    safe_title = scene_title.replace('"', '\\"')
    animation_blocks.extend([
        f'        title_bg = Rectangle('
        f'width=20, height=0.9, '
        f'fill_color={colors["title_bg"]}, '
        f'fill_opacity=1, '
        f'stroke_width=0)',
        f'        title_bg.move_to(UP * 3.3)',
        f'        title = Text("{safe_title}", font_size={TITLE_FONT}, '
        f'color={colors["title_color"]}, weight=BOLD)',
        f'        title.move_to(UP * 3.3)',
        f'        self.add(title_bg)',
        f'        self.add(title)',
    ])

    # ── Process narration ──────────────────────────────────────────────────────
    if narration and narration.strip():
        words = narration.split()
        total_words = len(words)
        word_index = 0

        while word_index < total_words:
            # ── Build one page of MAX_LINES lines ────────────────────────────
            page_line_vars = []   # track current Text object for each line
            page_word_count = 0

            for line_num in range(MAX_LINES):
                if word_index >= total_words:
                    break

                y_pos = FIRST_LINE_Y - (line_num * LINE_GAP)
                line_color = colors["line_colors"][line_num % len(colors["line_colors"])]
                current_line_words = []
                current_line_var = None

                for word_pos in range(WORDS_PER_LINE):
                    if word_index >= total_words:
                        break

                    word = words[word_index]
                    safe_word = word.replace('"', '\\"').replace("\\", "\\\\")
                    current_line_words.append(safe_word)
                    word_index += 1
                    page_word_count += 1

                    # Calculate when this word should appear
                    global_word_time = (word_index - 1) / WORDS_PER_SEC
                    add_wait(global_word_time)

                    # Build new line text with all words so far
                    line_text = " ".join(current_line_words)
                    new_var = nv("t")

                    animation_blocks.extend([
                        f'        {new_var} = Text("{line_text}", '
                        f'font_size={FONT_SIZE}, color={line_color}, weight=BOLD)',
                        f'        {new_var}.move_to(UP * {y_pos:.2f})',
                        f'        {new_var}.align_to(LEFT * 6.5, LEFT)',
                    ])

                    if current_line_var is None:
                        # First word — fade in fresh
                        animation_blocks.append(
                            f'        self.play(FadeIn({new_var}), run_time={WORD_TIME})'
                        )
                    else:
                        # Add new longer line on top — no fade out, no flicker
                        # Old line is covered by new line instantly via self.add
                        # then new word fades in cleanly
                        animation_blocks.extend([
                            f'        self.play('
                            f'FadeOut({current_line_var}), '
                            f'FadeIn({new_var}), '
                            f'run_time={WORD_TIME})'
                        ])

                    current_time += WORD_TIME
                    current_line_var = new_var

                if current_line_var:
                    page_line_vars.append(current_line_var)

            # ── Fade out entire page before next page ─────────────────────────
            if word_index < total_words and page_line_vars:
                animation_blocks.append(f"        self.wait(0.4)")
                current_time += 0.4
                vars_str = ", ".join(page_line_vars)
                animation_blocks.append(
                    f"        self.play(FadeOut(VGroup({vars_str})), "
                    f"run_time={PAGE_FADE_T})"
                )
                current_time += PAGE_FADE_T

    # ── Fill remaining time ────────────────────────────────────────────────────
    remaining = actual_duration - current_time
    if remaining > 0.1:
        animation_blocks.append(f"        self.wait({remaining:.2f})")

    class_name = f"Scene{scene_number:02d}"
    animation_code = "\n".join(animation_blocks)

    code = f'''from manim import *

config.background_color = {colors["background"]}
config.pixel_height = 1080
config.pixel_width  = 1920
config.frame_rate   = 30

class {class_name}(Scene):
    """
    Scene: {scene_title}
    Duration: {actual_duration}s
    Style: kinetic typography
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
    output_dir: str = None,
    narration: str = "", 
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

    if output_dir is None:
        from config import SCENES_DIR
        output_dir = SCENES_DIR
    os.makedirs(output_dir, exist_ok=True)
    

    class_name = f"Scene{scene_number:02d}"
    script_filename = f"scene_{scene_number:02d}_manim.py"
    script_path = os.path.join(output_dir, script_filename)
    output_filename = f"scene_{scene_number:02d}.mp4"
    output_path = os.path.join(output_dir, output_filename)

    #Step 1 & 2 : Generate code and write to file
    manim_code = generate_manim_scene_code(
        scene_number=scene_number,
        scene_title=scene_title,
        visual_elements=visual_elements,
        actual_duration=actual_duration,
        style=style,
        narration=narration,
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
        "--media_dir", output_dir
    ]
    print(f"  [Manim] Rendering {class_name} ({MANIM_QUALITY})...")
    print(f"  [Manim] This may take 30-120 seconds per scene...")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode == 0:
            # Step 4: Find the rendered MP4 in Manim's output directory
            # Manim saves to: media_dir/videos/script_name/quality/ClassName.mp4
            rendered_path = find_rendered_mp4(
                output_dir, class_name, script_filename
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