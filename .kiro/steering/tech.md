# Technology Stack

## Build System & Package Management

- **Build**: setuptools (pyproject.toml)
- **Python**: 3.9+ required, 3.10+ recommended
- **Package manager**: pip with virtualenv

## Core Dependencies

- `srt` - SRT parsing and composition
- `numpy` - Numerical operations
- `soundfile` - Audio I/O
- `tqdm` - Progress feedback
- `edge-tts==7.2.1` - Edge TTS backend (optional, ⚠️ 7.2.3 has bug)
- `pyrubberband` - High-quality time stretching (optional, falls back to ffmpeg atempo)
- `pytest` - Testing framework

## External Tools

- **ffmpeg** (required) - Audio/video processing and muxing
- **rubberband** (optional) - Audio time stretching, fallback to ffmpeg atempo if unavailable

## Common Commands

### Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Testing
```bash
python -m pytest -q
```

### CLI Usage
```bash
# Merge SRT with video
flexdub merge <srt> <video> --backend edge_tts --voice zh-CN-YunjianNeural

# Rebalance subtitle timing
flexdub rebalance <srt> --target-cpm 180 --panic-cpm 300

# Audit CPM
flexdub audit <srt> --min-cpm 180 --max-cpm 220 --save cpm.csv

# Project-level processing
flexdub project_merge <project_dir> --backend edge_tts --auto-voice

# Sync audit
flexdub sync_audit <video> <srt> --ar 48000 --win-ms 20
```

## Default Parameters

- Sample rate: `48000` Hz
- Target CPM: `180` (Chinese), `160-200` recommended
- Panic CPM: `300`
- Max shift: `1000` ms
- Jobs: `4` (Edge TTS), `1` (macOS Say or strict mode)
