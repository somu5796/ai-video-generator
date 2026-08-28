from renderers.html_renderer import HtmlRenderer
from renderers.pptx_renderer import PptxRenderer

# ── Content type (VideoStyle) → renderer ─────────────────────────────────────
# This is the "different tools called based on input" routing layer.
# Adding a new content type later is a registry entry, not a pipeline change —
# deck_agent.py and deck_preview_agent.py only ever call get_renderer_for_style().
#
# Renderer instances are cheap and stateless (no shared mutable state across
# scenes), so one shared instance per renderer class is fine.

_HTML_RENDERER = HtmlRenderer()
_PPTX_RENDERER = PptxRenderer()

RENDERER_REGISTRY = {
    "technical": _HTML_RENDERER,
    "finance": _PPTX_RENDERER,     # not implemented yet — see pptx_renderer.py
    "general": _HTML_RENDERER,
}


def get_renderer_for_style(style: str):
    """
    Returns the SlideRenderer instance registered for a given VideoStyle
    value. Falls back to HtmlRenderer for unknown styles so a new style
    string never hard-crashes deck mode — worst case it gets a working
    (if not custom-templated) renderer.
    """
    return RENDERER_REGISTRY.get(style, _HTML_RENDERER)
