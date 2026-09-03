import json
import re
from agents.script_agent import WORDS_PER_SECOND
from schemas.video_schema import Script

SEPARATOR = "=" * 80
SCENE_HEADER_RE = re.compile(r"^##\s*Scene\s+(\d+)\s*:\s*(.*)$")


def load_script_snapshot(path: str) -> Script:
    """
    Loads a full Script object from a previously saved script.json
    snapshot (the same structure Script Agent / Script Review produce
    internally — title, description, tags, style, speaker_config,
    every scene's visual_elements, timings, etc.).

    Unlike script_review.md (which is a deliberately partial,
    human-editable narration view — see write_review_file), this is
    the complete Pydantic dump, so it round-trips into a Script with
    no data loss and no LLM call needed.

    Raises FileNotFoundError / json.JSONDecodeError / pydantic
    ValidationError on bad input — callers should catch these and
    surface them as pipeline errors rather than crashing the run.
    """
    with open(path, "r") as f:
        data = json.load(f)
    return Script.model_validate(data)


def save_script_snapshot(script: Script, path: str) -> str:
    """
    Writes the full Script (same shape Script Agent's script.json
    dump uses) to disk. Called after script_review approves/re-parses
    edits, so script.json on disk always reflects the LATEST reviewed
    version — not the pre-review draft Script Agent originally wrote.

    This matters specifically because --script-file reads this same
    file back in later. Without this, a script.json snapshot taken
    from a reviewed run would silently replay the ORIGINAL narration/
    appear_at, discarding every edit made during review.
    """
    with open(path, "w") as f:
        json.dump(script.model_dump(), f, indent=2, default=str)
    return path


def write_review_file(script, path: str) -> str:
    """
    Writes the current script as a human-editable markdown file.
    Only narration (and, incidentally, the scene title on the header
    line) is meant to be edited — everything else is context.
    """
    style_val = script.style.value if hasattr(script.style, "value") else script.style

    lines = [
        f"# {script.title}",
        "",
        f"Description: {script.description}",
        f"Tags: {', '.join(script.tags)}",
        f"Style: {style_val} | Target duration: {script.target_duration}s | "
        f"Estimated total: {script.total_estimated_duration}s",
        "",
        "Edit the narration text below directly (scene titles too, if you like).",
        "Do NOT change the '## Scene N:' header format — it's how this file gets re-read.",
        "When done, save this file, go back to the terminal, and type 'approve' or 'revise'.",
        "",
        SEPARATOR,
    ]

    for scene in script.scenes:
        lines.append("")
        lines.append(f"## Scene {scene.scene_number}: {scene.title}")
        lines.append(f"<!-- estimated: {scene.estimated_duration:.1f}s | visual elements: {len(scene.visual_elements)} -->")
        lines.append("")
        lines.append(scene.narration or "")
        lines.append("")
        lines.append(SEPARATOR)

    with open(path, "w") as f:
        f.write("\n".join(lines))

    return path


def parse_review_file(path: str, script):
    """
    Re-reads the (possibly hand-edited) review file back onto `script`.

    Any scene whose narration text changed gets:
      - estimated_duration recalculated from the new word count
        (same word_count / WORDS_PER_SECOND formula Script Agent uses)
      - every visual_element's appear_at rescaled proportionally to
        the new duration, so relative ordering/timing stays sane
        without another LLM call
      - actual_duration/audio_file_path cleared, in case this review
        ever runs after Voice Agent, so a stale audio file is never
        silently kept against edited narration

    script.total_estimated_duration is recomputed from the (possibly
    updated) per-scene estimates.

    Mutates and returns the same Script object.
    """
    with open(path, "r") as f:
        raw_lines = f.read().splitlines()

    scene_blocks = {}
    current_num = None

    for line in raw_lines:
        stripped = line.strip()
        m = SCENE_HEADER_RE.match(stripped)
        if m:
            current_num = int(m.group(1))
            scene_blocks[current_num] = {"title": m.group(2).strip(), "narration_lines": []}
            continue
        if stripped == SEPARATOR:
            current_num = None
            continue
        if current_num is None:
            continue
        if stripped.startswith("<!--"):
            continue
        scene_blocks[current_num]["narration_lines"].append(line)

    for scene in script.scenes:
        block = scene_blocks.get(scene.scene_number)
        if not block:
            # Scene header missing from file (accidentally deleted) —
            # leave that scene untouched rather than guessing.
            continue

        new_title = block["title"] or scene.title
        new_narration = "\n".join(block["narration_lines"]).strip()
        new_narration = re.sub(r"\n{3,}", "\n\n", new_narration)

        if new_narration and new_narration != (scene.narration or "").strip():
            old_duration = scene.estimated_duration or 1.0
            new_word_count = len(new_narration.split())
            new_duration = round(max(new_word_count / WORDS_PER_SECOND, 0.5), 1)
            scale = (new_duration / old_duration) if old_duration > 0 else 1.0

            for el in scene.visual_elements:
                el.appear_at = round(min(el.appear_at * scale, max(new_duration - 0.2, 0.0)), 2)

            scene.narration = new_narration
            scene.estimated_duration = new_duration
            scene.actual_duration = None
            scene.audio_file_path = None

        scene.title = new_title

    script.total_estimated_duration = round(
        sum(s.estimated_duration for s in script.scenes), 1
    )
    return script