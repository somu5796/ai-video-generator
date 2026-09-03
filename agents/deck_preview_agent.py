import os
from schemas.video_schema import PipelineStatus, VideoStyle
from renderers.registry import get_renderer_for_style
from renderers.style_config import load_or_create_style_config, style_config_path
from utils.edited_slides import expected_state_filenames
from config import VIDEO_WIDTH, VIDEO_HEIGHT


def deck_preview_agent(state: dict) -> dict:
    """
    LangGraph node — Deck Preview gate (deck mode only).

    Renders ONLY the opening frame of each scene (cheap — one
    screenshot per scene, no video assembly, no audio needed) and
    pauses for approval before the full multi-state deck render runs.

    Runs BEFORE voice_agent on purpose: style/template revisions here
    cost nothing but a little render time, and happening before Voice
    Agent means as many revise cycles as needed never touch the
    ElevenLabs quota — that's reserved for the script-review gate only.

    Revise loop: the user edits deck_style.json directly (background/
    title/bullet colors, fonts) between rounds — no LLM call needed,
    mirrors the direct-edit pattern used by script_review_agent.

    Non-interactive override: state["preview_action"] (e.g. from a
    --preview-action CLI flag) skips the prompt once — useful for
    scripted/automated runs.
    """
    print("\n" + "=" * 50)
    print("[Deck Preview] Starting")
    print("=" * 50)

    script = state.get("script")
    if not script:
        return {"status": PipelineStatus.FAILED, "errors": ["Deck Preview: no script found in state"]}

    style = state.get("style", VideoStyle.TECHNICAL)
    style_str = style.value if hasattr(style, "value") else str(style)

    run_dirs = state.get("run_dirs")
    run_dir = run_dirs["run_dir"]
    preview_dir = run_dirs.get("preview_dir") or os.path.join(run_dir, "deck_preview")
    os.makedirs(preview_dir, exist_ok=True)

    renderer = get_renderer_for_style(style_str)
    forced_action = state.get("preview_action")

    while True:
        style_config = load_or_create_style_config(run_dir, style_str)

        # For each scene we render TWO frames:
        #   opening -> state_index=0  (first build state — style/template check)
        #   final   -> state_index=-1 (every element revealed together —
        #              this is the one to check for overlapping elements,
        #              since it's the most "crowded" the scene ever gets
        #              once the progressive reveal finishes)
        scene_previews = []
        errors = []
        for scene in script.scenes:
            frames = {}
            for label, idx in (("opening", 0), ("final", -1)):
                result = renderer.render_preview_image(
                    scene=scene,
                    output_dir=preview_dir,
                    width=VIDEO_WIDTH,
                    height=VIDEO_HEIGHT,
                    style_config=style_config,
                    state_index=idx,
                )
                if result["success"]:
                    frames[label] = result["file_path"]
                else:
                    errors.append(
                        f"Scene {scene.scene_number} {label} preview failed: {result['error']}"
                    )
            scene_previews.append((scene.scene_number, frames))

        if errors:
            print(f"[Deck Preview] ⚠️  {len(errors)} preview render(s) failed")
            for e in errors:
                print(f"  {e}")
            return {"status": PipelineStatus.FAILED, "errors": errors}

        print(f"\n[Deck Preview] Rendered opening + final frames for {len(scene_previews)} scene(s):")
        for scene_num, frames in scene_previews:
            print(f"  Scene {scene_num}:")
            if "opening" in frames:
                print(f"    opening : {frames['opening']}")
            if "final" in frames:
                print(f"    final   : {frames['final']}   <- check this one for overlaps")
        print(f"[Deck Preview] Style config (edit to tweak colors/fonts): {style_config_path(run_dir)}")

        if forced_action:
            action = forced_action
            forced_action = None  # only honor the override for the first round
            print(f"[Deck Preview] Using --preview-action {action}")
        else:
            action = input(
                "\nLook at the preview frames above. Type 'approve' to render the "
                "full deck, or 'revise' after editing deck_style.json to preview again "
                "[approve/revise]: "
            ).strip().lower()

        if action == "approve":
            print("[Deck Preview] ✅ Style approved — proceeding to full render")
            print(
                "\n[Deck Preview] If you want to hand-edit any scene's slides "
                "instead of auto-rendering, put images named exactly like this "
                "in a folder and pass it as --slides-dir:"
            )
            for scene in script.scenes:
                state_count = len(renderer.build_states(scene, style_config))
                names = expected_state_filenames(scene.scene_number, state_count)
                print(f"    Scene {scene.scene_number} ({state_count} states): {', '.join(names)}")
            return {"errors": []}
        elif action == "revise":
            print("[Deck Preview] Re-rendering previews with updated style...")
            continue
        else:
            print("[Deck Preview] Please type 'approve' or 'revise'")