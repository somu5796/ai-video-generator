import os
import subprocess


def assemble_images_to_video(
    image_durations: list,
    output_path: str,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
) -> dict:
    """
    Turns a list of (image_path, hold_duration) pairs into a silent MP4,
    each image held on screen for its given duration before cutting to
    the next — the "still slide build" technique used by course-style
    progressive-reveal videos.

    image_durations: [(image_path, hold_seconds), ...] in display order.

    Uses FFmpeg's concat demuxer with per-image `duration` directives —
    same "call FFmpeg directly via subprocess" approach as the rest of
    tools/moviepy_tool.py, for the same reason: precise, fast, no
    re-encode surprises.

    FFmpeg concat-with-durations quirk:
    the LAST duration directive is unreliable, so the final image is
    listed twice (once with its duration, once bare) — the documented
    workaround for this FFmpeg behavior.
    """
    if not image_durations:
        return {"success": False, "file_path": None, "error": "No images to assemble"}

    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)

    concat_list_path = os.path.join(output_dir, f"_concat_{os.path.basename(output_path)}.txt")

    try:
        with open(concat_list_path, "w") as f:
            for img_path, hold_duration in image_durations:
                abs_path = os.path.abspath(img_path)
                f.write(f"file '{abs_path}'\n")
                f.write(f"duration {max(hold_duration, 0.1):.3f}\n")
            # Repeat the final image once more without a duration line —
            # required by FFmpeg's concat demuxer to honor the last duration.
            last_img_path = os.path.abspath(image_durations[-1][0])
            f.write(f"file '{last_img_path}'\n")

        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-vf", f"scale={width}:{height},fps={fps}",
            "-pix_fmt", "yuv420p",
            "-y",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

        if os.path.exists(concat_list_path):
            os.remove(concat_list_path)

        if result.returncode == 0:
            return {"success": True, "file_path": output_path, "error": None}
        else:
            return {
                "success": False,
                "file_path": None,
                "error": f"FFmpeg image-to-video assembly failed: {result.stderr[-300:]}",
            }

    except subprocess.TimeoutExpired:
        if os.path.exists(concat_list_path):
            os.remove(concat_list_path)
        return {"success": False, "file_path": None, "error": "FFmpeg assembly timeout after 180 seconds"}
    except Exception as e:
        if os.path.exists(concat_list_path):
            os.remove(concat_list_path)
        return {"success": False, "file_path": None, "error": f"Unexpected error during assembly: {str(e)}"}
