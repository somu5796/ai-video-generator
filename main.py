import argparse
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
        required=True,
        help="Topic for the video e.g. 'Explain CAP theorem'"
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

    args = parser.parse_args()

    print(f"\nGenerating video: '{args.topic}'")
    print(f"Format: {args.format} | Style: {args.style}\n")

    result = run_pipeline(
        topic=args.topic,
        style=args.style,
        video_format=args.format,
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