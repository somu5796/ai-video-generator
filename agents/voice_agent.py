import os
import time
from schemas.video_schema import (PipelineStatus, SpeakerMode)
from tools.elevenlabs_tool import (
    generate_audio_for_text,
    generate_dialogue_audio,
    check_quota
)
from config import VOICE_ID_PRIMARY, VOICE_ID_SECONDARY, AUDIO_DIR

def voice_agent(state : dict) -> dict:
    """
    LangGraph node — Voice Agent.

    Reads Script from state, generates audio for each scene,
    updates each scene with audio_file_path and actual_duration.

    Why update scenes in place?
    Voice Agent doesn't change script structure — it enriches it.
    Same Script object, same scenes, just with audio paths filled in.
    This keeps state clean — downstream agents find everything
    they need in the same Script object.

    Quota check:
    Before generating any audio, we check remaining ElevenLabs
    quota. If insufficient for the full script, we fail early
    with a clear message rather than generating half the audio
    and failing mid-pipeline.

    Character estimation:
    1 character ≈ 1 char of narration text
    We sum all narration lengths before starting to estimate
    total characters needed.
    """
    print("\n" + "=" * 50)
    print("[Voice Agent] Starting")
    print("=" * 50)

    # Read Script from state
    script = state.get("script")
    if not script:
        return {
            "status": PipelineStatus.FAILED,
            "errors": ["Voice Agent: no script found in state"]
        }
    
    #Estimate total characters needed 
    total_chars =0
    for scene in script.scenes:
        if scene.narration:
            total_chars += len(scene.narration)
        elif scene.dialogue_lines:
            for line in scene.dialogue_lines:
                total_chars += len(line.text)
    
    print(f"[Voice Agent] Scenes to process : {len(script.scenes)}")
    print(f"[Voice Agent] Total characters  : {total_chars}")
    print(f"[Voice Agent] Speaker mode      : {script.speaker_config.mode}")


    # Check ElevenLabs quota before generating any audio
    quota = check_quota()
    if quota.get("success"):
        remaining = quota.get("remaining", 0)
        print(f"[Voice Agent] ElevenLabs quota  : {remaining} chars remaining")

        if remaining < total_chars:
            return {
                "status": PipelineStatus.FAILED,
                "errors": [
                    f"Insufficient ElevenLabs quota. "
                    f"Need {total_chars} chars, have {remaining} remaining."
                ]
            }
    else:
        # Quota check failed — warn but continue
        print(f"[Voice Agent] ⚠️  Could not check quota: {quota.get('error')}")

    # Generate audio for each scene
    updated_scenes = []
    total_actual_duration = 0.0
    errors = []

    for scene in script.scenes:
        scene_num = scene.scene_number
        output_filename = f"scene_{scene_num:02d}.mp3"
        # zero-padded: scene_01.mp3, scene_02.mp3 etc.
        # zero-padding ensures correct alphabetical sort order
        # scene_10 sorts after scene_09, not after scene_1

        # Use run-specific audio dir if available, else fall back to config default
        run_dirs = state.get("run_dirs")
        audio_output_dir = run_dirs["audio_dir"] if run_dirs else AUDIO_DIR
        os.makedirs(audio_output_dir, exist_ok=True)

        print(f"\n[Voice Agent] Processing Scene {scene_num}: {scene.title}")

        # Single narration mode
        if script.speaker_config.mode == SpeakerMode.SINGLE:
            if not scene.narration or not scene.narration.strip():
                error = f"Scene {scene_num} has no narration text"
                print(f"  [Voice Agent] ⚠️  {error}")
                errors.append(error)
                updated_scenes.append(scene)
                continue
            
            result = generate_audio_for_text(
                text=scene.narration,
                voice_id=script.speaker_config.speaker_a_voice_id or VOICE_ID_PRIMARY,
                output_filename=output_filename,
                output_dir=audio_output_dir, 
            )

        # Dialogue mode
        else:
            if not scene.dialogue_lines :
                # Fall back to narration if dialogue_lines missing
                print(f"  [Voice Agent] No dialogue lines, falling back to narration")
                result = generate_audio_for_text(
                    text=scene.narration or "",
                    voice_id=VOICE_ID_PRIMARY,
                    output_filename=output_filename,
                    output_dir=audio_output_dir, 
                )
            else:
                dialogue_data = [
                    {"speaker": dl.speaker, "text": dl.text}
                    for dl in scene.dialogue_lines
                ]
                result = generate_dialogue_audio(
                    dialogue_lines=dialogue_data,
                    output_filename=output_filename,
                    output_dir=audio_output_dir, 
                )
            
        # Handle result
        if result["success"]:
            # Update scene with audio info
            scene.audio_file_path = result["file_path"]
            scene.actual_duration = result["duration"]
            total_actual_duration += result["duration"]
            print(f"  [Voice Agent] Scene {scene_num} audio: {result['duration']}s")
        else:
            error = f"Scene {scene_num} audio failed: {result['error']}"
            print(f"  [Voice Agent] ❌ {error}")
            errors.append(error)
        
        updated_scenes.append(scene)    

        # Small delay between API calls — avoids rate limiting
        if scene_num < len(script.scenes):
            time.sleep(1.0)
    
    # Update script with enriched scenes
    script.scenes = updated_scenes

    print(f"\n[Voice Agent] Total actual duration: {total_actual_duration:.2f}s")
    print(f"[Voice Agent] Estimated duration was: {script.total_estimated_duration}s")
    print(f"[Voice Agent] Difference: {abs(total_actual_duration - script.total_estimated_duration):.2f}s")

    if errors:
        # Partial failure — some scenes succeeded
        print(f"[Voice Agent] ⚠️  Completed with {len(errors)} errors")
        return {
            "script": script,
            "status": PipelineStatus.FAILED,
            "errors": errors
        }

    # All scenes succeeded
    print(f"\n[Voice Agent] ✅ All scenes processed successfully")
    return {
        "script": script,
        "status": PipelineStatus.VOICE_COMPLETE,
        "errors": []
    }
