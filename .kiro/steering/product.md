# Product Overview

FlexDub is an elastic dubbing pipeline for video localization. It processes SRT subtitles and video files to generate dubbed content with synchronized audio and embedded subtitles.

## Core Capabilities

- Subtitle timeline rebalancing (CPM-based optimization with panic mode)
- TTS synthesis (Edge TTS, Doubao TTS)
- Elastic audio processing (silence removal, time stretching, padding)
- Automated audio-video muxing with soft subtitle embedding
- Quality assurance through sync auditing and CPM analysis
- GS 语义矫正：使用 gs.md 作为背景上下文，通过 LLM 矫正 SRT 翻译

## Key Workflow

Input (SRT + Video) → Semantic Restructure → CPM Audit → Rebalance → TTS Synthesis → Audio Stretching/Padding → Concatenation → Mux with Video → QA

### GS 语义矫正工作流
gs.md + SRT → 上下文提取 → 分段处理 → LLM 矫正 → 本地化审查 → refined.audio.srt

## Design Philosophy

- **LLM-first approach**: Semantic operations (text cleaning, sentence restructuring) happen before script execution
- **Text immutability**: Once in script stage, text content never changes (only timestamps)
- **Dual-track output**: Display SRT (for screen) and Audio SRT (for TTS) can be generated separately
- **Safety limits**: Single blocks ≤250 chars or ≤15s duration
