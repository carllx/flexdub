# flexdub Agent 操作手册 v3

**版本**: v3.0.0  
**架构**: Universal Agent Architecture  
**原则**: Thick Code, Thin Prompts

---

## 角色定位

flexdub Agent 是端到端配音管线的**中央协调器**。

**核心职责**：
- 语义重构 → 时间轴优化 → TTS 合成 → 音视频合流 → 质量审计

**关键边界**：
- **LLM 阶段**：文本内容理解（语义重构、说话人识别）
- **Script 阶段**：时间轴和媒体处理（rebalance、merge、audit）

---

## 核心原则

### 1. Thick Code, Thin Prompts
- **禁止**：在 Markdown 中写业务逻辑
- **必须**：所有逻辑封装为 Python 函数，Agent 仅调用工具

### 2. LLM-First
语义操作必须在脚本执行之前完成。

### 3. 文本不可变
进入 Script 阶段后，文本内容严格不可变，只能调整时间轴。

### 4. 强制 QA
生成任何 SRT 文件后，必须自动执行 `python -m flexdub qa` 检查。

### 5. 数据源优先级（SRT 为主体）
- **SRT 文件**：完整时间轴的唯一来源，生成的字幕必须覆盖 SRT 全部时间范围
- **gs.md 文件**：仅作为**参考**，用于校正翻译质量、识别说话人
- **❌ 禁止**：以 gs.md 的时间戳为基准生成字幕（gs.md 可能不完整）
- **✅ 必须**：以 SRT 的完整时间轴为基准，gs.md 仅辅助理解内容

---

## Agent 行为规范

### 禁止行为
- ❌ 直接修改 `data/output/` 中的文件
- ❌ 在 Script 阶段修改文本内容
- ❌ 跳过 QA 检查直接输出
- ❌ 猜测参数值
- ❌ **凭记忆编造 Doubao 音色名**（必须从 API 获取）
- ❌ **以 gs.md 为主体生成字幕**（gs.md 时间戳可能不完整）
- ❌ **丢弃 SRT 中的任何时间段**（输出必须覆盖 SRT 全部范围）

### 必须行为
- ✅ 使用 MCP 工具与 Python 逻辑交互
- ✅ 生成 SRT 后自动执行 QA 检查
- ✅ 遵循决策矩阵选择处理模式
- ✅ 专有名词首次出现使用 **English（中文翻译）** 格式，后续可用英文简称
- ✅ 使用 Doubao TTS 时**主动启动服务**（不要求用户手动启动）
- ✅ **先调用 `/speakers` API 获取有效音色列表**，再选择音色
- ✅ 根据角色上下文（性别、性格）**自动选择差异明显的音色**
- ✅ 只使用 **API 返回的精确音色名**（不要修改或简化）
- ✅ **以 SRT 为主体生成 TTS 字幕**（完整覆盖 SRT 时间范围）
- ✅ **gs.md 仅作参考**（用于说话人识别、翻译校正，不作为时间轴来源）

---

## 模式选择

| 条件 | 推荐模式 | 命令参数 |
|------|---------|---------|
| **默认（推荐）** | Mode B (弹性视频) | `--mode elastic-video --no-rebalance` |
| 时长固定（广告/短视频） | Mode A (弹性音频) | `--mode elastic-audio --clustered` |
| 多说话人 | 任意模式 + | `--voice-map voice_map.json --keep-brackets` |

### 模式说明

- **Mode B (elastic-video)**：保听感/保音质。TTS 自然语速输出，视频拉伸适配。适合教程、知识类内容。
- **Mode A (elastic-audio)**：保时间/保节奏。音频压缩适配原视频时长。适合有时长刚性约束或人脸出镜的场景。

**详细决策逻辑**: 参见 `flexdub/core/analyzer.py`

---

## 未来路线图：Mode C (Intelligent Hybrid)

> 此功能暂未实现，保留为未来讨论。

**设计理念**：感知驱动的混合对齐模式，作为智能调度层动态调用 Mode A/B。

**技术路径**：
- 基于 FFmpeg/OpenCV 的运动矢量分析
- 人脸/口型检测判定敏感片段
- 视频元数据 JSON 报表作为 Agent 决策输入

**决策逻辑**：
- CPM ≤ 250 且画面动态 → Mode A
- CPM > 300 且画面静态 → Mode B
- 检测到人脸且 CPM 极高 → Mode A 或提醒用户精简文本

---

## voice_map.json 格式（多说话人）

**Doubao TTS（默认）**：
```json
{
  "Host": "知性小棠",
  "Guest": "阳光甜妹",
  "DEFAULT": "知性小棠"
}
```

**Edge TTS（备用）**：
```json
{
  "Host": "zh-CN-YunjianNeural",
  "Guest": "zh-CN-XiaoxiaoNeural",
  "DEFAULT": "zh-CN-YunjianNeural"
}
```

- 键名对应 SRT 中的 `[Speaker:Name]` 标签
- **必须包含 `DEFAULT`** 用于未标注片段
- **⚠️ Doubao 音色必须从 API 获取**：`curl http://localhost:3456/speakers`
- **禁止凭记忆编造音色名**
- Agent 应根据上下文（角色性别、性格）自动选择差异明显的音色
- 详细说明参见：`.agent/skills/semantic_refine/SKILL.md`

---

## 快速命令参考

详细命令示例参见各技能文档：
- 单人/多人配音：`.agent/skills/auto_dub/SKILL.md`
- 语义重构：`.agent/skills/semantic_refine/SKILL.md`
- 视频下载：`.agent/skills/video_download/SKILL.md`

```bash
# 项目验证
flexdub validate_project <project_dir>

# 质量检查
flexdub qa <srt> --voice-map voice_map.json

# CPM 审计
flexdub audit <srt> --min-cpm 180 --max-cpm 300

# 同步审计
flexdub sync_audit <video> <srt>

# GS 语义矫正（LLM 驱动）
flexdub semantic_refine <gs.md> <srt> -o <output.refined.audio.srt> --include-speaker-tags

# GS 时间轴对齐（无需 LLM）
flexdub gs_align <gs.md> <srt> -o <output.audio.srt> --extract-glossary
```

---

## 默认参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--backend` | `doubao` | TTS 后端: `doubao`（默认）或 `edge_tts` |
| `--ar` | 48000 | 采样率 (Hz) |
| `--target-cpm` | 180 | 目标 CPM |
| `--panic-cpm` | 300 | 恐慌阈值 CPM |
| `--max-shift` | 1000 | 最大边界位移 (ms) |
| `--jobs` | 4 | 并发数 |
| `--max-chars` | 250 | 单块最大字符数 |
| `--max-duration` | 15000 | 单块最大时长 (ms) |

---

## TTS 后端

| 后端 | 说明 | 音色示例 |
|------|------|----------|
| `doubao` | 豆包 TTS（**默认推荐**） | `阳光甜妹`, `知性小棠`, `磁性俊宇` |
| `edge_tts` | Microsoft Edge TTS（备用） | `zh-CN-YunjianNeural`, `zh-CN-XiaoxiaoNeural` |

### Doubao TTS（默认）

**Agent 行为规范**：
1. Agent **必须主动启动** Doubao TTS 服务，不应要求用户手动启动
2. 启动命令：`node /Users/yamlam/Downloads/doubao-tts-api/cli/tts-server.js`
3. 验证服务：`curl http://localhost:3456/status`
4. **⚠️ 必须先查询有效音色列表**：`curl http://localhost:3456/speakers`
5. **禁止凭记忆编造音色名**，必须使用 API 返回的精确名称

**获取有效音色列表**：
```bash
# 必须在选择音色前执行此命令
curl -s http://localhost:3456/speakers | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('Female:', d['byCategory']['female'])
print('Male:', d['byCategory']['male'])
print('Special:', d['byCategory']['special'])
"
```

**音色选择流程**：
1. 启动 Doubao TTS 服务
2. 调用 `/speakers` API 获取当前有效音色列表
3. 根据角色性别、性格从列表中选择差异明显的音色
4. 使用 API 返回的**精确名称**（不要修改或简化）

**推荐音色组合**（差异明显）：

| 场景 | 角色 A | 角色 B | 说明 |
|------|--------|--------|------|
| 双女声 | 阳光甜妹 | 知性小棠 | 活泼 vs 成熟 |
| 双男声 | 磁性俊宇 | 阳光阿辰 | 成熟 vs 年轻 |
| 男女对话 | 磁性俊宇 | 温柔桃子 | 经典搭配 |
| 访谈节目 | 知性小棠 | 阳光甜妹 | 主持 vs 嘉宾 |

**已知限制**：
- 长文本（>75 字符）可能超时
- 服务超时默认 180 秒

### Edge TTS（备用）
- 开箱即用，无需额外配置
- 依赖：`pip install edge-tts==7.2.1`（⚠️ 7.2.3 有 bug）

---

## 技能包（渐进式披露）

Agent 采用**渐进式披露**架构加载技能：

1. **第一层**：启动时只加载 `.agent/skills/index.yaml`（元数据索引）
2. **第二层**：根据触发词按需加载具体 `SKILL.md`
3. **第三层**：执行时加载关联脚本和 MCP 工具

### 技能加载器

使用 `.agent/loader.py` 进行技能匹配和加载：

```python
from .agent.loader import SkillLoader

loader = SkillLoader()
loader.load_index()                    # 加载元数据索引
meta = loader.match_skill("下载视频")   # 匹配触发词
skill = loader.load_skill("video_download")  # 加载完整内容
```

### 技能索引

| 技能 | 触发词 | CLI 命令 | 用途 |
|------|--------|----------|------|
| `video_download` | 下载、YouTube、yt-dlp | - | 视频下载 |
| `semantic_refine` | 翻译、断句、说话人、术语、语义矫正 | `flexdub semantic_refine`, `flexdub gs_align` | 语义精炼 |
| `auto_dub` | 配音、dub、TTS | `flexdub merge` | 自动化配音 |
| `diagnosis` | 错误、失败、诊断 | `flexdub qa`, `flexdub audit` | 故障诊断 |

### 激活流程

```
用户输入 → 匹配触发词 → 加载 SKILL.md → 执行技能
```

**示例**：
- 用户说"下载这个视频" → 匹配"下载" → 加载 `video_download/SKILL.md`
- 用户说"TTS 失败了" → 匹配"失败" → 加载 `diagnosis/SKILL.md`

### 技能详情

查看具体技能文档：`.agent/skills/<skill_name>/SKILL.md`

---

## MCP 工具调用

Agent 通过 MCP 工具与 Python 逻辑交互：

```python
# 项目分析
result = call_tool("analyze_project", {"project_dir": "data/input/MyProject"})
# 返回: {"mode": "A", "cpm": 245, "duration_ms": 120000, ...}

# QA 检查
result = call_tool("run_qa_check", {
    "srt_path": "semantic_fixed.srt",
    "voice_map_path": "voice_map.json"
})

# 故障诊断
result = call_tool("diagnose_error", {"error_report": "path/to/error.json"})
```

---

## 工作流程

工作流定义在 `.agent/workflows/dubbing.md`，包含 8 个步骤：

```
1. 视频下载 → yt-dlp 下载视频和字幕
2. 字幕预处理 → 检测滚动式字幕并清理
3. 项目验证 → validate_project
4. 语义重构 → LLM 阶段（翻译 + 断句）
5. 生成 TTS 字幕 → semantic_refine（推荐）或 gs_align
6. QA 检查 → run_qa_check (MCP)
7. 配音合成 → Script 阶段
8. 质量审计 → audit / sync_audit
```

### Step 2: 字幕预处理（详细）

YouTube 自动字幕使用"滚动式"格式，需要检测并清理：

**检测滚动式字幕特征**：
- 大量 <50ms 的超短条目
- 同一文本在多个 cue 中重复
- 条目数量远超实际句子数

**清理命令**：
```bash
python scripts/clean_youtube_srt.py <input.srt> [output.srt]
```

### Step 5: 生成 TTS 字幕（详细）

生成符合 TTS 要求的 `audio.srt` 文件。

**⚠️ 核心原则：gs.md 提供翻译质量，SRT 提供精确时间轴**

#### 方案 A: LLM 语义矫正（推荐）- `flexdub semantic_refine`

当项目目录存在 `gs.md` 时，使用 LLM 驱动的语义矫正：

```bash
# 使用 gs.md 作为背景上下文，LLM 矫正 SRT 翻译
flexdub semantic_refine <gs.md> <原始.srt> \
  -o <output.refined.audio.srt> \
  --include-speaker-tags \
  --checkpoint-dir ./checkpoints
```

**semantic_refine 功能**：
1. **上下文提取**：从 gs.md 提取术语表、说话人、关键概念
2. **分段处理**：大文件自动分成 20-50 条目的 chunks
3. **LLM 矫正**：逐段调用 LLM 进行翻译矫正
4. **本地化审查**：检查字符长度（75 字符限制）、直译问题
5. **检查点恢复**：支持中断后继续处理

**环境变量配置**：
```bash
export FLEXDUB_LLM_API_KEY="your-api-key"
export FLEXDUB_LLM_BASE_URL="https://api.openai.com/v1/chat/completions"
export FLEXDUB_LLM_MODEL="gpt-4o-mini"
```

**输出**：
- `<basename>.refined.audio.srt`：语义矫正后的 TTS 字幕
- `<basename>.terminology.yaml`：术语表报告
- `<basename>.processing.log`：处理日志

#### 方案 B: 时间轴对齐（无需 LLM）- `flexdub gs_align`

如果只需要时间轴对齐，无需 LLM 矫正：

```bash
# 将 gs.md 的高质量翻译与 SRT 的精确时间轴对齐
flexdub gs_align <gs.md> <原始.srt> \
  -o <output.audio.srt> \
  --extract-glossary \
  --fuzzy-window-ms 3000
```

**gs_align 算法**：
1. **解析 gs.md**：提取 `### [MM:SS] Speaker` 格式的段落
2. **锚点匹配**：用 gs.md 的时间戳定位到 SRT 区间（±3秒模糊窗口）
3. **文本替换**：用 gs.md 的翻译文本替换 SRT 的机翻文本
4. **时间轴继承**：保留 SRT 的精确时间轴
5. **长段落拆分**：满足 75 字符 / 15 秒限制

**输出**：
- `<basename>.audio.srt`：TTS 用字幕（gs.md 翻译 + SRT 时间轴 + 说话人标签）
- `voice_map.json`：说话人音色映射
- `glossary.yaml`：自动提取的术语表（可选，使用 `--extract-glossary`）

#### 翻译质量对比

| 原始 SRT (机翻) | semantic_refine / gs_align 输出 |
|----------------|--------------------------------|
| "音乐] 好的，所以诺亚让我谈谈我" | "好的。Noah（诺亚）让我来谈谈..." |
| "呃，尝试将被称为修辞学的哲学领域操作化" | "修辞学"（Rhetoric）这一哲学领域进行"可操作化" |
| 碎片化断句，口语填充词 | 完整语义句子，术语规范 |

**验证**：
```bash
flexdub qa <audio.srt> --voice-map voice_map.json
```

**无 gs.md 时的备选方案**：
- 手动翻译或使用其他翻译工具
- 详见：`.agent/skills/semantic_refine/SKILL.md`

---

## 错误处理

- **TTS 失败**: 直接停止，返回错误码 1
- **QA 未通过**: 修复问题后重新检查
- **CPM 超标**: 使用 `--target-cpm 160 --max-shift 6000`

---

## 参考文档

### .agent 目录结构
```
.agent/
├── config.md           # 认知配置（核心原则、行为规范）
├── loader.py           # 技能加载器（渐进式披露实现）
├── workflows/          # 工作流定义
│   └── dubbing.md      # 配音工作流（8 步）
└── skills/             # 技能包
    ├── index.yaml      # 技能索引（第一层元数据）
    ├── video_download/ # 视频下载技能
    ├── semantic_refine/# 语义精炼技能
    ├── auto_dub/       # 自动配音技能
    └── diagnosis/      # 故障诊断技能
```

### 文档索引
- **技能索引**: `.agent/skills/index.yaml`
- **技能加载器**: `.agent/loader.py`
- **认知配置**: `.agent/config.md`
- **配音工作流**: `.agent/workflows/dubbing.md`
- **项目结构**: `.kiro/steering/structure.md`
- **技术栈**: `.kiro/steering/tech.md`
- **产品概述**: `.kiro/steering/product.md`
- **决策矩阵代码**: `flexdub/core/analyzer.py`
