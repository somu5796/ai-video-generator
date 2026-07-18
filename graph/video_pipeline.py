from langgraph.graph import StateGraph, START, END
from typing import Literal, Optional, TypedDict, Any

from schemas.video_schema import VideoState, PipelineStatus, VideoStyle
from agents.script_agent import script_agent
from agents.voice_agent import voice_agent
from agents.visual_agent import visual_agent
from agents.assembly_agent import assembly_agent
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



# ── Router functions ───────────────────────────────────────────────────────────
# After each agent, LangGraph calls a router function to decide
# which node to go to next.
# Routers return a string that matches an edge name.
# "continue" → proceed to next agent
# "error"    → go to error handler



def route_after_script(state: dict) -> Literal["continue", "error"]:
    """
    Routes after Script Agent.
    If script was generated successfully → continue to Voice Agent.
    If script failed → go to error handler.
    """
    if state.get("errors"):
        return "error"
    status = state.get("status")
    if hasattr(status, "value"):
        status = status.value
    if status == "script_complete":
        return "continue"
    return "error"


def route_after_voice(state: dict) -> Literal["continue", "error"]:
    """Routes after Voice Agent."""
    if state.get("errors"):
        return "error"
    status = state.get("status")
    if hasattr(status, "value"):
        status = status.value
    if status == "voice_complete":
        return "continue"
    return "error"


def route_after_visual(state: dict) -> Literal["continue", "error"]:
    """Routes after Visual Agent."""
    if state.get("errors"):
        return "error"
    status = state.get("status")
    if hasattr(status, "value"):
        status = status.value
    if status == "visuals_complete":
        return "continue"
    return "error"


# ── Error handler node ─────────────────────────────────────────────────────────

def error_handler(state: dict) -> dict:
    """
    Called when any agent fails.
    Logs the error clearly and sets final status to FAILED.

    Why have a dedicated error handler node?
    Without it, LangGraph would just stop silently.
    The error handler gives us a place to:
      → log what went wrong and which stage it failed at
      → send notifications (Slack, email) in production
      → clean up partial output files
      → return a structured error response to the caller
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

    Why a separate initialise node?
    Keeps agent code clean — agents don't need to know about
    directory creation. Single responsibility principle.
    Also means if directory creation fails, we catch it before
    wasting LLM API calls.
    """
    topic = state.get("topic", "unknown")
    video_format = state.get("format", "medium")
    style = state.get("style", "technical")

    print("\n" + "=" * 50)
    print("[Pipeline] STARTING VIDEO GENERATION PIPELINE")
    print("=" * 50)
    print(f"[Pipeline] Topic  : {topic}")
    print(f"[Pipeline] Format : {video_format}")
    print(f"[Pipeline] Style  : {style}")

    # Create unique output directories for this run
    run_dirs = get_output_dirs(topic)

    print(f"[Pipeline] Output : {run_dirs['run_dir']}")

    return {
        "run_dirs": run_dirs,
        "errors": []
    }


# ── Build the graph ────────────────────────────────────────────────────────────

def build_video_pipeline():
    """
    Constructs and compiles the LangGraph pipeline.

    Graph structure:
      START
        ↓
      initialise_pipeline
        ↓
      script_agent
        ↓ (success)          ↓ (error)
      voice_agent          error_handler → END
        ↓ (success)          ↓ (error)
      visual_agent         error_handler → END
        ↓ (success)          ↓ (error)
      assembly_agent       error_handler → END
        ↓
      END

    Why compile()?
    Compilation validates the graph structure — catches missing
    edges, unreachable nodes, and type mismatches before runtime.
    A compiled graph is also faster at execution time.
    """
    # Create graph with VideoState as the state schema
    # LangGraph uses this to validate state at each node
    graph = StateGraph(PipelineState)

    # ── Add nodes ──────────────────────────────────────
    graph.add_node("initialise", initialise_pipeline)
    graph.add_node("script_agent", script_agent)
    graph.add_node("voice_agent", voice_agent)
    graph.add_node("visual_agent", visual_agent)
    graph.add_node("assembly_agent", assembly_agent)
    graph.add_node("error_handler", error_handler)

    # ── Add edges ──────────────────────────────────────
    # START → initialise (always)
    graph.add_edge(START, "initialise")

    # initialise → script_agent (always)
    graph.add_edge("initialise", "script_agent")

    # script_agent → voice_agent OR error_handler
    graph.add_conditional_edges(
        "script_agent",
        route_after_script,
        {
            "continue": "voice_agent",
            "error": "error_handler"
        }
    )

    # voice_agent → visual_agent OR error_handler
    graph.add_conditional_edges(
        "voice_agent",
        route_after_voice,
        {
            "continue": "visual_agent",
            "error": "error_handler"
        }
    )

    # visual_agent → assembly_agent OR error_handler
    graph.add_conditional_edges(
        "visual_agent",
        route_after_visual,
        {
            "continue": "assembly_agent",
            "error": "error_handler"
        }
    )

    # assembly_agent → END (always — success or failure handled inside agent)
    graph.add_edge("assembly_agent", END)

    # error_handler → END (always)
    graph.add_edge("error_handler", END)

    # ── Compile ────────────────────────────────────────
    return graph.compile()


# ── Convenience function ───────────────────────────────────────────────────────

def run_pipeline(
    topic: str,
    style: str = "technical",
    video_format: str = "medium",
    target_duration: float = None,
) -> dict:
    """
    Entry point for running the full pipeline.
    Builds the graph, runs it, returns final state.

    This is what main.py and app.py call.
    They don't need to know anything about LangGraph internals —
    just call run_pipeline() with a topic and get back a result.
    """
    pipeline = build_video_pipeline()

    initial_state = {
        "topic": topic,
        "style": style,                    # string not enum
        "format": video_format,
        "target_duration": target_duration,
        "status": PipelineStatus.PENDING,
        "errors": [],
        "retry_count": 0,
        "run_dirs": None,
        "script": None,
        "final_video_path": None,
    }

    final_state = pipeline.invoke(initial_state)
    return final_state