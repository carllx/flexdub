# FlexDub 架构重构路线图 (v2 -> Universal Agent)

> **状态**: ✅ 已完成  
> **归档日期**: 2025-12-20  
> **原位置**: `Refactor_suggestions/Refactor Roadmap.md`

---

## 阶段 1: 基础设施搭建 (Infrastructure) ✅ 完成

目标：建立 Agent 的认知基础和与 Python 代码交互的标准接口。

- [x] **1.1 初始化认知文件**
    
    - 创建 `.agent/config.md`。
        
    - 内容：提取 `README.md` 和架构文档的核心信息，定义项目结构、关键目录用途。
        
    - 关键点：明确告诉 Agent "不要直接修改 output 文件，使用工具操作"。
        
- [x] **1.2 建立 MCP 服务器框架**
    
    - 创建目录 `flexdub/mcp/`。
        
    - 创建 `flexdub/mcp/server.py`。
        
    - 实现基础的 MCP Server 类（使用 `fastmcp` 或标准 `stdio` 通信模式）。
        
    - 依赖：确保 `requirements.txt` 支持 MCP 相关库（如需）。
        
- [x] **1.3 实现核心工具: `ProjectAnalyzer`**
    
    - **迁移逻辑**: 从 `agent_manual.md` 的 "2. 决策矩阵" 中提取逻辑。
        
    - **新建代码**: `flexdub/core/analyzer.py`。
        
    - **功能**:
        
        - `get_video_metrics(path)`: 返回时长、音频密度(CPM)。
            
        - `recommend_mode(metrics)`: 包含原文档中 "CPM > 300 -> Mode B" 的硬逻辑。
            
    - **MCP 暴露**: 在 `server.py` 中注册 `analyze_project` 工具。
        

## 阶段 2: 技能层迁移 (Skill Migration) ✅ 完成

目标：将 Markdown 中的伪代码转化为确定性的 Python 技能包。

- [x] **2.1 技能: 语义精炼 (Semantic Refinement)**
    
    - 创建目录 `.agent/skills/semantic_refine/`。
        
    - 创建 `SKILL.md`: 描述何时使用（"翻译生硬"、"需要断句优化"）。
        
    - **迁移逻辑**:
        
        - 从 v2 手册提取 "术语保留规则" 到 `.agent/skills/semantic_refine/terminology.py`。
            
        - 术语列表包含 3D/2D 软件、游戏引擎、工具名称、技术术语等。
            
- [x] **2.2 技能: 自动化配音闭环 (Auto-Dub Workflow)**
    
    - 创建目录 `.agent/skills/auto_dub/`。
        
    - **迁移逻辑**: 从 v2 手册提取 "3.1.2 强制 QA 环节" 和 "8. 故障排除"。
        
    - **核心代码**: 已有 `flexdub/pipelines/dubbing.py` 和 `elastic_video.py`。
        
    - **MCP 暴露**: `analyze_project` 和 `run_qa_check` 工具已注册。
        
- [x] **2.3 技能: 故障诊断 (Troubleshooting)**
    
    - 创建目录 `.agent/skills/diagnosis/`。
        
    - **迁移逻辑**: 将 `agent_manual.md` 中所有的错误码对照表移动到此目录。
        
    - 创建 `diagnose.py`: 解析 `error_report.json`，返回人类可读的修复建议。
        
    - **MCP 暴露**: `diagnose_error` 工具已注册。
        

## 阶段 3: 清理与集成 (Cleanup & Integration) ✅ 完成

目标：移除旧架构的脚手架，验证新架构。

- [x] **3.1 验证 MCP 工具链**
    
    - 编写脚本 `scripts/test_mcp_tools.py`，模拟 Agent 调用 `analyze_project` 和 `diagnose_error`。
        
    - 确保返回的是结构化 JSON 数据。
        
    - 测试结果: 4 通过, 0 失败。
        
- [x] **3.2 瘦身 Agent Manual**
    
    - 将 `agent_manual.md` 重命名为 `agent_manual_legacy.md` (备份, 4580 行)。
        
    - 创建新的 `agent_manual.md` (146 行, Thin Prompt)。
        
    - 内容仅包含：Role 定义、引用 `.agent/config.md`、以及简单的工具调用指引。
        
- [x] **3.3 最终验收**
    
    - 所有 17 个单元测试通过。
        
    - MCP 工具链验证通过。
        
    - macOS Say 后端已移除，Edge TTS 失败时直接停止。
        

## 阶段 4: 工作流层与渐进式披露 ✅ 完成 (新增)

目标：建立 Markdown 驱动的工作流编排和渐进式披露架构。

- [x] **4.1 创建配音工作流**
    
    - 创建 `.agent/workflows/dubbing.md`
        
    - 定义 6 步骤编排: 项目准备 → 分析 → 语义重构 → QA → 配音 → 审计
        
    - 包含 YAML Frontmatter 元数据 (name, description, triggers)
        
- [x] **4.2 实现工作流状态管理**
    
    - 创建 `flexdub/pipelines/workflow.py`
        
    - WorkflowState 数据类追踪状态
        
    - load/save_workflow_state 持久化到 JSON
        
- [x] **4.3 建立渐进式披露架构**
    
    - 创建 `.agent/skills/index.yaml` 技能索引（第一层元数据）
        
    - 为所有 SKILL.md 添加 YAML Frontmatter
        
    - 创建 `.agent/loader.py` 技能加载器
        
- [x] **4.4 规范化技能目录结构**
    
    - 将 Python 脚本移动到 `scripts/` 子目录
        
    - 统一目录结构: SKILL.md + scripts/ + references/
        
- [x] **4.5 新增视频下载技能**
    
    - 创建 `.agent/skills/video_download/SKILL.md`
        
    - 包含 yt-dlp 命令指南

---

## 附录：迁移对照表

| **原 Markdown 章节** | **新架构位置** | **形式** |
| ----------------- | ---------------------------------------- | -------------- |
| 2. 决策矩阵 | `flexdub/core/analyzer.py` | Python Code |
| 3.1 标准工作流 | `.agent/workflows/dubbing.md` | Markdown 工作流 |
| 3.1 工作流状态 | `flexdub/pipelines/workflow.py` | Python Code |
| 3.1.1 语义重构规范 | `.agent/skills/semantic_refine/SKILL.md` | Context/Prompt |
| 4.2 说话人标记 | `.agent/skills/semantic_refine/SKILL.md` | Context/Prompt |
| 7. 参数标准 | 工具 Docstrings / `pydantic` Models | Code Schema |
| 8. 故障排除 | `.agent/skills/diagnosis/` | Knowledge Base |
| YouTube 下载 | `.agent/skills/video_download/SKILL.md` | Context/Prompt |

---

## 最终架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    认知层 (Cognitive Layer)                  │
├─────────────────────────────────────────────────────────────┤
│  .agent/config.md          项目级上下文                       │
│  .agent/skills/index.yaml  技能索引（渐进式披露第一层）         │
│  .agent/workflows/*.md     工作流定义（Markdown 驱动）         │
│  .agent/loader.py          技能加载器                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    技能层 (Skills Layer)                     │
├─────────────────────────────────────────────────────────────┤
│  SKILL.md (YAML Frontmatter)  技能定义（第二层：按需加载）     │
│  scripts/*.py                 确定性执行脚本（第三层）         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    执行层 (Execution Layer)                  │
├─────────────────────────────────────────────────────────────┤
│  flexdub/mcp/server.py       MCP 工具接口                    │
│  flexdub/pipelines/*.py      Python 管线                     │
│  flexdub/core/*.py           核心算法                        │
└─────────────────────────────────────────────────────────────┘
```
