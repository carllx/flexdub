# Requirements Document: GS 语义矫正 SRT 翻译

## Introduction

本功能使用 gs.md 作为语义背景上下文，通过 LLM 逐步矫正 SRT 翻译质量。gs.md 的结构不固定，但包含人工校对的高质量翻译和核心思想。系统需要在处理大文件时保持专注，确保翻译对中国人可理解。

**核心设计理念**：
- gs.md 是**背景参考信息**，不是直接替换 SRT 的来源
- 使用**语义理解**而非机械对齐来矫正翻译
- **分段处理**大文件，保持上下文连贯性
- **本地化审查**确保中国人可理解

## Glossary

- **gs.md**: 人工校对的参考文档，包含高质量翻译、术语解释、核心思想（结构不固定）
- **SRT**: 原始字幕文件，包含机器翻译或初步翻译
- **Semantic_Refiner**: 语义矫正引擎，使用 LLM 理解 gs.md 并矫正 SRT
- **Context_Window**: 处理大文件时的上下文窗口，保持专注
- **Localization_Review**: 本地化审查，确保翻译对中国人自然可理解
- **Core_Concepts**: gs.md 中的核心思想和关键术语
- **Chunk**: 分段处理的单位，通常 20-50 条 SRT 条目

## Requirements

### Requirement 1: 语义理解 gs.md 背景

**User Story:** As a dubbing engineer, I want the system to understand gs.md as semantic context, so that it can guide SRT translation refinement intelligently.

#### Acceptance Criteria

1. WHEN loading gs.md, THE Semantic_Refiner SHALL extract core concepts, key terminology, and translation style
2. THE Semantic_Refiner SHALL handle gs.md with varying structures (no fixed format assumption)
3. WHEN gs.md contains speaker information, THE Semantic_Refiner SHALL extract speaker names and their speaking patterns
4. THE Semantic_Refiner SHALL identify the main topic and domain knowledge from gs.md

### Requirement 2: 分段处理大文件

**User Story:** As a dubbing engineer, I want the system to process large SRT files in focused chunks, so that translation quality remains consistent throughout.

#### Acceptance Criteria

1. WHEN SRT file exceeds 50 entries, THE Semantic_Refiner SHALL process in chunks of 20-50 entries
2. WHILE processing each chunk, THE Semantic_Refiner SHALL maintain context from previous chunks
3. THE Semantic_Refiner SHALL carry forward key terminology decisions across chunks
4. IF a sentence spans chunk boundaries, THE Semantic_Refiner SHALL handle it as a complete unit

### Requirement 3: LLM 驱动的翻译矫正

**User Story:** As a dubbing engineer, I want LLM to refine SRT translations using gs.md context, so that the output is more accurate and natural.

#### Acceptance Criteria

1. WHEN refining a chunk, THE Semantic_Refiner SHALL provide gs.md context to LLM
2. THE Semantic_Refiner SHALL instruct LLM to preserve original meaning while improving naturalness
3. THE Semantic_Refiner SHALL instruct LLM to use consistent terminology from gs.md
4. WHEN gs.md provides better phrasing for a concept, THE Semantic_Refiner SHALL adopt it
5. THE Semantic_Refiner SHALL preserve original SRT timestamps exactly

### Requirement 4: 中国人可理解性审查

**User Story:** As a dubbing engineer, I want translations reviewed for Chinese audience comprehension, so that the dubbed content sounds natural to native speakers.

#### Acceptance Criteria

1. THE Localization_Review SHALL check for unnatural literal translations
2. THE Localization_Review SHALL verify proper use of Chinese idioms and expressions
3. THE Localization_Review SHALL ensure technical terms are explained or translated appropriately
4. WHEN English terms are kept, THE Localization_Review SHALL verify they are commonly understood in Chinese context
5. THE Localization_Review SHALL flag overly long or complex sentences for simplification

### Requirement 5: 术语一致性

**User Story:** As a dubbing engineer, I want consistent terminology throughout the translation, so that the audience doesn't get confused by varying translations of the same term.

#### Acceptance Criteria

1. WHEN gs.md defines a term translation, THE Semantic_Refiner SHALL use it consistently
2. THE Semantic_Refiner SHALL build a terminology map from gs.md during initial parsing
3. IF SRT uses different translation for a defined term, THE Semantic_Refiner SHALL correct it
4. THE Semantic_Refiner SHALL output a terminology report showing all term mappings used

### Requirement 6: 说话人风格保持

**User Story:** As a dubbing engineer, I want each speaker's style preserved, so that different speakers sound distinct in the dubbed output.

#### Acceptance Criteria

1. WHEN gs.md identifies multiple speakers, THE Semantic_Refiner SHALL track speaker changes
2. THE Semantic_Refiner SHALL maintain consistent speaking style for each speaker
3. THE Semantic_Refiner SHALL add speaker tags in format `[Speaker: Name]` when requested
4. IF speaker information is unavailable, THE Semantic_Refiner SHALL use DEFAULT speaker

### Requirement 7: 输出质量保证

**User Story:** As a dubbing engineer, I want the output to meet TTS requirements, so that the dubbing pipeline works smoothly.

#### Acceptance Criteria

1. THE Semantic_Refiner SHALL ensure each segment is ≤75 characters for Doubao TTS
2. WHEN splitting long segments, THE Semantic_Refiner SHALL split at natural sentence boundaries
3. THE Semantic_Refiner SHALL remove markdown formatting from output
4. THE Semantic_Refiner SHALL output valid SRT format compatible with FlexDub pipeline
5. THE Semantic_Refiner SHALL preserve original SRT index numbers and timestamps

### Requirement 8: 进度和可恢复性

**User Story:** As a dubbing engineer, I want to see progress and resume interrupted processing, so that I don't lose work on large files.

#### Acceptance Criteria

1. THE Semantic_Refiner SHALL report progress as percentage of chunks processed
2. THE Semantic_Refiner SHALL save intermediate results after each chunk
3. IF processing is interrupted, THE Semantic_Refiner SHALL resume from the last completed chunk
4. THE Semantic_Refiner SHALL output a processing log with decisions made for each chunk

