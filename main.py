import argparse
import json
from graph.video_pipeline import run_pipeline
from schemas.video_schema import PipelineStatus


def main():
    """
    CLI entry point for the AI Video Generator.

    Usage:
      python3 main.py --topic "Explain CAP theorem"
      python3 main.py --topic "SQL vs NoSQL" --format auto --style finance
      python3 main.py --topic "What is Kafka" --format long
    """
    parser = argparse.ArgumentParser(
        description="AI Video Generator — Multi-agent pipeline"
    )
    parser.add_argument(
        "--topic",
        type=str,
        required=False,
        help=(
            "Topic for the video e.g. 'Explain CAP theorem'. "
            "Required unless --script-file is given, in which case it "
            "defaults to the script's title."
        )
    )
    parser.add_argument(
        "--script-file",
        type=str,
        default=None,
        help=(
            "Path to a pre-approved script.json snapshot (the full "
            "Script dump — same shape as output/<run>/script.json). "
            "When set, script_agent and script_review are skipped "
            "entirely and the pipeline runs straight from voice/deck "
            "generation — no LLM call spent regenerating the script."
        )
    )
    parser.add_argument(
        "--format",
        type=str,
        default="medium",
        choices=["short", "medium", "long", "auto"],
        help="Video format (default: medium = ~3 minutes)"
    )
    parser.add_argument(
        "--style",
        type=str,
        default="technical",
        choices=["technical", "finance", "general"],
        help="Visual style (default: technical)"
    )
    parser.add_argument(
        "--visual-mode",
        type=str,
        default="word-reveal",
        choices=["word-reveal", "deck"],
        help=(
            "word-reveal: original Manim kinetic-typography path (default). "
            "deck: generate a PDF/PPT-style deck and progressively reveal it "
            "in sync with narration, DeepLearning.AI-course style."
        )
    )
    parser.add_argument(
        "--review-action",
        type=str,
        default=None,
        choices=["approve", "revise"],
        help=(
            "Skip the interactive script-review prompt on its first round "
            "and use this action instead. Omit for interactive review "
            "(default)."
        )
    )
    parser.add_argument(
        "--preview-action",
        type=str,
        default=None,
        choices=["approve", "revise"],
        help=(
            "Deck mode only. Skip the interactive deck-preview prompt on "
            "its first round and use this action instead. Omit for "
            "interactive review (default)."
        )
    )

    args = parser.parse_args()

    if not args.script_file and not args.topic:
        parser.error("--topic is required unless --script-file is given")

    if args.script_file and not args.topic:
        # Default the topic (used only for output-dir naming/logging)
        # from the script's own title, so --script-file alone is enough.
        try:
            with open(args.script_file, "r") as f:
                args.topic = json.load(f).get("title", "untitled")
        except (OSError, json.JSONDecodeError) as e:
            parser.error(f"Could not read --script-file '{args.script_file}': {e}")

    print(f"\nGenerating video: '{args.topic}'")
    print(f"Format: {args.format} | Style: {args.style} | Visual mode: {args.visual_mode}")
    if args.script_file:
        print(f"Script file: {args.script_file} (skipping script generation + review)")
    print()

    result = run_pipeline(
        topic=args.topic,
        style=args.style,
        video_format=args.format,
        visual_mode=args.visual_mode,
        review_action=args.review_action,
        preview_action=args.preview_action,
        script_file=args.script_file,
    )

    status = result.get("status")
    if hasattr(status, "value"):
        status = status.value

    if status == "assembly_complete":
        print("\n" + "=" * 50)
        print("✅ VIDEO GENERATION COMPLETE")
        print("=" * 50)
        print(f"Final video: {result.get('final_video_path')}")
        print(f"Output dir : {result.get('run_dirs', {}).get('run_dir')}")
    else:
        print("\n" + "=" * 50)
        print("❌ VIDEO GENERATION FAILED")
        print("=" * 50)
        for error in result.get("errors", []):
            print(f"Error: {error}")


if __name__ == "__main__":
    main()