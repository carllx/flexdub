# Project Structure

## Directory Layout

```
pyvideotrans/           # Main package (flexdub)
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
│       ├── say.py      # macOS Say implementation
│       └── interfaces.py
└── pipelines/          # High-level workflows
    └── dubbing.py      # Audio build pipeline (TTS + stretch + concat)

data/
├── input/              # Raw videos and original subtitles
│   └── <ProjectName>/  # Standard project structure (1 MP4 + 1 SRT)
└── output/             # Processed outputs (dub.mp4, rebalance.srt, reports)

tests/                  # Unit and integration tests
plans/                  # Project documentation and decision matrices
agents/                 # Legacy agent scripts (being phased out)
scripts/                # Utility scripts
```

## Key Modules

### CLI (`pyvideotrans/cli/__main__.py`)
- Entry point for all commands
- Enforces text immutability (non-rewrite stages)
- Handles fallback logic and parameter validation

### Core Algorithms (`pyvideotrans/core/`)
- `subtitle.py`: SRT parsing, semantic restructure, LLM dual-track generation
- `rebalance.py`: CPM-based timeline optimization with borrowing and panic mode
- `audio.py`: Elastic audio pipeline (silence removal, stretch/pad, concat, mux)
- `lang.py`: Language detection and voice recommendation

### Pipelines (`pyvideotrans/pipelines/dubbing.py`)
- `build_audio_from_srt`: Per-segment TTS synthesis
- `build_audio_from_srt_clustered`: Clustered synthesis with micro-splitting

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
