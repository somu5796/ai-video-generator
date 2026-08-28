from renderers.base_renderer import SlideRenderer


class PptxRenderer(SlideRenderer):
    """
    Planned second renderer: real .pptx via python-pptx, exported to
    per-slide PNGs via LibreOffice headless (`soffice --headless
    --convert-to png`). Best fit for finance/table-structured and
    gadget-review/spec-table content, and produces an actual editable
    deck file as a bonus artifact.

    Not implemented yet — this is a placeholder so the registry and
    deck_agent already route to it correctly once it's built, without
    any pipeline changes. Implementing this is the natural next step
    after HtmlRenderer is validated end-to-end.
    """

    _NOT_IMPLEMENTED = (
        "PptxRenderer is not implemented yet. It's planned for the "
        "'finance' and 'gadget' content types (python-pptx + LibreOffice "
        "headless render). Use style='technical' for now, which routes "
        "to HtmlRenderer."
    )

    def build_states(self, scene, style_config: dict) -> list[dict]:
        raise NotImplementedError(self._NOT_IMPLEMENTED)

    def render_scene_video(self, scene, output_dir, fps, width, height, style_config) -> dict:
        return {"success": False, "file_path": None, "error": self._NOT_IMPLEMENTED}

    def render_preview_image(self, scene, output_dir, width, height, style_config, state_index: int = 0) -> dict:
        return {"success": False, "file_path": None, "error": self._NOT_IMPLEMENTED}