import os
from schemas.video_schema import PipelineStatus
from tools.moviepy_tool import (
    merge_video_audio,
    concatenate_videos,
    add_background_music,
    burn_subtitles,
)

from config import FINAL_DIR, SCENES_DIR

def assembly_agent(state: dict) -> dict:
    """
    LangGraph node — Assembly Agent.

    Takes all scene videos and audios, assembles final MP4.

    Pipeline:
      Step 1: merge video + audio for each scene
      Step 2: concatenate all merged scenes into one video
      Step 3: add background music (optional)
      Step 4: burn subtitles

    Why multiple steps instead of one FFmpeg command?
    Modularity — each step can fail and be debugged independently.
    Also allows skipping optional steps (music, subtitles)
    without affecting the core merge + concat.
    """
    print("\n" + "=" * 50)
    print("[Assembly Agent] Starting")
    print("=" * 50)

    script = state.get("script")
    if not script:
        return {
            "status": PipelineStatus.FAILED,
            "errors": ["Assembly Agent: no script found in state"]
        }
    
    run_dirs = state.get("run_dirs")
    scenes_dir = run_dirs["scenes_dir"] if run_dirs else SCENES_DIR
    final_dir = run_dirs["final_dir"] if run_dirs else FINAL_DIR
    
    os.makedirs(final_dir, exist_ok=True)    
    os.makedirs(scenes_dir, exist_ok=True)

    # Validate all scenes have both audio and video
    missing = []
    for scene in script.scenes:
        if not scene.audio_file_path or not os.path.exists(scene.audio_file_path):
            missing.append(f"Scene {scene.scene_number}: missing audio")
        if not scene.video_file_path or not os.path.exists(scene.video_file_path):
            missing.append(f"Scene {scene.scene_number}: missing video")


    if missing:
        return {
            "status": PipelineStatus.FAILED,
            "errors": ["Assembly Agent: missing audio/video for scenes"] + missing
        }
    
    print(f"[Assembly Agent] All {len(script.scenes)} scenes validated")

    # Step 1: Merge video + audio for each scene
    print("\n[Assembly Agent] Step 1: Merging audio into scene videos...")
    merged_paths = []
    errors = []

    for scene in script.scenes:
        merged_path = os.path.join(scenes_dir, f"scene_{scene.scene_number:02d}_merged.mp4")

        print(f"  Merging scene {scene.scene_number}...")
        result = merge_video_audio(
            video_path=scene.video_file_path,
            audio_path=scene.audio_file_path,
            output_path=merged_path,
        )

        if result["success"]:
            merged_paths.append(merged_path)
            print(f"  ✅ Scene {scene.scene_number} merged")
        else:
            error = f"Scene {scene.scene_number} merge failed: {result['error']}"
            errors.append(error)
            print(f"  ❌ {error}")

    if errors:
        return {
            "status": PipelineStatus.FAILED,
            "errors": ["Assembly Agent: merge failed for some scenes"] + errors
        }
    
    # Step 2: Concatenate all merged scenes
    print("\n[Assembly Agent] Step 2: Concatenating all scenes...")

    # Create safe filename from title
    safe_title = "".join(
        c if c.isalnum() or c in "._- " else "_"
        for c in script.title
    ).replace(" ", "_")[:50]

    concatenated_path = os.path.join(final_dir, f"{safe_title}_raw.mp4")

    result = concatenate_videos(
        video_paths=merged_paths,
        output_path=concatenated_path,
    )

    if not result["success"]:
        return {
            "status": PipelineStatus.FAILED,
            "errors": ["Assembly Agent: concatenation failed"] + [result["error"]]
        }
    
    print(f"  ✅ All scenes concatenated")

    # Step 3: Add background music (optional)
    print("\n[Assembly Agent] Step 3: Adding background music...")

    music_path = os.path.join("assets", "background_music.mp3")
    with_music_path = os.path.join(final_dir, f"{safe_title}_music.mp4")

    result = add_background_music(
        video_path=concatenated_path,
        music_path=music_path,
        output_path=with_music_path,
    )

    after_music_path = result["file_path"]
    print(f"  ✅ Music step complete")


    # Step 4: Burn subtitles 
    print("\n[Assembly Agent] Step 4: Burning subtitles...")

    final_path = os.path.join(final_dir, f"{safe_title}_final.mp4")

    # Convert scenes to plain dicts for moviepy_tool
    scenes_data = []
    for scene in script.scenes:
        scenes_data.append({
            "narration": scene.narration or "",
            "actual_duration": scene.actual_duration,
            "estimated_duration": scene.estimated_duration,
        })

    result = burn_subtitles(
        video_path=after_music_path,
        output_path=final_path,
        scenes=scenes_data,
    )

    if not result["success"]:
        # Subtitles failure is non-critical - use video without subtitles
        final_path = after_music_path
        print("  ⚠️  Subtitles skipped")
    else:
        print(f"  ✅ Subtitles burned in")

    
    # Final file size check 
    file_size_mb = os.path.getsize(final_path) / 1024 / 1024
    print(f"\n[Assembly Agent] ✅ Final video: {final_path}")
    print(f"[Assembly Agent] File size: {file_size_mb:.2f} MB")

    return {
        "final_video_path" : final_path,
        "status" : PipelineStatus.ASSEMBLY_COMPLETE,
        "errors" : []
    }
    
