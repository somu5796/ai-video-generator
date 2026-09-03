import os
from schemas.video_schema import PipelineStatus
from utils.script_review_utils import write_review_file, parse_review_file, save_script_snapshot


def script_review_agent(state: dict) -> dict:
    """
    LangGraph node — Script Review gate.

    Sits between script_agent and voice_agent. Voice Agent is the
    first node that spends ElevenLabs's limited free-tier monthly
    word quota, so nothing past this gate runs until the script is
    explicitly approved — a rejected or half-finished script now
    costs a Gemini call, never TTS minutes.

    Cyclic by design: writes script_review.md, waits for the user to
    edit narration directly in that file and respond, re-parses it,
    and loops back to write-and-wait again on 'revise'. Only 'approve'
    lets the graph continue to voice_agent.

    Non-interactive override: state["review_action"] (e.g. from a
    --review-action CLI flag) skips the prompt once — useful for
    scripted/automated runs.
    """
    print("\n" + "=" * 50)
    print("[Script Review] Starting")
    print("=" * 50)

    script = state.get("script")
    if not script:
        return {"status": PipelineStatus.FAILED, "errors": ["Script Review: no script found in state"]}

    run_dirs = state.get("run_dirs")
    run_dir = run_dirs["run_dir"] if run_dirs else "."
    review_path = os.path.join(run_dir, "script_review.md")

    forced_action = state.get("review_action")

    while True:
        write_review_file(script, review_path)
        print(f"\n[Script Review] Script written to: {review_path}")
        print(f"[Script Review] Title    : {script.title}")
        print(f"[Script Review] Scenes   : {len(script.scenes)}")
        print(f"[Script Review] Estimated: {script.total_estimated_duration}s")
        print("[Script Review] Open the file, edit narration directly, then respond below.")

        if forced_action:
            action = forced_action
            forced_action = None  # only honor the override for the first round
            print(f"[Script Review] Using --review-action {action}")
        else:
            action = input(
                "\nType 'approve' to lock this script and generate voice/video, or "
                "'revise' after editing the file to re-check it [approve/revise]: "
            ).strip().lower()

        # Re-parse regardless of action — pick up edits made before either response.
        try:
            script = parse_review_file(review_path, script)
        except FileNotFoundError:
            print(f"[Script Review] ⚠️  Could not find {review_path} — did you move or delete it?")
            continue

        # Keep script.json in sync with every reviewed round — not just on
        # approval — so a crash mid-review, or a --script-file taken from
        # this run later, never replays stale pre-review narration/timing.
        script_json_path = os.path.join(run_dir, "script.json")
        save_script_snapshot(script, script_json_path)

        if action == "approve":
            print(f"\n[Script Review] ✅ Approved")
            print(f"[Script Review] Final estimated duration: {script.total_estimated_duration}s")
            return {"script": script, "status": PipelineStatus.SCRIPT_COMPLETE, "errors": []}
        elif action == "revise":
            print("[Script Review] Re-reading edits, will show updated script again...")
            continue
        else:
            print("[Script Review] Please type 'approve' or 'revise'")
