# FlexDub Agent 认知配置

**版本**: v3.0.0  
**架构**: Universal Agent Architecture

---

## 项目概述

FlexDub 是一个弹性配音管线，用于视频本地化。核心能力：
- 字幕时间轴再平衡（基于 CPM 优化）
- TTS 合成（Edge TTS、Doubao TTS）
- 弹性音频处理（静音移除、时间拉伸、填充）
- 自动音视频合流与字幕嵌入

---

## 核心原则

### 1. Thick Code, Thin Prompts
- **禁止**：在 Markdown 中写业务逻辑
- **必须**：所有逻辑封装为 Python 函数，Agent 仅调用工具

### 2. LLM-First 原则
- 语义操作（文本清洗、断句、说话人识别）在 LLM 阶段完成
- Script 阶段只处理时间轴和媒体

### 3. 文本不可变原则
- 进入 Script 阶段后，文本内容严格不可变
- 只有 `rewrite` 命令可以修改文本

---

## 目录结构

```
flexdub/
├── core/           # 核心算法
│   ├── analyzer.py # 项目分析器（决策矩阵）
│   ├── audio.py    # 音频处理
│   ├── qa.py       # 质量检查
│   ├── rebalance.py# CPM 再平衡
│   └── subtitle.py # 字幕处理
├── mcp/            # MCP 服务器接口
│   └── server.py   # MCP 工具注册
├── pipelines/      # 高级工作流
│   ├── dubbing.py  # 配音管线
│   └── elastic_video.py # 弹性视频管线
└── cli/            # CLI 入口

.agent/
├── config.md           # 本文件（认知配置）
├── workflows/          # 工作流定义（Markdown 驱动）
│   └── dubbing.md      # 配音工作流
└── skills/             # 技能包（渐进式披露架构）
    ├── index.yaml      # 技能索引（第一层：元数据）
    ├── video_download/ # YouTube 视频下载
    │   └── SKILL.md
    ├── semantic_refine/# 语义精炼
    │   ├── SKILL.md
    │   └── scripts/terminology.py
    ├── auto_dub/       # 自动配音
    │   └── SKILL.md
    └── diagnosis/      # 故障诊断
        ├── SKILL.md
        └── scripts/diagnose.py

data/
├── input/          # 输入项目（视频 + 字幕）
└── output/         # 输出产物
```

---

## Agent 行为规范

### 禁止行为
1. ❌ 直接修改 `data/output/` 中的文件
2. ❌ 在 Script 阶段修改文本内容
3. ❌ 跳过 QA 检查直接输出
4. ❌ 猜测参数值

### 必须行为
1. ✅ 使用 MCP 工具与 Python 逻辑交互
2. ✅ 生成 SRT 后自动执行 QA 检查
3. ✅ 遵循决策矩阵选择处理模式
4. ✅ 保留专业术语英文原文

---

## 工具调用指南

### 项目分析
```python
# 使用 MCP 工具
result = call_tool("analyze_project", {"project_dir": "data/input/MyProject"})
# 返回: {"mode": "A", "cpm": 245, "duration_ms": 120000, ...}
```

### 配音执行
```python
# 使用 MCP 工具
result = call_tool("run_auto_dub", {
    "project_dir": "data/input/MyProject",
    "mode": "elastic-audio",
    "voice": "zh-CN-YunjianNeural"
})
```

### 故障诊断
```python
# 使用 MCP 工具
result = call_tool("diagnose_error", {"error_report": "path/to/error.json"})
# 返回: {"cause": "...", "fix_steps": [...]}
```

---

## 模式选择决策

| 条件 | 推荐模式 | 原因 |
|------|---------|------|
| CPM ≤ 300 | Mode A | 音频可压缩适配 |
| CPM > 300 | Mode B | 需要自然语速 |
| 视频时长固定要求 | Mode A | 保持原始时长 |
| 音质优先 | Mode B | 自然朗读 |

---

## 参考文档

- 操作手册: `agent_manual.md`
- 技能详情: `.agent/skills/*/SKILL.md`
- CLI 参考: `python -m flexdub --help`
