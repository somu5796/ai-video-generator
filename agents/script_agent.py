import json
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from utils.llm_helpers import extract_text_from_response

from schemas.video_schema import (
    VideoState,
    Script,
    Scene,
    VisualElement,
    VisualType,
    VideoStyle,
    SpeakerConfig,
    SpeakerMode,
    DialogueLine,
    PipelineStatus,
)
from config import (
    GOOGLE_API_KEY,
    LLM_MODEL,
    LLM_TEMPERATURE,
    VIDEO_FORMATS,
    DEFAULT_FORMAT,
    VOICE_ID_PRIMARY,
    VOICE_ID_SECONDARY,
)


# ── Speaking rate constant ─────────────────────────────────────────────────────
# Average English speaking rate for educational content.
# 2.3 words/sec is slightly slower than conversation — good for learning.
# This is used both for duration estimation and appear_at calculation.
WORDS_PER_SECOND = 2.3


# ── Prompt Template ────────────────────────────────────────────────────────────
# Two prompt variants:
#   SCRIPT_PROMPT_FIXED    → when format has a target duration
#   SCRIPT_PROMPT_AUTO     → when format="auto", LLM decides length
#
# Why two prompts?
# Telling the LLM "cover this in 180 seconds" vs "cover this completely"
# produces fundamentally different scripts. Auto mode removes the
# artificial constraint so content drives length, not the other way around.

SCRIPT_PROMPT_FIXED = PromptTemplate(
    template="""You are an expert educational video script writer.
Create a detailed, engaging video script for the following topic.

TOPIC: {topic}
STYLE: {style}
TARGET DURATION: {target_duration} seconds
SPEAKER MODE: {speaker_mode}
SCENE COUNT: Generate between {min_scenes} and {max_scenes} scenes.
             Each scene should be {scene_duration_hint} seconds of narration.

CRITICAL RULES — follow these exactly:

1. OUTPUT FORMAT: Return ONLY a valid JSON object. No markdown code blocks,
   no explanation text before or after. Start with {{ and end with }}.

2. APPEAR_AT TIMING — this is the most important rule:
   Each visual element's appear_at must be the exact second in the scene
   when the narration MENTIONS that element.

   Calculate like this:
   - Count words in narration up to where you mention the element
   - Divide by 2.3 (words per second speaking rate)
   - That is the appear_at value

   Example:
   Narration: "Today we explore three concepts. First is Consistency"
   "First is Consistency" starts at word 6 → 6/2.3 = 2.6 seconds
   So: appear_at: 2.6

   NEVER set all elements to appear_at: 0.0
   Elements must appear PROGRESSIVELY through the scene.
   First element can be 0.0, but each subsequent one must be later.

3. VISUAL TYPES — use only these exact string values:
   "title"     → main heading of a scene (use once per scene)
   "subtitle"  → supporting text under title
   "bullet"    → key point that appears as narrator mentions it
   "diagram"   → box/node structure (describe connections in text)
   "code"      → code snippet (use for technical topics)
   "equation"  → mathematical formula
   "arrow"     → connection between two concepts
   "highlight" → emphasis on existing element

4. ESTIMATED DURATION: Calculate as word_count_of_narration / 2.3

5. DIALOGUE MODE (only when speaker_mode is "dialogue"):
   Use dialogue_lines array instead of narration field.
   Set narration to empty string "" when using dialogue_lines.
   Alternate speaker_a and speaker_b naturally.
   speaker_a asks or introduces, speaker_b explains in depth.

6. SCENE STRUCTURE:
   Scene 1: Hook — grab attention, state what viewer will learn
   Scene 2 to N-1: Core content — one concept per scene
   Scene N: Summary + call to action

7. TAGS: Generate 8-10 relevant YouTube tags.
8. DESCRIPTION: Write a compelling 2-3 sentence YouTube description.

Return this exact JSON structure:
{{
  "title": "video title here",
  "description": "youtube description here",
  "tags": ["tag1", "tag2"],
  "style": "{style}",
  "speaker_config": {{
    "mode": "{speaker_mode}",
    "speaker_a_voice_id": "{voice_id_primary}",
    "speaker_b_voice_id": "{voice_id_secondary}"
  }},
  "scenes": [
    {{
      "scene_number": 1,
      "title": "scene title",
      "narration": "full narration text for this scene",
      "dialogue_lines": null,
      "visual_elements": [
        {{
          "element_id": "e1",
          "text": "element text",
          "visual_type": "title",
          "appear_at": 0.0,
          "duration": 4.0,
          "position": "center",
          "emphasis": false
        }}
      ],
      "estimated_duration": 25.0,
      "transition": "fade"
    }}
  ],
  "total_estimated_duration": {target_duration}.0,
  "target_duration": {target_duration}.0
}}""",
    input_variables=[
        "topic", "style", "target_duration", "speaker_mode",
        "min_scenes", "max_scenes", "scene_duration_hint",
        "voice_id_primary", "voice_id_secondary"
    ]
)


SCRIPT_PROMPT_AUTO = PromptTemplate(
    template="""You are an expert educational video script writer.
Create a detailed, engaging video script for the following topic.

TOPIC: {topic}
STYLE: {style}
SPEAKER MODE: {speaker_mode}
SCENE COUNT: Generate between {min_scenes} and {max_scenes} scenes.

DURATION RULE: Cover the topic completely and naturally.
Do not pad content to fill time. Do not rush to be brief.
Let the depth of the topic determine the video length.
Simple topics: 2-4 minutes. Complex topics: 8-15 minutes.

CRITICAL RULES — follow these exactly:

1. OUTPUT FORMAT: Return ONLY a valid JSON object. No markdown code blocks,
   no explanation text before or after. Start with {{ and end with }}.

2. APPEAR_AT TIMING — this is the most important rule:
   Each visual element's appear_at must be the exact second in the scene
   when the narration MENTIONS that element.

   Calculate like this:
   - Count words in narration up to where you mention the element
   - Divide by 2.3 (words per second speaking rate)
   - That is the appear_at value

   Example:
   Narration: "Today we explore three concepts. First is Consistency"
   "First is Consistency" starts at word 6 → 6/2.3 = 2.6 seconds
   So: appear_at: 2.6

   NEVER set all elements to appear_at: 0.0
   Elements must appear PROGRESSIVELY through the scene.

3. VISUAL TYPES — use only these exact string values:
   "title"     → main heading of a scene (use once per scene)
   "subtitle"  → supporting text under title
   "bullet"    → key point that appears as narrator mentions it
   "diagram"   → box/node structure (describe connections in text)
   "code"      → code snippet
   "equation"  → mathematical formula
   "arrow"     → connection between two concepts
   "highlight" → emphasis on existing element

4. ESTIMATED DURATION: Calculate as word_count_of_narration / 2.3

5. DIALOGUE MODE (only when speaker_mode is "dialogue"):
   Use dialogue_lines array instead of narration field.
   Set narration to empty string "" when using dialogue_lines.
   Alternate speaker_a and speaker_b naturally.

6. SCENE STRUCTURE:
   Scene 1: Hook — grab attention, state what viewer will learn
   Scene 2 to N-1: Core content — one concept per scene
   Scene N: Summary + call to action

7. TAGS: Generate 8-10 relevant YouTube tags.
8. DESCRIPTION: Write a compelling 2-3 sentence YouTube description.

Return this exact JSON structure:
{{
  "title": "video title here",
  "description": "youtube description here",
  "tags": ["tag1", "tag2"],
  "style": "{style}",
  "speaker_config": {{
    "mode": "{speaker_mode}",
    "speaker_a_voice_id": "{voice_id_primary}",
    "speaker_b_voice_id": "{voice_id_secondary}"
  }},
  "scenes": [
    {{
      "scene_number": 1,
      "title": "scene title",
      "narration": "full narration text for this scene",
      "dialogue_lines": null,
      "visual_elements": [
        {{
          "element_id": "e1",
          "text": "element text",
          "visual_type": "title",
          "appear_at": 0.0,
          "duration": 4.0,
          "position": "center",
          "emphasis": false
        }}
      ],
      "estimated_duration": 25.0,
      "transition": "fade"
    }}
  ],
  "total_estimated_duration": 0.0,
  "target_duration": 0.0
}}""",
    input_variables=[
        "topic", "style", "speaker_mode",
        "min_scenes", "max_scenes",
        "voice_id_primary", "voice_id_secondary"
    ]
)


# ── Helper Functions ───────────────────────────────────────────────────────────

def estimate_duration(narration: str) -> float:
    """
    Calculates estimated scene duration from narration word count.

    Why recalculate instead of trusting LLM value?
    LLMs sometimes produce duration values inconsistent with
    the actual narration length. We always recalculate and
    override whatever the LLM provided — ground truth only.
    """
    if not narration or not narration.strip():
        return 0.0
    word_count = len(narration.split())
    return round(word_count / WORDS_PER_SECOND, 1)


def detect_speaker_mode(topic: str, style: VideoStyle) -> SpeakerMode:
    """
    Automatically decides between single voice and dialogue
    based on topic keywords and content style.

    Why auto-detect instead of always asking user?
    For business video generation, the system should make
    intelligent decisions automatically. Users describe what
    they want, not how to implement it.

    Dialogue triggers:
      Comparison topics      → "SQL vs NoSQL", "REST vs GraphQL"
      Q&A format topics      → "interview questions", "FAQ"
      Finance topics         → naturally suit question/answer format
      Debate-style topics    → "should you use microservices?"
    """
    dialogue_triggers = [
        "vs", "versus", "compare", "difference between",
        "q&a", "interview", "debate", "pros and cons",
        "should i", "which is better", "faq", "questions",
        "explained simply", "for beginners"
    ]

    topic_lower = topic.lower()
    is_dialogue_topic = any(
        trigger in topic_lower for trigger in dialogue_triggers
    )
    is_finance = style == VideoStyle.FINANCE

    if is_dialogue_topic or is_finance:
        return SpeakerMode.DIALOGUE
    return SpeakerMode.SINGLE


def clean_llm_json_output(raw_output: str) -> str:
    """
    Strips markdown formatting and extracts pure JSON from LLM response.

    Why is this needed?
    Even with explicit instructions to return pure JSON,
    LLMs occasionally wrap output in ```json ... ``` blocks
    or add explanatory text before/after the JSON object.
    This is a known LLM behaviour — defensive parsing is essential
    in production systems that depend on structured LLM output.

    Strategy:
      1. Remove markdown code block markers
      2. Find the outermost { } pair
      3. Return only that substring
    """
    # Remove markdown code blocks if present
    raw_output = re.sub(r"```json\s*", "", raw_output)
    raw_output = re.sub(r"```\s*", "", raw_output)

    # Find outermost JSON object boundaries
    start = raw_output.find("{")
    end = raw_output.rfind("}") + 1

    if start == -1 or end == 0:
        raise ValueError(
            f"No JSON object found in LLM output. "
            f"First 200 chars: {raw_output[:200]}"
        )

    return raw_output[start:end]


def validate_and_fix_scene(scene_data: dict, scene_number: int) -> dict:
    """
    Validates a single scene dict and fixes common LLM mistakes.

    Why fix instead of reject and retry?
    Retrying costs an LLM call (latency + quota).
    Most issues are minor and fixable programmatically.
    We only retry if the issue is fundamental
    (wrong JSON structure, missing required fields).

    Fixes applied:
      1. Recalculate estimated_duration from actual narration
         (LLM duration estimates are unreliable)
      2. Fix appear_at=0.0 for all elements
         (means LLM ignored the timing rule — distribute evenly)
      3. Reassign sequential element_ids
         (LLM sometimes duplicates IDs)
      4. Ensure scene_number matches position
         (LLM sometimes numbers incorrectly)
    """
    narration = scene_data.get("narration", "")

    # Fix 1: always recalculate duration from actual narration
    if narration and narration.strip():
        scene_data["estimated_duration"] = estimate_duration(narration)
    else:
        # dialogue mode — estimate from dialogue lines if present
        dialogue_lines = scene_data.get("dialogue_lines") or []
        if dialogue_lines:
            total_text = " ".join(
                line.get("text", "") for line in dialogue_lines
            )
            scene_data["estimated_duration"] = estimate_duration(total_text)

    # Fix 2: check if all appear_at values are identical (LLM ignored timing)
    elements = scene_data.get("visual_elements", [])
    if len(elements) > 1:
        appear_at_values = [e.get("appear_at", 0.0) for e in elements]
        all_same = len(set(appear_at_values)) == 1

        if all_same:
            # Distribute elements evenly through scene duration
            duration = scene_data.get("estimated_duration", 20.0)
            interval = duration / len(elements)
            for i, element in enumerate(elements):
                element["appear_at"] = round(i * interval, 1)
            print(
                f"  [Fix] Scene {scene_number}: redistributed "
                f"{len(elements)} elements evenly (LLM set all to same appear_at)"
            )

    # Fix 3: reassign sequential element IDs to ensure uniqueness
    for i, element in enumerate(elements):
        element["element_id"] = f"e{i + 1}"

    # Fix 4: ensure scene number matches actual position
    scene_data["scene_number"] = scene_number

    return scene_data


def parse_script_from_llm(raw_output: str, style: VideoStyle) -> Script:
    """
    Converts raw LLM string output into a validated Script Pydantic object.

    Pipeline:
      raw string
        → strip markdown → clean JSON string
        → json.loads() → Python dict
        → validate_and_fix_scene() on each scene → fixed dict
        → Script(**script_dict) → Pydantic validates all fields and types

    If Pydantic validation fails (wrong type, missing field, invalid enum)
    it raises a clear ValidationError telling us exactly what went wrong.
    This surfaces LLM mistakes early rather than causing silent failures
    downstream in Voice or Visual agents.
    """
    # Step 1: extract pure JSON
    clean_json = clean_llm_json_output(raw_output)

    # Step 2: parse to Python dict
    try:
        script_dict = json.loads(clean_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM produced invalid JSON: {e}. Output: {clean_json[:300]}")

    # Step 3: validate and fix each scene
    raw_scenes = script_dict.get("scenes", [])
    if not raw_scenes:
        raise ValueError("LLM produced script with no scenes")

    fixed_scenes = []
    for i, scene_data in enumerate(raw_scenes, start=1):
        fixed_scene = validate_and_fix_scene(scene_data, i)
        fixed_scenes.append(fixed_scene)

    script_dict["scenes"] = fixed_scenes

    # Step 4: recalculate total duration from fixed scene durations
    total_duration = sum(
        s.get("estimated_duration", 0) for s in fixed_scenes
    )
    script_dict["total_estimated_duration"] = round(total_duration, 1)

    # Step 5: Pydantic validates all fields — catches any remaining issues
    try:
        script = Script(**script_dict)
    except Exception as e:
        raise ValueError(f"Script schema validation failed: {e}")

    return script


# ── Main LangGraph Node Function ───────────────────────────────────────────────

def script_agent(state: dict) -> dict:
    """
    LangGraph node function — Script Agent.

    LangGraph node contract:
      INPUT:  full state dict (all fields from VideoState)
      OUTPUT: dict containing ONLY the fields this node changed
              LangGraph merges this back into full state automatically

    Why return partial dict not full state?
    Each node is responsible for its own outputs only.
    Returning full state would require every node to know about
    every field — tight coupling and maintenance nightmare.
    Returning only changed fields = loose coupling = clean architecture.

    Flow:
      1. Read topic, style, format from state
      2. Look up format config (duration, scene count limits)
      3. Detect speaker mode automatically
      4. Choose correct prompt (fixed duration vs auto)
      5. Call Gemini LLM
      6. Parse, validate, fix output
      7. Return script + updated status

    Retry logic:
      Up to 3 attempts if LLM output is invalid.
      On retry, previous error is appended to prompt as context.
      This guides the LLM to fix the specific issue on next attempt.
      After 3 failures, pipeline status set to FAILED.
    """
    print("\n" + "=" * 50)
    print("[Script Agent] Starting")
    print("=" * 50)

    # ── Read from state ────────────────────────────────
    topic = state["topic"]
    style = state.get("style", VideoStyle.TECHNICAL)
    video_format = state.get("format", DEFAULT_FORMAT)

    # Convert style to VideoStyle enum if it came as string
    if isinstance(style, str):
        style = VideoStyle(style)

    # ── Look up format config ──────────────────────────
    # VIDEO_FORMATS dict maps format name to duration and scene limits
    format_config = VIDEO_FORMATS.get(video_format, VIDEO_FORMATS[DEFAULT_FORMAT])
    target_duration = (
        state.get("target_duration")      # user override takes priority
        or format_config["target_duration"]  # format default second
    )
    min_scenes = format_config["min_scenes"]
    max_scenes = format_config["max_scenes"]
    is_auto = target_duration is None

    # ── Detect speaker mode ────────────────────────────
    speaker_mode = detect_speaker_mode(topic, style)

    print(f"[Script Agent] Topic          : {topic}")
    print(f"[Script Agent] Style          : {style.value}")
    print(f"[Script Agent] Format         : {video_format}")
    print(f"[Script Agent] Target duration: {target_duration or 'auto'}")
    print(f"[Script Agent] Scene range    : {min_scenes} - {max_scenes}")
    print(f"[Script Agent] Speaker mode   : {speaker_mode.value}")

    # ── Build prompt ───────────────────────────────────
    if is_auto:
        prompt = SCRIPT_PROMPT_AUTO.format(
            topic=topic,
            style=style.value,
            speaker_mode=speaker_mode.value,
            min_scenes=min_scenes,
            max_scenes=max_scenes,
            voice_id_primary=VOICE_ID_PRIMARY,
            voice_id_secondary=VOICE_ID_SECONDARY,
        )
    else:
        # Calculate hint for scene duration
        scene_duration_hint = int(target_duration / min_scenes)

        prompt = SCRIPT_PROMPT_FIXED.format(
            topic=topic,
            style=style.value,
            target_duration=int(target_duration),
            speaker_mode=speaker_mode.value,
            min_scenes=min_scenes,
            max_scenes=max_scenes,
            scene_duration_hint=scene_duration_hint,
            voice_id_primary=VOICE_ID_PRIMARY,
            voice_id_secondary=VOICE_ID_SECONDARY,
        )

    # ── Initialise LLM ─────────────────────────────────
    llm = ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=LLM_TEMPERATURE
    )

    # ── Retry loop ─────────────────────────────────────
    # Up to 3 attempts with error feedback on each retry
    last_error = None
    current_prompt = prompt

    for attempt in range(1, 4):
        try:
            print(f"\n[Script Agent] Attempt {attempt}/3 — calling LLM...")
            response = llm.invoke(current_prompt)
            raw_output = extract_text_from_response(response)
            print(f"[Script Agent] LLM response received ({len(raw_output)} chars)")

            # Parse and validate
            script = parse_script_from_llm(raw_output, style)

            # Validate scene count
            scene_count = len(script.scenes)

            if scene_count < min_scenes:
                raise ValueError(
                    f"Too few scenes generated: {scene_count}. "
                    f"Minimum required: {min_scenes}."
                )

            if scene_count > max_scenes:
                # Trim excess scenes rather than rejecting
                print(
                    f"[Script Agent] Trimming from {scene_count} "
                    f"to {max_scenes} scenes"
                )
                script.scenes = script.scenes[:max_scenes]
                # Recalculate total duration after trim
                script.total_estimated_duration = round(
                    sum(s.estimated_duration for s in script.scenes), 1
                )

            # Success
            print(f"\n[Script Agent] ✅ Script generated successfully")
            print(f"[Script Agent] Title    : {script.title}")
            print(f"[Script Agent] Scenes   : {len(script.scenes)}")
            print(f"[Script Agent] Duration : {script.total_estimated_duration}s")
            print(f"[Script Agent] Tags     : {', '.join(script.tags[:3])}...")

            return {
                "script": script,
                "status": PipelineStatus.SCRIPT_COMPLETE,
                "errors": []
            }

        except Exception as e:
            last_error = str(e)
            print(f"[Script Agent] ⚠️  Attempt {attempt} failed: {last_error}")

            if attempt < 3:
                # Append error to prompt so LLM knows what to fix
                current_prompt = (
                    prompt +
                    f"\n\nPREVIOUS ATTEMPT FAILED WITH THIS ERROR:\n{last_error}"
                    f"\n\nPlease fix this specific issue in your response."
                )
                print(f"[Script Agent] Retrying with error feedback...")

    # All attempts failed
    error_msg = (
        f"Script generation failed after 3 attempts. "
        f"Last error: {last_error}"
    )
    print(f"\n[Script Agent] ❌ {error_msg}")

    return {
        "status": PipelineStatus.FAILED,
        "errors": [error_msg]
    }

