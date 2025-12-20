# Project Structure

## Directory Layout

```
flexdub/           # Main package (flexdub)
├── __init__.py
├── __main__.py
├── cli/                # CLI entrypoints
│   └── __main__.py     # Command parsers (merge, rebalance, audit, etc.)
├── core/               # Core algorithms
│   ├── adapters.py     # External format adapters (WhisperX, Gemini)
│   ├── audio.py        # Audio processing (concat, mux, stretch, silence)
│   ├── io.py           # Segment JSON I/O
│   ├── lang.py         # Language detection and voice mapping
│   ├── rebalance.py    # CPM-based timeline rebalancing
│   └── subtitle.py     # SRT I/O, semantic restructure, LLM integration
├── backends/           # TTS backends
│   └── tts/
│       ├── edge.py     # Edge TTS implementation
│       ├── doubao.py   # Doubao TTS implementation (HTTP service)
│       └── interfaces.py
└── pipelines/          # High-level workflows
    └── dubbing.py      # Audio build pipeline (TTS + stretch + concat)

data/
├── input/              # Raw videos and original subtitles
│   └── <ProjectName>/  # Standard project structure (1 MP4 + 1 SRT)
└── output/             # Processed outputs (dub.mp4, rebalance.srt, reports)

tests/                  # Unit and integration tests
scripts/                # Utility scripts

.agent/                 # Agent cognitive layer
├── config.md           # Cognitive configuration
├── loader.py           # Skill loader
├── skills/             # Skill packages (progressive disclosure)
└── workflows/          # Workflow definitions
```

## Key Modules

### CLI (`flexdub/cli/__main__.py`)
- Entry point for all commands
- Enforces text immutability (non-rewrite stages)
- Parameter validation (no fallback on TTS failure)

### Core Algorithms (`flexdub/core/`)
- `subtitle.py`: SRT parsing, semantic restructure, LLM dual-track generation
- `rebalance.py`: CPM-based timeline optimization with borrowing and panic mode
- `audio.py`: Elastic audio pipeline (silence removal, stretch/pad, concat, mux)
- `lang.py`: Language detection and voice recommendation

### Pipelines (`flexdub/pipelines/dubbing.py`)
- `build_audio_from_srt`: Per-segment TTS synthesis
- `build_audio_from_srt_clustered`: Clustered synthesis with micro-splitting

### Pipelines (`flexdub/pipelines/elastic_video.py`)
- Mode B (elastic-video) pipeline - default mode
- Supports Edge TTS and Doubao TTS backends
- TTS cache for resume/retry capability
- Retry mechanism (3 attempts, 2s delay)
- Character length validation (75 char threshold)
- Bracket content filtering before TTS

## Data Models

- `SRTItem(start_ms, end_ms, text)` - Core subtitle representation
- `Segment(start_ms, end_ms, text)` - Rebalancing data structure

## Standard Project Structure

Each project under `data/input/<ProjectName>/` must contain:
- Exactly one `*.mp4` file
- Exactly one `*.srt` file

Validation: `flexdub validate_project <project_dir>`

## Output Artifacts

- `<basename>.dub.mp4` - Final dubbed video
- `<basename>.rebalance.srt` - Rebalanced subtitle
- `<basename>.display.srt` - Display-optimized subtitle (dual-track mode)
- `<basename>.audio.srt` - TTS-optimized subtitle (dual-track mode)
- `cpm.csv` - CPM audit report
- `process.log` - Processing log
- `report.json` - Validation and metadata
- `sync_debug.log` - Sync audit debug info
