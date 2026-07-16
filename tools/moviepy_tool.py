import os
import subprocess
from pathlib import Path

from config import (
    FINAL_DIR,
    AUDIO_DIR,
    BACKGROUND_MUSIC_VOLUME,
)

def merge_video_audio(
    video_path: str,
    audio_path: str,
    output_path: str,
    ) -> dict:
    """
    Merges a silent Manim MP4 with an ElevenLabs MP3.

    Why are they separate?
    Manim renders video without audio — it has no TTS capability.
    ElevenLabs generates audio without video.
    Assembly Agent combines them.

    We use FFmpeg directly via subprocess rather than MoviePy here
    because FFmpeg handles audio/video sync more precisely and
    is significantly faster for simple merge operations.

    FFmpeg command breakdown:
      -i video_path     → input 1: video file (no audio stream)
      -i audio_path     → input 2: audio file
      -c:v copy         → copy video stream as-is (no re-encode = fast)
      -c:a aac          → encode audio as AAC (YouTube compatible)
      -shortest         → end when shorter stream ends
      -y                → overwrite output if exists
    """

    cmd =[
        "ffmpeg",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        "-y",
        output_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return {
                "success": True,
                "output_path": output_path,
                "error": None
            }
        else:
            return {
                "success": False,
                "output_path": None,
                "error": f"FFmpeg merge failed: {result.stderr[-300:]}"
            }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output_path": None,
            "error": f"FFmpeg merge timeout after 120 seconds"
        }
    except Exception as e:
        return {
            "success": False,
            "output_path": None,
            "error": f"Unexpected error during FFmpeg merge: {str(e)}"
        }

def concatenate_videos(
    video_paths: list,
    output_path: str,
) -> dict:
    """
    Concatenates multiple MP4s into one in order.

    Uses FFmpeg concat demuxer — the most reliable method for
    concatenating same-codec videos without re-encoding.

    Steps:
      1. Write a concat list file (FFmpeg requires this format)
      2. Run FFmpeg concat command
      3. Return path to concatenated video

    Concat list file format:
      file '/path/to/scene_01_final.mp4'
      file '/path/to/scene_02_final.mp4'
      file '/path/to/scene_03_final.mp4'

    Why not re-encode during concat?
    Re-encoding at this stage would take much longer and
    reduce quality. We copy streams directly — fast and lossless.
    """

    os.makedirs(FINAL_DIR, exist_ok=True)

    # Write concat list file
    concat_list_path = os.path.join(FINAL_DIR, "concat_list.txt")
    with open(concat_list_path, "w") as f:
        for video_path in video_paths:
            # FFmpeg requires absolute paths with escaped characters
            abs_path = os.path.abspath(video_path)
            f.write(f"file '{abs_path}'\n")
    
    cmd =[
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy",
        "-y",
        output_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        # Clean up concat list
        if os.path.exists(concat_list_path):
            os.remove(concat_list_path)

        if result.returncode == 0:
            return {
                "success": True,
                "output_path": output_path,
                "error": None
            }
        else:
            return {
                "success": False,
                "output_path": None,
                "error": f"FFmpeg concat failed: {result.stderr[-300:]}"
            }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output_path": None,
            "error": f"FFmpeg concat timeout after 300 seconds"
        }
    except Exception as e:
        return {
            "success": False,
            "output_path": None,
            "error": f"Unexpected error during FFmpeg concat: {str(e)}"
        }
    
def add_background_music(
    video_path: str,
    music_path: str,
    output_path: str,
    music_volume: float = BACKGROUND_MUSIC_VOLUME,
) -> dict:
    """
    Mixes background music into the video at low volume.

    FFmpeg audio filter breakdown:
      [1:a]volume={music_volume}[music]
        → take audio stream from input 2 (music file)
        → reduce its volume to music_volume (0.08 = 8% of original)
        → name this stream 'music'

      [0:a][music]amix=inputs=2:duration=first
        → mix original audio (0:a) with music stream
        → duration=first means stop when first stream ends
          (prevents music from continuing after narration ends)

    Why 0.08 volume for music?
    Educational videos need narration clearly audible.
    Background music at 8% is felt rather than heard —
    adds atmosphere without competing with the voice.
    """

    if not os.path.exists(music_path):
        import shutil
        shutil.copy2(video_path, output_path)
        return {
            "success": True,
            "file_path": output_path,
            "error": f"Background music file not found. Copied video without music."
        }
    
    filter_complex = (
        f"[1:a]volume={music_volume}[music];"
        f"[0:a][music]amix=inputs=2:duration=first[aout]"
    )

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-i", music_path,
        "-filter_complex", filter_complex,
        "-map", "0:v",  # take video from first input
        "-map", "[aout]",  # take mixed audio from filter
        "-c:v", "copy",  # copy video stream as-is
        "-c:a", "aac",   # encode audio as AAC
        "-shortest",     # end when shortest stream ends
        "-y",
        output_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            return {
                "success": True,
                "file_path": output_path,
                "error": None
            }
        else:
            # Music mixing failed — return video without music
            print(f"  [MoviePy] ⚠️  Music mixing failed, continuing without music")
            import shutil
            shutil.copy2(video_path, output_path)
            return {
                "success": False,
                "file_path": output_path,
                "error": None
            }
    except Exception as e:
        import shutil
        shutil.copy2(video_path, output_path)
        return {"success": True, "file_path": output_path, "error": None}

# def burn_subtitles(
#     video_path: str,
#     output_path: str,
#     scenes: list,
# ) -> dict:
#     """
#     Burns subtitles into the video using scene narration text.

#     For Stage 1 we use a simple approach:
#     Generate an SRT file from scene narration and durations,
#     then burn it into the video with FFmpeg.

#     Why not use Whisper here?
#     Whisper would transcribe the audio to generate subtitles.
#     For Stage 1, using our narration text directly is simpler
#     and produces perfect subtitles since we know exactly
#     what was said.

#     Whisper-based subtitles (Stage 2 improvement):
#     Would handle pronunciation differences between our text
#     and how ElevenLabs actually spoke it — more accurate timing.

#     SRT format:
#       1
#       00:00:00,000 --> 00:00:05,000
#       First subtitle text

#       2
#       00:00:05,000 --> 00:00:10,000
#       Second subtitle text
#     """
#     # Generate SRT file from scene data
#     srt_path = os.path.join(FINAL_DIR, "subtitles.srt")

#     with open(srt_path, "w", encoding="utf-8") as f:
#         subtitle_index = 1
#         current_time = 0.0

#         for scene in scenes:
#             narration = scene.get("narration", "")
#             duration = scene.get("actual_duration", scene.get("estimated_duration", 30.0))

#             if not narration:
#                 current_time += duration
#                 continue

#             # Split narration into subtitle chunks (~10 words each)
#             # Long narration on one subtitle is hard to read

#             words = narration.split()
#             chunk_size = 10
#             chunks = [
#                 " ".join(words[i:i+chunk_size])
#                 for i in range(0, len(words), chunk_size)
#             ]

#             chunk_duration = duration / len(chunks)

#             for chunk in chunks:
#                 start = current_time
#                 end = current_time + chunk_duration

#                 # Format timestamps as SRT format: HH:MM:SS,mmm
#                 start_srt = format_srt_time(start)
#                 end_srt = format_srt_time(end)

#                 f.write(f"{subtitle_index}\n")
#                 f.write(f"{start_srt} --> {end_srt}\n")
#                 f.write(f"{chunk}\n\n")

#                 subtitle_index += 1
#                 current_time += chunk_duration
                
#    # Burn subtitles with FFmpeg
#     # Use absolute path — FFmpeg subtitle filter requires it
#     abs_srt_path = os.path.abspath(srt_path)
#     abs_video_path = os.path.abspath(video_path)
#     abs_output_path = os.path.abspath(output_path)

#     cmd = [
#         "ffmpeg",
#         "-i", abs_video_path,
#         "-vf", f"subtitles='{abs_srt_path}'",
#         "-c:a", "copy",
#         "-y",
#         abs_output_path
#     ]

#     try:
#         result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
#         if result.returncode == 0:
#             return {
#                 "success": True,
#                 "output_path": output_path,
#                 "error": None
#             }
#         else:
#             # Subtitle burning failed — return video without subtitles
#             print(f"  [MoviePy] ⚠️  Subtitle burn failed, continuing without subtitles")
#             import shutil
#             shutil.copy2(video_path, output_path)
#             return {"success": True, "file_path": output_path, "error": None}
#     except Exception as e:
#         import shutil
#         shutil.copy2(video_path, output_path)
#         return {"success": True, "file_path": output_path, "error": None}

# def format_srt_time(seconds: float) -> str:
#     """
#     Converts seconds to SRT timestamp format: HH:MM:SS,mmm

#     Example: 125.5 → 00:02:05,500
#     """
#     hours = int(seconds // 3600)
#     minutes = int((seconds % 3600) // 60)
#     secs = int(seconds % 60)
#     millis = int((seconds % 1) * 1000)
#     return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def burn_subtitles(
    video_path: str,
    output_path: str,
    scenes: list,
) -> dict:
    """
    Burns subtitles into video.
    Note: Requires FFmpeg compiled with libass.
    If unavailable, copies video as-is — subtitles skipped.
    Stage 2 improvement: use Whisper + libass for accurate subtitles.
    """
    import shutil

    # Check if subtitles filter is available
    check = subprocess.run(
        ["ffmpeg", "-filters"],
        capture_output=True, text=True
    )

    if "subtitles" not in check.stdout:
        print("  [MoviePy] libass not available — subtitles skipped")
        print("  [MoviePy] Install with: brew install ffmpeg --with-libass")
        shutil.copy2(video_path, output_path)
        return {"success": True, "file_path": output_path, "error": None}

    # Generate SRT
    srt_path = os.path.join(FINAL_DIR, "subtitles.srt")
    _generate_srt(srt_path, scenes)

    # Copy SRT to current directory — avoids path issues on Mac
    shutil.copy2(srt_path, "temp_subs.srt")

    cmd = [
        "ffmpeg",
        "-i", os.path.abspath(video_path),
        "-vf", "subtitles=temp_subs.srt",
        "-c:a", "copy",
        "-y",
        os.path.abspath(output_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if os.path.exists("temp_subs.srt"):
            os.remove("temp_subs.srt")

        if result.returncode == 0:
            return {"success": True, "file_path": output_path, "error": None}
        else:
            print("  [MoviePy] Subtitle burn failed — continuing without")
            shutil.copy2(video_path, output_path)
            return {"success": True, "file_path": output_path, "error": None}
    except Exception as e:
        if os.path.exists("temp_subs.srt"):
            os.remove("temp_subs.srt")
        shutil.copy2(video_path, output_path)
        return {"success": True, "file_path": output_path, "error": None}


def _generate_srt(srt_path: str, scenes: list):
    """Extracts SRT generation into its own function for reuse."""
    with open(srt_path, "w", encoding="utf-8") as f:
        subtitle_index = 1
        current_time = 0.0

        for scene in scenes:
            narration = scene.get("narration", "")
            duration = scene.get("actual_duration") or scene.get("estimated_duration", 30.0)

            if not narration:
                current_time += duration
                continue

            words = narration.split()
            chunk_size = 10
            chunks = [
                " ".join(words[i:i+chunk_size])
                for i in range(0, len(words), chunk_size)
            ]
            chunk_duration = duration / len(chunks)

            for chunk in chunks:
                start_srt = format_srt_time(current_time)
                end_srt = format_srt_time(current_time + chunk_duration)
                f.write(f"{subtitle_index}\n{start_srt} --> {end_srt}\n{chunk}\n\n")
                subtitle_index += 1
                current_time += chunk_duration