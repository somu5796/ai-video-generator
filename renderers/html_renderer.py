import os
from renderers.base_renderer import SlideRenderer
from tools.slide_video_tool import assemble_images_to_video

# Minimum time (seconds) a build state stays on screen.
# Prevents near-zero-duration flashes when the script crams
# several appear_at values very close together.
MIN_HOLD_DURATION = 0.6


class HtmlRenderer(SlideRenderer):
    """
    Renders each scene as a series of HTML/CSS slides, screenshotted
    with Playwright, then stitched into a silent video with timed
    holds per build state — the DeepLearning.AI-style progressive
    reveal, but for the "technical" content type (dark background,
    code-friendly, matches the existing manim "general"/"technical"
    color language already used in tools/manim_tool.py).

    Fully local, fully free: Playwright + a Chromium binary,
    installed once (`pip install playwright && playwright install
    chromium`) — no API calls, no per-render cost.
    """

    # ── Build state computation ────────────────────────────────────────────

    def build_states(self, scene, style_config: dict) -> list[dict]:
        duration = scene.actual_duration or scene.estimated_duration or 10.0
        elements = sorted(scene.visual_elements, key=lambda e: e.appear_at)

        if not elements:
            # No elements at all — a single static title-only state
            # for the full scene duration.
            return [{
                "revealed": [],
                "highlighted_ids": set(),
                "appear_at": 0.0,
                "hold_duration": duration,
            }]

        # Group elements that appear at the same instant so they reveal
        # together in one build state (e.g. a title + subtitle both at 0.0),
        # instead of flashing through near-zero-duration states.
        groups = []
        for el in elements:
            if groups and abs(el.appear_at - groups[-1][0].appear_at) < 1e-6:
                groups[-1].append(el)
            else:
                groups.append([el])

        states = []
        revealed = []          # non-highlight elements shown so far, in order
        highlighted_ids = set()  # element_ids currently emphasized

        for group in groups:
            appear_at = group[0].appear_at
            for el in group:
                if el.visual_type.value == "highlight":
                    # A highlight doesn't add new content — it marks an
                    # already-revealed element (matched by text) as
                    # emphasized in this and subsequent states.
                    target = next(
                        (r for r in revealed if r.text.strip() == el.text.strip()),
                        None,
                    )
                    if target:
                        highlighted_ids.add(target.element_id)
                else:
                    revealed.append(el)

            states.append({
                "revealed": list(revealed),
                "highlighted_ids": set(highlighted_ids),
                "appear_at": appear_at,
                "hold_duration": None,  # filled in below
            })

        # Second pass: hold_duration = time until the NEXT state's
        # appear_at, or remaining scene duration for the last state.
        for i, state in enumerate(states):
            if i + 1 < len(states):
                hold = states[i + 1]["appear_at"] - state["appear_at"]
            else:
                hold = duration - state["appear_at"]
            state["hold_duration"] = max(hold, MIN_HOLD_DURATION)

        return states

    # ── HTML template ───────────────────────────────────────────────────────

    def _render_html(self, scene, state: dict, style_config: dict, width: int, height: int) -> str:
        c = style_config
        body_parts = []

        for el in state["revealed"]:
            is_hl = el.element_id in state["highlighted_ids"]
            vt = el.visual_type.value
            text = _escape(el.text)

            if vt == "title":
                body_parts.append(
                    f'<div class="slide-title{" hl" if is_hl else ""}">{text}</div>'
                )
            elif vt == "subtitle":
                body_parts.append(
                    f'<div class="slide-subtitle{" hl" if is_hl else ""}">{text}</div>'
                )
            elif vt == "bullet":
                body_parts.append(
                    f'<div class="bullet{" hl" if is_hl else ""}">'
                    f'<span class="bullet-mark">&#10148;</span>'
                    f'<span>{text}</span></div>'
                )
            elif vt == "code":
                body_parts.append(
                    f'<pre class="code-block{" hl" if is_hl else ""}">{text}</pre>'
                )
            elif vt == "equation":
                body_parts.append(
                    f'<div class="concept-box equation{" hl" if is_hl else ""}">{text}</div>'
                )
            elif vt == "diagram":
                body_parts.append(
                    f'<div class="concept-box diagram{" hl" if is_hl else ""}">{text}</div>'
                )
            elif vt == "arrow":
                body_parts.append(
                    f'<div class="arrow-row{" hl" if is_hl else ""}">'
                    f'<span class="arrow-label">{text}</span>'
                    f'<span class="arrow-glyph">&#10132;</span></div>'
                )
            else:
                body_parts.append(f'<div class="bullet">{text}</div>')

        body_html = "\n".join(body_parts)

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body {{
    margin: 0; padding: 0;
    width: {width}px; height: {height}px;
    background: {c['background_color']};
    font-family: {c['font_family']};
    overflow: hidden;
  }}
  .slide {{
    box-sizing: border-box;
    width: 100%; height: 100%;
    padding: 150px 110px 72px;
    display: flex;
    flex-direction: column;
    align-items: flex-start;     /* bullets/code/etc stay left-aligned */
    justify-content: flex-start; /* content grows DOWN from the title —
                                     it never re-centers as elements are
                                     revealed, so the title stays put */
    gap: 36px;
    overflow: hidden;            /* a slide that overflows should be
                                     trimmed with less content, not spill
                                     into the scene label */
  }}
  .scene-label {{
    position: absolute;
    top: 32px; left: 96px;
    color: {c['subtitle_color']}88;
    font-size: 20px;
    letter-spacing: 1px;
    text-transform: uppercase;
  }}
  .slide-title {{
    font-family: {c['title_font_family']};
    color: {c['title_color']};
    font-size: 58px;
    font-weight: 700;
    line-height: 1.2;
    align-self: center;   /* pin to top-center of the slide */
    text-align: center;
    max-width: 88%;
    margin-bottom: 10px;
  }}
  .slide-subtitle {{
    color: {c['subtitle_color']};
    font-size: 32px;
    font-weight: 400;
    align-self: center;
    text-align: center;
    max-width: 80%;
    margin-bottom: 8px;
  }}
  .bullet {{
    display: flex; align-items: center; gap: 18px;
    color: {c['bullet_color']};
    font-size: 36px;
    font-weight: 600;
  }}
  .bullet-mark {{ color: {c['accent_color']}; font-size: 28px; }}
  .code-block {{
    background: {c['code_bg']};
    color: {c['code_text']};
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 26px;
    padding: 24px 32px;
    border-radius: 10px;
    white-space: pre-wrap;
    line-height: 1.5;
  }}
  .concept-box {{
    align-self: center;
    border: 2px solid {c['accent_color']};
    background: {c['highlight_bg']};
    color: {c['title_color']};
    font-size: 48px;
    font-weight: 700;
    padding: 28px 56px;
    border-radius: 14px;
    text-align: center;
  }}
  .arrow-row {{
    display: flex; align-items: center; gap: 24px;
    color: {c['subtitle_color']};
    font-size: 30px;
  }}
  .arrow-glyph {{ color: {c['accent_color']}; font-size: 40px; }}
  .hl {{
    text-shadow: 0 0 18px {c['accent_color']};
    transform: scale(1.03);
  }}
</style>
</head>
<body>
  <div class="scene-label">{_escape(scene.title)}</div>
  <div class="slide">
    {body_html}
  </div>
</body>
</html>"""

    # ── Rendering (Playwright) ─────────────────────────────────────────────

    def render_scene_video(self, scene, output_dir, fps, width, height, style_config) -> dict:
        os.makedirs(output_dir, exist_ok=True)
        states = self.build_states(scene, style_config)

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {
                "success": False,
                "file_path": None,
                "error": (
                    "playwright not installed. Run: "
                    "pip install playwright && playwright install chromium"
                ),
            }

        image_durations = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": width, "height": height})

                for i, state in enumerate(states, start=1):
                    html = self._render_html(scene, state, style_config, width, height)
                    page.set_content(html)
                    img_path = os.path.join(
                        output_dir, f"scene_{scene.scene_number:02d}_state_{i:02d}.png"
                    )
                    page.screenshot(path=img_path)
                    image_durations.append((img_path, state["hold_duration"]))

                browser.close()
        except Exception as e:
            return {
                "success": False,
                "file_path": None,
                "error": f"Playwright rendering failed: {e}",
            }

        video_path = os.path.join(output_dir, f"scene_{scene.scene_number:02d}.mp4")
        return assemble_images_to_video(
            image_durations=image_durations,
            output_path=video_path,
            fps=fps,
            width=width,
            height=height,
        )

    def render_preview_image(self, scene, output_dir, width, height, style_config, state_index: int = 0) -> dict:
        os.makedirs(output_dir, exist_ok=True)
        states = self.build_states(scene, style_config)

        try:
            state = states[state_index]
        except IndexError:
            return {
                "success": False,
                "file_path": None,
                "error": (
                    f"state_index {state_index} out of range — scene "
                    f"{scene.scene_number} only has {len(states)} build state(s)"
                ),
            }

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {
                "success": False,
                "file_path": None,
                "error": (
                    "playwright not installed. Run: "
                    "pip install playwright && playwright install chromium"
                ),
            }

        # Name the file by what it actually shows, not just its index —
        # "final" is the one the user should check for overlaps.
        if state_index == 0:
            label = "opening"
        elif state_index in (-1, len(states) - 1):
            label = "final"
        else:
            label = f"state{state_index + 1:02d}"

        img_path = os.path.join(
            output_dir, f"scene_{scene.scene_number:02d}_preview_{label}.png"
        )
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": width, "height": height})
                html = self._render_html(scene, state, style_config, width, height)
                page.set_content(html)
                page.screenshot(path=img_path)
                browser.close()
        except Exception as e:
            return {"success": False, "file_path": None, "error": f"Preview render failed: {e}"}

        return {"success": True, "file_path": img_path, "error": None}


def _escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )