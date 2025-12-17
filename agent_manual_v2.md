# PyVideoTrans Agent 操作手册 v2.4

**文档版本：** v2.4.1  
**代码版本：** v2.0.0  
**最后更新：** 2025-12-09  
**反省机制：** 已启用

---

## 📋 目录

1. [核心理念](#1-核心理念)
2. [决策矩阵](#2-决策矩阵)
3. [标准工作流](#3-标准工作流)
4. [多说话人协议](#4-多说话人协议)
5. [场景配置模板](#5-场景配置模板)
6. [CLI 命令参考](#6-cli-命令参考)
7. [参数标准](#7-参数标准)
8. [故障排除](#8-故障排除)
9. [Agent 技能库](#9-agent-技能库)
10. [Agent 反省机制](#10-agent-反省机制)
11. [附录](#11-附录)

---

## 1. 核心理念

### 1.1 角色定位

PyVideoTrans Agent 是端到端配音管线的**中央协调器**，负责：

- **语义重构**：提升字幕的 TTS 流畅度和可读性
- **时间轴优化**：基于 CPM 的智能平衡
- **语音合成**：多后端 TTS 支持（Edge TTS / macOS Say）
- **音视频合流**：自动化处理与质量审计

**关键职责边界：**
- **LLM 阶段**：所有涉及文本内容理解的操作
- **Script 阶段**：所有涉及时间轴和媒体处理的操作

---

### 1.2 LLM-First 原则

**核心规则：语义操作必须在脚本执行之前完成。**

#### LLM 阶段（语义操作）
- 文本清洗、术语校对
- 断句合并、标点重建
- 说话人识别与标注
- 生成 Display SRT（屏幕显示）和 Audio SRT（TTS 朗读）

#### Script 阶段（媒体操作）
- 时间轴再平衡（rebalance）
- 音频合成与拉伸
- 视频合流与字幕嵌入
- 质量审计

**执行顺序：**
```
LLM 阶段 → Script 阶段
   ↓           ↓
语义完美    时间精准
```


---

### 1.3 文本不可变原则

**规则：进入 Script 阶段后，文本内容严格不可变，只能调整时间轴。**

#### 实现机制

代码中强制检查：
```python
# 进入 Script 阶段前捕获原始文本
orig_texts = [i.text for i in items]

# ... 处理时间轴 ...

# 处理后验证文本未变
after_texts = [i.text for i in items]
if after_texts != orig_texts:
    raise RuntimeError("text mutated in script stage")
```

#### 唯一例外

只有 `rewrite` 命令可以修改文本内容，因为它属于 LLM 阶段。

#### 违规示例

❌ **错误：** 在 `rebalance` 命令中使用 `--strip-meta`
```bash
# 这会导致错误，因为 strip-meta 会修改文本
python -m pyvideotrans rebalance video.srt --strip-meta
```

✅ **正确：** 先用 `rewrite` 清理，再 `rebalance`
```bash
# 1. LLM 阶段：清理文本
python -m pyvideotrans rewrite video.srt --strip-meta -o video.clean.srt

# 2. Script 阶段：优化时间轴
python -m pyvideotrans rebalance video.clean.srt
```

---

### 1.4 双轨字幕设计

**目标：** 分离"屏幕显示"和"TTS 朗读"的需求。

#### 两种字幕的区别

| 特性 | Display SRT | Audio SRT |
|------|-------------|-----------|
| **用途** | 屏幕显示 | TTS 合成 |
| **分段策略** | 保留原始分段，行长适中 | 按终止标点合并为完整句 |
| **时间轴** | 保持原始时间戳 | 重组为首行开始到末行结束 |
| **优先级** | 可读性 | 流畅性 |

#### 启用方式

```bash
# 方式 1：使用本地算法生成双轨
--auto-dual-srt

# 方式 2：使用 LLM 生成双轨（推荐，质量更高）
--auto-dual-srt --llm-dual-srt
```

#### 回退机制

```
IF --llm-dual-srt 启用 THEN
    尝试调用 LLM API
    IF API 不可用或失败 THEN
        自动回退到本地 semantic_restructure 算法
    END IF
END IF
```

**配置 LLM（可选）：**
```bash
export PYVIDEOTRANS_LLM_PROVIDER="openai"
export PYVIDEOTRANS_LLM_API_KEY="sk-..."
export PYVIDEOTRANS_LLM_BASE_URL="https://api.openai.com/v1"
export PYVIDEOTRANS_LLM_MODEL="gpt-4o-mini"
```


---

## 2. 决策矩阵

### 2.0 快速决策表

**Agent 快速定位执行路径：**

| 用户需求 | 模式 | 关键参数 | 分片策略 | 跳转章节 |
|---------|------|---------|---------|---------|
| 固定视频时长 | Mode A | `--clustered` | ≤250字符/≤15秒 | 5.1 |
| 自然语速优先 | Mode B | `--mode elastic-video --no-rebalance` | ≤100字符/≤6秒 | 5.5 |
| 多说话人 | 任意 | `--voice-map --keep-brackets` | 按模式选择 | 5.2 |
| 高密度字幕 | Mode A | `--target-cpm 160 --max-shift 6000` | ≤200字符/≤12秒 | 5.3 |
| 严格质量 | Mode A | `--no-fallback --jobs 1` | ≤250字符/≤15秒 | 5.4 |

**模式核心差异：**

| 特性 | Mode A (弹性音频) | Mode B (弹性视频) |
|------|------------------|------------------|
| 视频时长 | 保持不变 ✅ | 增加 10-30% ⚠️ |
| 音频质量 | 可能压缩 ⚠️ | 自然清晰 ✅ |
| 处理速度 | 快 ✅ | 慢 5-10 倍 ⚠️ |
| 最大字符 | 250 | 100 |
| 最大时长 | 15 秒 | 6 秒 |
| CPM 要求 | ≤300（严格） | 400+ 可接受 |
| rebalance | 推荐 | 不需要 |

---

### 2.1 任务分类表（LLM vs Script）

**核心原则：语义理解用 LLM，数学计算用 Script。**

| 任务类型 | 负责方 | 工具/方法 | 原因 |
|---------|--------|----------|------|
| **内容清洗** | LLM | IDE Agent / LLM API | 需要理解上下文语义，识别噪声 |
| **术语校对** | LLM | IDE Agent / LLM API | 需要识别专有名词（Blender, Maya） |
| **断句重构** | LLM | IDE Agent / LLM API | 需要识别语法结构（主谓宾） |
| **说话人识别** | LLM | IDE Agent / LLM API | 需要根据上下文推断对话关系 |
| **标点重建** | LLM | IDE Agent / LLM API | 需要理解句子完整性 |
| **时间轴对齐** | Script | `rebalance` 命令 | 数学计算问题（CPM 优化） |
| **⚠️ 多源内容对齐** | **LLM** | **IDE Agent 手动对齐** | **需要语义理解，禁止脚本自动化** |
| **音频拉伸** | Script | `merge` 命令 | 信号处理问题（Rubberband） |
| **音频合成** | Script | `merge` 命令 | I/O 和并发控制 |
| **视频合流** | Script | `merge` 命令 | FFmpeg 调用 |
| **CPM 审计** | Script | `audit` 命令 | 统计计算 |
| **同步审计** | Script | `sync_audit` 命令 | 波形分析 |

#### Agent 执行规则

```
IF 任务涉及文本内容理解 THEN
    使用 LLM 能力
    - IDE 中直接使用 Agent 对话
    - 或配置 LLM API 使用 --llm-dual-srt
ELSE IF 任务涉及时间/音频/视频计算 THEN
    调用 Python 脚本
    - rebalance: 时间轴优化
    - merge: 音频合成与合流
    - audit: 质量检查
END IF
```

#### ⚠️ 关键反模式警告（2025-12-08 新增）

**反模式 1：多源对齐使用脚本自动化**

❌ **错误做法**：
```python
# 尝试用脚本自动对齐 gs.md 和 SRT
def align_md_with_srt(md_file, srt_file):
    # 这是错误的！MD 时间不准确，无法程序化对齐
    ...
```

✅ **正确做法**：
- 多源对齐（如 gs.md + SRT）是**语义理解任务**
- 必须由 Agent/LLM 手动理解内容后对齐
- gs.md 提供**准确内容**，SRT 提供**准确时间**
- Agent 需要理解语义才能正确匹配

**反模式 2：生成 SRT 后不执行 QA**

❌ **错误做法**：
```
Agent 生成 SRT → 直接告诉用户完成
```

✅ **正确做法**：
```
Agent 生成 SRT → 自动执行 QA 检查 → 修复问题 → 告诉用户完成
```

**规则：生成任何 SRT 文件后，Agent 必须自动执行 `python -m pyvideotrans qa` 命令，无需等待用户请求。**

#### ⚠️ Agent 语义重构强制行为

**当用户要求处理 SRT 文件时，Agent 必须：**

```
1. 【禁止】直接复制原始 SRT 内容
2. 【禁止】仅做表面格式调整
3. 【禁止】跳过说话人识别步骤
4. 【禁止】保留明显的机器翻译错误

5. 【必须】逐段理解原文语义
6. 【必须】识别并修正翻译错误
7. 【必须】识别所有说话人并添加标签
8. 【必须】合并碎片句为完整语义单元
9. 【必须】保留专业术语英文原文
10.【必须】生成 voice_map.json（多人场景）
```

**判断标准：如果输出的 SRT 与原始 SRT 相似度 > 80%，说明 Agent 没有正确执行语义重构。**

---

### 2.2 说话人场景识别

#### 判断标准

| 场景类型 | 特征 | 示例 |
|---------|------|------|
| **单人场景** | 整个视频只有一个说话人 | 教程、演讲、旁白 |
| **多人场景** | 存在对话、访谈、多角色 | 访谈、对话、多角色配音 |

#### Agent 识别流程

```
STEP 1: 分析原始 SRT 内容
  检查是否存在以下特征：
  - 对话标记：如 "A: ...", "B: ..."
  - 说话人标签：如 "[Speaker:Name]"
  - 破折号前缀：如 "- 你好", "— 是的"
  - 上下文对话：如问答结构

STEP 2: 确定处理模式
  IF 检测到多说话人特征 THEN
      模式 = "多人模式"
      → 要求 LLM 标注说话人：[Speaker:Name]
      → 生成 voice_map.json
      → 使用 --voice-map 和 --keep-brackets
  ELSE
      模式 = "单人模式"
      → 使用单一 --voice 参数
  END IF
```

#### 示例判断

**单人场景：**
```srt
1
00:00:01,000 --> 00:00:03,000
大家好，欢迎来到今天的教程。

2
00:00:03,500 --> 00:00:05,000
首先我们打开 Blender 软件。
```

**多人场景：**
```srt
1
00:00:01,000 --> 00:00:03,000
你好，今天天气真好。

2
00:00:03,500 --> 00:00:05,000
是啊，我们去公园吧。
```
→ 需要 LLM 标注为：
```srt
1
00:00:01,000 --> 00:00:03,000
[Speaker:Alice] 你好，今天天气真好。

2
00:00:03,500 --> 00:00:05,000
[Speaker:Bob] 是啊，我们去公园吧。
```


---

### 2.3 参数选择决策树

```
开始处理
    ↓
是否需要修改文本内容？
    ├─ 是 → 使用 rewrite 命令（LLM 阶段）
    │       ├─ 需要清理元标记？→ --strip-meta
    │       ├─ 需要清理噪声？→ --strip-noise
    │       └─ 输出 semantic_fixed.srt
    │
    └─ 否 → 进入 Script 阶段
            ↓
        是否多说话人？
            ├─ 是 → 准备 voice_map.json
            │       使用 --voice-map --keep-brackets
            │
            └─ 否 → 使用单一 --voice
                    ↓
                是否需要再平衡？
                    ├─ 是 → 使用 rebalance 命令
                    │       ├─ 高密度字幕？→ --target-cpm 160 --max-shift 6000
                    │       └─ 常规字幕？→ 使用默认参数
                    │
                    └─ 否 → 使用 --no-rebalance 或 --clustered
                            ↓
                        选择 TTS 后端
                            ├─ Edge TTS → --backend edge_tts
                            │   ├─ 严格模式？→ --no-fallback --jobs 1
                            │   └─ 常规模式？→ --jobs 4
                            │
                            └─ macOS Say → --backend macos_say
                                           （自动 jobs=1）
                                ↓
                            执行 merge 命令
                                ↓
                            质量审计（sync_audit, audit）
```

---

## 3. 标准工作流

**所有场景通用的串行流程。**

### 3.0 Phase 0: 视频准备

#### 视频下载（推荐质量）

使用 yt-dlp 下载 YouTube 视频时，推荐使用 **720p** 或 **1080p** 质量：

```bash
# 推荐：720p（适中质量，文件较小，字体清晰）
# 注意：使用 %(title)s 作为文件夹名，--restrict-filenames 确保文件名安全
yt-dlp -f "bestvideo[height<=720]+bestaudio/best[height<=720]" \
  --merge-output-format mp4 \
  --restrict-filenames \
  -o "data/input/%(title)s/%(title)s.%(ext)s" \
  --write-subs --sub-lang en \
  --write-auto-subs \
  --write-thumbnail \
  "https://www.youtube.com/watch?v=VIDEO_ID"

# 高质量：1080p（字体更清晰，文件较大）
yt-dlp -f "bestvideo[height<=1080]+bestaudio/best[height<=1080]" \
  --merge-output-format mp4 \
  --restrict-filenames \
  -o "data/input/%(title)s/%(title)s.%(ext)s" \
  --write-subs --sub-lang en \
  --write-auto-subs \
  --write-thumbnail \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

**⚠️ 文件夹命名规则（重要）**：
- 使用视频标题 `%(title)s` 作为文件夹名，便于识别内容
- **必须使用 `--restrict-filenames`**：自动将特殊字符替换为安全字符
  - 空格 → `_`（下划线）
  - 冒号 `:`、问号 `?`、引号 `"`、斜杠 `/` 等 → `_` 或移除
  - 非 ASCII 字符（如中文全角符号 `：`、`–`）→ 移除或替换
- 不使用视频 ID `%(id)s`，因为 ID 无法直观反映视频内容

**⚠️ 为什么必须使用 `--restrict-filenames`**：
- 视频标题常包含特殊字符（如 `No Vibes Allowed： Solving Hard Problems`）
- 这些字符会导致 shell 脚本转义错误、路径解析失败
- 使用该参数后，文件名变为 `No_Vibes_Allowed_Solving_Hard_Problems`，安全可靠

#### 质量选择指南

| 质量 | 分辨率 | 文件大小 | 适用场景 |
|------|--------|----------|----------|
| **720p** | 1280×720 | ~50-150MB/10min | ✅ 推荐：教程视频，字体清晰 |
| **1080p** | 1920×1080 | ~100-300MB/10min | 高质量需求，屏幕演示 |
| **480p** | 854×480 | ~30-80MB/10min | ⚠️ 不推荐：字体可能模糊 |
| **360p** | 640×360 | ~20-50MB/10min | ❌ 避免：字体难以辨认 |

**重要提示：**
- 教程视频中的命令行、代码、菜单文字需要清晰可读
- 720p 是质量与文件大小的最佳平衡点
- 避免使用 360p/480p，会导致屏幕内容模糊

#### 下载字幕

```bash
# 下载自动生成的字幕
yt-dlp --write-auto-subs --sub-lang en --skip-download \
  --restrict-filenames \
  -o "data/input/%(title)s/%(title)s" \
  "https://www.youtube.com/watch?v=VIDEO_ID"

# 下载手动字幕（如果有）
yt-dlp --write-subs --sub-lang en --skip-download \
  --restrict-filenames \
  -o "data/input/%(title)s/%(title)s" \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

#### 项目目录结构

```
data/input/<VideoTitle>/
├── <VideoTitle>.mp4      # 视频文件（720p 或 1080p）
├── <VideoTitle>.srt      # 原始字幕（时间参考文件）
├── gs.md                 # 内容参考文件（可选，内容准确但时间不精确）
├── tts_mode_b.srt        # Mode B TTS 字幕（融合生成）
├── semantic_fixed.srt    # Mode A 语义重构字幕（合并优先）
└── voice_map.json        # 说话人映射（多人场景）
```

**文件角色说明：**

| 文件 | 角色 | 特点 |
|------|------|------|
| `*.srt` (原始) | **时间参考文件** | 时间戳精确，但内容可能有机器翻译错误 |
| `gs.md` | **内容参考文件** | 内容准确完整，但时间标记粗略或缺失 |
| `tts_mode_b.srt` | **Mode B 输出** | 融合两者，超细粒度分片，用于弹性视频 |
| `semantic_fixed.srt` | **Mode A 输出** | 融合两者，合并为语义单元，用于弹性音频 |

---

### 3.1 Phase 1: 语义重构（LLM 阶段）

#### 负责方
- **IDE Agent**（推荐）：直接在 Kiro IDE 中对话
- **LLM API**：配置环境变量使用 `--llm-dual-srt`

#### 任务清单

1. **读取原始 SRT**
2. **内容清洗**
   - 去除噪声符号（`*`, `` ` ``, 零宽字符）
   - 去除幻觉文本（如重复的"谢谢观看"）
   - 规范化空格
3. **术语保留**
   - 软件名称：Blender, Maya, Photoshop 等保持英文
   - 快捷键：`Ctrl + .`, `Shift + A` 等保持原样
   - 专业术语：UV Editor, Node Editor 等保持英文
4. **断句重构**（按模式区分 - 重要！）
   
   **⚠️ 核心原则：Mode A 和 Mode B 采用不同的分片策略**
   
   | 参数 | Mode A (弹性音频) | Mode B (弹性视频) |
   |------|------------------|------------------|
   | **平均时长** | 8-12 秒 | 3-4 秒 |
   | **最大时长** | 15 秒 | 6 秒 |
   | **最大字符** | 250 字符 | 100 字符 |
   | **分片点** | 段落/句群 | 每个句子 |
   | **片段数量** | 可大幅减少 | 原始 80%-120% |
   | **CPM 要求** | 严格（≤300） | 宽松（400+ 可接受） |
   
   ---
   
   **Mode A 分片策略（合并优先）**：
   - 合并为完整语义单元（多个句子可合并）
   - 单片段 ≤250 字符，≤15 秒
   - 在段落或句群边界分片
   - 推荐执行 rebalance 优化 CPM
   
   ---
   
   **Mode B 分片策略（超细粒度）**：
   
   - **严格保持原始时间边界**：
     - 原始 SRT 的每个时间段都是一个潜在的分片点
     - 只在语义完整的情况下才合并相邻片段
     - 合并后的片段时长不超过 6 秒
   
   - **按句号强制分片**：
     - 每个完整句子（以。？！结尾）必须独立成片
     - 即使原始 SRT 中两个句子在同一时间段，也要分开
     - 分片时使用原始时间段的中点作为分界
   
   - **按逗号/分号分片**：
     - 当片段超过 80 字符时，在逗号、分号处分片
     - 当片段超过 4 秒时，在逗号、分号处分片
     - 分片时按字符比例分配时间
   
   - **按停顿分片**：
     - 原始 SRT 中 > 300ms 的间隙处必须保持分片
     - 这些间隙通常对应说话人的自然停顿
   
   - **片段数量目标**：
     - 输出片段数量应为原始 SRT 的 80%-120%
     - 片段数量过少（< 50%）说明合并过度，需要重新分片
   
   **⚠️ Mode B 关键警告**：
   - Mode B 依赖精确的时间轴来拉伸视频
   - 过度合并会导致视频拉伸比例异常（ratio > 2.0 或 < 0.5）
   - 片段越细，时间对齐越精确，音画同步越好
5. **说话人标注**（多人场景）
   - 识别对话关系
   - 添加 `[Speaker:Name]` 标签
6. **生成双轨 SRT**（可选）
   - Display SRT：保留原始分段
   - Audio SRT：合并为完整句

#### 输出产物
- `semantic_fixed.srt` 或 `rewritten.srt`
- `voice_map.json`（多人场景）

#### 质量检查
```bash
# 验证 SRT 结构
python -c "import srt; srt.parse(open('semantic_fixed.srt').read())"

# 检查术语保留（随机抽样 ≥20 段）
grep -E "Blender|Maya|UV Editor" semantic_fixed.srt

# 检查单块限制
python -m pyvideotrans audit semantic_fixed.srt --max-chars 250
```

---

### 3.1.1 语义重构执行规范（强制）

**⚠️ 重要：Agent 必须严格按照以下流程执行语义重构，不得跳过任何步骤。**

#### 执行前置条件

```
在开始语义重构之前，Agent 必须：
1. 完整读取原始 SRT 文件
2. 完整读取参考文档（如 gs.md、transcript.md 等，如果存在）
3. 理解视频主题和专业领域
4. 识别说话人数量和对话模式
```

#### 强制执行的思考过程

**Agent 必须在内部完成以下思考步骤（不可跳过）：**

```
STEP 1: 内容理解（必须）
├─ 问题：这个视频讲的是什么主题？
├─ 问题：涉及哪些专业领域？（3D建模、编程、设计等）
├─ 问题：有哪些专业术语需要保留英文？
└─ 输出：主题摘要 + 术语列表

STEP 2: 说话人分析（必须）
├─ 问题：有几个说话人？
├─ 问题：如何区分不同说话人？（语气、称呼、问答模式）
├─ 问题：每个说话人的角色是什么？（主讲、助手、嘉宾）
└─ 输出：说话人列表 + 识别特征

STEP 3: 质量问题识别（必须）
├─ 问题：原始 SRT 有哪些翻译错误？
├─ 问题：有哪些机器转录的噪声？
├─ 问题：有哪些断句不合理的地方？
└─ 输出：问题清单 + 修复方案

STEP 4: 逐段重构（必须）
├─ 对每个片段：比对原文和参考文档
├─ 对每个片段：修正翻译错误
├─ 对每个片段：添加说话人标签
├─ 对每个片段：优化断句和标点
└─ 输出：重构后的 SRT 内容
```

#### 输入输出对比示例（必读）

**示例 1：机器翻译错误修正**

❌ **原始 SRT（错误）：**
```srt
1
00:00:01,510 --> 00:00:05,870
[Music] hey guys heading in Morton from flip
[音乐] 嗨，大家，从flip前往Morton

2
00:00:05,870 --> 00:00:09,410
normals here in this tutorial we're gonna check out how to read apologize
在这里的教程中，我们将学习如何阅读道歉
```

✅ **重构后 SRT（正确）：**
```srt
1
00:00:01,510 --> 00:00:09,410
[Speaker:Henning] 嗨，大家好，我是 Flip Normals 的 Henning Morton。在这个教程中，我们将学习如何在 Maya 中进行重拓扑。
```

**修正说明：**
- "heading in Morton from flip normals" → "我是 Flip Normals 的 Henning Morton"（人名和频道名）
- "read apologize" → "重拓扑"（retopology 的误识别）
- 添加说话人标签

**⚠️ Mode B 超细粒度分片（强制）：**
Mode B 必须严格按原始时间边界分片，每个句子独立：
```srt
1
00:00:01,510 --> 00:00:05,870
[Speaker:Henning] 嗨，大家好，我是 Flip Normals 的 Henning Morton。

2
00:00:05,870 --> 00:00:09,410
[Speaker:Henning] 在这个教程中，我们将学习如何在 Maya 中进行重拓扑。
```
**关键**：保持原始 SRT 的时间边界（1,510-5,870 和 5,870-9,410），不要合并！

---

**示例 2：专业术语保留 + 超细粒度分片**

❌ **原始 SRT（错误）：**
```srt
3
00:00:10,040 --> 00:00:14,629
something in Maya this is not going to be in terms of the deep principles of
在Maya中，这不会涉及到深层次的原则。

4
00:00:14,809 --> 00:00:19,369
topology is purely gonna be what tools to use how do you get started with route
拓扑学纯粹是关于使用什么工具，以及如何开始进行路由设置。
```

❌ **错误的重构（过度合并）：**
```srt
2
00:00:10,040 --> 00:00:19,369
[Speaker:Henning] 这不会涉及拓扑的深层原理，而是纯粹讲解使用什么工具，如何开始重拓扑，以及一些通用的良好实践。
```
**问题**：合并了 9 秒的内容，Mode B 会导致视频拉伸异常！

✅ **正确的重构（保持原始时间边界）：**
```srt
3
00:00:10,040 --> 00:00:14,629
[Speaker:Henning] 这不会涉及拓扑的深层原理。

4
00:00:14,809 --> 00:00:19,369
[Speaker:Henning] 而是纯粹讲解使用什么工具，如何开始重拓扑。
```

**修正说明：**
- "route" → "重拓扑"（retopology 的误识别）
- 保留 "Maya" 英文
- **严格保持原始时间边界**：10,040-14,629 和 14,809-19,369

---

**示例 3：多说话人识别**

❌ **原始 SRT（无说话人标签）：**
```srt
24
00:01:21,240 --> 00:01:25,899
can no longer select it there's nothing you can do to it anymore except when you
无法再选择它，除了当您

25
00:01:25,899 --> 00:01:32,610
I think was next before yeah I think so and it just got so much better
我想是 NEX 之前吧？我想是的，而且它变得好多了。
```

✅ **重构后 SRT（有说话人标签）：**
```srt
11
00:01:21,240 --> 00:01:25,899
[Speaker:Henning] 这是一个非常方便的工具，Maya 中已经有好几个版本了。当他们获得建模工具包时，Maya 建模速度提升了大约十倍。

12
00:01:25,899 --> 00:01:32,610
[Speaker:Assistant] 我想是 NEX 之前吧？我想是的，而且它变得好多了。
```

**识别依据：**
- 第一句是陈述性讲解 → 主讲人 Henning
- 第二句是回应性评论（"我想是..."） → 助手 Assistant
- 语气从讲解变为对话 → 说话人切换

---

#### 常见错误模式（必须避免）

| 错误类型 | 错误示例 | 正确做法 |
|---------|---------|---------|
| **直接复制原文** | 不修改机器翻译错误 | 必须理解语义后重写 |
| **术语翻译** | "Quad Draw" → "四边形绘制" | 保留英文 "Quad Draw" |
| **忽略说话人** | 不添加 [Speaker:Name] 标签 | 必须识别并标注所有说话人 |
| **碎片化保留** | 保持原始的短句分段 | 合并为完整的语义单元 |
| **时间轴错误** | 修改原始时间戳 | 合并时使用首段开始+末段结束 |
| **过度合并** | 单块超过 250 字符或 15 秒 | 在逗号/分号处切分 |

---

#### 质量验收标准（按模式区分）

**Agent 生成的 semantic_fixed.srt 必须满足以下条件：**

| 指标 | Mode A | Mode B | 验证方法 |
|------|--------|--------|----------|
| **SRT 格式** | 100% 有效 | 100% 有效 | `srt.parse()` 无异常 |
| **说话人覆盖率** | 100% | 100% | 每行都有 `[Speaker:Name]` |
| **术语保留率** | 100% | 100% | 抽样检查 |
| **单块字符数** | ≤250 字符 | ≤100 字符 | `audit --max-chars` |
| **单块时长** | ≤15 秒 | ≤6 秒 | 计算 end_ms - start_ms |
| **片段数量比** | 不限制 | 原始 80%-120% | 对比原始片段数 |
| **CPM 要求** | ≤300（严格） | 400+ 可接受 | `audit` 命令 |
| **翻译准确率** | ≥95% | ≥95% | 人工抽样 20 段 |
| **时间轴连续性** | 无重叠 | 无重叠 | 检查相邻片段时间 |

---

#### Agent 自检清单（按模式区分）

```markdown
## 语义重构自检清单

### 1. 内容质量（通用）
- [ ] 我是否完整阅读了原始 SRT？
- [ ] 我是否理解了视频的主题和专业领域？
- [ ] 我是否识别并修正了所有机器翻译错误？
- [ ] 我是否保留了所有专业术语的英文？

### 2. 说话人标注（通用）
- [ ] 我是否识别了所有说话人？
- [ ] 我是否为每个片段添加了 [Speaker:Name] 标签？
- [ ] 我是否创建了 voice_map.json？
- [ ] voice_map.json 是否包含 DEFAULT？

### 3a. 断句优化（Mode A）
- [ ] 是否合并为完整语义单元？
- [ ] 所有片段是否都 ≤250 字符？
- [ ] 所有片段是否都 ≤15 秒？
- [ ] CPM 是否 ≤300？

### 3b. 断句优化（Mode B）
- [ ] 是否严格保持原始 SRT 的时间边界？
- [ ] 每个完整句子是否独立成片？
- [ ] 超过 80 字符的片段是否在逗号/分号处分片？
- [ ] 所有片段是否都 ≤100 字符？
- [ ] 所有片段是否都 ≤6 秒？
- [ ] 片段数量是否为原始 SRT 的 80%-120%？

### 4. 格式验证（通用）
- [ ] SRT 格式是否有效？
- [ ] 时间轴是否连续无重叠？
- [ ] 编码是否为 UTF-8？
```

---

### 3.1.2 强制 QA 环节（质量门禁）

**⚠️ 重要：语义重构完成后，Agent 必须执行以下 QA 检查，任何检查项未通过都必须修正后才能继续。**

#### QA 命令

```bash
# 执行 QA 检查
python -m pyvideotrans qa semantic_fixed.srt --voice-map voice_map.json

# 输出示例
[QA] SRT Valid: True
[QA] Speaker Coverage: 100.0%
[QA] Timeline Complete: True
[QA] First Start: 1510ms, Last End: 842310ms
[QA] Voice Map Valid: True
[QA] Voice Map Has DEFAULT: True
[QA] ALL PASSED: True
```

#### 6 大类检查清单

| 检查类别 | 检查项 | 通过标准 |
|---------|--------|---------|
| **1. 内容完整性** | SRT 格式有效 | 能被正确解析 |
| **2. 说话人标注** | 说话人覆盖率 | = 100% |
| **3. 时间轴完整性** | 覆盖整个视频 | 首尾时间正确 |
| **4. 字符限制** | 单片段字符数 | ≤ 250 字符 |
| **5. 时长限制** | 单片段时长 | ≤ 15 秒 |
| **6. voice_map 验证** | 格式有效且包含 DEFAULT | 必须通过 |

#### 质量门禁标准

```
ALL PASSED = True  →  可以进入 Phase 2
ALL PASSED = False →  必须修正问题后重新检查
```

#### ⚠️ Agent 强制行为（2025-12-08 新增）

**规则：Agent 在生成任何 SRT 文件后，必须自动执行 QA 检查，不得等待用户请求。**

```
Agent 工作流程：
1. 生成 SRT 文件（如 BMAD_Method.audio.srt）
2. 【自动】执行 QA 检查：python -m pyvideotrans qa <srt_file>
3. 【自动】检查结果，如有问题则修复
4. 【自动】重新执行 QA 直到 ALL PASSED = True
5. 向用户报告完成状态

禁止行为：
- ❌ 生成 SRT 后直接告诉用户"完成"
- ❌ 等待用户要求才执行 QA
- ❌ QA 失败后不修复就继续下一步
```

**原因**：QA 检查是质量门禁，跳过会导致后续 TTS 合成失败或质量问题。

#### 强制复测流程

如果 QA 检查未通过：

1. **识别问题**：查看 QA 输出中的具体失败项
2. **修正问题**：
   - 说话人覆盖率不足 → 补充缺失的 `[Speaker:Name]` 标签
   - 字符超限 → 拆分过长的片段
   - 时长超限 → 调整时间轴或拆分片段
   - voice_map 无效 → 修正 JSON 格式或添加 DEFAULT
3. **重新检查**：再次运行 `python -m pyvideotrans qa`
4. **循环直到通过**：ALL PASSED = True

#### QA 报告输出

```bash
# 输出 QA 报告到文件
python -m pyvideotrans qa semantic_fixed.srt --voice-map voice_map.json -o qa_report.json
```

---

#### 参考文档使用规范

**当存在多个输入源时（如 SRT + Markdown 笔记）：**

```
优先级规则：
1. 时间轴：以 SRT 文件为准（时间准确）
2. 文本内容：以参考文档为准（内容准确）
3. 说话人：根据上下文语义推断

合并策略：
1. 读取 SRT 获取时间轴骨架
2. 读取参考文档获取正确内容
3. 按时间顺序对齐两者
4. 用参考文档内容替换 SRT 中的错误翻译
5. 添加说话人标签
6. 优化断句
```

**示例：**

| 来源 | 时间 | 内容 |
|------|------|------|
| SRT | 00:00:01,510 --> 00:00:05,870 | "从flip前往Morton"（错误） |
| 参考文档 | - | "我是 Flip Normals 的 Henning Morton" |
| 输出 | 00:00:01,510 --> 00:00:05,870 | "[Speaker:Henning] 我是 Flip Normals 的 Henning Morton" |

---

#### 处理长文档的策略

**判断标准：**
- 视频时长 > 15 分钟
- 原始 SRT > 1000 行
- 预估输出 > 500 个片段

**推荐方法：**

**方式 1：分段处理（推荐）**
```bash
# 1. 将原始 SRT 按时间分段（每段 10 分钟）
# 手动或使用工具切分

# 2. 分别处理每段（使用 IDE Agent）
# 第 1 批：0-10 分钟
# 第 2 批：10-20 分钟
# 第 3 批：20-30 分钟

# 3. 使用 fsAppend 逐步添加到输出文件
```

**方式 2：增量处理**
```bash
# 在 IDE 中分批处理，每次处理 50-100 个片段
# 使用 fsAppend 逐步添加，避免单次写入过多内容
```

**注意事项：**
- 每次 fsAppend 不超过 50 行
- 保持说话人标签的一致性
- 确保时间轴连续性

---

#### 处理多源输入

**场景 1：SRT + Markdown 逐字稿**

**输入：**
- `original.srt`：时间准确，内容可能不准确（机器转录）
- `transcript.md`：内容准确，包含说话人标识

**处理策略：**
1. 使用 SRT 的时间轴作为基准
2. 使用 Markdown 的文本内容
3. 按时间戳对齐两者
4. 合并碎片句，优化 TTS 流畅度

**场景 2：双语字幕对齐**

**输入：**
- `source.srt`：源语言字幕（时间准确）
- `target.txt`：目标语言翻译（纯文本）

**处理策略：**
1. 按句子边界切分翻译文本
2. 按顺序映射到 SRT 时间轴
3. 调整合并策略以匹配翻译长度

---

#### 术语保留规则

**软件名称（保持英文）：**
- 3D 软件：Maya, Blender, ZBrush, 3ds Max, Houdini, Cinema 4D
- 2D 软件：Photoshop, Illustrator, After Effects
- 游戏引擎：Unity, Unreal Engine, Godot

**工具名称（保持英文）：**
- Maya 工具：Quad Draw, Live Surface, Modeling Toolkit
- ZBrush 工具：ZRemesher, DynaMesh, ZModeler
- 通用工具：UV Editor, Node Editor, Outliner

**技术术语（保持英文或混合）：**
- 拓扑术语：Retopology, Quads, N-gons, Poles, Edge Flow
- 动画术语：Rigging, Skinning, Blend Shapes
- 渲染术语：Subsurface Scattering, PBR, HDRI

**快捷键（保持原样）：**
- `Ctrl + Z`, `Shift + A`, `Alt + Click`
- `Tab` 键, `3` 键（平滑预览）

**识别规则：**
1. 全大写缩写：保持原样（UV, PBR, HDRI, TTS）
2. 驼峰命名：保持原样（ZRemesher, EdgeFlow）
3. 带连字符：保持原样（3ds Max, After Effects）

**处理示例：**

❌ **错误：** `打开 玛雅 软件，使用 四边形绘制 工具`

✅ **正确：** `打开 Maya 软件，使用 Quad Draw 工具`

---

#### 时间轴合并算法

**规则：合并时使用第一个片段的开始时间和最后一个片段的结束时间。**

**示例：**

**原始 SRT（碎片化）：**
```srt
1
00:00:01,000 --> 00:00:02,000
大家好

2
00:00:02,500 --> 00:00:04,000
我是 Henning

3
00:00:04,500 --> 00:00:06,000
欢迎来到今天的教程
```

**合并后（完整句）：**
```srt
1
00:00:01,000 --> 00:00:06,000
[Speaker:Henning] 大家好，我是 Henning，欢迎来到今天的教程。
```

**计算公式：**
```python
merged_item = SRTItem(
    start_ms = fragments[0].start_ms,      # 第一个片段的开始
    end_ms = fragments[-1].end_ms,         # 最后一个片段的结束
    text = " ".join(f.text for f in fragments)  # 合并文本
)
```

**注意事项：**
1. 不要修改原始时间戳的精度
2. 确保合并后的时长合理（不超过 15 秒）
3. 如果合并后超过 250 字符，需要在逗号/分号处切分

---

#### 自动化质量验证

**验证脚本：**
```bash
# 1. 验证 SRT 结构
python -c "
import srt
with open('semantic_fixed.srt', 'r', encoding='utf-8') as f:
    items = list(srt.parse(f.read()))
    print(f'✅ SRT 结构有效，共 {len(items)} 个片段')
"

# 2. 验证说话人标签
python -c "
import re
with open('semantic_fixed.srt', 'r', encoding='utf-8') as f:
    content = f.read()
    speakers = re.findall(r'\[Speaker:(\w+)\]', content)
    unique_speakers = set(speakers)
    print(f'✅ 检测到 {len(unique_speakers)} 个说话人: {unique_speakers}')
    print(f'✅ 总共 {len(speakers)} 个标签')
"

# 3. 验证单块长度
python -c "
import srt
with open('semantic_fixed.srt', 'r', encoding='utf-8') as f:
    items = list(srt.parse(f.read()))
    long_items = [i for i in items if len(i.content) > 250]
    long_duration = [i for i in items if (i.end - i.start).total_seconds() > 15]
    
    if long_items:
        print(f'⚠️  {len(long_items)} 个片段超过 250 字符')
    else:
        print('✅ 所有片段 ≤250 字符')
    
    if long_duration:
        print(f'⚠️  {len(long_duration)} 个片段超过 15 秒')
    else:
        print('✅ 所有片段 ≤15 秒')
"

# 4. 验证 voice_map.json
python -c "
import json
with open('voice_map.json', 'r', encoding='utf-8') as f:
    voice_map = json.load(f)
    
    if 'DEFAULT' not in voice_map:
        print('❌ 缺少 DEFAULT 音色')
    else:
        print('✅ voice_map.json 包含 DEFAULT')
    
    print(f'✅ 配置了 {len(voice_map)} 个音色映射')
"
```


---

### 3.2 Phase 2: 时间轴优化（Script 阶段）

#### 负责方
Python 脚本（`rebalance` 命令）

#### 任务
基于 CPM（每分钟字符数）优化字幕时间轴，确保朗读速度合理。

#### 何时跳过
- 启用 `--clustered` 模式（自动跳过）
- 启用 `--auto-dual-srt` 模式（自动跳过）
- 手动指定 `--no-rebalance`

#### 命令示例

**常规场景：**
```bash
python -m pyvideotrans rebalance semantic_fixed.srt \
  --target-cpm 180 \
  --panic-cpm 300 \
  --max-shift 1000 \
  -o semantic_fixed.rebalance.srt
```

**高密度字幕（CPM ≥ 900）：**
```bash
python -m pyvideotrans rebalance semantic_fixed.srt \
  --target-cpm 160 \
  --panic-cpm 300 \
  --max-shift 6000 \
  -o semantic_fixed.rebalance.srt
```

#### 约束
- **严格不可变文本内容**
- 只调整 `start_ms` 和 `end_ms`
- 代码会自动验证文本未变

#### 输出产物
- `*.rebalance.srt`

---

### 3.3 Phase 3: 音频合成与视频处理（Script 阶段）

#### 负责方
Python 脚本（`merge` 命令）

#### 两种处理模式

**Mode A: Elastic Audio（弹性音频）- 默认**
- 固定视频时长
- 音频被压缩/拉伸以适配字幕时间窗口
- 处理速度快
- 适合时长固定的场景

**Mode B: Elastic Video（弹性视频）**
- 固定音频语速（自然朗读）
- 视频被拉伸/压缩以适配音频时长
- 处理速度慢（需要视频重新编码）
- 适合音质优先的场景
- **新功能**：
  - 间隙检测与处理（> 100ms 的间隙保持原始时长）
  - 空白片段跳过（生成静音音频）
  - 同步诊断报告（`--debug-sync`）
  - 自动生成新时间轴字幕（`*.mode_b.srt`）
  - 异常拉伸比例警告（ratio < 0.3 或 > 3.0）

#### Mode 选择决策

```
用户提问：
"你想要固定视频时长还是自然语速？"

IF 用户选择"自然语速" THEN
    使用 Mode B (--mode elastic-video)
    ├─ 优点：语速自然，音质清晰
    ├─ 缺点：视频时长增加 10-30%
    └─ 处理时间：5-10 倍慢
ELSE
    使用 Mode A (--mode elastic-audio)
    ├─ 优点：时长固定，处理快
    ├─ 缺点：音频可能被压缩
    └─ 处理时间：快速
END IF
```

#### 任务（Mode A）
1. TTS 合成（Edge TTS / macOS Say）
2. 静音移除（CPM ≤ 260 且时长 ≥ 1200ms）
3. 音频拉伸/填充（匹配时间轴）
4. 音频拼接
5. 视频合流
6. 字幕嵌入（可选）

#### 任务（Mode B）
1. TTS 合成（自然语速，无时间约束，支持缓存）
2. 间隙检测（识别 > 100ms 的字幕间隙）
3. 逐片段提取视频
4. 计算视频拉伸比例（ratio = TTS时长 / 原始时长）
5. 视频片段拉伸/压缩（间隙片段保持原始时长）
6. 生成间隙静音音频
7. 重建时间线（累计 TTS 时长 + 间隙时长）
8. 视频片段拼接
9. 音视频合流
10. 生成新时间轴字幕（`*.mode_b.srt`）
11. 字幕嵌入（可选）
12. 时长验证（Expected = Actual）

#### 命令示例

**Mode A - 单人场景：**
```bash
python -m pyvideotrans merge semantic_fixed.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --ar 48000 \
  --clustered \
  --mode elastic-audio \
  -o video.dub.mp4
```

**Mode A - 多人场景：**
```bash
python -m pyvideotrans merge semantic_fixed.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --voice-map voice_map.json \
  --keep-brackets \
  --clustered \
  --mode elastic-audio \
  -o video.dub.mp4
```

**Mode B - 单人场景（自然语速）：**
```bash
python -m pyvideotrans merge semantic_fixed.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --ar 48000 \
  --mode elastic-video \
  -o video.dub.mp4
```

**Mode B - 多人场景（自然语速）：**
```bash
python -m pyvideotrans merge semantic_fixed.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --voice-map voice_map.json \
  --mode elastic-video \
  --no-rebalance \
  -o video.dub.mp4
```

#### 关键参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--backend` | TTS 后端（edge_tts / macos_say） | 必填 |
| `--voice` | 音色 ID | 必填 |
| `--ar` | 采样率（Hz） | 48000 |
| `--jobs` | 并发数 | 4（Edge TTS），1（macOS Say） |
| `--mode` | 处理模式（elastic-audio / elastic-video） | elastic-audio |
| `--clustered` | 聚类合成（保留微锚点，Mode A 专用） | False |
| `--no-fallback` | 禁用后端回退（强制 jobs=1） | False |
| `--keep-brackets` | 保留括号（多人场景必需） | False |
| `--voice-map` | 说话人音色映射文件 | None |

#### Mode A 输出产物
- `*.dub.mp4`（最终视频，时长不变）
- `*.audio.wav`（合成音频，临时文件）

#### Mode B 输出产物
- `*.dub.mp4`（最终视频，时长可能增加）
- `*.mode_b.srt`（新时间轴字幕，自动生成）
- `*.sync_diag.log`（同步诊断日志，需 `--debug-sync`）
- 中间产物：
  - 逐片段提取的视频
  - 逐片段拉伸的视频
  - 合成的音频片段
  - TTS 缓存（`tts_cache/` 目录）

#### Mode B 诊断命令

```bash
# 启用同步诊断
python -m pyvideotrans merge semantic_fixed.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --mode elastic-video \
  --debug-sync \
  -o video.dub.mp4

# 诊断日志示例 (*.sync_diag.log)
[MODE_B_SYNC_DIAGNOSTICS]
total_original_ms=841746
total_new_ms=933696
overall_ratio=1.1092

[SEGMENTS]
idx=0 type=NORMAL orig=4360ms tts=9456ms ratio=2.169 new_start=0ms new_end=9456ms
idx=1 type=NORMAL orig=4170ms tts=7608ms ratio=1.824 new_start=9456ms new_end=17064ms
...
idx=85 type=GAP orig=120000ms tts=120000ms ratio=1.000 (间隙保持原始时长)

[WARNINGS]
Segment 91: abnormal stretch ratio 0.309  # 拉伸比例异常警告
```

#### Mode B 时长验证

处理完成后自动验证：
```
[MODE_B] Duration verification:
[MODE_B]   Expected (TTS + gaps): 933696ms
[MODE_B]   Actual audio: 933696ms
[MODE_B]   Difference: 0ms  ✅
```

如果差异 > 100ms，会输出警告。

#### Mode 对比表

| 特性 | Mode A | Mode B |
|------|--------|--------|
| **视频时长** | 保持不变 ✅ | 增加 10-30% ⚠️ |
| **音频质量** | 可能压缩 ⚠️ | 自然清晰 ✅ |
| **语速** | 可能过快 ⚠️ | 正常自然 ✅ |
| **处理速度** | 快 ✅ | 慢（5-10 倍） ⚠️ |
| **视频画面** | 完全保持 ✅ | 轻微拉伸 ⚠️ |
| **间隙处理** | 静音填充 | 保持原始视频 ✅ |
| **字幕输出** | 原始时间轴 | 新时间轴 (`*.mode_b.srt`) ✅ |
| **诊断功能** | `--debug-sync` | `--debug-sync` + 详细日志 ✅ |
| **适用场景** | 时长固定 | 质量优先 |


---

### 3.3.1 Mode B 分段处理与自动合并

#### 适用场景
- 视频时长 > 15 分钟
- 需要自然语速（Mode B）
- 需要自动合并所有分段

#### 完整流程

**Step 1: 分段处理**

```bash
# 处理第 1 段
python -m pyvideotrans merge \
  "data/input/ProjectName/chunks/part01.srt" \
  "data/input/ProjectName/video.mp4" \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --voice-map voice_map.json \
  --mode elastic-video \
  --ar 48000 \
  --jobs 2 \
  -o "data/output/ProjectName/mode_b_part01.mp4"

# 处理第 2 段
python -m pyvideotrans merge \
  "data/input/ProjectName/chunks/part02.srt" \
  "data/input/ProjectName/video.mp4" \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --voice-map voice_map.json \
  --mode elastic-video \
  --ar 48000 \
  --jobs 2 \
  -o "data/output/ProjectName/mode_b_part02.mp4"

# ... 继续处理其他段 ...
```

**Step 2: 自动合并所有分段**

```bash
# 使用 ffmpeg concat demuxer 合并
cat > concat_list.txt <<EOF
file 'mode_b_part01.mp4'
file 'mode_b_part02.mp4'
file 'mode_b_part03.mp4'
file 'mode_b_part04.mp4'
file 'mode_b_part05.mp4'
file 'mode_b_part06.mp4'
EOF

ffmpeg -f concat -safe 0 -i concat_list.txt \
  -c copy -y "final_output.mp4"
```

**Step 3: 验证合并结果**

```bash
# 检查总时长
ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 "final_output.mp4"

# 检查音视频同步
python -m pyvideotrans sync_audit "final_output.mp4" \
  "data/input/ProjectName/semantic_fixed.srt"
```

#### Agent 自动合并脚本

Agent 应该能够自动执行以下流程：

```python
# 伪代码
def merge_mode_b_segments(project_dir, output_file):
    """
    自动合并 Mode B 处理的所有分段
    """
    # 1. 查找所有 mode_b_part*.mp4 文件
    segments = sorted(glob.glob(f"{project_dir}/mode_b_part*.mp4"))
    
    if not segments:
        raise FileNotFoundError("未找到 mode_b_part*.mp4 文件")
    
    # 2. 创建 concat 列表
    concat_file = tempfile.mktemp(suffix=".txt")
    with open(concat_file, "w") as f:
        for seg in segments:
            f.write(f"file '{seg}'\n")
    
    # 3. 执行 ffmpeg concat
    cmd = [
        "ffmpeg", "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c", "copy", "-y", output_file
    ]
    subprocess.run(cmd, check=True)
    
    # 4. 清理临时文件
    os.unlink(concat_file)
    
    # 5. 验证输出
    duration = get_video_duration(output_file)
    print(f"✅ 合并完成: {output_file} ({duration:.2f}s)")
```

#### Agent 提示词

当用户要求合并 Mode B 分段时，Agent 应该：

1. **确认分段文件**
   ```
   我检测到以下 Mode B 分段文件：
   - mode_b_part01.mp4 (7:42)
   - mode_b_part02.mp4 (6:45)
   - mode_b_part03.mp4 (6:09)
   - mode_b_part04.mp4 (5:49)
   - mode_b_part05.mp4 (5:30)
   - mode_b_part06.mp4 (0:43)
   
   总时长：32:38
   ```

2. **执行合并**
   ```
   正在合并所有分段...
   ✅ 合并完成: final_output.mp4 (32:38)
   ```

3. **验证结果**
   ```
   正在验证音视频同步...
   ✅ 同步检查通过
   ```

---

### 3.4 Phase 4: 质量审计（Script 阶段）

#### 负责方
Python 脚本（`audit`, `sync_audit` 命令）

#### 任务 1: CPM 审计

检查字幕 CPM 是否在合理范围内。

```bash
python -m pyvideotrans audit semantic_fixed.srt \
  --min-cpm 180 \
  --max-cpm 220 \
  --save cpm_report.csv
```

**输出：**
- 控制台输出超出范围的片段
- `cpm_report.csv`（可选）

**阈值：**
- 推荐范围：180-300 CPM（中文，Mode A）
- 警告阈值：CPM ≥ 900（需要特殊处理）

---

#### 任务 2: 同步审计

检查音频波形起点与字幕时间戳的同步性。

```bash
python -m pyvideotrans sync_audit video.dub.mp4 semantic_fixed.srt \
  --ar 48000 \
  --win-ms 20 \
  -o sync_report/
```

**输出：**
- `*.sync_audit.csv`（同步偏差报告）
- `*.sync_debug.log`（调试日志）

**阈值：**
- 可接受范围：`|delta_ms| ≤ 180ms`
- 需要修复：`|delta_ms| > 180ms`

**常见问题：**
1. 使用了错误的字幕文件（应使用 rebalance.srt）
2. 静音移除过度（高密度片段应跳过）
3. 时间拉伸倍率错误

---

## 4. 多说话人协议

### 4.1 单人 vs 多人判断标准

#### 自动识别特征

| 特征类型 | 单人场景 | 多人场景 |
|---------|---------|---------|
| **对话标记** | 无 | 有（A:, B:, - , —） |
| **说话人标签** | 无 | 有（[Speaker:Name]） |
| **上下文结构** | 连续叙述 | 问答/对话结构 |
| **语气变化** | 一致 | 交替变化 |

#### Agent 判断流程

```python
# 伪代码
def detect_multi_speaker(srt_items):
    indicators = 0
    
    # 检查对话标记
    for item in srt_items:
        if item.text.startswith(("- ", "— ", "A:", "B:")):
            indicators += 1
        if "[Speaker:" in item.text:
            indicators += 1
    
    # 检查问答结构
    questions = sum(1 for item in srt_items if "?" in item.text or "？" in item.text)
    if questions > len(srt_items) * 0.2:  # 超过 20% 是问句
        indicators += 1
    
    return indicators >= 2  # 至少 2 个指标
```


---

### 4.2 说话人标记规范

#### 语法标准（LLM 输出）

**格式：** `[Speaker:Name] 内容` 或 `【Speaker:Name】 内容`

**示例：**
```srt
1
00:00:01,000 --> 00:00:05,000
[Speaker:John] 大家好，我们开始今天的教程。

2
00:00:05,500 --> 00:00:08,000
[Speaker:Alice] 没错，首先打开 Blender。

3
00:00:08,500 --> 00:00:10,000
[Speaker:John] 注意这里的 UV Editor 设置。
```

#### 标记规则

1. **位置：** 必须在文本开头
2. **格式：** 使用方括号 `[]` 或 `【】`
3. **分隔符：** 使用英文冒号 `:` 或中文冒号 `：`
4. **命名：** Name 使用英文或拼音，避免特殊字符
5. **一致性：** 同一说话人在整个 SRT 中使用相同 Name

#### 代码解析逻辑

```python
# pyvideotrans/core/subtitle.py
def extract_speaker(text: str) -> Tuple[Optional[str], str]:
    """
    提取说话人标签和清理后的文本
    
    输入: "[Speaker:John] Hello world"
    输出: ("John", "Hello world")
    """
    s = text.strip()
    
    # 支持 [Speaker:Name] 和 【Speaker:Name】
    if s.startswith("[") or s.startswith("【"):
        # 查找结束括号
        end = s.find("]") if s.startswith("[") else s.find("】")
        if end > 0:
            tag = s[1:end]
            # 支持 : 和 ：
            delim_pos = tag.find(":") if ":" in tag else tag.find("：")
            if delim_pos > 0:
                name = tag[delim_pos+1:].strip()
                rest = s[end+1:].lstrip()
                return (name or None), rest
    
    return None, text
```

---

### 4.3 voice_map.json 配置

#### 文件格式

```json
{
  "John": "zh-CN-YunjianNeural",
  "Alice": "zh-CN-XiaoxiaoNeural",
  "Bob": "zh-CN-YunxiNeural",
  "DEFAULT": "zh-CN-YunjianNeural"
}
```

#### 配置规则

1. **必须包含 DEFAULT**：用于未映射的说话人或无标签片段
2. **Name 必须匹配**：与 SRT 中的 `[Speaker:Name]` 完全一致
3. **Voice ID 有效**：使用 Edge TTS 支持的音色 ID

#### 使用方式

```bash
python -m pyvideotrans merge semantic_fixed.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --voice-map voice_map.json \
  --keep-brackets \
  --clustered
```

#### 回退逻辑

```
FOR 每个聚类 cluster:
    提取首个片段的说话人标签 speaker_name
    
    IF speaker_name 存在 AND speaker_name 在 voice_map 中:
        使用 voice_map[speaker_name]
    ELSE IF speaker_name 不存在或未映射:
        使用 voice_map["DEFAULT"]
        记录日志：[SPEAKER_MAP] speaker=XXX not_mapped use DEFAULT
    END IF
END FOR
```

---

### 4.4 多人工作流示例

#### 完整流程

**Step 1: LLM 阶段 - 识别并标注说话人**

在 IDE 中使用 Agent：
```
请分析以下 SRT 字幕，识别说话人并添加 [Speaker:Name] 标签：

[粘贴原始 SRT 内容]

要求：
1. 识别对话中的不同说话人
2. 为每个说话人分配一个简短的英文名称（如 John, Alice）
3. 在每个片段开头添加 [Speaker:Name] 标签
4. 保持原有时间轴不变
5. 输出完整的 SRT 格式
```

**Step 2: 创建 voice_map.json**

```bash
cat > voice_map.json <<EOF
{
  "John": "zh-CN-YunjianNeural",
  "Alice": "zh-CN-XiaoxiaoNeural",
  "DEFAULT": "zh-CN-YunjianNeural"
}
EOF
```

**Step 3: 验证标签**

```bash
# 检查说话人标签
grep -E "\[Speaker:" semantic_fixed.srt

# 统计说话人数量
grep -oE "\[Speaker:[^\]]+\]" semantic_fixed.srt | sort | uniq -c
```

**Step 4: 执行合成**

```bash
python -m pyvideotrans merge semantic_fixed.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --voice-map voice_map.json \
  --keep-brackets \
  --clustered \
  --ar 48000 \
  -o video.dub.mp4
```

**Step 5: 质量检查**

```bash
# 检查日志中的音色映射
grep "SPEAKER_MAP" process.log

# 同步审计
python -m pyvideotrans sync_audit video.dub.mp4 semantic_fixed.srt
```


---

## 5. 场景配置模板

### 5.1 常规中文配音（单人，Mode A）

**适用场景：** 教程、演讲、旁白（视频时长固定）

**完整流程：**

```bash
# 1. LLM 阶段：语义重构（在 IDE 中使用 Agent）
# 分片策略：≤250 字符，≤15 秒
# 输出：semantic_fixed.srt

# 2. 项目校验
python -m pyvideotrans validate_project "data/input/ProjectName"

# 3. CPM 审计（Mode A 要求 ≤300）
python -m pyvideotrans audit semantic_fixed.srt \
  --min-cpm 180 --max-cpm 300 \
  --save cpm_report.csv

# 4. 端到端处理（使用 --clustered 自动跳过 rebalance）
python -m pyvideotrans project_merge "data/input/ProjectName" \
  --backend edge_tts \
  --auto-voice \
  --target-lang zh \
  --ar 48000 \
  --jobs 4 \
  --clustered \
  --embed-subtitle original \
  --subtitle-lang zh

# 5. 同步审计
python -m pyvideotrans sync_audit \
  "data/output/ProjectName/ProjectName.dub.mp4" \
  "data/input/ProjectName/semantic_fixed.srt" \
  --ar 48000
```

**注意**：`--clustered` 模式自动跳过 rebalance，直接使用原始时间轴。

**预期输出：**
- `data/output/ProjectName/ProjectName.dub.mp4`
- `data/output/ProjectName/process.log`
- `data/output/ProjectName/cpm.csv`
- `data/output/ProjectName/report.json`

---

### 5.2 多人对话配音

**适用场景：** 访谈、对话、多角色配音

**完整流程：**

```bash
# 1. LLM 阶段：识别说话人并标注
# 在 IDE 中使用 Agent 分析 SRT，添加 [Speaker:Name] 标签
# 输出：semantic_fixed.srt

# 2. 创建 voice_map.json
cat > voice_map.json <<EOF
{
  "Host": "zh-CN-YunjianNeural",
  "Guest": "zh-CN-XiaoxiaoNeural",
  "DEFAULT": "zh-CN-YunjianNeural"
}
EOF

# 3. 验证标签
grep -E "\[Speaker:" semantic_fixed.srt | head -5

# 4. 执行合成
python -m pyvideotrans merge semantic_fixed.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --voice-map voice_map.json \
  --keep-brackets \
  --clustered \
  --ar 48000 \
  --jobs 4 \
  -o video.dub.mp4

# 5. 检查音色映射
grep "SPEAKER_MAP" process.log

# 6. 同步审计
python -m pyvideotrans sync_audit video.dub.mp4 semantic_fixed.srt
```

**关键参数：**
- `--voice-map voice_map.json`：指定音色映射
- `--keep-brackets`：保留 `[Speaker:Name]` 标签以便解析
- `--clustered`：聚类合成，保持说话人边界

---

### 5.3 高密度字幕处理

**适用场景：** CPM ≥ 900 或时长 < 800ms 且字符 ≥ 30

**完整流程：**

```bash
# 1. LLM 阶段：降低单块上限
# 在 IDE 中使用 Agent，要求：
# - 单块最多 200 字符
# - 单块最多 12 秒
# - 在逗号/分号处切分长句
# 输出：semantic_fixed.srt

# 或使用 rewrite 命令
python -m pyvideotrans rewrite video.srt \
  --max-chars 200 \
  --max-duration 12000 \
  --strip-meta \
  -o semantic_fixed.srt

# 2. 再平衡：扩大窗口
python -m pyvideotrans rebalance semantic_fixed.srt \
  --target-cpm 160 \
  --panic-cpm 300 \
  --max-shift 6000 \
  -o semantic_fixed.rebalance.srt

# 3. 合成
python -m pyvideotrans merge semantic_fixed.rebalance.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --ar 48000 \
  --jobs 4 \
  -o video.dub.mp4

# 4. 同步审计
python -m pyvideotrans sync_audit video.dub.mp4 semantic_fixed.rebalance.srt
```

**关键参数调整：**
- `--target-cpm 160`（降低目标 CPM）
- `--panic-cpm 300`（保持恐慌阈值）
- `--max-shift 6000`（扩大边界位移窗口）

---

### 5.4 严格 Edge 模式（高质量）

**适用场景：** 要求最高质量，禁止回退到 macOS Say

**完整流程：**

```bash
# 1. LLM 阶段：语义重构
# 输出：semantic_fixed.srt

# 2. 预检 Edge TTS 网络
python - <<'PY'
import asyncio, tempfile, edge_tts

async def main():
    tmp = tempfile.mktemp(suffix=".mp3")
    c = edge_tts.Communicate("测试。你好，世界。", voice="zh-CN-YunjianNeural")
    await c.save(tmp)
    print(f"预检成功: {tmp}")

asyncio.run(main())
PY

# 3. 合成（严格模式）
python -m pyvideotrans merge semantic_fixed.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --ar 48000 \
  --jobs 1 \
  --no-fallback \
  --clustered \
  -o video.edge.dub.mp4

# 4. 同步审计
python -m pyvideotrans sync_audit video.edge.dub.mp4 semantic_fixed.srt
```

**关键参数：**
- `--jobs 1`：降低并发，减少网络不稳定
- `--no-fallback`：禁用后端回退，失败即停
- `--clustered`：聚类合成，保留微锚点

**失败处理：**
- 如果 Edge TTS 失败，命令会返回非零退出码
- 不会生成任何输出文件
- 检查网络连接后重试

---

### 5.5 Mode B - 自然语速配音（质量优先）

**适用场景：** 
- 教学视频、讲解视频
- 对音质要求高
- 视频时长可以灵活调整
- 静态画面为主

#### Mode B 语义重构策略（细粒度分片）

**⚠️ 重要：Mode B 对时间轴精度要求更高，需要采用细粒度分片策略。**

| 策略 | Mode A | Mode B |
|------|--------|--------|
| 分片粒度 | 可以合并多句 | 按句号分片 |
| 时间边界 | 可以调整 | 保持原始边界 |
| 片段数量 | 可以大幅减少 | 接近原始（80%-120%） |
| 单片段时长 | ≤15 秒 | 建议 ≤10 秒 |

**Mode B 分片规则：**

1. **按句号分片**：每个完整句子（以。？！结尾）独立成片
2. **保持原始时间边界**：尽量使用原始 SRT 的 start_ms 和 end_ms
3. **按停顿分片**：原始 SRT 中 > 500ms 的间隙处保持分片
4. **避免过度合并**：单片段建议 ≤ 10 秒
5. **片段数量检查**：重构后片段数应接近原始（80%-120%）

**示例对比：**

❌ **过度合并（不推荐）：**
```srt
1
00:00:01,510 --> 00:00:19,369
[Speaker:Henning] 嗨，大家好，我是 Flip Normals 的 Henning Morton。在这个教程中，我们将学习如何在 Maya 中进行重拓扑。这不会涉及拓扑的深层原理，而是纯粹讲解使用什么工具，如何开始重拓扑。
```
问题：17.8 秒的片段会导致视频拉伸不均匀

✅ **细粒度分片（推荐）：**
```srt
1
00:00:01,510 --> 00:00:05,870
[Speaker:Henning] 嗨，大家好，我是 Flip Normals 的 Henning Morton。

2
00:00:05,870 --> 00:00:10,040
[Speaker:Henning] 在这个教程中，我们将学习如何在 Maya 中进行重拓扑。

3
00:00:10,040 --> 00:00:14,809
[Speaker:Henning] 这不会涉及拓扑的深层原理，而是纯粹讲解使用什么工具。

4
00:00:14,809 --> 00:00:19,369
[Speaker:Henning] 如何开始重拓扑，以及一些通用的良好实践。
```
优点：每个片段 4-5 秒，视频拉伸更均匀

**完整流程（单个视频）：**

```bash
# 1. LLM 阶段：语义重构
# 输出：semantic_fixed.srt

# 2. 执行 Mode B 合成
python -m pyvideotrans merge semantic_fixed.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --ar 48000 \
  --mode elastic-video \
  --jobs 2 \
  -o video.mode_b.dub.mp4

# 3. 验证结果
ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 "video.mode_b.dub.mp4"

# 4. 同步审计
python -m pyvideotrans sync_audit video.mode_b.dub.mp4 semantic_fixed.srt
```

**完整流程（长视频分段处理）：**

```bash
# 1. LLM 阶段：分段处理语义重构
# 输出：semantic_part01.srt, semantic_part02.srt, ...

# 2. 分段处理（Mode B）
for i in {01..06}; do
  echo "处理第 $i 段..."
  python -m pyvideotrans merge \
    "data/input/ProjectName/chunks/semantic_part${i}.srt" \
    "data/input/ProjectName/video.mp4" \
    --backend edge_tts \
    --voice zh-CN-YunjianNeural \
    --voice-map voice_map.json \
    --mode elastic-video \
    --ar 48000 \
    --jobs 2 \
    -o "data/output/ProjectName/mode_b_part${i}.mp4"
done

# 3. 自动合并所有分段
cat > concat_list.txt <<EOF
file 'mode_b_part01.mp4'
file 'mode_b_part02.mp4'
file 'mode_b_part03.mp4'
file 'mode_b_part04.mp4'
file 'mode_b_part05.mp4'
file 'mode_b_part06.mp4'
EOF

ffmpeg -f concat -safe 0 -i concat_list.txt \
  -c copy -y "final_output.mp4"

# 4. 验证合并结果
ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 "final_output.mp4"

# 5. 同步审计
python -m pyvideotrans sync_audit "final_output.mp4" \
  "data/input/ProjectName/semantic_fixed.srt"
```

**关键参数：**
- `--mode elastic-video`：启用 Mode B
- `--jobs 2`：建议 2-4 并发（视频处理较慢）
- `--voice-map`：多说话人场景必需

**预期结果：**
- 视频时长增加 10-30%（取决于 TTS 语速）
- 语速自然，音质清晰
- 视频画面轻微拉伸（通常不明显）

**性能指标：**
- 处理速度：~3-4 秒/片段
- 总处理时间：100 片段 ≈ 5-10 分钟
- 输出文件大小：与原视频相近或略小

**对比 Mode A：**

| 特性 | Mode A | Mode B |
|------|--------|--------|
| 时长 | 29:04 | 32:37 (+12%) |
| 语速 | 可能过快 | 自然 ✅ |
| 音质 | 压缩 | 清晰 ✅ |
| 处理时间 | 快 | 慢 5-10 倍 |
| 视频画面 | 原样 | 轻微拉伸 |

---

### 5.6 Mode 选择决策流程

**Agent 应该在处理前询问用户：**

```
检测到长视频（> 15 分钟），需要选择处理模式：

【Mode A - 弹性音频】（默认）
✅ 视频时长保持不变
✅ 处理速度快
⚠️ 音频可能被压缩，语速可能过快

【Mode B - 弹性视频】（实验性）
✅ 语速自然，音质清晰
✅ 适合教学讲解类内容
⚠️ 视频时长增加 10-30%
⚠️ 处理速度慢（5-10 倍）

请选择 (A/B)? [默认: A]
```

**根据用户选择执行相应流程：**

```python
if user_choice == "B":
    # Mode B 流程
    for segment in segments:
        merge_with_mode_b(segment)
    merge_all_segments()
else:
    # Mode A 流程（默认）
    for segment in segments:
        merge_with_mode_a(segment)
```


---

## 6. CLI 命令参考

### 6.1 merge - 合成与合流

**用途：** 完整的音频合成与视频合流流程

**语法：**
```bash
python -m pyvideotrans merge <srt_path> <video_path> \
  --backend {edge_tts,macos_say} \
  --voice <voice_id> \
  [选项]
```

**必需参数：**
- `srt_path`：字幕文件路径
- `video_path`：视频文件路径
- `--backend`：TTS 后端（edge_tts / macos_say）
- `--voice`：音色 ID

**常用选项：**
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--ar` | 48000 | 采样率（Hz） |
| `--jobs` | 4 | 并发数（Edge TTS），macOS Say 强制为 1 |
| `--clustered` | False | 启用聚类合成 |
| `--no-fallback` | False | 禁用后端回退（强制 jobs=1） |
| `--voice-map` | None | 说话人音色映射文件 |
| `--keep-brackets` | False | 保留括号（多人场景必需） |
| `--subtitle-path` | None | 嵌入字幕文件路径 |
| `--subtitle-lang` | None | 字幕语言代码（如 zh, en） |
| `-o, --output` | 自动生成 | 输出文件路径 |

**行为：**
1. 读取 SRT 和视频
2. 可选：再平衡时间轴（除非 --clustered 或 --no-rebalance）
3. 合成音频（TTS）
4. 拉伸/填充音频以匹配时长
5. 合流音视频
6. 可选：嵌入字幕

**输出：** `<video_dir>/<video_basename>.dub.mp4`

---

### 6.2 rebalance - 时间轴再平衡

**用途：** 基于 CPM 优化字幕时间轴

**语法：**
```bash
python -m pyvideotrans rebalance <srt_path> [选项]
```

**必需参数：**
- `srt_path`：字幕文件路径

**常用选项：**
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--target-cpm` | 180 | 目标 CPM |
| `--panic-cpm` | 300 | 恐慌阈值 CPM |
| `--max-shift` | 1000 | 最大边界位移（ms） |
| `-o, --output` | 自动生成 | 输出文件路径 |

**行为：**
- 调整字幕时间轴以优化 CPM
- **严格不改变文本内容**
- 使用借时算法和恐慌模式

**输出：** `<basename>.rebalance.srt`

**约束：**
- 文本内容必须与输入完全一致
- 代码会自动验证文本未变

---

### 6.3 audit - CPM 审计

**用途：** 检查字幕 CPM 是否在合理范围

**语法：**
```bash
python -m pyvideotrans audit <srt_path> [选项]
```

**必需参数：**
- `srt_path`：字幕文件路径

**常用选项：**
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--min-cpm` | 180 | 审计最小 CPM |
| `--max-cpm` | 220 | 审计最大 CPM |
| `--save` | None | 保存 CSV 报告路径 |

**行为：**
- 计算每个片段的 CPM
- 输出超出范围的片段
- 可选：生成 CSV 报告

**输出：**
- 控制台输出
- 可选：CSV 报告

---

### 6.4 rewrite - 语义重构

**用途：** 合并碎片化字幕，清理文本（LLM 阶段）

**语法：**
```bash
python -m pyvideotrans rewrite <srt_path> [选项]
```

**必需参数：**
- `srt_path`：字幕文件路径

**常用选项：**
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--strip-meta` | False | 移除元标记（如 [音乐]） |
| `--strip-noise` | False | 清理噪声符号 |
| `--max-chars` | 250 | 单块最大字符数 |
| `--max-duration` | 15000 | 单块最大时长（ms） |
| `-o, --output` | 自动生成 | 输出文件路径 |

**行为：**
1. 按终止标点合并碎片化字幕
2. 超过上限时在逗号/分号处切分
3. 清理噪声符号（可选）
4. 移除元标记如 `[音乐]`（可选）

**输出：** `<basename>.rewritten.srt`

**注意：** 这是唯一可以修改文本的命令。

---

### 6.5 project_merge - 项目级端到端处理

**用途：** 自动执行完整流程，生成所有产物

**语法：**
```bash
python -m pyvideotrans project_merge <project_dir> \
  --backend {edge_tts,macos_say} \
  [选项]
```

**必需参数：**
- `project_dir`：项目目录路径（必须包含 1 个 MP4 和 1 个 SRT）
- `--backend`：TTS 后端

**常用选项：**
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--auto-voice` | False | 自动检测语言并推荐音色 |
| `--target-lang` | None | 目标语言（zh, en 等） |
| `--ar` | 48000 | 采样率（Hz） |
| `--target-cpm` | 180 | 目标 CPM |
| `--panic-cpm` | 300 | 恐慌阈值 CPM |
| `--max-shift` | 1000 | 最大边界位移（ms） |
| `--jobs` | 4 | 并发数 |
| `--clustered` | False | 启用聚类合成 |
| `--auto-dual-srt` | False | 自动生成双轨字幕 |
| `--embed-subtitle` | None | 嵌入字幕类型（none/original/rebalance/display） |
| `--subtitle-lang` | None | 字幕语言代码 |

**行为：**
- 自动执行完整流程
- 生成所有产物和报告

**输出目录：** `data/output/<ProjectName>/`
- `process.log` - 处理日志
- `cpm.csv` - CPM 审计报告
- `report.json` - 元数据报告
- `<ProjectName>.dub.mp4` - 最终视频
- `<basename>.rebalance.srt` - 再平衡字幕
- `<basename>.display.srt` - 显示字幕（双轨模式）
- `<basename>.audio.srt` - 音频字幕（双轨模式）

---

### 6.6 sync_audit - 同步审计

**用途：** 检查音频波形起点与字幕时间戳的同步性

**语法：**
```bash
python -m pyvideotrans sync_audit <video_path> <srt_path> [选项]
```

**必需参数：**
- `video_path`：视频文件路径
- `srt_path`：字幕文件路径

**常用选项：**
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--ar` | 48000 | 采样率（Hz） |
| `--win-ms` | 20 | 波形窗口（ms） |
| `-o, --output` | 自动生成 | 输出目录 |

**行为：**
- 提取视频音频
- 检测每个片段的波形起点
- 与字幕时间戳对比
- 计算偏差

**输出：**
- `*.sync_audit.csv` - 同步偏差报告
- `*.sync_debug.log` - 调试日志

**阈值：** `|delta_ms| ≤ 180ms` 为可接受范围

---

### 6.7 validate_project - 项目结构校验

**用途：** 验证项目目录结构是否符合要求

**语法：**
```bash
python -m pyvideotrans validate_project <project_dir>
```

**必需参数：**
- `project_dir`：项目目录路径

**要求：**
- 项目目录下必须有且仅有 1 个 `.mp4` 文件
- 项目目录下必须有且仅有 1 个 `.srt` 文件

**行为：**
- 检查文件数量
- 检测语言
- 推荐音色
- 检测负 PTS

**输出：** `data/output/<ProjectName>/validation.json`

**示例输出：**
```json
{
  "project_name": "ProjectName",
  "video_file": "video.mp4",
  "srt_file": "subtitle.srt",
  "detected_language": "zh",
  "recommended_voice": "zh-CN-YunjianNeural",
  "recommend_robust_ts": false
}
```


---

### 6.8 qa - 质量检查

**用途：** 检查语义重构后的 SRT 文件质量（Mode B 必需）

**语法：**
```bash
python -m pyvideotrans qa <srt_path> [选项]
```

**必需参数：**
- `srt_path`：字幕文件路径

**常用选项：**
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--voice-map` | None | voice_map.json 路径 |
| `--video-duration-ms` | None | 视频总时长（ms） |
| `--max-chars` | 250 | 单片段最大字符数 |
| `--max-duration-ms` | 15000 | 单片段最大时长（ms） |
| `-o, --output` | None | 输出 QA 报告（JSON） |

**检查项：**
| 检查类别 | 检查项 | 通过标准 |
|---------|--------|---------|
| **1. SRT 格式** | 格式有效 | 能被正确解析 |
| **2. 说话人标注** | 覆盖率 | = 100% |
| **3. 时间轴完整性** | 覆盖整个视频 | 首尾时间正确 |
| **4. 字符限制** | 单片段字符数 | ≤ 250 字符 |
| **5. 时长限制** | 单片段时长 | ≤ 15 秒 |
| **6. voice_map** | 格式有效且包含 DEFAULT | 必须通过 |

**输出示例：**
```
[QA] SRT Valid: True
[QA] Speaker Coverage: 100.0%
[QA] Timeline Complete: True
[QA] First Start: 1510ms, Last End: 842310ms
[QA] Voice Map Valid: True
[QA] Voice Map Has DEFAULT: True
[QA] ALL PASSED: True
```

**返回值：**
- `0`：所有检查通过
- `1`：有检查项未通过

**使用场景：**
- 语义重构完成后，进入 Mode B 处理前必须执行
- 任何检查项未通过都必须修正后才能继续

---

## 7. 参数标准

**权威来源：** `.kiro/specs/agent-orchestration-system/parameter-standards.md`

### 7.1 默认参数表

| 参数 | 默认值 | 适用命令 | 说明 |
|------|--------|----------|------|
| `--ar` | `48000` | merge, json_merge, project_merge, sync_audit | 采样率（Hz） |
| `--target-cpm` | `180` | merge, rebalance, json_merge, project_merge | 目标 CPM（每分钟字符数） |
| `--panic-cpm` | `300` | merge, rebalance, json_merge, project_merge | 恐慌阈值 CPM |
| `--max-shift` | `1000` | merge, rebalance, json_merge, project_merge | 最大边界位移（ms） |
| `--jobs` | `4` | merge, json_merge, project_merge | 并发数（Edge TTS） |
| `--min-cpm` | `180` | audit, json_audit | 审计最小 CPM |
| `--max-cpm` | `220` | audit, json_audit | 审计最大 CPM |
| `--win-ms` | `20` | sync_audit | 波形窗口（ms） |
| `--max-chars` | `250` | rewrite | 单块最大字符数 |
| `--max-duration` | `15000` | rewrite | 单块最大时长（ms） |

**注意：** 这些是代码中的默认值，不要在文档中使用不同的值。

---

### 7.2 参数互斥规则

| 参数 A | 参数 B | 关系 | 说明 |
|--------|--------|------|------|
| `--keep-brackets` | `--strip-meta` | **互斥** | 不能同时使用 |
| `--clustered` | `--no-rebalance` | **冗余** | clustered 已自动跳过 rebalance |
| `--llm-dual-srt` | `--auto-dual-srt` | **依赖** | llm-dual-srt 需要 auto-dual-srt |

**详细说明：**

1. **`--keep-brackets` vs `--strip-meta`**
   - `--keep-brackets`：保留所有括号内容
   - `--strip-meta`：移除 `[` `]` `【` `】` 括号
   - 不能同时使用，会产生冲突

2. **`--clustered` vs `--no-rebalance`**
   - `--clustered` 已自动跳过 rebalance
   - 建议只使用 `--clustered`

3. **`--llm-dual-srt` 依赖 `--auto-dual-srt`**
   - `--llm-dual-srt` 需要 `--auto-dual-srt` 启用
   - 代码中会自动处理，但建议显式指定

---

### 7.3 自动行为说明

#### 1. `--clustered` 模式
```python
if args.clustered or args.auto_dual_srt:
    # 自动跳过 rebalance
    # 使用 build_audio_from_srt_clustered
```

#### 2. `--no-fallback` 模式
```python
if backend == "macos_say" or args.no_fallback:
    jobs = 1  # 强制串行
```

#### 3. `--robust-ts` 自动检测
```python
auto_robust = detect_negative_ts(args.video_path)
mux_audio_video(..., robust_ts=(args.robust_ts or auto_robust))
```
**说明：** 即使用户不指定 `--robust-ts`，系统也会自动检测负 PTS 并启用。

#### 4. `--llm-dual-srt` 回退
```python
if args.llm_dual_srt:
    try:
        d_items, a_items = llm_generate_dual_srt(items)
    except:
        # 回退到本地 semantic_restructure
        d_items = items
        a_items = semantic_restructure(items)
```

---

## 8. 故障排除

### 8.1 Edge TTS 网络不稳定

**症状：**
- `ClientConnectorError` 或合成超时
- 部分片段合成失败
- `NoAudioReceived: No audio was received` 错误

**解决方案：**

```bash
# 方案 0：检查 edge-tts 版本（首选！）
# ⚠️ 2025-12-08 发现：edge-tts 7.2.3 存在 bug，需降级到 7.2.1
pip show edge-tts  # 查看当前版本
pip install edge-tts==7.2.1  # 降级到稳定版本

# 方案 1：降低并发
python -m pyvideotrans merge semantic_fixed.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --jobs 1

# 方案 2：启用严格模式（失败即停）
python -m pyvideotrans merge semantic_fixed.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --jobs 1 \
  --no-fallback

# 方案 3：预检网络
curl -I https://speech.platform.bing.com/
```

**⚠️ Edge TTS 版本问题（2025-12-08 新增）**

| 版本 | 状态 | 说明 |
|------|------|------|
| 7.2.3 | ❌ 有 bug | 返回 "No audio received" 错误 |
| 7.2.1 | ✅ 稳定 | 推荐使用 |

**诊断步骤**：
```bash
# 1. 测试 Edge TTS 是否正常
source .venv/bin/activate
edge-tts --text "测试" --voice zh-CN-YunjianNeural --write-media test.mp3

# 2. 如果报错 "No audio received"，降级版本
pip install edge-tts==7.2.1

# 3. 重新测试
edge-tts --text "测试" --voice zh-CN-YunjianNeural --write-media test.mp3
```

**预防措施：**
- 使用稳定的网络连接
- 避免高峰时段
- 考虑使用代理
- **锁定 edge-tts 版本为 7.2.1**

---

### 8.2 FFmpeg robust-ts 报错（FFmpeg 8）

**症状：**
```
Option muxpreload ... cannot be applied to input url
```

**原因：**
`muxpreload/muxdelay` 是输出选项，但代码放在了输入之前（FFmpeg 8 更严格）。

**解决方案：**

```bash
# 方案 1：不使用 --robust-ts（推荐）
# 系统会自动检测负 PTS 并启用

# 方案 2：手动合流
ffmpeg -y -i "video.mp4" -i "mix.wav" \
  -map 0:v:0 -map 1:a:0 \
  -c:v copy -c:a aac \
  "output.mp4"
```

**预防措施：**
- 让系统自动检测负 PTS
- 不要手动指定 `--robust-ts`

---

### 8.3 字幕嵌入失败（中文 SRT）

**症状：**
- 合流返回非零退出码
- 字幕未嵌入到视频中

**原因：**
SRT 编码非 UTF-8 with BOM，FFmpeg 无法正确解析。

**解决方案：**

```bash
# 添加 BOM
iconv -f utf-8 -t utf-8 "input.srt" | \
  (printf '\xEF\xBB\xBF'; cat) > "output.srt"

# 或使用 Python
python -c "
with open('input.srt', 'r', encoding='utf-8') as f:
    content = f.read()
with open('output.srt', 'w', encoding='utf-8-sig') as f:
    f.write(content)
"
```

**预防措施：**
- 确保 SRT 文件使用 UTF-8 编码
- 使用 `--subtitle-lang` 指定语言代码

---

### 8.4 语义重构后 TTS 不连贯

**症状：**
- 长片段合成超时
- 语气断裂
- 朗读不完整

**原因：**
单块字符过多（>250）或时长过长（>15s）。

**解决方案：**

```bash
# 方案 1：在 LLM 阶段降低上限
# 在 IDE 中使用 Agent，要求：
# - 单块最多 200 字符
# - 单块最多 12 秒

# 方案 2：使用 rewrite 命令
python -m pyvideotrans rewrite video.srt \
  --max-chars 200 \
  --max-duration 12000 \
  -o semantic_fixed.srt
```

**预防措施：**
- 在 LLM 阶段严格控制单块大小
- 使用 `audit` 命令预检

---

### 8.5 高密度片段无法读全

**症状：**
- CPM ≥ 900 的片段朗读不完整
- 音频被截断

**原因：**
时间窗口太短，无法容纳完整朗读。

**解决方案：**

```bash
# 方案 1：在 LLM 阶段分句
# 在 IDE 中使用 Agent，要求：
# - 在逗号/分号处切分长句
# - 单块最多 150 字符

# 方案 2：在再平衡阶段扩窗
python -m pyvideotrans rebalance video.srt \
  --target-cpm 160 \
  --panic-cpm 300 \
  --max-shift 6000 \
  -o video.rebalance.srt
```

**预防措施：**
- 使用 `audit` 命令识别高密度片段
- 在 LLM 阶段预先处理

---

### 8.6 同步偏差过大

**症状：**
`sync_audit` 报告 `|delta_ms| > 180ms`

**排查步骤：**

1. **检查是否使用了正确的字幕文件**
   ```bash
   # 应使用 rebalance.srt，而不是原始 SRT
   python -m pyvideotrans sync_audit video.dub.mp4 video.rebalance.srt
   ```

2. **检查静音移除是否过度**
   - 高密度片段（CPM > 260）应跳过静音移除
   - 短片段（< 1200ms）应跳过静音移除

3. **检查时间拉伸倍率**
   ```python
   # 正确的倍率计算
   tempo = src_ms / target_ms
   ```

**解决方案：**

```bash
# 方案 1：重新再平衡
python -m pyvideotrans rebalance video.srt \
  --target-cpm 180 \
  --max-shift 2000 \
  -o video.rebalance.srt

# 方案 2：使用聚类模式（保留微锚点）
python -m pyvideotrans merge video.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --clustered
```

---

### 8.7 多说话人音色错配

**症状：**
- 不同说话人使用了相同音色
- 日志显示 "not_mapped use DEFAULT"

**排查步骤：**

1. **检查 SRT 标签格式**
   ```bash
   grep -E "\[Speaker:" semantic_fixed.srt | head -5
   ```
   确保格式为 `[Speaker:Name]`

2. **检查 voice_map.json**
   ```bash
   cat voice_map.json
   ```
   确保 Name 与 SRT 中完全一致

3. **检查日志**
   ```bash
   grep "SPEAKER_MAP" process.log
   ```

**解决方案：**

```bash
# 方案 1：修正 SRT 标签
# 在 IDE 中使用 Agent 重新标注

# 方案 2：更新 voice_map.json
cat > voice_map.json <<EOF
{
  "John": "zh-CN-YunjianNeural",
  "Alice": "zh-CN-XiaoxiaoNeural",
  "DEFAULT": "zh-CN-YunjianNeural"
}
EOF

# 方案 3：确保使用 --keep-brackets
python -m pyvideotrans merge semantic_fixed.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --voice-map voice_map.json \
  --keep-brackets \
  --clustered
```

---

### 8.8 Mode B 视频拉伸过度

**症状：**
- 视频时长增加超过 30%
- 视频画面明显慢放

**原因：**
TTS 语速比原字幕时间窗口慢很多，导致拉伸比例过大。

**排查步骤：**

1. **检查拉伸比例**
   ```bash
   # 原视频时长
   ffprobe -v error -show_entries format=duration \
     -of default=noprint_wrappers=1:nokey=1 "original.mp4"
   
   # Mode B 输出时长
   ffprobe -v error -show_entries format=duration \
     -of default=noprint_wrappers=1:nokey=1 "mode_b_output.mp4"
   
   # 计算拉伸比例
   python -c "print(f'拉伸比例: {mode_b_duration / original_duration:.2%}')"
   ```

2. **检查字幕密度**
   ```bash
   python -m pyvideotrans audit semantic_fixed.srt
   ```
   如果 CPM 很高（> 300），说明字幕很密集

**解决方案：**

```bash
# 方案 1：在 LLM 阶段降低单块上限
# 在 IDE 中使用 Agent，要求：
# - 单块最多 150 字符
# - 单块最多 10 秒
# - 在逗号/分号处切分长句

# 方案 2：使用 Mode A（如果拉伸过度不可接受）
python -m pyvideotrans merge semantic_fixed.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --mode elastic-audio \
  --clustered
```

**预防措施：**
- 在 LLM 阶段严格控制单块大小
- 使用 `audit` 命令预检 CPM
- 对于高密度字幕，优先使用 Mode A

---

### 8.9 Mode B 处理超时

**症状：**
- 视频处理卡住
- 进程占用 CPU 100%
- 无法完成处理

**原因：**
视频重新编码耗时过长，特别是对于大分辨率视频。

**排查步骤：**

1. **检查视频分辨率**
   ```bash
   ffprobe -v error -select_streams v:0 \
     -show_entries stream=width,height \
     -of default=noprint_wrappers=1:nokey=1 "video.mp4"
   ```

2. **检查片段数量**
   ```bash
   grep -c "^[0-9]" semantic_fixed.srt
   ```

**解决方案：**

```bash
# 方案 1：降低并发数
python -m pyvideotrans merge semantic_fixed.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --mode elastic-video \
  --jobs 1  # 降低并发

# 方案 2：分段处理（推荐）
# 将大视频分成多个小段，分别处理
# 然后使用 ffmpeg concat 合并

# 方案 3：使用 Mode A（快速处理）
python -m pyvideotrans merge semantic_fixed.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --mode elastic-audio \
  --clustered
```

**预防措施：**
- 对于长视频（> 15 分钟），优先使用分段处理
- 对于高分辨率视频（> 1080p），考虑使用 Mode A
- 监控系统资源使用情况

---

### 8.10 Mode B 分段合并失败

**症状：**
- 合并后的视频无法播放
- 音视频不同步
- 文件损坏

**原因：**
分段文件格式不一致或合并参数错误。

**排查步骤：**

1. **检查分段文件**
   ```bash
   # 验证每个分段文件
   for f in mode_b_part*.mp4; do
     ffprobe -v error "$f" > /dev/null && echo "✅ $f" || echo "❌ $f"
   done
   ```

2. **检查合并列表**
   ```bash
   cat concat_list.txt
   ```

**解决方案：**

```bash
# 方案 1：重新生成合并列表
cd data/output/ProjectName
ls -1 mode_b_part*.mp4 | awk '{print "file '"'"'" $0 "'"'"'"}' > concat_list.txt

# 方案 2：使用正确的 ffmpeg 命令
ffmpeg -f concat -safe 0 -i concat_list.txt \
  -c copy -y "final_output.mp4"

# 方案 3：验证合并结果
ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 "final_output.mp4"

# 方案 4：如果仍然失败，使用重新编码
ffmpeg -i "mode_b_part01.mp4" -i "mode_b_part02.mp4" \
  -filter_complex "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]" \
  -map "[v]" -map "[a]" -y "final_output.mp4"
```

**预防措施：**
- 确保所有分段文件格式一致
- 使用 `-c copy` 避免重新编码
- 验证每个分段文件的完整性


---

## 9. Agent 技能库

### 9.1 视频处理技能

#### 9.1.1 弹性配音模式选择

**技能描述**：根据用户需求和视频特征选择最适合的配音模式

**应用场景**：
- 用户要求固定视频时长 → Mode A (elastic-audio)
- 用户要求自然语速 → Mode B (elastic-video)
- 教学视频、讲解内容 → 推荐 Mode B
- 时长严格限制 → 推荐 Mode A

**决策逻辑**：
```python
def choose_dubbing_mode(user_requirements, video_type, duration_constraint):
    """智能选择配音模式"""
    if duration_constraint == "strict":
        return "elastic-audio"
    elif user_requirements.get("natural_speed", False):
        return "elastic-video"
    elif video_type in ["tutorial", "lecture", "explanation"]:
        # 推荐但询问用户
        return "elastic-video"
    else:
        return "elastic-audio"  # 默认
```

**用户引导话术**：
```
检测到长视频，需要选择处理模式：

【Mode A - 弹性音频】（默认）
✅ 视频时长保持不变
✅ 处理速度快
⚠️ 音频可能被压缩，语速可能过快

【Mode B - 弹性视频】（实验性）
✅ 语速自然，音质清晰
✅ 适合教学讲解类内容
⚠️ 视频时长增加 10-30%
⚠️ 处理时间较长

请选择 (A/B)? [默认: A]
```

---

#### 9.1.2 视频分段与合并

**技能描述**：智能分段处理长视频并自动合并

**应用场景**：
- 视频时长 > 15 分钟
- 内存限制需要分段处理
- Mode B 处理需要逐段操作

**实现方法**：
```bash
# 分段处理
for i in {01..06}; do
  python -m pyvideotrans merge "part${i}.srt" "video.mp4" \
    --mode elastic-video -o "mode_b_part${i}.mp4"
done

# 自动合并
cat > concat_list.txt <<EOF
file 'mode_b_part01.mp4'
file 'mode_b_part02.mp4'
...
EOF

ffmpeg -f concat -safe 0 -i concat_list.txt -c copy final_output.mp4
```

**质量验证**：
```bash
# 验证总时长
ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 "final_output.mp4"

# 验证音视频同步
python -m pyvideotrans sync_audit "final_output.mp4" "semantic_fixed.srt"
```

---

#### 9.1.3 网络传输优化

**技能描述**：根据文件大小自动选择压缩策略

**应用场景**：
- 文件 > 500MB 需要压缩
- 网络传输需要优化
- 存储空间有限

**压缩策略**：
```python
def choose_compression_strategy(file_size_mb):
    """选择压缩策略"""
    if file_size_mb > 1000:
        return "high_compression"  # CRF 28
    elif file_size_mb > 500:
        return "medium_compression"  # CRF 23
    else:
        return "no_compression"  # -c copy
```

**实现命令**：
```bash
# 直接合并（无压缩）
ffmpeg -f concat -safe 0 -i concat_list.txt -c copy output.mp4

# 中等压缩（平衡质量和大小）
ffmpeg -f concat -safe 0 -i concat_list.txt \
  -c:v libx264 -crf 23 -preset fast -c:a copy output.mp4

# 高压缩（网络优化）
ffmpeg -f concat -safe 0 -i concat_list.txt \
  -c:v libx264 -crf 28 -preset medium -c:a aac -b:a 128k output.mp4
```

---

### 9.2 问题诊断技能

#### 9.2.1 音频质量问题诊断

**技能描述**：识别和解决音频质量问题

**常见问题与解决方案**：

| 问题 | 症状 | 解决方案 |
|------|------|----------|
| 语速过快 | 音频压缩严重，难以听清 | 使用 Mode B |
| 音频截断 | 高密度片段朗读不完整 | 降低单块上限，扩大时间窗口 |
| 音视频不同步 | sync_audit 报告偏差 > 180ms | 检查字幕文件，重新再平衡 |
| TTS 合成失败 | 部分片段无音频 | 降低并发数，检查网络 |

**诊断流程**：
```bash
# 1. CPM 审计
python -m pyvideotrans audit semantic_fixed.srt

# 2. 同步审计
python -m pyvideotrans sync_audit video.dub.mp4 semantic_fixed.rebalance.srt

# 3. 检查日志
grep -E "ERROR|WARNING" process.log
```

---

#### 9.2.2 处理超时问题

**技能描述**：处理长时间运行的任务

**解决策略**：

1. **降低并发数**：
   ```bash
   --jobs 1  # 或 --jobs 2
   ```

2. **分段处理**：
   - 将长视频分成多个小段
   - 分别处理后合并

3. **使用更快的编码预设**：
   ```bash
   # Mode B 中使用 fast 预设
   --preset fast
   ```

4. **监控系统资源**：
   ```bash
   # 监控 CPU 和内存使用
   top -p $(pgrep -f pyvideotrans)
   ```

---

#### 9.2.3 文件大小优化

**技能描述**：平衡质量和文件大小

**优化方法**：

1. **分析原始文件**：
   ```bash
   ls -lh video.mp4
   ffprobe -v error -show_entries format=size,duration video.mp4
   ```

2. **根据用途选择压缩级别**：
   - 本地存储：无压缩或低压缩
   - 网络传输：中等压缩
   - 移动设备：高压缩

3. **提供多个选项**：
   ```
   输出文件较大（650MB），建议压缩：
   
   1. 直接合并（无压缩，650MB）
   2. 中等压缩（约 400MB，推荐）
   3. 高压缩（约 250MB，网络优化）
   
   请选择 (1/2/3)? [默认: 2]
   ```

---

### 9.3 用户交互技能

#### 9.3.1 模式选择引导

**技能描述**：帮助用户选择最适合的处理模式

**引导流程**：

1. **分析视频特征**：
   - 视频时长
   - 内容类型（教学/娱乐/演示）
   - 字幕密度

2. **提供推荐**：
   ```
   根据视频分析：
   - 时长：29:04
   - 类型：教学视频
   - 字幕密度：中等（CPM 180-220）
   
   推荐使用 Mode B（弹性视频）
   理由：教学视频适合自然语速，提升学习体验
   ```

3. **说明利弊**：
   - 清晰列出每种模式的优缺点
   - 提供预期结果（时长变化、处理时间）

4. **确认选择**：
   ```
   确认使用 Mode B？
   - 预计输出时长：32-34 分钟
   - 预计处理时间：30-40 分钟
   
   继续？(Y/n)
   ```

---

#### 9.3.2 进度反馈

**技能描述**：提供清晰的处理进度信息

**反馈格式**：
```
正在处理分段...
[████████░░] 80% (4/5 完成)

已完成：
✅ mode_b_part01.mp4 (7:42) - 8分钟前
✅ mode_b_part02.mp4 (6:45) - 6分钟前
✅ mode_b_part03.mp4 (6:09) - 4分钟前
✅ mode_b_part04.mp4 (5:49) - 2分钟前

处理中：
⏳ mode_b_part05.mp4 ... (预计 5 分钟)

待处理：
⏸️  mode_b_part06.mp4
```

**实现方法**：
```python
class ProcessingProgress:
    def __init__(self, total_segments):
        self.total_segments = total_segments
        self.completed = 0
        self.start_time = time.time()
    
    def update(self, completed_count):
        self.completed = completed_count
        progress = (completed_count / self.total_segments) * 100
        elapsed = time.time() - self.start_time
        
        if completed_count > 0:
            avg_time = elapsed / completed_count
            remaining = avg_time * (self.total_segments - completed_count)
            print(f"进度: {progress:.1f}% | 预计剩余: {remaining/60:.1f} 分钟")
```

---

#### 9.3.3 结果总结

**技能描述**：提供处理结果的详细总结

**总结内容**：

```
✅ 处理完成！

【处理信息】
- 模式：Mode B（弹性视频）
- 输入时长：29:04
- 输出时长：32:37 (+12%)
- 处理时间：33 分钟

【文件信息】
- 输出文件：final_output.mp4
- 文件大小：650MB
- 视频质量：1080p, CRF 18

【质量检查】
✅ 音视频同步正常（平均偏差 45ms）
✅ 所有片段处理成功
✅ 无错误或警告

【建议】
- 文件较大，建议压缩后传输
- 可使用 merge_and_compress.py 进行压缩
```

---

### 9.4 自动化技能

#### 9.4.1 智能参数选择

**技能描述**：根据视频特征自动选择最佳参数

**参数优化逻辑**：

```python
def optimize_parameters(video_info, srt_info):
    """智能参数优化"""
    params = {}
    
    # 根据视频时长选择分段策略
    if video_info['duration'] > 900:  # 15分钟
        params['segment_strategy'] = 'split'
        params['segment_duration'] = 600  # 10分钟/段
    
    # 根据内容类型推荐模式
    if srt_info['content_type'] in ['tutorial', 'lecture']:
        params['mode'] = 'elastic-video'
    else:
        params['mode'] = 'elastic-audio'
    
    # 根据字幕密度调整参数
    avg_cpm = srt_info['avg_cpm']
    if avg_cpm > 300:
        params['target_cpm'] = 160
        params['max_shift'] = 6000
    else:
        params['target_cpm'] = 180
        params['max_shift'] = 1000
    
    # 根据文件大小选择压缩级别
    if video_info['size_mb'] > 500:
        params['compression'] = 'medium'
    
    return params
```

---

#### 9.4.2 错误自动恢复

**技能描述**：自动处理常见错误并恢复

**恢复策略**：

| 错误类型 | 恢复策略 |
|---------|---------|
| TTS 网络失败 | 重试 3 次，降低并发数 |
| 内存不足 | 降低并发数，分段处理 |
| FFmpeg 编码失败 | 切换编码预设，重试 |
| 文件损坏 | 重新生成该片段 |

**实现示例**：
```python
def robust_tts_synthesis(text, voice, max_retries=3):
    """带重试的 TTS 合成"""
    for attempt in range(max_retries):
        try:
            return synthesize_tts(text, voice)
        except NetworkError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 指数退避
                print(f"TTS 失败，{wait_time}秒后重试...")
                time.sleep(wait_time)
            else:
                raise
```

---

#### 9.4.3 批量处理

**技能描述**：高效处理多个视频文件

**批量策略**：

1. **并行处理多个项目**：
   ```bash
   # 使用 GNU parallel
   ls -d data/input/*/ | parallel -j 2 \
     python -m pyvideotrans project_merge {} --backend edge_tts --auto-voice
   ```

2. **统一参数配置**：
   ```bash
   # 创建配置文件
   cat > batch_config.json <<EOF
   {
     "backend": "edge_tts",
     "mode": "elastic-video",
     "ar": 48000,
     "jobs": 2
   }
   EOF
   ```

3. **批量质量检查**：
   ```bash
   # 检查所有输出
   for f in data/output/*/final_output.mp4; do
     python -m pyvideotrans sync_audit "$f" "${f%.mp4}.srt"
   done
   ```

---

### 9.5 字幕融合技能

#### 9.5.0 模式选择前置（强制）

**⚠️ 关键决策点：必须在语义重构之前确定处理模式！**

**原因**：Mode A 和 Mode B 对字幕分片策略有截然不同的要求：

| 特性 | Mode A (弹性音频) | Mode B (弹性视频) |
|------|------------------|------------------|
| **分片粒度** | 较大（8-15秒） | 超细（3-6秒） |
| **最大字符** | 250 字符 | 100 字符 |
| **CPM 要求** | **严格**（≤300 CPM） | **宽松**（400+ 可接受） |
| **合并策略** | 合并为语义单元 | 保持原始边界 |
| **rebalance** | 推荐执行 | 不需要 |
| **原因** | 音频被压缩到固定时间窗口，CPM 过高会导致语速过快 | 视频拉伸适配音频，TTS 自然语速，CPM 只影响拉伸比例 |

**强制工作流**：

```
用户请求处理视频
    ↓
【强制询问】选择处理模式？
    ↓
    ├─ Mode A (弹性音频)
    │   ├─ 分片策略：合并为完整语义单元
    │   ├─ 单片段限制：≤250 字符，≤15 秒
    │   ├─ CPM 目标：≤300（panic-cpm）
    │   ├─ 推荐执行 rebalance（或使用 --clustered）
    │   └─ 输出：semantic_fixed.srt → [rebalance.srt]
    │
    └─ Mode B (弹性视频)
        ├─ 分片策略：超细粒度，保持原始边界
        ├─ 单片段限制：≤100 字符，≤6 秒
        ├─ CPM 容忍：400+ 可接受
        ├─ 不需要 rebalance（使用 --no-rebalance）
        └─ 输出：tts_mode_b.srt（直接用于 merge）
```

**用户引导话术**：

```
在开始处理之前，请选择配音模式：

【Mode A - 弹性音频】
✅ 视频时长保持不变
✅ 处理速度快
⚠️ 音频可能被压缩，需要严格控制 CPM（≤300）
⚠️ 语速可能较快

【Mode B - 弹性视频】（推荐教学视频）
✅ 语速自然，音质清晰
✅ CPM 要求宽松（300+ 可接受）
⚠️ 视频时长增加 10-30%
⚠️ 需要超细粒度分片

请选择 (A/B)? 
```

**⚠️ 重要**：一旦选择模式，后续的分片策略、CPM 阈值、是否 rebalance 都由模式决定，不可混用！

---

#### 9.5.1 多源字幕融合（MD + SRT）

**技能描述**：将 Markdown 文档（内容准确）与 SRT 字幕（时间准确）融合生成高质量 TTS 字幕

**应用场景**：
- 有参考文档（gs.md、transcript.md）+ 原始 SRT
- MD 文档内容完整准确，但时间标记不精确
- SRT 时间轴准确，但内容可能有机器翻译错误

**融合策略**：

```
优先级规则：
1. 时间轴：以 SRT 文件为准（时间准确）
2. 文本内容：以 MD 文档为准（内容准确）
3. 说话人：根据 MD 文档的时间标记推断

融合步骤：
1. 解析 MD 文档，提取时间标记和对应内容
2. 解析 SRT 文件，获取精确时间轴
3. 按时间顺序对齐两者
4. 用 MD 内容替换 SRT 中的错误翻译
5. 添加说话人标签
6. 按细粒度策略分片
```

**实现示例**：

```python
# 伪代码
def merge_md_srt(md_content, srt_items):
    """融合 MD 文档和 SRT 字幕"""
    
    # 1. 从 MD 提取时间标记和内容
    md_segments = parse_md_timestamps(md_content)
    # 例如: [(0, 21, "开场介绍内容..."), (21, 68, "技巧1内容...")]
    
    # 2. 按 SRT 时间轴分配 MD 内容
    output_items = []
    for srt_item in srt_items:
        start_sec = srt_item.start.total_seconds()
        end_sec = srt_item.end.total_seconds()
        
        # 找到对应的 MD 内容
        md_text = find_matching_md_content(md_segments, start_sec, end_sec)
        
        # 创建新片段
        output_items.append(SRTItem(
            start=srt_item.start,
            end=srt_item.end,
            text=f"[Speaker:Instructor] {md_text}"
        ))
    
    return output_items
```

---

#### 9.5.2 CPM 容忍度策略（按模式区分）

**技能描述**：根据处理模式采用不同的 CPM 阈值策略

**⚠️ 关键区别**：

| 指标 | Mode A (弹性音频) | Mode B (弹性视频) |
|------|------------------|------------------|
| **目标 CPM** | 180（默认） | 不限制 |
| **最大 CPM** | ≤300（严格） | 400+ 可接受 |
| **超标处理** | 推荐拆分或 rebalance | 可以忽略 |
| **原因** | 音频压缩到固定时间，CPM 高 = 语速快 | 视频拉伸适配音频，CPM 只影响拉伸比例 |

---

**Mode A CPM 标准（严格）**：

| CPM 范围 | 占比要求 | 处理方式 |
|---------|---------|---------|
| 0-180 | 任意 | ✅ 理想 |
| 180-220 | ≥60% | ✅ 目标范围 |
| 220-280 | ≤30% | ⚠️ 建议 rebalance |
| 280-300 | ≤10% | ⚠️ 建议拆分或 rebalance |
| >300 | ≤5% | ⚠️ 高密度，需特殊处理 |

**Mode A 决策逻辑**：
```python
def evaluate_cpm_mode_a(cpms):
    """Mode A: 严格 CPM 控制"""
    avg_cpm = sum(cpms) / len(cpms)
    over_300 = sum(1 for c in cpms if c > 300) / len(cpms)
    
    if over_300 > 0.05:  # 超过 5% 的片段 > 300 CPM
        return "⚠️ 需要优化", "高密度片段较多，建议拆分或使用 --max-shift 6000"
    elif avg_cpm > 250:
        return "⚠️ 建议 rebalance", "平均 CPM 偏高，执行 rebalance 优化"
    else:
        return "✅ 通过", "CPM 分布合理"
```

---

**Mode B CPM 标准（宽松）**：

| CPM 范围 | 占比要求 | 说明 |
|---------|---------|------|
| 0-200 | 任意 | ✅ 理想 |
| 200-300 | 任意 | ✅ 良好 |
| 300-400 | ≤25% | ✅ 可接受 |
| 400-500 | ≤10% | ⚠️ 关注但可接受 |
| >500 | ≤5% | ⚠️ 建议优化 |

**Mode B 决策逻辑**：
```python
def evaluate_cpm_mode_b(cpms):
    """Mode B: 宽松 CPM 控制"""
    total = len(cpms)
    over_500 = sum(1 for c in cpms if c > 500) / total
    
    if over_500 > 0.10:  # 超过 10% 的片段 > 500 CPM
        return "⚠️ 建议优化", "部分片段 CPM 过高，可能导致视频拉伸异常"
    else:
        return "✅ 通过", "CPM 分布可接受，可以继续处理"
```

---

**用户引导话术（Mode B）**：

```
CPM 分析结果（Mode B 标准）：
- 平均 CPM: 208
- 超过 300 CPM 的片段: 21 个 (8.1%)
- 超过 400 CPM 的片段: 3 个 (1.2%)

评估：✅ 通过
说明：Mode B 下，CPM 只影响视频拉伸比例，当前分布可接受

继续处理？(Y/n) [默认: Y]
```

**用户引导话术（Mode A）**：

```
CPM 分析结果（Mode A 标准）：
- 平均 CPM: 208
- 超过 300 CPM 的片段: 21 个 (8.1%)

评估：❌ 不通过
说明：Mode A 下，CPM > 300 会导致语速过快，必须优化

建议操作：
1. 拆分高 CPM 片段
2. 执行 rebalance 优化时间轴

是否自动优化？(Y/n)
```

---

#### 9.5.3 分片策略（按模式区分）

**技能描述**：根据处理模式采用不同的分片策略

---

**Mode A 分片策略（合并优先）**：

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| 平均片段时长 | 8-12 秒 | 合并为完整语义单元 |
| 最大片段时长 | 15 秒 | 超过需强制分片 |
| 最大字符数 | 200-250 字符 | 允许较长片段 |
| 分片点 | 段落、句群 | 按语义完整性分片 |
| CPM 控制 | **严格** | 必须 ≤300，超过需 rebalance |

**Mode A 分片逻辑**：
```python
def segment_mode_a(md_content, srt_items):
    """Mode A: 合并为完整语义单元"""
    segments = []
    current_text = ""
    current_start = None
    
    for item in srt_items:
        if current_start is None:
            current_start = item.start
        
        current_text += item.text + " "
        
        # 在句号/问号/感叹号处检查是否分片
        if re.search(r'[。？！]$', item.text.strip()):
            # 检查是否达到分片条件
            duration = (item.end - current_start).total_seconds()
            if duration >= 8 or len(current_text) >= 150:
                segments.append((current_start, item.end, current_text.strip()))
                current_text = ""
                current_start = None
    
    return segments
```

---

**Mode B 分片策略（超细粒度）**：

> 📌 **参考**：详细参数见 [2.0 快速决策表](#20-快速决策表) 和 [3.1 断句重构](#31-phase-1-语义重构llm-阶段)

| 参数 | 推荐值 |
|------|--------|
| 平均片段时长 | 3-4 秒 |
| 最大片段时长 | 6 秒 |
| 最大字符数 | 100 字符 |
| CPM 控制 | 400+ 可接受 |

---

**实战案例对比**：

**Mode B 案例（本次处理）**：
```
输入：
- 原始 SRT: 198 个片段，14.8 分钟
- MD 文档: 完整中文内容

输出（Mode B 策略）：
- 生成 SRT: 258 个片段
- 平均时长: 3.5 秒
- 平均 CPM: 208
- 超过 300 CPM: 21 个 (8.1%) ✅ 可接受
- 质量评估: ✅ 通过

关键决策：
1. 保持原始 SRT 的时间边界作为参考
2. 按 MD 文档的语义结构分片
3. 每个完整句子独立成片
4. 超过 80 字符在逗号处分片
5. CPM 300+ 可接受（Mode B 特性）
```

**Mode A 案例（假设）**：
```
输入：
- 原始 SRT: 198 个片段，14.8 分钟
- MD 文档: 完整中文内容

输出（Mode A 策略）：
- 生成 SRT: ~80 个片段
- 平均时长: 11 秒
- 平均 CPM: 目标 180
- 超过 300 CPM: 0 个 ❌ 不允许
- 推荐执行 rebalance

关键决策：
1. 合并为完整语义单元
2. 严格控制 CPM ≤300
3. 超过 300 CPM 必须拆分
4. 推荐执行 rebalance 优化时间轴
```

---

#### 9.5.4 TTS 字幕生成工作流（用户请求处理）

**技能描述**：当用户提供项目文件夹并请求生成 TTS 字幕时，Agent 自动识别文件角色并执行融合

**⚠️ 核心理解**：用户通常只需说"帮我处理这个文件夹的字幕"或"生成 TTS 字幕"，Agent 应自动：
1. 识别文件夹中的内容参考文件和时间参考文件
2. 确定处理模式（默认 Mode B）
3. 执行多源融合生成高质量 TTS 字幕

---

**Step 1: 自动识别文件角色**

```python
def identify_project_files(project_dir):
    """
    自动识别项目文件夹中的文件角色
    
    返回:
    - content_ref: 内容参考文件（MD 文档，内容准确）
    - time_ref: 时间参考文件（SRT 字幕，时间精确）
    - video: 视频文件
    """
    files = os.listdir(project_dir)
    
    # 识别内容参考文件（优先级：gs.md > transcript.md > *.md）
    content_ref = None
    for pattern in ['gs.md', 'transcript.md', '*.md']:
        matches = [f for f in files if fnmatch(f, pattern)]
        if matches:
            content_ref = matches[0]
            break
    
    # 识别时间参考文件（原始 SRT，排除已生成的）
    time_ref = None
    srt_files = [f for f in files if f.endswith('.srt')]
    # 排除已生成的文件
    excluded = ['tts_mode_b.srt', 'semantic_fixed.srt', 'rebalance.srt', 
                'display.srt', 'audio.srt']
    original_srts = [f for f in srt_files if f not in excluded]
    if original_srts:
        time_ref = original_srts[0]
    
    # 识别视频文件
    video = None
    video_files = [f for f in files if f.endswith('.mp4')]
    if video_files:
        video = video_files[0]
    
    return {
        'content_ref': content_ref,  # 内容准确，时间粗略
        'time_ref': time_ref,        # 时间精确，内容可能有误
        'video': video
    }
```

---

**Step 2: 判断说话人场景**

```python
def detect_speaker_mode(content_ref_path, time_ref_path):
    """
    分析内容判断是单人还是多人场景
    
    检查特征：
    - MD 文档中的说话人标记（如 "### [00:00] 讲师"）
    - SRT 中的对话标记
    - 问答结构
    """
    # 读取内容参考文件
    with open(content_ref_path, 'r') as f:
        content = f.read()
    
    # 检查说话人标记
    speaker_patterns = [
        r'###\s*\[\d+:\d+\]\s*(\w+)',  # ### [00:00] 讲师
        r'\[Speaker:(\w+)\]',           # [Speaker:Name]
        r'^(\w+)[:：]',                 # Name: 或 Name：
    ]
    
    speakers = set()
    for pattern in speaker_patterns:
        matches = re.findall(pattern, content, re.MULTILINE)
        speakers.update(matches)
    
    if len(speakers) > 1:
        return 'multi_speaker', list(speakers)
    else:
        return 'single_speaker', list(speakers) or ['Instructor']
```

---

**Step 3: 执行融合生成**

**Agent 执行流程（用户请求 TTS 字幕时）：**

```
用户请求: "帮我处理 data/input/Maya Tutorial... 文件夹的字幕"
    ↓
【Step 1】识别文件
    ├─ 内容参考: gs.md ✅
    ├─ 时间参考: Maya Tutorial....srt ✅
    └─ 视频文件: Maya Tutorial....mp4 ✅
    ↓
【Step 2】判断场景
    ├─ 检测说话人数量
    └─ 结果: 单人场景 / 多人场景
    ↓
【Step 3】确认模式（默认 Mode B）
    ├─ Mode B: 超细粒度分片，自然语速
    └─ Mode A: 合并优先，固定时长
    ↓
【Step 4】执行融合
    ├─ 读取 MD 文档获取正确内容
    ├─ 读取 SRT 获取精确时间轴
    ├─ 按时间对齐两者
    ├─ 添加说话人标签
    └─ 按模式策略分片
    ↓
【Step 5】输出文件
    ├─ tts_mode_b.srt（Mode B）
    ├─ voice_map.json（多人场景）
    └─ 执行 QA 检查
```

---

**Step 4: 单人 vs 多人处理差异**

| 处理步骤 | 单人场景 | 多人场景 |
|---------|---------|---------|
| **说话人标签** | `[Speaker:Instructor]` 统一 | `[Speaker:Name]` 按角色区分 |
| **voice_map.json** | 只需 DEFAULT | 每个说话人单独映射 |
| **分片策略** | 按语义完整性 | 按说话人切换点 + 语义 |
| **TTS 参数** | `--voice` 单一音色 | `--voice-map` + `--keep-brackets` |

**多人场景额外步骤：**
```python
# 生成 voice_map.json
voice_map = {
    "Instructor": "zh-CN-YunjianNeural",
    "Assistant": "zh-CN-XiaoxiaoNeural",
    "DEFAULT": "zh-CN-YunjianNeural"
}
```

---

**Step 5: 完整示例**

**用户请求：**
```
帮我处理 data/input/Maya Tutorial - How to Bake Normal Maps from High Poly to Low Poly 文件夹的字幕
```

**Agent 响应：**
```
我来分析这个项目文件夹...

【文件识别】
✅ 内容参考文件: gs.md（完整中文内容）
✅ 时间参考文件: Maya Tutorial....srt（88 个片段，7:15）
✅ 视频文件: Maya Tutorial....mp4

【场景分析】
- 说话人数量: 1（单人教程）
- 主题: Maya 法线贴图烘焙
- 专业术语: Normal Map, Transfer Maps, UV, Tangent Space 等

【处理模式】
默认使用 Mode B（弹性视频），特点：
- 超细粒度分片（≤100 字符，≤6 秒）
- 自然语速，音质清晰
- 视频时长可能增加 10-30%

开始生成 TTS 字幕...

【输出文件】
✅ tts_mode_b.srt（87 个片段）
✅ voice_map.json
✅ QA 检查通过

下一步可执行：
python -m pyvideotrans merge "tts_mode_b.srt" "video.mp4" \
  --backend edge_tts --voice zh-CN-YunjianNeural \
  --mode elastic-video --no-rebalance -o "video.dub.mp4"
```

---

#### 9.5.5 字幕嵌入规范（多人场景简化）

**技能描述**：在合成视频时嵌入字幕，多人场景需要简化说话人标签

**⚠️ 关键规则**：
- TTS 字幕中使用完整标签：`[Speaker:Instructor]` 用于音色映射
- 嵌入视频的字幕需要简化：`[Instructor]` 更简洁易读

**处理流程：**

```python
def prepare_display_subtitle(tts_srt_path, output_path):
    """
    将 TTS 字幕转换为显示字幕
    - 去除 "Speaker:" 前缀
    - 保留说话人名称用于区分
    """
    import srt
    
    with open(tts_srt_path, 'r', encoding='utf-8') as f:
        items = list(srt.parse(f.read()))
    
    for item in items:
        # [Speaker:Instructor] → [Instructor]
        item.content = re.sub(
            r'\[Speaker:(\w+)\]',
            r'[\1]',
            item.content
        )
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(srt.compose(items))
```

**命令示例：**

```bash
# 1. 先生成显示字幕（简化标签）
python -c "
import srt, re
with open('tts_mode_b.srt', 'r', encoding='utf-8') as f:
    items = list(srt.parse(f.read()))
for item in items:
    item.content = re.sub(r'\[Speaker:(\w+)\]', r'[\1]', item.content)
with open('display.srt', 'w', encoding='utf-8') as f:
    f.write(srt.compose(items))
"

# 2. 合成视频时嵌入简化后的字幕
python -m pyvideotrans merge tts_mode_b.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --voice-map voice_map.json \
  --keep-brackets \
  --mode elastic-video \
  --subtitle-path display.srt \
  --subtitle-lang zh \
  -o video.dub.mp4
```

**字幕对比：**

| 用途 | 文件 | 格式 | 示例 |
|------|------|------|------|
| TTS 合成 | `tts_mode_b.srt` | `[Speaker:Name]` | `[Speaker:Instructor] 大家好` |
| 视频嵌入 | `display.srt` | `[Name]` | `[Instructor] 大家好` |
| 单人场景 | `display.srt` | 无标签 | `大家好` |

**单人场景处理：**
```python
# 单人场景可以完全去除标签
for item in items:
    item.content = re.sub(r'\[Speaker:\w+\]\s*', '', item.content)
```

---

## 10. Agent 反省机制

### 10.1 反省机制概述

**目标**：让 Agent 能够从每次任务中学习，积累经验，持续改进。

**核心能力**：
- 自动识别问题和改进机会
- 提取可复用的经验和技能
- 更新知识库和文档
- 在未来任务中应用学到的经验

---

### 10.2 反省触发条件

Agent 应在以下情况下自动触发反省：

1. **任务完成后**：
   - 每次视频配音完成
   - 每次问题解决完成
   - 每次功能开发完成

2. **遇到错误或异常时**：
   - TTS 合成失败
   - 视频处理错误
   - 参数配置问题

3. **用户反馈问题时**：
   - 用户报告质量问题
   - 用户提出改进建议
   - 用户遇到使用困难

4. **发现新的优化机会时**：
   - 发现更好的处理方法
   - 发现参数优化空间
   - 发现流程改进机会

---

### 10.3 反省流程

```
任务执行
    ↓
任务回顾 → 分析刚完成的任务
    ↓
问题识别 → 发现处理中的问题和改进点
    ↓
经验提取 → 总结可复用的经验和教训
    ↓
技能更新 → 将新学到的技能添加到知识库
    ↓
文档更新 → 更新相关文档和指南
    ↓
下次应用 → 在后续任务中应用新技能
```

---

### 10.4 学习记录格式

每次反省后，Agent 应该记录：

```markdown
## 学习记录 - [日期时间]

### 任务描述
- 任务类型：[视频配音/问题解决/功能开发]
- 处理内容：[具体描述]
- 输出结果：[成功/失败/部分成功]

### 遇到的问题
- 问题1：[描述]
  - 原因：[分析]
  - 解决方案：[具体方法]
  - 效果：[结果评估]

### 新学到的技能
- 技能名称：[具体技能]
- 应用场景：[何时使用]
- 实现方法：[具体步骤]
- 置信度：[高/中/低]

### 改进建议
- 流程优化：[建议]
- 工具改进：[建议]
- 文档更新：[需要更新的内容]

### 下次注意事项
- [重要提醒]
- [避免的错误]
- [最佳实践]
```

---

### 10.5 反省机制实现

#### 10.5.1 反省触发器

```python
class AgentReflection:
    def __init__(self):
        self.learning_log = "agent_manual_v2_lessons_learned.md"
        self.improvements_log = "agent_manual_v2_improvements.md"
    
    def trigger_reflection(self, trigger_type, context):
        """触发反省机制"""
        if trigger_type == "task_completed":
            self.reflect_on_task(context)
        elif trigger_type == "error_encountered":
            self.reflect_on_error(context)
        elif trigger_type == "user_feedback":
            self.reflect_on_feedback(context)
        elif trigger_type == "optimization_found":
            self.reflect_on_optimization(context)
```

#### 10.5.2 经验提取

```python
def extract_lessons(self, context):
    """提取经验教训"""
    lessons = []
    
    # 分析处理模式选择
    if context.get("mode") == "elastic-video":
        if context.get("stretch_ratio", 1.0) > 1.3:
            lessons.append(
                "视频拉伸超过30%，下次建议提醒用户可能的画面影响"
            )
    
    # 分析处理时间
    if context.get("duration", 0) > 600:  # 10分钟
        lessons.append(
            "处理时间较长，考虑优化分段策略或降低并发"
        )
    
    # 分析文件大小
    if context.get("output_size", 0) > 1000:  # 1GB
        lessons.append(
            "输出文件较大，下次主动提供压缩选项"
        )
    
    return lessons
```

#### 10.5.3 技能更新

```python
def update_skills_database(self, new_skill):
    """更新技能数据库"""
    skill_entry = {
        "name": new_skill["name"],
        "description": new_skill["description"],
        "use_cases": new_skill["use_cases"],
        "implementation": new_skill["implementation"],
        "learned_from": new_skill["context"],
        "confidence": 0.7,  # 初始置信度
        "usage_count": 0
    }
    
    # 添加到技能库
    self.skills_db.append(skill_entry)
    
    # 更新 agent_manual_v2.md
    self.update_manual_with_skill(skill_entry)
```

---

### 10.6 反省执行示例

**场景**：完成 Mode B 视频配音任务

```python
# 任务完成后自动反省
task_result = {
    "type": "video_dubbing",
    "mode": "elastic-video",
    "duration": 480,  # 8分钟
    "stretch_ratio": 1.15,
    "output_size": 650,  # MB
    "success": True,
    "issues": ["处理时间较长", "文件大小偏大"]
}

agent.trigger_reflection("task_completed", task_result)
```

**生成的学习记录**：

```markdown
## 学习记录 - 2024-11-30 14:33

### 任务描述
- 任务类型：视频配音 (Mode B)
- 处理内容：Maya 教学视频，32分钟
- 输出结果：成功，视频拉伸15%

### 遇到的问题
- 问题1：处理时间较长（8分钟/段）
  - 原因：视频重新编码耗时
  - 解决方案：分段处理，降低并发数
  - 效果：成功完成，但仍需优化

- 问题2：输出文件较大（650MB）
  - 原因：重新编码导致文件增大
  - 解决方案：开发自动压缩脚本
  - 效果：用户可根据需求选择压缩级别

### 新学到的技能
- 技能名称：网络传输优化
- 应用场景：大文件输出时自动提供压缩选项
- 实现方法：检测文件大小，提供多级压缩选择
- 置信度：高

### 改进建议
- 流程优化：对于长视频，主动建议分段处理
- 工具改进：添加处理时间预估功能
- 文档更新：更新 Mode B 的性能指标说明

### 下次注意事项
- 长视频优先询问用户是否接受较长处理时间
- 主动提供文件大小优化选项
- 在处理过程中提供更详细的进度信息
```

---

### 10.7 持续改进循环

```
任务执行 → 结果分析 → 问题识别 → 解决方案 → 技能提取 → 文档更新 → 下次应用
    ↑                                                                    ↓
    ←←←←←←←←←←←←←←← 验证效果 ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
```

**关键指标**：
- **学习效率**：新技能的获取速度
- **应用成功率**：学到的技能在实际中的有效性
- **问题解决能力**：遇到类似问题时的处理改进
- **用户满意度**：用户对 Agent 表现的反馈

---

### 10.8 反省质量评估

Agent 应该定期评估自己的反省质量：

1. **学习记录完整性**：
   - 是否记录了所有重要问题
   - 是否提取了可复用的经验
   - 是否提出了具体的改进建议

2. **技能应用效果**：
   - 新学到的技能是否在后续任务中使用
   - 使用后是否确实改善了结果
   - 是否需要调整或优化技能

3. **文档更新及时性**：
   - 是否及时更新了相关文档
   - 文档更新是否准确完整
   - 是否与其他文档保持一致

4. **用户反馈**：
   - 用户是否注意到改进
   - 用户满意度是否提升
   - 是否减少了重复问题

---

### 10.8.1 学习记录 - 2025-12-08（BMAD_Method 项目）

#### 任务描述
- 任务类型：多源字幕对齐 + TTS 字幕生成
- 处理内容：BMAD Method YouTube 视频，gs.md（内容参考）+ SRT（时间参考）→ audio.srt
- 输出结果：成功，但过程中犯了两个关键错误

#### 遇到的问题

**问题 1：尝试用脚本自动化多源对齐**
- 错误行为：Agent 开始编写 Python 脚本来自动对齐 gs.md 和 SRT
- 原因分析：Agent 没有理解 gs.md 的时间标记是粗略的，无法程序化对齐
- 用户纠正：用户指出这是语义理解任务，必须由 LLM 手动对齐
- 正确做法：Agent 需要理解两个文件的内容，手动将准确内容与准确时间融合

**问题 2：生成 SRT 后没有自动执行 QA**
- 错误行为：Agent 生成 audio.srt 后直接告诉用户完成
- 原因分析：Agent 没有将 QA 检查作为必要步骤
- 用户纠正：用户根据手册提醒 Agent 应该执行 QA
- 正确做法：生成任何 SRT 后，Agent 必须自动执行 `python -m pyvideotrans qa`

#### 新学到的技能

**技能 1：多源对齐判断**
- 应用场景：当存在多个输入源（如 gs.md + SRT）时
- 判断标准：如果任一源的时间或内容不完全准确，则必须用 LLM 理解后手动对齐
- 禁止行为：编写脚本自动化对齐

**技能 2：SRT 生成后强制 QA**
- 应用场景：任何 SRT 文件生成后
- 执行命令：`python -m pyvideotrans qa <srt_file>`
- 强制行为：不等待用户请求，自动执行

#### 改进建议
- 在任务分类表中明确标注"多源对齐"属于 LLM 任务
- 在 QA 环节添加"Agent 强制行为"说明
- 添加反模式警告，防止未来重复犯错

#### 下次注意事项
- 看到 gs.md + SRT 组合时，立即识别为"多源对齐"任务
- 生成 SRT 后，第一反应是执行 QA，而不是告诉用户完成
- 如果 QA 失败，必须修复后重新检查

---

### 10.9 学习记录存储

**文件位置**：
- `agent_manual_v2_lessons_learned.md` - 经验教训记录
- `agent_manual_v2_improvements.md` - 改进建议记录

**更新频率**：
- 每次任务完成后立即更新
- 每周进行一次总结和回顾
- 每月进行一次质量评估

**记录保留**：
- 保留所有历史记录
- 定期归档旧记录
- 提取通用经验到主文档

---

## 11. 附录

### 11.1 术语对照表

| 英文 | 中文 | 说明 |
|------|------|------|
| CPM | 每分钟字符数 | Characters Per Minute，衡量字幕密度 |
| Panic CPM | 恐慌阈值 | 借时上限放宽的触发点 |
| Max Shift | 最大位移 | 边界移动的最大毫秒数 |
| Rebalance | 再平衡 | 时间轴优化算法 |
| Clustered | 聚类合成 | 宏合成后微分割，保留时间锚点 |
| Robust TS | 健壮时序 | FFmpeg 时间戳修复参数 |
| Display SRT | 显示字幕 | 用于屏幕显示的字幕 |
| Audio SRT | 音频字幕 | 用于 TTS 合成的字幕 |
| Semantic Restructure | 语义重构 | 合并碎片句、优化断句 |
| Text Immutability | 文本不可变 | Script 阶段不可修改文本内容 |
| LLM-First | LLM 优先 | 语义操作必须在脚本执行之前 |
| Voice Map | 音色映射 | 说话人到 TTS 音色的映射表 |
| Speaker Tag | 说话人标签 | `[Speaker:Name]` 格式的标记 |

---

### 11.2 推荐音色列表

#### 中文男声

| 音色 ID | 特点 | 推荐场景 |
|---------|------|----------|
| `zh-CN-YunjianNeural` | 稳定、自然 | **通用推荐**，教程、旁白 |
| `zh-CN-YunxiNeural` | 年轻、活力 | 科技、游戏内容 |
| `zh-CN-YunyangNeural` | 专业、沉稳 | 新闻、商务内容 |

#### 中文女声

| 音色 ID | 特点 | 推荐场景 |
|---------|------|----------|
| `zh-CN-XiaoxiaoNeural` | 温柔、清晰 | **通用推荐**，教程、客服 |
| `zh-CN-XiaoyiNeural` | 亲切、自然 | 故事、对话 |
| `zh-CN-XiaohanNeural` | 专业、标准 | 新闻、播报 |

#### 采样率

- **推荐：** `48000` Hz（高质量）
- **备选：** `24000` Hz（节省空间）

**注意：** 所有音色均已在 48000 Hz 和 24000 Hz 下验证通过。

---

### 11.3 质量检查清单

#### LLM 阶段检查

- [ ] SRT 结构有效（通过 `srt.parse()` 验证）
- [ ] 术语保留率 100%（随机抽样 ≥20 段）
- [ ] Mode A: 单块 ≤250 字符，≤15 秒
- [ ] Mode B: 单块 ≤100 字符，≤6 秒
- [ ] 说话人标签格式正确（多人场景）
- [ ] 无噪声符号（`*`, `` ` ``, 零宽字符）
- [ ] 无元标记（`[音乐]`, `[掌声]` 等）

#### Script 阶段检查

- [ ] 文本内容未变（rebalance 后）
- [ ] Mode A: CPM ≤300
- [ ] Mode B: CPM 400+ 可接受
- [ ] 所有 WAV 文件存在且非零大小
- [ ] 视频合流成功（退出码 0）
- [ ] 同步偏差 ≤180ms（sync_audit）

#### 多人场景检查

- [ ] 所有片段有说话人标签
- [ ] voice_map.json 包含所有说话人
- [ ] voice_map.json 包含 DEFAULT
- [ ] 日志显示正确的音色映射
- [ ] 不同说话人使用不同音色

---

### 11.4 常见问题 FAQ

#### Q1: 何时使用 LLM，何时使用脚本？

**A:** 参考决策矩阵（第 2.1 节）：
- **涉及文本内容理解** → 使用 LLM
- **涉及时间/音频/视频计算** → 使用脚本

#### Q2: 如何判断是单人还是多人场景？

**A:** 参考说话人场景识别（第 2.2 节）：
- 检查对话标记、说话人标签、破折号前缀
- 检查问答结构
- 至少 2 个指标 → 多人场景

#### Q3: 何时跳过再平衡？

**A:** 以下情况自动跳过：
- 启用 `--clustered` 模式
- 启用 `--auto-dual-srt` 模式
- 手动指定 `--no-rebalance`

#### Q4: 如何处理高密度字幕（CPM ≥ 900）？

**A:** 参考场景配置模板（第 5.3 节）：
1. 在 LLM 阶段降低单块上限（200 字符，12 秒）
2. 在再平衡阶段扩大窗口（target_cpm=160, max_shift=6000）

#### Q5: Edge TTS 失败如何处理？

**A:** 参考故障排除（第 8.1 节）：
1. 降低并发（--jobs 1）
2. 启用严格模式（--no-fallback）
3. 预检网络连接

#### Q6: 如何配置 LLM 双轨模式？

**A:** 设置环境变量：
```bash
export PYVIDEOTRANS_LLM_PROVIDER="openai"
export PYVIDEOTRANS_LLM_API_KEY="sk-..."
export PYVIDEOTRANS_LLM_BASE_URL="https://api.openai.com/v1"
export PYVIDEOTRANS_LLM_MODEL="gpt-4o-mini"
```
然后使用 `--auto-dual-srt --llm-dual-srt`

#### Q7: 如何验证多说话人配置？

**A:** 参考多人工作流示例（第 4.4 节）：
1. 检查 SRT 标签：`grep -E "\[Speaker:" semantic_fixed.srt`
2. 统计说话人：`grep -oE "\[Speaker:[^\]]+\]" semantic_fixed.srt | sort | uniq -c`
3. 检查日志：`grep "SPEAKER_MAP" process.log`

#### Q8: Mode A 和 Mode B 有什么区别？

**A:** 参考 [2.0 快速决策表](#20-快速决策表)，核心差异：
- **Mode A**：视频时长不变，音频可能压缩，处理快
- **Mode B**：视频时长增加 10-30%，音质自然，处理慢 5-10 倍

#### Q9: 如何使用 Mode B？

**A:** 参考 [5.5 Mode B 配音](#55-mode-b---自然语速配音质量优先)：
```bash
python -m pyvideotrans merge semantic_fixed.srt video.mp4 \
  --backend edge_tts --voice zh-CN-YunjianNeural \
  --mode elastic-video --no-rebalance -o video.dub.mp4
```

#### Q10: Mode B 处理太慢/拉伸过度怎么办？

**A:** 参考 [8.8-8.9 故障排除](#88-mode-b-视频拉伸过度)：
- 降低并发：`--jobs 1`
- 分段处理后合并
- 降低单块上限（≤100 字符）
- 或改用 Mode A

#### Q11: 如何合并 Mode B 分段？

**A:** 参考 [3.3.1 分段处理](#331-mode-b-分段处理与自动合并)：
```bash
ffmpeg -f concat -safe 0 -i concat_list.txt -c copy final_output.mp4
```

#### Q12: 用户只提供文件夹，如何自动识别文件？

**A:** 参考 [9.5.4 TTS 字幕生成工作流](#954-tts-字幕生成工作流用户请求处理)：
- **内容参考文件**：`gs.md` 或 `transcript.md`（内容准确，时间粗略）
- **时间参考文件**：原始 `.srt` 文件（时间精确，内容可能有误）
- Agent 自动融合两者生成高质量 TTS 字幕

#### Q13: 多人场景字幕嵌入时如何简化标签？

**A:** 参考 [9.5.5 字幕嵌入规范](#955-字幕嵌入规范多人场景简化)：
- TTS 字幕：`[Speaker:Instructor]`（用于音色映射）
- 显示字幕：`[Instructor]`（去除 "Speaker:" 前缀）
- 单人场景：可完全去除标签

#### Q14: yt-dlp 下载时文件夹应该用什么命名？

**A:** 使用视频标题 `%(title)s` 作为文件夹名，**必须加 `--restrict-filenames`**：
```bash
yt-dlp --restrict-filenames -o "data/input/%(title)s/%(title)s.%(ext)s" "URL"
```
- `--restrict-filenames` 会将特殊字符（空格、冒号、问号等）替换为下划线或移除
- 避免 shell 脚本转义错误和路径解析失败
- 不使用视频 ID，因为标题更直观易识别

---

### 11.5 参考文档

- **代码仓库：** `pyvideotrans/`
- **参数标准：** `.kiro/specs/agent-orchestration-system/parameter-standards.md`
- **需求规范：** `.kiro/specs/agent-orchestration-system/requirements.md`
- **多说话人协议：** `plans/04_Multi_Speaker_Protocol_v1.0.md`
- **语义优先工作流：** `plans/03_Semantic_First_Workflow_v1.0.md`
- **决策矩阵：** `plans/02_Decision_Matrix_v1.0.md`

---

### 11.6 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v2.4.1 | 2025-12-09 | **Edge TTS 版本问题**：7.2.3 有 bug，需降级到 7.2.1 |
| v2.4.0 | 2025-12-08 | **关键反模式警告**：多源对齐禁止脚本自动化、SRT 生成后强制 QA |
| v2.3.0 | 2025-12-01 | 新增多源字幕融合工作流、字幕嵌入简化规范、yt-dlp 标题命名 |
| v2.2.0 | 2025-12-01 | 统一 Mode A/B 参数标准，消除矛盾，精简冗余 |
| v2.1.0 | 2024-11-30 | 添加 Agent 技能库和反省机制 |
| v2.0.0 | 2024-11-30 | 完全重构，建立 LLM-First 原则和决策矩阵 |
| v1.0.0 | 2024-11-29 | 初始版本 |

---

### 11.7 贡献指南

#### 文档更新流程

1. **修改前检查：** 确认修改不与 `parameter-standards.md` 冲突
2. **修改文档：** 更新相应章节
3. **更新版本：** 增加版本号，记录变更历史
4. **同步引用：** 更新所有引用此文档的文件
5. **验证：** 运行 `scripts/validate_docs.sh` 验证一致性

#### 参数变更流程

1. **修改代码：** 更新 CLI 默认值
2. **更新 parameter-standards.md：** 记录新的默认值
3. **更新 agent_manual_v2.md：** 同步参数表
4. **更新示例：** 修改所有命令示例
5. **验证：** 确保所有文档一致

---

## 结语

本手册旨在为 PyVideoTrans Agent 提供清晰、可执行的操作指南。核心原则是：

1. **LLM-First：** 语义操作必须在脚本执行之前
2. **Text Immutability：** Script 阶段严格不可变文本
3. **Decision Matrix：** 明确任务分类，避免工具误用
4. **Multi-Speaker Protocol：** 标准化多人场景处理

遵循本手册，Agent 可以高效、准确地完成端到端配音任务。

---

**文档结束**

