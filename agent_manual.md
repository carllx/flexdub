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

---

## Agent 行为规范

### 禁止行为
- ❌ 直接修改 `data/output/` 中的文件
- ❌ 在 Script 阶段修改文本内容
- ❌ 跳过 QA 检查直接输出
- ❌ 猜测参数值
- ❌ **凭记忆编造 Doubao 音色名**（必须从 API 获取）

### 必须行为
- ✅ 使用 MCP 工具与 Python 逻辑交互
- ✅ 生成 SRT 后自动执行 QA 检查
- ✅ 遵循决策矩阵选择处理模式
- ✅ 保留专业术语英文原文
- ✅ 使用 Doubao TTS 时**主动启动服务**（不要求用户手动启动）
- ✅ **先调用 `/speakers` API 获取有效音色列表**，再选择音色
- ✅ 根据角色上下文（性别、性格）**自动选择差异明显的音色**
- ✅ 只使用 **API 返回的精确音色名**（不要修改或简化）

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
python -m flexdub validate_project <project_dir>

# 质量检查
python -m flexdub qa <srt> --voice-map voice_map.json

# CPM 审计
python -m flexdub audit <srt> --min-cpm 180 --max-cpm 300

# 同步审计
python -m flexdub sync_audit <video> <srt>
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

| 技能 | 触发词 | MCP 工具 | 用途 |
|------|--------|----------|------|
| `video_download` | 下载、YouTube、yt-dlp | - | 视频下载 |
| `semantic_refine` | 翻译、断句、说话人、术语 | - | 语义精炼 |
| `auto_dub` | 配音、dub、TTS | `analyze_project`, `run_qa_check` | 自动化配音 |
| `diagnosis` | 错误、失败、诊断 | `diagnose_error` | 故障诊断 |

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
5. SRT 融合 → 结合 gs.md + 清理后 SRT 生成 TTS 用 SRT
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

### Step 5: SRT 融合（详细）

当项目目录存在 `gs.md`（人工校对的逐字稿）时，采用融合策略：

**输入**：
- `gs.md`：内容准确（人工翻译/校对），时间戳粗略
- `*.srt`（清理后）：时间准确（来自 YouTube），内容可能有误

**融合逻辑**：
1. 从 `gs.md` 提取带时间戳的文本段落
2. 从清理后的 SRT 提取精确时间轴
3. 对齐两者，生成最终 `audio.srt`
4. 如有多说话人，同时生成 `voice_map.json`

**输出**：
- `<basename>.audio.srt`：TTS 用字幕（精确时间 + 准确内容）
- `voice_map.json`：说话人映射（如有多人）

详细步骤说明参见：`.agent/workflows/dubbing.md`

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
│   └── dubbing.md      # 配音工作流（6 步）
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
