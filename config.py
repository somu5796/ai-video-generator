import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ───────────────────────────────────────────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# ── LLM ───────────────────────────────────────────────────────────────────────
LLM_MODEL = "gemma-4-26b-a4b-it"
LLM_TEMPERATURE = 0.7        # higher than RAG project — we want creative scripts

# ── ElevenLabs Voice IDs ───────────────────────────────────────────────────────
# These are free tier voice IDs from ElevenLabs
# Rachel — calm, clear, educational — best for technical content
VOICE_ID_PRIMARY = "EXAVITQu4vr4xnSDxMaL"
# Antoni — warm, conversational — used as second speaker in dialogue mode
VOICE_ID_SECONDARY = "ErXwobaYiN019PkySvjV"

# ── Video Settings ─────────────────────────────────────────────────────────────
VIDEO_FORMATS = {
    "short":       {"target_duration": 60,   "min_scenes": 2, "max_scenes": 4},
    "medium":      {"target_duration": 180,  "min_scenes": 4, "max_scenes": 8},
    "long":        {"target_duration": 600,  "min_scenes": 8, "max_scenes": 18},
    "auto":        {"target_duration": None, "min_scenes": 3, "max_scenes": 40},
}
DEFAULT_FORMAT = "medium"

# ── Manim Settings ────────────────────────────────────────────────────────────
MANIM_QUALITY = "medium_quality" # low_quality / medium_quality / high_quality
                                 # low = fast render for testing
                                 # high = slow but crisp for final output
MANIM_FPS = 30                   # frames per second
VIDEO_WIDTH = 1920               # 1080p
VIDEO_HEIGHT = 1080

# ── Audio Settings ─────────────────────────────────────────────────────────────
AUDIO_FORMAT = "mp3"
BACKGROUND_MUSIC_VOLUME = 0.08   # very low — just atmosphere, not distracting

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
SCRIPTS_DIR = os.path.join(OUTPUTS_DIR, "scripts")
AUDIO_DIR = os.path.join(OUTPUTS_DIR, "audio")
SCENES_DIR = os.path.join(OUTPUTS_DIR, "scenes")
FINAL_DIR = os.path.join(OUTPUTS_DIR, "final")

# ── Pipeline Settings ──────────────────────────────────────────────────────────
MAX_RETRIES = 3                  # how many times to retry a failed agent