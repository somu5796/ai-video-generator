from schemas.video_schema import PipelineStatus, VideoStyle
from renderers.registry import get_renderer_for_style
from renderers.style_config import load_or_create_style_config
from utils.edited_slides import find_edited_states_for_scene
from tools.slide_video_tool import assemble_images_to_video
from config import SCENES_DIR, MANIM_FPS, VIDEO_WIDTH, VIDEO_HEIGHT
import os


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

    Edited-slides escape hatch (state["slides_dir"]):
    For each scene, build_states() is always computed from the
    script's own timing (same as before — you don't hand-edit
    timing, only images). If slides_dir contains a COMPLETE matching
    set of scene_{N}_state_{i}.png files for a scene, those images
    are used directly instead of an auto-render for that scene —
    otherwise that scene auto-renders exactly as before. This means
    slides_dir works per-scene, not all-or-nothing: hand-edit only
    the scenes that need it, leave the rest on autopilot.
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
    slides_dir = state.get("slides_dir")

    print(f"[Deck Agent] Scenes to render : {len(script.scenes)}")
    print(f"[Deck Agent] Style            : {style_str}")
    print(f"[Deck Agent] Renderer         : {type(renderer).__name__}")
    if slides_dir:
        print(f"[Deck Agent] Edited slides dir: {slides_dir} (used where a complete set exists)")

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

        # Timing always comes from the script — build_states() is computed
        # the same way whether the images end up auto-rendered or hand-edited.
        build_states = renderer.build_states(scene, style_config)
        edited_images = find_edited_states_for_scene(slides_dir, scene_num, len(build_states))

        if edited_images:
            print(f"  [Deck Agent] Using {len(edited_images)} edited slide(s) for scene {scene_num}")
            video_path = os.path.join(scenes_output_dir, f"scene_{scene_num:02d}.mp4")
            image_durations = [
                (img_path, bs["hold_duration"])
                for img_path, bs in zip(edited_images, build_states)
            ]
            result = assemble_images_to_video(
                image_durations=image_durations,
                output_path=video_path,
                fps=MANIM_FPS,
                width=VIDEO_WIDTH,
                height=VIDEO_HEIGHT,
            )
        else:
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
