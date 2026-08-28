from abc import ABC, abstractmethod


class SlideRenderer(ABC):
    """
    Contract every deck renderer must implement.

    Why an interface instead of one renderer?
    Different content types need different visual tools — a
    finance breakdown wants tables, a tech explainer wants dark
    mode + code blocks. Deck Agent doesn't care HOW a renderer
    makes images, only that it can turn a Scene into:
      1. a set of "build state" images (progressive reveal frames)
      2. a silent scene video assembled from those images

    Every concrete renderer (HtmlRenderer, PptxRenderer, ...) is
    swapped in by the registry based on VideoStyle — deck_agent.py
    never imports a concrete renderer directly.
    """

    @abstractmethod
    def build_states(self, scene, style_config: dict) -> list[dict]:
        """
        Turns one Scene into an ordered list of build states.

        A build state is one frame of the progressive reveal —
        e.g. state 1 = title only, state 2 = title + bullet 1,
        state 3 = title + bullet 1 + bullet 2, etc. This mirrors
        how a PowerPoint "build" or a DeepLearning.AI course slide
        reveals content piece by piece as narration reaches it.

        Returns a list of dicts:
          [{"elements": [...], "hold_duration": float}, ...]
        hold_duration is derived from consecutive appear_at values
        (or actual_duration/estimated_duration for the final state) —
        callers don't need to recompute timing themselves.
        """
        raise NotImplementedError

    @abstractmethod
    def render_scene_video(
        self,
        scene,
        output_dir: str,
        fps: int,
        width: int,
        height: int,
        style_config: dict,
    ) -> dict:
        """
        Renders the full progressive-reveal video for one scene.

        Must return the SAME contract as tools/manim_tool.py's
        render_manim_scene() so it's a drop-in replacement:
          {"success": bool, "file_path": str | None, "error": str | None}

        This is what makes Deck Agent a true swap for Visual Agent —
        Assembly Agent never needs to know which one ran.
        """
        raise NotImplementedError

    @abstractmethod
    def render_preview_image(
        self,
        scene,
        output_dir: str,
        width: int,
        height: int,
        style_config: dict,
        state_index: int = 0,
    ) -> dict:
        """
        Renders ONE build state as a single PNG.

        state_index selects which build state to render:
          0  -> opening frame (first state) — quick style/template check.
          -1 -> final frame (last state, i.e. EVERY element revealed
                together) — this is the frame that matters for catching
                overlapping elements, since it's the most "crowded" the
                scene will ever get once the progressive reveal finishes.

        Used by the deck-preview gate so the user can sanity-check both
        style/template AND layout (no overlaps) before paying the cost
        of a full multi-state render across every scene.

        Returns: {"success": bool, "file_path": str | None, "error": str | None}
        """
        raise NotImplementedError