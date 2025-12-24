# 实现计划: GS 语义矫正 SRT 翻译

## 概述

本实现计划将设计文档中的组件转化为可执行的编码任务。核心是创建一个使用 gs.md 作为语义背景上下文，通过 LLM 逐步矫正 SRT 翻译的系统。

**关键设计决策**：
- gs.md 作为**背景参考信息**，不是直接替换来源
- **分段处理**大文件，保持上下文连贯
- **LLM 驱动**翻译矫正，确保中国人可理解
- 支持**中断恢复**，大文件处理更可靠

## 任务列表

- [x] 1. 创建核心数据模型
  - [x] 1.1 定义数据类
    - 在 `flexdub/core/semantic_refine.py` 创建新模块
    - 实现 `SemanticContext` 数据类（core_topic, domain, terminology, speakers, key_concepts）
    - 实现 `SpeakerProfile` 数据类（name, role, speaking_style, first_appearance_ms）
    - 实现 `Chunk` 数据类（index, items, start_ms, end_ms, context_summary）
    - 实现 `ProcessingState` 数据类（用于检查点恢复）
    - _Requirements: 1.1, 2.1_
  - [ ]* 1.2 编写数据模型属性测试
    - **Property 2: 条目数量保持**
    - **Validates: Requirements 7.5**

- [x] 2. 实现 Context Extractor（上下文提取器）
  - [x] 2.1 创建 ContextExtractor 类
    - 实现 `extract(gs_content)` 方法，提取语义上下文
    - 实现 `extract_terminology(content)` 方法，提取术语映射
    - 实现 `extract_speakers(content)` 方法，提取说话人信息
    - 支持不固定的 gs.md 结构
    - _Requirements: 1.1, 1.2, 1.3_
  - [ ]* 2.2 编写 ContextExtractor 属性测试
    - **Property 3: 术语一致性**
    - **Validates: Requirements 5.1, 5.3**

- [x] 3. 实现 Chunk Manager（分段管理器）
  - [x] 3.1 创建 ChunkManager 类
    - 实现 `create_chunks(srt_items)` 方法，将 SRT 分成 20-50 条目的 chunks
    - 实现 `get_context_for_chunk(chunk_index)` 方法，获取上下文
    - 实现 `save_checkpoint(chunk_index, result)` 方法，保存检查点
    - 实现 `load_checkpoint()` 方法，加载检查点
    - _Requirements: 2.1, 2.2, 2.3, 8.2, 8.3_
  - [ ]* 3.2 编写 ChunkManager 属性测试
    - **Property 6: 分段处理完整性**
    - **Property 7: 跨 Chunk 上下文连贯性**
    - **Property 8: 检查点和可恢复性**
    - **Validates: Requirements 2.1, 2.2, 2.3, 8.2, 8.3**

- [x] 4. 检查点 - 确保基础组件测试通过
  - 运行 `pytest tests/` 确保基础组件测试通过
  - 如有问题请询问用户

- [x] 5. 实现 LLM Refiner（LLM 矫正器）
  - [x] 5.1 创建 LLMRefiner 类
    - 实现 `refine_chunk(chunk, previous_context)` 方法
    - 实现 `build_prompt(chunk, previous_context)` 方法，构建 LLM prompt
    - 实现 `parse_response(response)` 方法，解析 LLM 响应
    - Prompt 包含：背景信息、术语表、前文摘要、矫正要求
    - _Requirements: 3.1, 3.2, 3.3, 3.5_
  - [ ]* 5.2 编写 LLMRefiner 属性测试
    - **Property 1: 时间戳和索引不变性**
    - **Validates: Requirements 3.5, 7.5**

- [x] 6. 实现 Localization Reviewer（本地化审查器）
  - [x] 6.1 创建 LocalizationReviewer 类
    - 实现 `review(items)` 方法，审查翻译质量
    - 实现 `check_sentence_length(text)` 方法，检查句子长度
    - 实现 `LocalizationIssue` 数据类，记录问题
    - _Requirements: 4.1, 4.5_
  - [ ]* 6.2 编写 LocalizationReviewer 属性测试
    - **Property 4: 字符长度限制**
    - **Validates: Requirements 7.1, 7.2**

- [x] 7. 实现 Output Generator（输出生成器）
  - [x] 7.1 创建 OutputGenerator 类
    - 实现 `generate_srt(items, include_speaker_tags)` 方法
    - 实现 `generate_terminology_report(terminology)` 方法
    - 实现 `generate_processing_log(chunks, issues)` 方法
    - 说话人标签格式：`[Speaker: Name]`
    - _Requirements: 6.3, 7.1, 7.3, 7.4_
  - [ ]* 7.2 编写 OutputGenerator 属性测试
    - **Property 5: 有效 SRT 格式**
    - **Property 9: 说话人标签格式**
    - **Property 10: Markdown 清理**
    - **Validates: Requirements 6.3, 7.3, 7.4**

- [x] 8. 检查点 - 确保所有组件测试通过
  - 运行 `pytest tests/` 确保所有组件测试通过
  - 如有问题请询问用户

- [x] 9. 实现主流程 SemanticRefiner
  - [x] 9.1 创建 SemanticRefiner 类
    - 整合所有组件：ContextExtractor, ChunkManager, LLMRefiner, LocalizationReviewer, OutputGenerator
    - 实现 `refine(gs_path, srt_path, output_path)` 主方法
    - 实现进度报告和日志输出
    - _Requirements: 8.1, 8.4_

- [x] 10. 更新 CLI 接口
  - [x] 10.1 添加 semantic_refine 命令
    - 在 `flexdub/cli/__main__.py` 添加新命令
    - 参数：gs_path, srt_path, -o output, --include-speaker-tags, --checkpoint-dir
    - 输出：refined.audio.srt, terminology.yaml, processing.log
    - _Requirements: 7.4, 8.1_

- [x] 11. 集成测试
  - [x] 11.1 使用 Ian Bogost 项目进行端到端测试
    - 运行 `flexdub semantic_refine` 命令
    - 验证 414 条目完整处理
    - 验证术语一致性
    - 验证本地化审查结果
    - _Requirements: 2.1, 5.1_

- [x] 12. 最终检查点
  - 运行完整测试套件 `pytest tests/ -v`
  - 确保所有测试通过，如有问题请询问用户

## 备注

- 标记 `*` 的任务为可选测试任务，可跳过以加快 MVP 开发
- 每个任务都引用了具体的需求以便追溯
- 检查点确保增量验证
- 属性测试验证通用正确性属性
- 单元测试验证具体示例和边界情况

## LLM 集成说明

本功能需要 LLM API 支持。建议使用：
- **Claude API** - 推荐，语义理解能力强
- **OpenAI API** - 备选
- **本地 LLM** - 如 Ollama，用于离线场景

LLM 调用应支持：
- 重试机制（3 次）
- 超时处理
- 响应格式验证

