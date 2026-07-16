import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ───────────────────────────────────────────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

ELEVENLABS_MODEL = "eleven_multilingual_v2"

# ── LLM ───────────────────────────────────────────────────────────────────────
LLM_MODEL = "gemma-4-26b-a4b-it"
LLM_TEMPERATURE = 0.7        # higher than RAG project — we want creative scripts

# ── ElevenLabs Voice IDs ───────────────────────────────────────────────────────
# Roger - Laid-Back, Casual, Resonant → CwhRBWXzGAHq8TQ4Fs17
# Sarah - Mature, Reassuring, Confident → EXAVITQu4vr4xnSDxMaL
# Laura - Enthusiast, Quirky Attitude → FGY2WhTYpPnrIDTdsKH5
# Charlie - Deep, Confident, Energetic → IKne3meq5aSn9XLyUdCD
# George - Warm, Captivating Storyteller → JBFqnCBsd6RMkjVDRZzb
# Callum - Husky Trickster → N2lVS1w4EtoT3dr4eOWO
# River - Relaxed, Neutral, Informative → SAz9YHcvj6GT2YYXdXww
# Harry - Fierce Warrior → SOYHLrjzK2X1ezoPC6cr
# Liam - Energetic, Social Media Creator → TX3LPaxmHKxFdv7VOQHJ
# Alice - Clear, Engaging Educator → Xb7hH8MSUJpSbSDYk0k2
VOICE_ID_PRIMARY = "Xb7hH8MSUJpSbSDYk0k2"  # Alice — clear, engaging, educational — used for single-speaker narration
# L used as second speaker in dialogue mode
VOICE_ID_SECONDARY = "FGY2WhTYpPnrIDTdsKH5"

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