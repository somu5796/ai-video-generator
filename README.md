# AI Video Generator

Generate high-quality educational videos from any technical topic or
question using AI.

The application takes a topic or question (e.g. **"What is Apache
Kafka?"**) and automatically generates:

-   📝 Research-backed script
-   🎙️ AI voice narration
-   🎬 Animated scenes (Manim)
-   🖼️ Dynamic subtitles
-   🎵 Background music
-   🎥 Final rendered video

------------------------------------------------------------------------

## Example

Generate a video for a topic:

``` bash
python src/main.py "What is Apache Kafka?"
```

or

``` bash
python src/main.py "Explain CAP Theorem"
```

or

``` bash
python src/main.py "How do Kafka partitions work?"
```

The generated video will be available under:

``` text
output/videos/
```

------------------------------------------------------------------------

## Project Flow

``` text
User Topic
      │
      ▼
LLM Research & Script Generation
      │
      ▼
Scene Planning
      │
      ▼
Narration Generation (TTS)
      │
      ▼
Manim Animation Generation
      │
      ▼
Subtitle Generation
      │
      ▼
Background Music Mixing
      │
      ▼
FFmpeg Video Composition
      │
      ▼
Final MP4 Video
```

------------------------------------------------------------------------

## Tech Stack

-   Python
-   LangGraph
-   LangChain
-   Google Gemini
-   Manim
-   ElevenLabs / Google TTS
-   Whisper
-   FFmpeg
-   MoviePy

------------------------------------------------------------------------

## Features

-   Generate videos from a single prompt
-   AI-generated educational scripts
-   Automatic scene generation
-   Smooth narration synchronization
-   Word-by-word subtitle animation
-   Background music mixing
-   Fully automated video rendering pipeline

------------------------------------------------------------------------

## Project Structure

``` text
src/
├── graph/
├── agents/
├── prompts/
├── services/
├── animations/
├── utils/
└── main.py

output/
├── videos/
├── audio/
├── subtitles/
└── scenes/
```

------------------------------------------------------------------------

## Workflow

``` text
User Prompt
      │
      ▼
 Script Agent
      │
      ▼
 Scene Generator
      │
      ▼
 Voice Generator
      │
      ▼
 Animation Renderer
      │
      ▼
 Subtitle Generator
      │
      ▼
 Video Composer
      │
      ▼
 Final Video
```

------------------------------------------------------------------------

## Current Status (Phase 1)

-   ✅ End-to-end video generation
-   ✅ AI-generated script
-   ✅ Narration generation
-   ✅ Animated educational slides
-   ✅ Dynamic subtitles
-   ✅ Background music
-   ✅ Final MP4 rendering

------------------------------------------------------------------------

## Planned (Phase 2)

-   Better visual templates
-   semantic caching
-   Intelligent scene transitions
-   Rich diagrams and illustrations
-   Multi-language support
-   Multiple narration voices
-   Custom video themes
-   Better pacing and animation timing
-   Thumbnail generation
-   YouTube upload integration
-   Fesible for instagram or youtube shorts 30 sec or 1 min 
