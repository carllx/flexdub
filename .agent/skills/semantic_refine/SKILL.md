---
name: semantic_refine
description: 语义精炼技能 - 使用 LLM 修正翻译错误、优化断句、标注说话人、保留专业术语
triggers:
  - "翻译生硬"
  - "断句优化"
  - "说话人识别"
  - "术语保留"
  - "语义矫正"
version: 2.0.0
---

# 技能：语义精炼 (Semantic Refinement)

## 何时使用

当遇到以下情况时激活此技能：
- 原始 SRT 包含机器翻译错误
- 字幕断句不合理，影响 TTS 流畅度
- 需要识别和标注说话人
- 需要保留专业术语英文原文

## 推荐命令：`flexdub semantic_refine`

**当项目目录存在 `gs.md` 时，使用 `semantic_refine` 命令进行 LLM 驱动的语义矫正**：

```bash
# 使用 gs.md 作为背景上下文，LLM 矫正 SRT 翻译
flexdub semantic_refine <gs.md> <srt> \
  -o <output.refined.audio.srt> \
  --include-speaker-tags \
  --checkpoint-dir <dir>
```

**semantic_refine 功能**：
- 从 gs.md 提取术语表、说话人、关键概念
- LLM 驱动的翻译矫正（分段处理，支持断点续传）
- 本地化审查（75 字符限制、直译检测）
- 自动添加说话人标签 `[Speaker:Name]`
- 生成 terminology.yaml 和 processing.log

**环境变量配置**：
```bash
export FLEXDUB_LLM_API_KEY="your-api-key"
export FLEXDUB_LLM_BASE_URL="https://api.openai.com/v1/chat/completions"
export FLEXDUB_LLM_MODEL="gpt-4o-mini"
```

## 备选命令：`flexdub gs_align`

**如果只需要时间轴对齐（无需 LLM 矫正）**：

```bash
# 将 gs.md 的高质量翻译与 SRT 的精确时间轴对齐
flexdub gs_align <gs.md> <原始.srt> \
  -o <output.audio.srt> \
  --extract-glossary \
  --fuzzy-window-ms 3000
```

**gs_align 优势**：
- 自动继承 gs.md 的高质量翻译
- 保留 SRT 的精确时间轴
- 自动提取术语表 (glossary.yaml)
- 自动生成 voice_map.json
- 满足 75 字符 / 15 秒限制
- 无需 LLM API

## 输入

- 原始 SRT 文件
- gs.md 参考文档（推荐）
- 目标模式（Mode A 或 Mode B）

## 输出

- `*.refined.audio.srt` - 语义矫正后的字幕（semantic_refine 输出）
- `*.audio.srt` - 时间轴对齐后的字幕（gs_align 输出）
- `voice_map.json` - 说话人音色映射（多人场景）
- `terminology.yaml` - 术语表报告
- `processing.log` - 处理日志

## voice_map.json 格式

多说话人场景必须生成 `voice_map.json`。

**⚠️ 重要：必须先获取有效音色列表**

```bash
# 在选择音色前必须执行
curl -s http://localhost:3456/speakers | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('Female:', d['byCategory']['female'])
print('Male:', d['byCategory']['male'])
"
```

**Doubao TTS（默认推荐）**：
```json
{
  "Host": "知性小棠",
  "Guest": "阳光甜妹",
  "Narrator": "磁性俊宇",
  "DEFAULT": "知性小棠"
}
```

**Edge TTS（备用）**：
```json
{
  "Host": "zh-CN-YunjianNeural",
  "Guest": "zh-CN-XiaoxiaoNeural",
  "Narrator": "zh-CN-YunxiNeural",
  "DEFAULT": "zh-CN-YunjianNeural"
}
```

**规则**：
- 键名必须与 SRT 中的 `[Speaker:Name]` 标签匹配
- **必须包含 `DEFAULT` 键**，用于未标注说话人的片段
- **⚠️ 禁止凭记忆编造音色名**
- **必须使用 `/speakers` API 返回的精确名称**
- Agent 应根据角色上下文（性别、性格）自动选择差异明显的音色

**推荐音色组合**（差异明显）：
| 场景 | 角色 A | 角色 B |
|------|--------|--------|
| 双女声 | 阳光甜妹 | 知性小棠 |
| 双男声 | 磁性俊宇 | 阳光阿辰 |
| 男女对话 | 磁性俊宇 | 温柔桃子 |
| 访谈节目 | 知性小棠 | 阳光甜妹 |

## 执行规则

### 1. 专有名词处理规则

**首次出现**：使用 **English Original（中文翻译）** 格式
**后续提及**：可使用英文简称

**示例**：
- 首次：`Giorgia Lupi（乔治亚·卢皮）是一位数据可视化设计师`
- 后续：`Lupi 的作品展示了...`

**适用范围**：
- **人名**: Giorgia Lupi（乔治亚·卢皮）, Stefanie Posavec（斯蒂芬妮·波萨维克）
- **地名**: Brooklyn（布鲁克林）, London（伦敦）
- **3D 软件**: Maya, Blender, ZBrush, 3ds Max, Houdini, Cinema 4D
- **2D 软件**: Photoshop, Illustrator, After Effects
- **游戏引擎**: Unity, Unreal Engine, Godot
- **工具名称**: Quad Draw, Live Surface, UV Editor, Node Editor
- **技术术语**: Retopology, Quads, N-gons, PBR, HDRI
- **快捷键**: Ctrl + Z, Shift + A, Alt + Click

**注意**：软件名、工具名、快捷键通常无需中文翻译，直接保留英文即可。

### 2. 分片策略

| 模式 | 最大字符 | 最大时长 | 分片点 |
|------|---------|---------|--------|
| Mode A | 250 | 15 秒 | 段落/句群边界 |
| Mode B | 100 | 6 秒 | 每个句子 |

### 3. 说话人标注格式

```
[Speaker:Name] 文本内容
```

### 4. 质量门禁

完成后必须执行 QA 检查：
```bash
python -m flexdub qa semantic_fixed.srt --voice-map voice_map.json
```

ALL PASSED = True 才能继续下一步。

## 相关代码

- `flexdub.core.semantic_refine.SemanticRefiner` - LLM 驱动的语义矫正主类
- `flexdub.core.semantic_refine.ContextExtractor` - gs.md 上下文提取
- `flexdub.core.semantic_refine.LLMRefiner` - LLM 翻译矫正
- `flexdub.core.semantic_refine.LocalizationReviewer` - 本地化审查
- `flexdub.core.gs_align.align_gs_to_srt()` - gs.md 与 SRT 对齐算法
- `flexdub.core.gs_align.extract_glossary_from_gs()` - 术语表自动提取
- `flexdub.core.subtitle.semantic_restructure()` - 本地语义重构算法
- `flexdub.core.qa.run_qa_checks()` - 质量检查
