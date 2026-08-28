from langgraph.graph import StateGraph, START, END
from typing import Literal, Optional, TypedDict, Any

from schemas.video_schema import VideoState, PipelineStatus, VideoStyle, Script
from agents.script_agent import script_agent
from agents.script_review_agent import script_review_agent
from agents.voice_agent import voice_agent
from agents.visual_agent import visual_agent
from agents.deck_agent import deck_agent
from agents.deck_preview_agent import deck_preview_agent
from agents.assembly_agent import assembly_agent
from utils.script_review_utils import load_script_snapshot
from config import get_output_dirs
import os


# ── State TypedDict ────────────────────────────────────────────────────────────
# LangGraph uses this to know which fields exist in state
# and how to merge partial updates from each node.
# Every node returns a dict with only changed fields —
# LangGraph merges them into this full state automatically.

class PipelineState(TypedDict, total=False):
    topic: str
    style: str
    format: str
    target_duration: Optional[float]
    output_filename: Optional[str]
    run_dirs: Optional[dict]
    script: Optional[Any]
    final_video_path: Optional[str]
    status: Any
    errors: list
    retry_count: int

    # v2 additions
    visual_mode: str                    # "word-reveal" (default) or "deck"
    review_action: Optional[str]        # CLI override: "approve" | "revise", consumed once
    preview_action: Optional[str]       # CLI override: "approve" | "revise", consumed once

    # v3 addition
    script_file: Optional[str]          # path to a pre-approved script.json snapshot;
                                         # when set, script_agent + script_review are skipped entirely


# ── Router functions ───────────────────────────────────────────────────────────
# After each agent, LangGraph calls a router function to decide
# which node to go to next.
# Routers return a string that matches an edge name.
# "continue" → proceed to next agent
# "error"    → go to error handler


def _status_value(state: dict) -> str:
    status = state.get("status")
    return status.value if hasattr(status, "value") else status


def route_after_initialise(state: dict) -> Literal["script_agent", "deck_preview", "voice_agent", "error"]:
    """
    Routes right after initialise_pipeline.

    If a script_file was supplied and initialise_pipeline successfully
    loaded it into state["script"] (status already SCRIPT_COMPLETE),
    skip script_agent AND script_review_agent entirely — no LLM call,
    no re-approval of a script that's already approved — and go
    straight to the same fork route_after_review would have used:
    deck_preview for deck mode, voice_agent for word-reveal mode.

    If loading the script_file failed, initialise_pipeline will have
    set status=FAILED with an error message — route to error_handler.

    Otherwise (no script_file given), fall through to the normal
    script_agent → script_review path, completely unchanged.
    """
    if state.get("errors"):
        return "error"
    if state.get("script_file") and _status_value(state) == "script_complete":
        if state.get("visual_mode") == "deck":
            return "deck_preview"
        return "voice_agent"
    return "script_agent"


def route_after_script(state: dict) -> Literal["continue", "error"]:
    """Routes after Script Agent."""
    if state.get("errors"):
        return "error"
    if _status_value(state) == "script_complete":
        return "continue"
    return "error"


def route_after_review(state: dict) -> Literal["deck_preview", "voice_agent", "error"]:
    """
    Routes after the Script Review gate.
    Deck mode goes through the deck-preview gate first (style approval,
    no ElevenLabs cost); word-reveal mode goes straight to Voice Agent
    exactly as before.
    """
    if state.get("errors"):
        return "error"
    if _status_value(state) != "script_complete":
        return "error"
    if state.get("visual_mode") == "deck":
        return "deck_preview"
    return "voice_agent"


def route_after_deck_preview(state: dict) -> Literal["continue", "error"]:
    """Routes after the Deck Preview gate."""
    if state.get("errors"):
        return "error"
    return "continue"


def route_after_voice(state: dict) -> Literal["deck_agent", "visual_agent", "error"]:
    """
    Routes after Voice Agent.
    Deck mode goes to Deck Agent (progressive-reveal render);
    word-reveal mode goes to the original Manim Visual Agent.
    Nothing about the word-reveal path changes.
    """
    if state.get("errors"):
        return "error"
    if _status_value(state) != "voice_complete":
        return "error"
    if state.get("visual_mode") == "deck":
        return "deck_agent"
    return "visual_agent"


def route_after_visual(state: dict) -> Literal["continue", "error"]:
    """
    Routes after either Visual Agent or Deck Agent.
    Both return the same status (visuals_complete) on success —
    Assembly Agent doesn't need to know which one ran.
    """
    if state.get("errors"):
        return "error"
    if _status_value(state) == "visuals_complete":
        return "continue"
    return "error"


# ── Error handler node ─────────────────────────────────────────────────────────

def error_handler(state: dict) -> dict:
    """
    Called when any agent fails.
    Logs the error clearly and sets final status to FAILED.
    """
    errors = state.get("errors", [])
    status = state.get("status")

    print("\n" + "=" * 50)
    print("[Pipeline] ❌ PIPELINE FAILED")
    print("=" * 50)
    print(f"[Pipeline] Status: {status}")
    for error in errors:
        print(f"[Pipeline] Error: {error}")

    return {
        "status": PipelineStatus.FAILED,
        "errors": errors
    }


# ── Pipeline initialiser node ──────────────────────────────────────────────────

def initialise_pipeline(state: dict) -> dict:
    """
    First node in the pipeline — runs before any agent.

    Responsibilities:
      1. Create topic-based output directories
      2. Store dirs in state so all agents use them
      3. Log pipeline start with all config
      4. If script_file is set, load that pre-approved script.json
         snapshot now, so route_after_initialise can skip straight
         past script_agent/script_review_agent — no LLM call spent
         regenerating a script the user already has.
    """
    topic = state.get("topic", "unknown")
    video_format = state.get("format", "medium")
    style = state.get("style", "technical")
    visual_mode = state.get("visual_mode", "word-reveal")
    script_file = state.get("script_file")

    print("\n" + "=" * 50)
    print("[Pipeline] STARTING VIDEO GENERATION PIPELINE")
    print("=" * 50)
    print(f"[Pipeline] Topic       : {topic}")
    print(f"[Pipeline] Format      : {video_format}")
    print(f"[Pipeline] Style       : {style}")
    print(f"[Pipeline] Visual mode : {visual_mode}")
    if script_file:
        print(f"[Pipeline] Script file : {script_file} (skipping script_agent + script_review)")

    # Create unique output directories for this run
    run_dirs = get_output_dirs(topic)

    print(f"[Pipeline] Output : {run_dirs['run_dir']}")

    result = {
        "run_dirs": run_dirs,
        "errors": []
    }

    if script_file:
        try:
            script = load_script_snapshot(script_file)
        except Exception as e:
            print(f"[Pipeline] ❌ Failed to load script_file '{script_file}': {e}")
            return {
                "run_dirs": run_dirs,
                "status": PipelineStatus.FAILED,
                "errors": [f"Failed to load script_file '{script_file}': {e}"],
            }

        print(f"[Pipeline] Loaded script  : {script.title}")
        print(f"[Pipeline] Scenes         : {len(script.scenes)}")
        print(f"[Pipeline] Estimated      : {script.total_estimated_duration}s")

        result["script"] = script
        result["status"] = PipelineStatus.SCRIPT_COMPLETE

    return result


# ── Build the graph ────────────────────────────────────────────────────────────

def build_video_pipeline():
    """
    Constructs and compiles the LangGraph pipeline.

    Graph structure:
      START
        ↓
      initialise_pipeline
        ↓ (no script_file)         ↓ (script_file loaded ok)        ↓ (script_file failed)
      script_agent          deck_preview / voice_agent*           error_handler → END
        ↓ (success)              ↓ (error)
      script_review             error_handler → END
        ↓ (deck mode)  ↓ (word-reveal mode)     ↓ (error)
      deck_preview      voice_agent            error_handler → END
        ↓ (approved)      ↓                     ↓ (error)
      voice_agent        visual_agent          error_handler → END
        ↓ (deck)  ↓ (word-reveal)               ↓ (error)
      deck_agent  visual_agent                 error_handler → END
        ↓                                       ↓ (error)
      assembly_agent                           error_handler → END
        ↓
      END

    * When state["script_file"] points at a saved script.json
      snapshot, initialise_pipeline loads it directly into
      state["script"] and sets status=SCRIPT_COMPLETE. route_after_
      initialise then skips script_agent AND script_review_agent
      entirely (no LLM call, no re-approval of an already-approved
      script) and jumps straight to the same fork route_after_review
      normally uses: deck_preview for deck mode, voice_agent for
      word-reveal mode.

    script_review and deck_preview are cyclic gates — each loops on
    itself internally (via input()/file re-read) until the user
    approves, so they only ever hand off "forward" from the graph's
    perspective. The word-reveal path is completely untouched:
    script_agent → voice_agent → visual_agent → assembly_agent.
    """
    graph = StateGraph(PipelineState)

    # ── Add nodes ──────────────────────────────────────
    graph.add_node("initialise", initialise_pipeline)
    graph.add_node("script_agent", script_agent)
    graph.add_node("script_review", script_review_agent)
    graph.add_node("deck_preview", deck_preview_agent)
    graph.add_node("voice_agent", voice_agent)
    graph.add_node("visual_agent", visual_agent)
    graph.add_node("deck_agent", deck_agent)
    graph.add_node("assembly_agent", assembly_agent)
    graph.add_node("error_handler", error_handler)

    # ── Add edges ──────────────────────────────────────
    graph.add_edge(START, "initialise")

    graph.add_conditional_edges(
        "initialise",
        route_after_initialise,
        {
            "script_agent": "script_agent",
            "deck_preview": "deck_preview",
            "voice_agent": "voice_agent",
            "error": "error_handler",
        }
    )

    graph.add_conditional_edges(
        "script_agent",
        route_after_script,
        {"continue": "script_review", "error": "error_handler"}
    )

    graph.add_conditional_edges(
        "script_review",
        route_after_review,
        {
            "deck_preview": "deck_preview",
            "voice_agent": "voice_agent",
            "error": "error_handler",
        }
    )

    graph.add_conditional_edges(
        "deck_preview",
        route_after_deck_preview,
        {"continue": "voice_agent", "error": "error_handler"}
    )

    graph.add_conditional_edges(
        "voice_agent",
        route_after_voice,
        {
            "deck_agent": "deck_agent",
            "visual_agent": "visual_agent",
            "error": "error_handler",
        }
    )

    graph.add_conditional_edges(
        "visual_agent",
        route_after_visual,
        {"continue": "assembly_agent", "error": "error_handler"}
    )

    graph.add_conditional_edges(
        "deck_agent",
        route_after_visual,
        {"continue": "assembly_agent", "error": "error_handler"}
    )

    graph.add_edge("assembly_agent", END)
    graph.add_edge("error_handler", END)

    return graph.compile()


# ── Convenience function ───────────────────────────────────────────────────────

def run_pipeline(
    topic: str,
    style: str = "technical",
    video_format: str = "medium",
    target_duration: float = None,
    visual_mode: str = "word-reveal",
    review_action: str = None,
    preview_action: str = None,
    script_file: str = None,
) -> dict:
    """
    Entry point for running the full pipeline.
    Builds the graph, runs it, returns final state.

    script_file: path to a pre-approved script.json snapshot (the
    full Script dump, same shape output/<run>/script.json already
    has). When set, script_agent and script_review_agent are skipped
    entirely — see route_after_initialise / initialise_pipeline.
    """
    pipeline = build_video_pipeline()

    initial_state = {
        "topic": topic,
        "style": style,
        "format": video_format,
        "target_duration": target_duration,
        "visual_mode": visual_mode,
        "review_action": review_action,
        "preview_action": preview_action,
        "script_file": script_file,
        "status": PipelineStatus.PENDING,
        "errors": [],
        "retry_count": 0,
        "run_dirs": None,
        "script": None,
        "final_video_path": None,
    }

    final_state = pipeline.invoke(initial_state, config={"recursion_limit": 100})
    return final_state