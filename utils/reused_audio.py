import os


def find_existing_audio_for_scene(audio_dir: str, scene_number: int) -> str:
    """
    Looks for a previously-generated scene_{N:02d}.mp3 in audio_dir —
    the exact filename Voice Agent already writes on every run (see
    agents/voice_agent.py's output_filename pattern).

    Point --audio-dir at any prior run's outputs/<run>/audio/ folder
    to reuse its audio instead of spending ElevenLabs quota again —
    typically the SAME run you're re-doing a slides-only fix for, so
    the narration is guaranteed to match the script you're re-running.

    Returns the path if found, else None (caller falls back to
    generating that scene's audio normally — same per-scene fallback
    pattern as find_edited_states_for_scene).
    """
    if not audio_dir or not os.path.isdir(audio_dir):
        return None

    path = os.path.join(audio_dir, f"scene_{scene_number:02d}.mp3")
    return path if os.path.exists(path) else None
