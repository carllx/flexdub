# FlexDub — v2.0.0

## Overview（概览）
- Elastic dubbing pipeline for SRT + Video: audit, rebalance, TTS, stretch/pad, concat, mux, QA.

```mermaid
flowchart LR
  In[Data/Input] --> Audit[Audit CPM (每分钟字符数)]
  Audit --> Rebal[Rebalance (再平衡)]
  Rebal --> Build[TTS + Silence Removal]
  Build --> Fit[Stretch/Pad]
  Fit --> Concat[Concat WAVs]
  Concat --> Mux[Mux to MP4 + Subtitle]
  Mux --> QA[Audit + ffprobe]
```

## Quick Start（快速开始）
- Create venv and install deps:
  - `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- System deps:
  - `ffmpeg` and `rubberband` binaries recommended; will fallback to `atempo` if Rubber Band is unavailable.
- Workspace:
  - Place original media in `data/input/` (videos, audio) and subtitles (`.srt`).
  - Outputs (final MP4/SRT) will be written to `data/output/` or alongside input video by default.

## Command Examples（命令示例）

### Mode A: Elastic Audio (Default) - 弹性音频模式（默认）
Compress audio to fit video timing. Best for fixed-duration videos.
压缩音频以适配视频时长。适合时长固定的视频。

```bash
python -m flexdub merge \
  "/path/to/subtitle.srt" \
  "/path/to/video.mp4" \
  -o "/path/to/output.mp4" \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --mode elastic-audio \
  --clustered \
  --ar 48000 \
  --jobs 4
```

### Mode B: Elastic Video (Experimental) - 弹性视频模式（实验性）
Stretch video to fit natural-speed audio. Best for quality-focused content.
拉伸视频以适配自然语速音频。适合注重质量的内容。

```bash
python -m flexdub merge \
  "/path/to/subtitle.srt" \
  "/path/to/video.mp4" \
  -o "/path/to/output.mp4" \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --mode elastic-video \
  --voice-map voice_map.json \
  --ar 48000 \
  --jobs 2
```

**See [ELASTIC_MODES.md](ELASTIC_MODES.md) for detailed comparison.**
- Merge JSON segments (WhisperX/Gemini3):
```bash
python -m flexdub json_merge \
  "/path/to/segments.json" \
  "/path/to/video.mp4" \
  -o "/path/to/output.mp4" \
  --source whisperx \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --ar 48000 \
  --target-cpm 260 \
  --panic-cpm 350 \
  --max-shift 1000 \
  --jobs 4
```

## Folder Structure（文件夹结构）
- `data/input/` — raw videos and original subtitles (原始视频与字幕)
- `data/output/` — processed outputs (处理结果)
- `agents/srt_duration_agent/srt_resegment.py` — CPM rebalance algorithm（时轴再平衡）
- `agents/srt_dubbing_agent/srt_dub_merge.py` — elastic pipeline + CLI（弹性管线与命令行）
- `tests/` — unit and performance tests（测试）
- `agent_manual.md` — agent manual（代理手册）
- `roadmap.md` — project roadmap（项目路线图）

## Features（特性）
- CPM borrowing with panic mode（CPM 借还与恐慌模式）
- Silence removal + Rubber Band stretch, fallback ffmpeg `atempo`（去静音与保形变速）
- Edge TTS concurrency, macOS `say` sequential fallback（并发与回退）
- Progress feedback via `tqdm`（进度反馈）
- Language detection and auto voice mapping（语言检测与自动音色映射）

## Environment（开发环境配置要求）
- Python 3.10+ recommended.
- `ffmpeg` installed and in PATH.
- `rubberband` optional for best audio quality; otherwise `atempo` fallback.
- Python deps: `edge-tts` (optional), `pyrubberband` (optional), `srt`, `soundfile`, `numpy`, `tqdm`.
- macOS `say` is supported as a local TTS fallback.

## Contributing（贡献指南）
- Fork and create a feature branch: `git checkout -b feat/your-topic`.
- Run tests locally: `python -m pytest -q`.
- Follow SemVer for user-facing changes; update `CHANGELOG.md`.
- Write clear commit messages; open a PR with description and screenshots/logs.
- Ensure no large binaries are committed (`.gitignore` covers media in `data/`).

## References（参考）
- Agent Manual: `agents/agent_manual.md`
- Roadmap: `roadmap.md`

## Versioning（版本）
- Semantic Versioning (SemVer). Current: `v2.0.0`.
- See `CHANGELOG.md` for important changes.
- Validate project folder and generate validation.json:
```bash
python -m flexdub validate_project "data/input/<ProjectName>"
```
- Project end-to-end dubbing with auto language/voice:
```bash
python -m flexdub project_merge \
  "data/input/<ProjectName>" \
  --backend edge_tts \
  --auto-voice \
  --target-lang zh \
  --ar 48000 \
  --target-cpm 260 \
  --panic-cpm 350 \
  --max-shift 1000 \
  --jobs 1 \
  --embed-original-subtitle \
  --subtitle-lang zh
```