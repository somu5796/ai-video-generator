from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# ── Enums — constrained value sets ────────────────────────────────────────────
# Enums prevent invalid values at schema level.
# If agent tries to set visual_type="random", Pydantic rejects it immediately.

class VisualType(str, Enum):
    """
    Types of visual elements Manim can render.
    Each type maps to a specific Manim animation in visual_agent.py.
    """
    TITLE = "title"           # large centered text, fades in
    SUBTITLE = "subtitle"     # smaller text below title
    BULLET = "bullet"         # bullet point, appears with arrow
    DIAGRAM = "diagram"       # box/node diagram
    CODE = "code"             # code block with syntax highlight
    EQUATION = "equation"     # mathematical equation
    ARROW = "arrow"           # arrow connecting two elements
    HIGHLIGHT = "highlight"   # highlights existing element


class SpeakerMode(str, Enum):
    """
    Single = one AI voice throughout.
    Dialogue = two voices alternating (for Q&A or debate style videos).
    """
    SINGLE = "single"
    DIALOGUE = "dialogue"


class VideoStyle(str, Enum):
    """
    Controls color scheme and animation style in Manim.
    Technical = dark background, code-friendly colors (like 3Blue1Brown)
    Finance = clean white, professional
    General = colorful, accessible
    """
    TECHNICAL = "technical"
    FINANCE = "finance"
    GENERAL = "general"


class PipelineStatus(str, Enum):
    """
    Tracks which stage the pipeline is currently in.
    Used by LangGraph to route between nodes and handle errors.
    """
    PENDING = "pending"
    SCRIPT_COMPLETE = "script_complete"
    VOICE_COMPLETE = "voice_complete"
    VISUALS_COMPLETE = "visuals_complete"
    ASSEMBLY_COMPLETE = "assembly_complete"
    FAILED = "failed"


# ── Core building blocks ───────────────────────────────────────────────────────

class VisualElement(BaseModel):
    """
    A single visual element that appears on screen.
    appear_at is seconds from the START of this scene (not the whole video).
    The Visual Agent uses appear_at to schedule Manim animations.

    Example:
      narration: "CAP theorem has three parts: Consistency, Availability..."
      elements:
        VisualElement(text="Consistency", appear_at=2.5, type=BULLET)
        VisualElement(text="Availability", appear_at=3.8, type=BULLET)
    """
    element_id: str = Field(description="Unique ID within the scene e.g. 'e1', 'e2'")
    text: str = Field(description="Text content to display")
    visual_type: VisualType = Field(description="How this element should be rendered")
    appear_at: float = Field(description="Seconds from scene start when element appears")
    duration: float = Field(default=3.0, description="How long element stays visible")
    position: str = Field(default="center", description="center / top / bottom / left / right")
    emphasis: bool = Field(default=False, description="If True, animate with extra attention effect")


class DialogueLine(BaseModel):
    """
    Used only when speaker_mode = DIALOGUE.
    Each line is spoken by either speaker_a or speaker_b.
    Voice Agent maps these to different ElevenLabs voice IDs.

    Example for finance Q&A video:
      DialogueLine(speaker="speaker_a", text="What is inflation?")
      DialogueLine(speaker="speaker_b", text="Inflation is the rate at which...")
    """
    speaker: str = Field(description="speaker_a or speaker_b")
    text: str = Field(description="What this speaker says")


class SpeakerConfig(BaseModel):
    """
    Maps speaker roles to ElevenLabs voice IDs.
    Kept in schema so Voice Agent and Script Agent share the same config.
    voice_id values come from ElevenLabs dashboard.
    """
    mode: SpeakerMode = Field(default=SpeakerMode.SINGLE)
    speaker_a_voice_id: str = Field(
        default="EXAVITQu4vr4xnSDxMaL",  # ElevenLabs 'Rachel' — calm, educational
        description="Primary voice ID from ElevenLabs"
    )
    speaker_b_voice_id: Optional[str] = Field(
        default="ErXwobaYiN019PkySvjV",  # ElevenLabs 'Antoni' — warm, conversational
        description="Secondary voice ID, only used in DIALOGUE mode"
    )


# ── Scene — the core unit of a video ──────────────────────────────────────────

class Scene(BaseModel):
    """
    A Scene is one continuous segment of the video.
    Think of it like a slide in a presentation — but with:
      - narration that gets converted to audio
      - visual elements that appear progressively
      - exact timing for each element

    A 3 minute video typically has 6-10 scenes.

    Fields added progressively by each agent:
      Script Agent  → fills everything except audio_file_path, video_file_path
      Voice Agent   → fills audio_file_path, actual_duration
      Visual Agent  → fills video_file_path
    """
    scene_number: int = Field(description="1-indexed scene number")
    title: str = Field(description="Short title for this scene e.g. 'What is Consistency?'")
    narration: str = Field(description="Full narration text spoken during this scene")
    dialogue_lines: Optional[list[DialogueLine]] = Field(
        default=None,
        description="Used instead of narration when mode=DIALOGUE"
    )
    visual_elements: list[VisualElement] = Field(
        description="Elements to display, ordered by appear_at"
    )
    estimated_duration: float = Field(
        description="Script agent's estimate in seconds based on narration length"
    )
    transition: str = Field(
        default="fade",
        description="Transition to next scene: fade / slide / wipe"
    )

    # Filled by Voice Agent
    audio_file_path: Optional[str] = Field(
        default=None,
        description="Path to generated MP3 for this scene"
    )
    actual_duration: Optional[float] = Field(
        default=None,
        description="Actual audio duration in seconds from ElevenLabs"
    )

    # Filled by Visual Agent
    video_file_path: Optional[str] = Field(
        default=None,
        description="Path to rendered MP4 for this scene"
    )


# ── Script — output of Script Agent ───────────────────────────────────────────

class Script(BaseModel):
    """
    Complete structured script for the video.
    Script Agent produces this. All other agents consume it.
    """
    title: str = Field(description="Video title")
    description: str = Field(description="YouTube description (generated with script)")
    tags: list[str] = Field(description="YouTube tags for discoverability")
    style: VideoStyle = Field(description="Visual style for Manim rendering")
    speaker_config: SpeakerConfig = Field(description="Voice configuration")
    scenes: list[Scene] = Field(description="Ordered list of scenes")
    total_estimated_duration: float = Field(
        description="Sum of all scene estimated_durations in seconds"
    )
    target_duration: float = Field(
        default=180.0,
        description="Target video length in seconds (default 3 minutes)"
    )


# ── Pipeline State — the LangGraph shared state ────────────────────────────────

class VideoState(BaseModel):
    """
    The central state object passed between all LangGraph nodes.
    Every agent reads from this and writes back to this.

    This is the most important class in the project.
    If you understand VideoState, you understand the entire pipeline.

    LangGraph passes this as a dictionary between nodes.
    Each node receives the full state and returns updated fields only.
    """

    # Input fields — set by user before pipeline starts
    topic: str = Field(description="What the video is about")
    style: VideoStyle = Field(
        default=VideoStyle.TECHNICAL,
        description="Visual style"
    )
    target_duration: float = Field(
        default=180.0,
        description="Target video duration in seconds"
    )
    output_filename: Optional[str] = Field(
        default=None,
        description="Custom output filename. Auto-generated from topic if None."
    )

    # Filled progressively by each agent
    script: Optional[Script] = Field(
        default=None,
        description="Filled by Script Agent"
    )
    final_video_path: Optional[str] = Field(
        default=None,
        description="Filled by Assembly Agent"
    )

    # Pipeline control fields
    status: PipelineStatus = Field(
        default=PipelineStatus.PENDING,
        description="Current pipeline stage"
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Errors from any agent. Pipeline stops if this is non-empty."
    )
    retry_count: int = Field(
        default=0,
        description="Number of retries attempted. Max retries defined in config."
    )