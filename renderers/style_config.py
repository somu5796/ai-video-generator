import json
import os

# ── Default style configs, keyed by VideoStyle value ────────────────────────
# These are intentionally editable — the deck-preview gate lets the user
# tweak this JSON on disk and re-render just the preview frames, without
# touching any Python code or spending ElevenLabs quota.

DEFAULT_STYLE_CONFIGS = {
    "technical": {
        "background_color": "#0D1117",
        "title_color": "#58A6FF",
        "subtitle_color": "#E6EDF3",
        "bullet_color": "#3FB950",
        "accent_color": "#F0883E",
        "highlight_bg": "#F0883E22",
        "code_bg": "#161B22",
        "code_text": "#E6EDF3",
        "font_family": "'JetBrains Mono', 'Fira Code', monospace",
        "title_font_family": "Georgia, 'Times New Roman', serif",
    },
    "finance": {
        "background_color": "#FFFDE7",
        "title_color": "#1A237E",
        "subtitle_color": "#212121",
        "bullet_color": "#1B5E20",
        "accent_color": "#E65100",
        "highlight_bg": "#E6510022",
        "code_bg": "#FFF9C4",
        "code_text": "#212121",
        "font_family": "'Helvetica Neue', Arial, sans-serif",
        "title_font_family": "'Helvetica Neue', Arial, sans-serif",
    },
    "general": {
        "background_color": "#0D1117",
        "title_color": "#58A6FF",
        "subtitle_color": "#FFFFFF",
        "bullet_color": "#3FB950",
        "accent_color": "#FFA657",
        "highlight_bg": "#FFA65722",
        "code_bg": "#161B22",
        "code_text": "#FFFFFF",
        "font_family": "Arial, sans-serif",
        "title_font_family": "Georgia, serif",
    },
}


def default_style_config(style: str) -> dict:
    """Returns a copy of the default style config for a given VideoStyle value."""
    return dict(DEFAULT_STYLE_CONFIGS.get(style, DEFAULT_STYLE_CONFIGS["technical"]))


def style_config_path(run_dir: str) -> str:
    """Where the editable style JSON lives for a given run."""
    return os.path.join(run_dir, "deck_style.json")


def load_or_create_style_config(run_dir: str, style: str) -> dict:
    """
    Loads deck_style.json if it already exists (user may have edited it
    during a preview-revise cycle), otherwise writes the default config
    for this style and returns that.
    """
    path = style_config_path(run_dir)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)

    config = default_style_config(style)
    save_style_config(run_dir, config)
    return config


def save_style_config(run_dir: str, config: dict) -> str:
    path = style_config_path(run_dir)
    os.makedirs(run_dir, exist_ok=True)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    return path
