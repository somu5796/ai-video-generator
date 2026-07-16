from schemas.video_schema import PipelineStatus, VideoStyle
from tools.manim_tool import render_manim_scene

def visual_agent(state : dict) -> dict:
    """
    LangGraph node — Visual Agent.

    Reads Script from state, renders a Manim MP4 for each scene,
    updates each scene with video_file_path.

    Why visual agent is the slowest agent:
      Each scene requires:
        1. Code generation (instant)
        2. Manim rendering (30-120 seconds per scene)

      A 4-scene video = 2-8 minutes of rendering time.
      This is CPU-bound work — Manim renders frame by frame.

    Production note:
      In a real deployment, scene rendering would be
      parallelized across multiple CPU cores or cloud workers.
      For this POC, we render sequentially.
    """
    print("\n" + "=" * 50)
    print("[Visual Agent] Starting")
    print("=" * 50)

    script = state.get("script")
    if not script:
        return {
            "status": PipelineStatus.FAILED,
            "errors": ["Visual Agent: no script found in state"]
        }

    # Get style for color scheme
    style = state.get("style", VideoStyle.TECHNICAL)
    style_str = style.value if hasattr(style, "value") else str(style)

    print(f"[Visual Agent] Scenes to render : {len(script.scenes)}")
    print(f"[Visual Agent] Style            : {style_str}")
    print(f"[Visual Agent] Warning          : Rendering takes 30-120s per scene")

    updated_scenes = []
    errors = []

    for scene in script.scenes:
        scene_num = scene.scene_number
        print(f"\n[Visual Agent] Rendering Scene {scene_num}: {scene.title}")

        # Use actual_duration from Voice Agent for precise sync
        # If Voice Agent hasn't run, fall back to estimated_duration
        duration = scene.actual_duration or scene.estimated_duration

        if not duration or duration <= 0:
            error = f"Scene {scene_num} has no valid duration"
            errors.append(error)
            updated_scenes.append(scene)
            continue
        
        # Convert visual elements to plain dicts for manim_tool
        visual_elements = []
        for el in scene.visual_elements:
            visual_elements.append({
                "element_id": el.element_id,
                "text": el.text,
                "visual_type": el.visual_type.value,
                "appear_at": el.appear_at,
                "duration": el.duration,
                "position": el.position,
                "emphasis": el.emphasis,
            })
        
        # Render the scene
        result = render_manim_scene(
            scene_number=scene_num,
            scene_title=scene.title,
            visual_elements=visual_elements,
            actual_duration=duration,
            style=style_str,
        )

        if result.["success"]:
            scene.video_file_path = result["file_path"]
            print(f"  [Visual Agent] ✅ Scene {scene_num} rendered")
        else:
            error = f"Scene {scene_num} render failed: {result['error']}"
            print(f"  [Visual Agent] ❌ {error}")
            errors.append(error)
        
        updated_scenes.append(scene)
    
    script.scenes = updated_scenes

    if errors:
        print(f"\n[Visual Agent] ⚠️  Completed with {len(errors)} errors")
        return {
            "script": script,
            "status": PipelineStatus.FAILED,
            "errors": errors
        }
    
    print(f"\n[Visual Agent] ✅ All scenes rendered successfully")
    return {
        "script": script,
        "status": PipelineStatus.VISUALS_COMPLETE,
        "errors": []
    }
