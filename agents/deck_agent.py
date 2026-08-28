from schemas.video_schema import PipelineStatus, VideoStyle
from renderers.registry import get_renderer_for_style
from renderers.style_config import load_or_create_style_config
from config import SCENES_DIR, MANIM_FPS, VIDEO_WIDTH, VIDEO_HEIGHT


def deck_agent(state: dict) -> dict:
    """
    LangGraph node — Deck Agent (visual-mode "deck").

    Same contract as visual_agent: reads Script from state, fills
    scene.video_file_path for every scene, returns status
    VISUALS_COMPLETE. This is intentional — Assembly Agent merges
    audio into scene.video_file_path and concatenates scenes without
    caring whether that file came from Manim or from a stitched
    image sequence. Nothing downstream changes.

    Renderer choice is delegated to the registry, keyed by style —
    that's the "different tool per content type" behavior.
    """
    print("\n" + "=" * 50)
    print("[Deck Agent] Starting")
    print("=" * 50)

    script = state.get("script")
    if not script:
        return {
            "status": PipelineStatus.FAILED,
            "errors": ["Deck Agent: no script found in state"],
        }

    style = state.get("style", VideoStyle.TECHNICAL)
    style_str = style.value if hasattr(style, "value") else str(style)

    run_dirs = state.get("run_dirs")
    scenes_output_dir = run_dirs["scenes_dir"] if run_dirs else SCENES_DIR
    run_dir = run_dirs["run_dir"] if run_dirs else scenes_output_dir

    style_config = load_or_create_style_config(run_dir, style_str)
    renderer = get_renderer_for_style(style_str)

    print(f"[Deck Agent] Scenes to render : {len(script.scenes)}")
    print(f"[Deck Agent] Style            : {style_str}")
    print(f"[Deck Agent] Renderer         : {type(renderer).__name__}")

    updated_scenes = []
    errors = []

    for scene in script.scenes:
        scene_num = scene.scene_number
        print(f"\n[Deck Agent] Rendering Scene {scene_num}: {scene.title}")

        if not (scene.actual_duration or scene.estimated_duration):
            error = f"Scene {scene_num} has no valid duration"
            errors.append(error)
            updated_scenes.append(scene)
            continue

        result = renderer.render_scene_video(
            scene=scene,
            output_dir=scenes_output_dir,
            fps=MANIM_FPS,
            width=VIDEO_WIDTH,
            height=VIDEO_HEIGHT,
            style_config=style_config,
        )

        if result["success"]:
            scene.video_file_path = result["file_path"]
            print(f"  [Deck Agent] ✅ Scene {scene_num} rendered")
        else:
            error = f"Scene {scene_num} deck render failed: {result['error']}"
            print(f"  [Deck Agent] ❌ {error}")
            errors.append(error)

        updated_scenes.append(scene)

    script.scenes = updated_scenes

    if errors:
        print(f"\n[Deck Agent] ⚠️  Completed with {len(errors)} errors")
        return {"script": script, "status": PipelineStatus.FAILED, "errors": errors}

    print(f"\n[Deck Agent] ✅ All scenes rendered successfully")
    return {"script": script, "status": PipelineStatus.VISUALS_COMPLETE, "errors": []}
