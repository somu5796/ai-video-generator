import os
import time
import requests
from pathlib import Path
from pydub import AudioSegment
from config import ( ELEVENLABS_API_KEY, ELEVENLABS_MODEL, AUDIO_DIR, AUDIO_FORMAT, VOICE_ID_PRIMARY, VOICE_ID_SECONDARY )

# ElevenLabs API endpoint for text-to-speech
ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"
ELEVENLABS_TTS_URL = f"{ELEVENLABS_BASE_URL}/text-to-speech"

# Voice settings — controls how the voice sounds
# stability: 0.0 = expressive/variable, 1.0 = consistent/robotic
# similarity_boost: how closely to match the original voice
# style: speaking style intensity (0.0 = neutral, 1.0 = very styled)
DEFAULT_VOICE_SETTINGS = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.3,
    "use_speaker_boost": True
}

def get_audio_duration(file_path: str) -> float:
    """
    Returns duration of an audio file in seconds using pydub.

    Why measure duration after generation?
    ElevenLabs speaks at its own pace — faster or slower than our
    word-count estimate. Visual Agent needs actual duration to sync
    animations correctly. We always measure, never assume.
    """
    audio = AudioSegment.from_mp3(file_path)
    duration_seconds = len(audio) / 1000.0  # pydub uses milliseconds
    return round(duration_seconds, 2)

def generate_audio_for_text(
    text : str,
    voice_id : str,
    output_filename : str,
    output_dir: str = None,      # Run dirs path
    voice_settings : dict = None
) -> dict :
    """
    Calls ElevenLabs API to convert text to speech.
    Saves MP3 to outputs/audio/ and returns file info.

    Returns dict with:
      success: bool
      file_path: str (path to saved MP3)
      duration: float (actual audio duration in seconds)
      characters_used: int (for tracking free tier usage)
      error: str (if success=False)

    Why return a dict instead of just the file path?
    Caller needs duration for animation sync, character count
    for quota tracking, and error info for retry logic.
    All in one return avoids multiple function calls.
    """

    if voice_settings is None:
        voice_settings = DEFAULT_VOICE_SETTINGS
    
    if output_dir is None:
        output_dir = AUDIO_DIR

    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_filename)

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg"
    }

    payload = {
        "text": text,
        "model_id": ELEVENLABS_MODEL,
        # eleven_monolingual_v1: fastest, English only, lowest latency
        # eleven_multilingual_v2: slower, supports 29 languages
        # Use monolingual for development — switch to multilingual
        # if you add non-English content later
        "voice_settings": voice_settings
    }

    url = f"{ELEVENLABS_TTS_URL}/{voice_id}"

    try:
        print(f"  [ElevenLabs] Generating audio for {len(text)} chars...")
        response = requests.post(url, headers=headers, json=payload, timeout=60)

        if response.status_code == 200:
            #Save MP3 to file
            with open(output_path, "wb") as f:
                f.write(response.content)
            # Measure actual duration
            duration = get_audio_duration(output_path)
            print(f"  [ElevenLabs] ✅ Saved: {output_filename} ({duration}s)")

            return {
                "success": True,
                "file_path": output_path,
                "duration": duration,
                "characters_used": len(text),
                "error": None
            }
        elif response.status_code == 401:
            return {
                "success": False,
                "file_path": None,
                "duration": None,
                "characters_used": 0,
                "error": "Unauthorized: Invalid ElevenLabs API key."
            }
        elif response.status_code == 429:
            return {
                "success": False,
                "file_path": None,
                "duration": None,
                "characters_used": 0,
                "error": "ElevenLabs quota exceeded. Free tier: 10,000 chars/month."
            }
        else:
            error_details = response.text[:200]  # Truncate to first 200 chars
            return {
                "success": False,
                "file_path": None,
                "duration": None,
                "characters_used": 0,
                "error": f"ElevenLabs API error {response.status_code}: {error_details}"
            }
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "file_path": None,
            "duration": None,
            "characters_used": 0,
            "error": f"ElevenLabs API timeout error after 60 seconds"
        }
    except Exception as e:
        return {
            "success": False,
            "file_path": None,
            "duration": None,
            "characters_used": 0,
            "error": f"Unexpected error: {str(e)}"
        }

def generate_dialogue_audio(
    dialogue_lines: list,
    output_filename: str,
    output_dir: str = None,
) -> dict:
    """
    Generates audio for dialogue mode — alternating between two voices.

    Strategy:
      1. Generate separate MP3 for each dialogue line
      2. Concatenate all lines in order using pydub
      3. Add small pause between speaker switches (natural conversation feel)
      4. Save as single MP3

    Why concatenate instead of one API call?
    ElevenLabs doesn't support multi-speaker in one call.
    We generate each line separately and stitch them together.
    This also lets us add natural pauses between speakers.

    dialogue_lines format:
      [
        {"speaker": "speaker_a", "text": "What is CAP theorem?"},
        {"speaker": "speaker_b", "text": "CAP theorem defines..."},
      ]
    """

    if output_dir is None:
        from config import AUDIO_DIR
        output_dir = AUDIO_DIR
    os.makedirs(output_dir, exist_ok=True)

    # Map speaker roles to voice IDs
    voice_map = {
        "speaker_a": VOICE_ID_PRIMARY,
        "speaker_b": VOICE_ID_SECONDARY,
    }

    # Small pause between speakers — 400ms feels natural
    pause = AudioSegment.silent(duration=400)

    combined_audio = AudioSegment.empty()
    total_characters = 0
    temp_files = []

    for i, line in enumerate(dialogue_lines):
        speaker = line.get("speaker", "speaker_a")
        text = line.get("text", "")
        voice_id = voice_map.get(speaker, VOICE_ID_PRIMARY)
        temp_filename = f"temp_dialogue_{i}.mp3"
        temp_path = os.path.join(output_dir, temp_filename)

        print(f"  [ElevenLabs] Dialogue line {i+1}/{len(dialogue_lines)} — {speaker}")

        # Generate audio for this line
        result = generate_audio_for_text(
            text=text,
            voice_id=voice_id,
            output_filename=temp_filename,
            output_dir=output_dir
        )

        if not result["success"]:
            # Clean up temp files on failure
            for f in temp_files:
                if os.path.exists(f):
                    os.remove(f)
            return {
                "success": False,
                "file_path": None,
                "duration": None,
                "characters_used": total_characters,
                "error": f"Failed on dialogue line {i+1}: {result['error']}"
            }

        # Add this line's audio + pause to combined
        line_audio = AudioSegment.from_mp3(temp_path)
        combined_audio += line_audio + pause
        total_characters += result["characters_used"]
        temp_files.append(temp_path)

        #Small delay to avoid hitting rate limits
        time.sleep(0.5)

    # Save final combined audio
    output_path = os.path.join(output_dir, output_filename)
    combined_audio.export(output_path, format="mp3")
    duration = len(combined_audio) / 1000.0  # pydub uses milliseconds

    #Clean up temp files
    for f in temp_files:
        if os.path.exists(f):
            os.remove(f)
    print(f"  [ElevenLabs] ✅ Dialogue saved: {output_filename} ({duration:.2f}s)")

    return {
        "success": True,
        "file_path": output_path,
        "duration": round(duration, 2),
        "characters_used": total_characters,
        "error": None
    }

def check_quota() -> dict:
    """
    Checks remaining ElevenLabs character quota.
    Call this before generating audio to avoid mid-pipeline failures.

    Returns dict with:
      character_limit: int
      character_count: int (used this month)
      remaining: int
    """
    headers = {"xi-api-key": ELEVENLABS_API_KEY}
    url = f"{ELEVENLABS_BASE_URL}/user/subscription"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            limit = data.get("character_limit", 0)
            count = data.get("character_count", 0)
            remaining = limit - count
            return {
                "success": True,
                "character_limit": limit,
                "character_count": count,
                "remaining": remaining
            }
        else:
            return {
                "success": False,
                "error": f"Status {response.status_code}: {response.text[:100]}"
            }
    except Exception as e:
        return {"success": False, "error": str(e)}