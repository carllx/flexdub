# Implementation Plan: Universal Agent Architecture

## Status: ✅ 完成

本重构已于 2025-12-19 完成。

---

- [x] 1. 基础设施搭建
  - [x] 1.1 创建认知配置 `.agent/config.md`
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  - [x] 1.2 创建 MCP 服务器 `flexdub/mcp/server.py`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  - [x] 1.3 实现项目分析器 `flexdub/core/analyzer.py`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 2. 技能层迁移
  - [x] 2.1 语义精炼技能 `.agent/skills/semantic_refine/`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  - [x] 2.2 自动配音技能 `.agent/skills/auto_dub/`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_
  - [x] 2.3 故障诊断技能 `.agent/skills/diagnosis/`
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  - [x] 2.4 视频下载技能 `.agent/skills/video_download/`

- [x] 3. 工作流层建立
  - [x] 3.1 创建配音工作流 `.agent/workflows/dubbing.md`
    - _Requirements: 5.1_
  - [x] 3.2 实现工作流状态管理 `flexdub/pipelines/workflow.py`
    - _Requirements: 5.2, 5.3, 5.4_

- [x] 4. 渐进式披露架构
  - [x] 4.1 创建技能索引 `.agent/skills/index.yaml`
  - [x] 4.2 实现技能加载器 `.agent/loader.py`

- [x] 5. 清理与集成
  - [x] 5.1 瘦身 Agent Manual (v2 → legacy, 创建 v3)
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  - [x] 5.2 MCP 工具链验证 `scripts/test_mcp_tools.py`
    - _Requirements: 8.1, 8.2, 8.3, 8.4_
  - [x] 5.3 删除 macOS Say 后端
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 6. 最终验收
  - [x] 6.1 运行测试套件 (17 passed)
  - [x] 6.2 验证技能加载器

---

## 产出物

| 类型 | 文件 |
|------|------|
| 认知层 | `.agent/config.md`, `.agent/loader.py` |
| 技能层 | `.agent/skills/*/SKILL.md`, `index.yaml` |
| 工作流 | `.agent/workflows/dubbing.md` |
| MCP | `flexdub/mcp/server.py` |
| 核心 | `flexdub/core/analyzer.py`, `qa.py` |
| 管线 | `flexdub/pipelines/workflow.py` |
| 文档 | `agent_manual.md` |
