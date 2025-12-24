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
- `aiohttp` - Async HTTP client (for Doubao TTS backend)
- `pyrubberband` - High-quality time stretching (optional, falls back to ffmpeg atempo)
- `pytest` - Testing framework

## External Tools

- **ffmpeg** (required) - Audio/video processing and muxing
- **rubberband** (optional) - Audio time stretching, fallback to ffmpeg atempo if unavailable
- **doubao-tts-api** (optional) - Doubao TTS 服务，使用 `--backend doubao` 时需要

### Doubao TTS 服务

使用豆包 TTS 后端前需启动外部服务：

```bash
# 启动服务（Agent 应主动执行）
node /Users/yamlam/Downloads/doubao-tts-api/cli/tts-server.js

# 验证服务
curl http://localhost:3456/status
```

**⚠️ 获取有效音色列表（必须）**：
```bash
# 禁止凭记忆编造音色名，必须从 API 获取
curl -s http://localhost:3456/speakers | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('Female:', d['byCategory']['female'])
print('Male:', d['byCategory']['male'])
"
```

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
# Merge SRT with video (Doubao TTS - 默认推荐)
flexdub merge <srt> <video> --backend doubao --voice 磁性俊宇

# Merge SRT with video (Edge TTS - 备用)
flexdub merge <srt> <video> --backend edge_tts --voice zh-CN-YunjianNeural

# gs.md 与 SRT 时间轴对齐（翻译质量优化）
flexdub gs_align <gs.md> <srt> -o <output.audio.srt> --extract-glossary

# GS 语义矫正 SRT 翻译（LLM 驱动）
flexdub semantic_refine <gs.md> <srt> -o <output.refined.audio.srt> --include-speaker-tags

# Rebalance subtitle timing
flexdub rebalance <srt> --target-cpm 180 --panic-cpm 300

# Audit CPM
flexdub audit <srt> --min-cpm 180 --max-cpm 220 --save cpm.csv

# Project-level processing
flexdub project_merge <project_dir> --backend doubao --auto-voice

# Sync audit
flexdub sync_audit <video> <srt> --ar 48000 --win-ms 20

# QA check
flexdub qa <srt> --voice-map voice_map.json --tts-char-threshold 75
```

## Default Parameters

- Sample rate: `48000` Hz
- Target CPM: `180` (Chinese), `160-200` recommended
- Panic CPM: `300`
- Max shift: `1000` ms
- Jobs: `4` (Edge TTS), `1` (strict mode with --no-fallback)
- TTS char threshold: `75` (Doubao TTS 对长文本敏感，超过可能超时)

## TTS 字符长度限制

Doubao TTS 对长文本敏感，超过 75 字符的段落可能导致超时失败。

### 预检查
```bash
# 使用 qa 命令检查 SRT 是否有超长段落
flexdub qa <srt> --backend doubao --tts-char-threshold 75
```

### 转换时跳过检查
```bash
# 如果确定要跳过字符长度检查
flexdub merge <srt> <video> --backend doubao --skip-length-check
```

### 建议
- 超过 75 字符的段落建议重新措辞缩短
- 保持语义不变的情况下精简表达
- 使用 `flexdub qa` 预检查后再转换

## LLM 集成（semantic_refine）

`semantic_refine` 命令使用 LLM 进行翻译矫正，需要配置 API：

### 环境变量配置
```bash
export FLEXDUB_LLM_API_KEY="your-api-key"
export FLEXDUB_LLM_BASE_URL="https://api.openai.com/v1/chat/completions"
export FLEXDUB_LLM_MODEL="gpt-4o-mini"
```

### 命令行参数
```bash
flexdub semantic_refine <gs.md> <srt> \
  --api-key <key> \
  --base-url <url> \
  --model <model> \
  --include-speaker-tags \
  --checkpoint-dir <dir>
```

### 功能特性
- **分段处理**：大文件自动分成 20-50 条目的 chunks
- **检查点恢复**：支持中断后继续处理
- **术语一致性**：从 gs.md 提取术语表，确保翻译一致
- **本地化审查**：检查字符长度、直译问题
- **说话人标签**：可选添加 `[Speaker: Name]` 标签
