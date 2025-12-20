---
name: semantic_refine
description: 语义精炼技能 - 修正翻译错误、优化断句、标注说话人、保留专业术语
triggers:
  - "翻译生硬"
  - "断句优化"
  - "说话人识别"
  - "术语保留"
version: 1.0.0
---

# 技能：语义精炼 (Semantic Refinement)

## 何时使用

当遇到以下情况时激活此技能：
- 原始 SRT 包含机器翻译错误
- 字幕断句不合理，影响 TTS 流畅度
- 需要识别和标注说话人
- 需要保留专业术语英文原文

## 输入

- 原始 SRT 文件
- 参考文档（可选，如 gs.md、transcript.md）
- 目标模式（Mode A 或 Mode B）

## 输出

- `semantic_fixed.srt` - 语义重构后的字幕
- `voice_map.json` - 说话人音色映射（多人场景）

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

### 1. 术语保留（硬编码）

以下术语必须保持英文：
- **3D 软件**: Maya, Blender, ZBrush, 3ds Max, Houdini, Cinema 4D
- **2D 软件**: Photoshop, Illustrator, After Effects
- **游戏引擎**: Unity, Unreal Engine, Godot
- **工具名称**: Quad Draw, Live Surface, UV Editor, Node Editor
- **技术术语**: Retopology, Quads, N-gons, PBR, HDRI
- **快捷键**: Ctrl + Z, Shift + A, Alt + Click

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

- `flexdub.core.subtitle.semantic_restructure()` - 本地语义重构算法
- `flexdub.core.subtitle.extract_speaker()` - 说话人提取
- `flexdub.core.qa.run_qa_checks()` - 质量检查
