# Product Overview

FlexDub is an elastic dubbing pipeline for video localization. It processes SRT subtitles and video files to generate dubbed content with synchronized audio and embedded subtitles.

## Core Capabilities

- Subtitle timeline rebalancing (CPM-based optimization with panic mode)
- TTS synthesis (Edge TTS, Doubao TTS)
- Elastic audio processing (silence removal, time stretching, padding)
- Automated audio-video muxing with soft subtitle embedding
- Quality assurance through sync auditing and CPM analysis

## Key Workflow

Input (SRT + Video) → Semantic Restructure → CPM Audit → Rebalance → TTS Synthesis → Audio Stretching/Padding → Concatenation → Mux with Video → QA

## Design Philosophy

- **LLM-first approach**: Semantic operations (text cleaning, sentence restructuring) happen before script execution
- **Text immutability**: Once in script stage, text content never changes (only timestamps)
- **Dual-track output**: Display SRT (for screen) and Audio SRT (for TTS) can be generated separately
- **Safety limits**: Single blocks ≤250 chars or ≤15s duration
