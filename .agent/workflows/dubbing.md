# 配音工作流 (Dubbing Workflow)

---
name: dubbing
description: 端到端视频配音工作流
version: 2.0.0
triggers:
  - "配音"
  - "dub"
  - "翻译视频"
---

## 概述

此工作流编排完整的视频配音流程，从项目准备到最终输出。

## 前置条件

- 项目目录包含 1 个 MP4 和 1 个 SRT 文件
- 已安装 ffmpeg
- TTS 后端可用：doubao（默认）或 edge-tts

## 工作流步骤（8 步）

```
┌─────────────────┐
│  1. 视频下载     │ → yt-dlp 下载视频和字幕
└────────┬────────┘
         ▼
┌─────────────────┐
│  2. 字幕预处理   │ → 检测滚动式字幕并清理
└────────┬────────┘
         ▼
┌─────────────────┐
│  3. 项目验证     │ → validate_project
└────────┬────────┘
         ▼
┌─────────────────┐
│  4. 语义重构     │ → LLM 阶段（翻译 + 断句）
└────────┬────────┘
         ▼
┌─────────────────┐
│  5. SRT 融合     │ → 结合 gs.md + 清理后 SRT
└────────┬────────┘
         ▼
┌─────────────────┐
│  6. QA 检查      │ → run_qa_check
└────────┬────────┘
         ▼
┌─────────────────┐
│  7. 配音合成     │ → Doubao TTS（默认）
└────────┬────────┘
         ▼
┌─────────────────┐
│  8. 质量审计     │ → 同步检查、CPM 审计
└─────────────────┘
```

---

## Step 1: 视频下载

**触发条件**: 用户提供 YouTube URL

**执行**:
```bash
yt-dlp -f "bestvideo[height<=720]+bestaudio/best[height<=720]" \
  --merge-output-format mp4 \
  --restrict-filenames \
  -o "data/input/%(title)s/%(title)s.%(ext)s" \
  --write-auto-subs \
  --sub-lang en \
  "<URL>"
```

**输出**: `<ProjectName>/*.mp4`, `<ProjectName>/*.vtt`

---

## Step 2: 字幕预处理

**触发条件**: 下载完成

**检测滚动式字幕特征**:
- 大量 <50ms 的超短条目
- 同一文本在多个 cue 中重复
- 条目数量远超实际句子数

**执行**:
```bash
# VTT → SRT
ffmpeg -i input.vtt input.srt

# 清理滚动式字幕
python scripts/clean_youtube_srt.py input.srt output.srt
```

**输出**: 清理后的 `*.srt`（时间准确）

---

## Step 3: 项目验证

**执行**:
```bash
python -m flexdub validate_project <project_dir>
```

**检查项目目录是否存在 `gs.md`**:
- 存在 → 进入 Step 5（SRT 融合）
- 不存在 → 进入 Step 4（语义重构）

---

## Step 4: 语义重构 (LLM 阶段)

**触发条件**: 无 gs.md 时执行

**激活技能**: `semantic_refine`

**任务**:
1. 翻译英文字幕为中文
2. 优化断句以适配 TTS
3. 添加说话人标签 `[Speaker:Name]`
4. 生成 `voice_map.json`

**执行**:
```bash
# 如果有 gs.md，使用 semantic_refine 命令（LLM 驱动）
flexdub semantic_refine <gs.md> <srt> \
  -o semantic_fixed.srt \
  --include-speaker-tags

# 如果无 gs.md，需要手动翻译或使用其他翻译工具
```

**输出**: `semantic_fixed.srt`, `voice_map.json`

---

## Step 5: SRT 融合（关键步骤）

**触发条件**: 项目目录存在 `gs.md`

**输入**:
- `gs.md`：内容准确（人工翻译/校对），时间戳粗略
- `*.srt`（清理后）：时间准确（来自 YouTube），内容可能有误

**方案 A: LLM 语义矫正（推荐）** - `flexdub semantic_refine`

```bash
# 使用 gs.md 作为背景上下文，LLM 矫正 SRT 翻译
flexdub semantic_refine <gs.md> <原始.srt> \
  -o <output.refined.audio.srt> \
  --include-speaker-tags \
  --checkpoint-dir ./checkpoints
```

**semantic_refine 功能**:
1. **上下文提取**：从 gs.md 提取术语表、说话人、关键概念
2. **分段处理**：大文件自动分成 20-50 条目的 chunks
3. **LLM 矫正**：逐段调用 LLM 进行翻译矫正
4. **本地化审查**：检查字符长度（75 字符限制）、直译问题
5. **检查点恢复**：支持中断后继续处理

**方案 B: 时间轴对齐（无需 LLM）** - `flexdub gs_align`

```bash
# 将 gs.md 与原始 SRT 时间轴对齐
flexdub gs_align <gs.md> <原始.srt> \
  -o <output.audio.srt> \
  --extract-glossary \
  --fuzzy-window-ms 3000
```

**gs_align 算法**:
1. **解析 gs.md**：提取 `### [MM:SS] Speaker` 格式的段落
2. **锚点匹配**：用 gs.md 的时间戳定位到 SRT 区间（±3秒模糊窗口）
3. **文本替换**：用 gs.md 的翻译文本替换 SRT 文本
4. **时间轴继承**：保留 SRT 的精确时间轴
5. **长段落拆分**：满足 75 字符 / 15 秒限制

**输出**:
- `<basename>.refined.audio.srt` 或 `<basename>.audio.srt`：TTS 用字幕
- `voice_map.json`：说话人音色映射
- `terminology.yaml` / `glossary.yaml`：术语表

**验证**:
```bash
flexdub qa <audio.srt> --voice-map voice_map.json
```

---

## Step 6: QA 检查（强制）

**执行**:
```bash
python -m flexdub qa <srt> --voice-map voice_map.json
```

**必须通过的检查**:
- SRT 格式有效
- 说话人覆盖率 100%
- 无超长段落（>75 字符）
- 无超时段落（>15 秒）
- voice_map.json 包含 DEFAULT

**决策点**:
- `ALL PASSED: True` → 继续
- `ALL PASSED: False` → 返回修复

---

## Step 7: 配音合成（关键步骤）

**Agent 必须行为**:

### 7.1 启动 Doubao TTS 服务
```bash
# Agent 主动启动，不要求用户手动操作
node /Users/yamlam/Downloads/doubao-tts-api/cli/tts-server.js

# 验证服务
curl http://localhost:3456/status
```

### 7.2 获取有效音色列表（必须）
```bash
# ⚠️ 禁止凭记忆编造音色名
curl -s http://localhost:3456/speakers | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('Female:', d['byCategory']['female'])
print('Male:', d['byCategory']['male'])
"
```

### 7.3 选择差异明显的音色

根据角色性别、性格从 API 返回的列表中选择：

| 场景 | 角色 A | 角色 B |
|------|--------|--------|
| 双女声 | 阳光甜妹 | 知性小棠 |
| 双男声 | 磁性俊宇 | 阳光阿辰 |
| 男女对话 | 磁性俊宇 | 温柔桃子 |

### 7.4 执行配音
```bash
python -m flexdub merge <srt> <video> \
  --backend doubao \
  --voice-map voice_map.json \
  --keep-brackets \
  -o <output>.dub.mp4
```

**错误处理**:
- `Frame detached` 错误 → 重启 Doubao 服务后重试
- TTS 失败 → 检查音色名是否有效

---

## Step 8: 质量审计

**执行**:
```bash
# CPM 审计
python -m flexdub audit <srt> --min-cpm 180 --max-cpm 300

# 同步审计
python -m flexdub sync_audit <video> <srt>
```

---

## 经验教训（本次转换总结）

### ✅ 正确做法

1. **先查询 API 再选音色**：`curl http://localhost:3456/speakers`
2. **Agent 主动启动服务**：不要求用户手动操作
3. **选择差异明显的音色**：避免听起来像同一个人
4. **检查 gs.md 是否存在**：优先使用人工校对的内容
5. **拆分长段落**：满足 75 字符 / 15 秒限制

### ❌ 错误做法

1. **凭记忆编造音色名**：如 `活泼女声_灿灿`（无效）
2. **要求用户手动启动服务**
3. **跳过 QA 检查**
4. **忽略项目目录中的 gs.md**

---

## 相关资源

- **Agent 手册**: `agent_manual.md`
- **技能包**: `.agent/skills/`
- **CLI 命令**: `python -m flexdub --help`
