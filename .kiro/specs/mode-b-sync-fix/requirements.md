# Requirements Document

## Introduction

本需求文档定义了 Mode B（弹性视频）管线的三个关键问题的修复方案：

1. **音视频同步不准确**：TTS 时长计算和视频拉伸逻辑存在问题，导致说话时机与画面不匹配
2. **Agent Manual v2 缺少 QA 环节**：语义重构阶段缺乏强制性的质量检查机制
3. **最终视频缺少字幕**：Mode B 改变了时间轴后，原字幕不再适用，需要生成新字幕

## Glossary

- **Mode B (Elastic Video)**：弹性视频模式，固定音频语速，拉伸/压缩视频以匹配 TTS 时长
- **TTS (Text-to-Speech)**：文本转语音合成
- **SRT**：SubRip 字幕格式
- **CPM (Characters Per Minute)**：每分钟字符数，衡量语速的指标
- **Segment**：字幕片段，包含开始时间、结束时间和文本内容
- **Stretch Ratio**：拉伸比例，TTS 时长 / 原始片段时长
- **Gap**：字幕片段之间的间隙时间
- **voice_map.json**：说话人到音色的映射配置文件
- **semantic_fixed.srt**：语义重构后的字幕文件

## Requirements

### Requirement 1: 音视频同步精确对齐

**User Story:** As a 视频制作者, I want Mode B 输出的视频中说话时机与画面精确对齐, so that 观众能够获得自然的观看体验。

#### Acceptance Criteria

1. WHEN 处理每个字幕片段 THEN the System SHALL 从 TTS 缓存文件读取实际音频时长（而非估算）
2. WHEN 原始字幕存在间隙（gap > 0）THEN the System SHALL 保留该间隙对应的视频片段不进行拉伸
3. WHEN 字幕片段文本为空或仅包含空白字符 THEN the System SHALL 跳过该片段的 TTS 合成并保留原始视频时长
4. WHEN 计算视频拉伸比例 THEN the System SHALL 使用公式 ratio = TTS实际时长 / 原始片段时长
5. WHEN 拼接所有视频片段 THEN the System SHALL 按照新时间轴顺序拼接，确保累计时长与音频总时长一致
6. WHEN 处理完成 THEN the System SHALL 输出同步诊断报告，包含每个片段的原始时长、TTS 时长、拉伸比例

### Requirement 2: Agent Manual v2 强制 QA 环节

**User Story:** As a Agent 使用者, I want 语义重构阶段有强制性的质量检查机制, so that 后续处理步骤不会因为前期错误而白费。

#### Acceptance Criteria

1. WHEN Agent 完成语义重构 THEN the Agent SHALL 执行强制性的自检清单，包含内容完整性、翻译质量、说话人标注、断句优化、时间轴完整性、格式验证六大类检查
2. WHEN 任何检查项未通过 THEN the Agent SHALL 停止流程并修正问题，直到所有检查通过
3. WHEN 检查说话人覆盖率 THEN the Agent SHALL 验证 100% 的片段都有 [Speaker:Name] 标签
4. WHEN 检查时间轴完整性 THEN the Agent SHALL 验证第一个片段的开始时间和最后一个片段的结束时间覆盖整个视频
5. WHEN 检查翻译准确率 THEN the Agent SHALL 随机抽样至少 20 个片段进行人工验证
6. WHEN 所有检查通过 THEN the Agent SHALL 生成质量检查报告并记录到输出目录

### Requirement 3: Mode B 自动生成新字幕

**User Story:** As a 视频制作者, I want Mode B 处理后自动生成匹配新时间轴的字幕文件, so that 最终视频能够正确显示字幕。

#### Acceptance Criteria

1. WHEN Mode B 处理完成 THEN the System SHALL 自动生成新的 SRT 字幕文件，时间轴与输出视频匹配
2. WHEN 生成新字幕 THEN the System SHALL 使用累计 TTS 时长作为每个片段的新时间轴
3. WHEN 新字幕生成完成 THEN the System SHALL 将新字幕文件保存为 `*.mode_b.srt`
4. WHEN 用户指定 `--embed-subtitle` 参数 THEN the System SHALL 自动将新字幕嵌入到输出视频中
5. WHEN 嵌入字幕 THEN the System SHALL 支持指定字幕语言（`--subtitle-lang`）
6. WHEN 处理多说话人场景 THEN the System SHALL 在新字幕中保留 [Speaker:Name] 标签或根据用户选择移除

### Requirement 4: 同步诊断与调试

**User Story:** As a 开发者, I want 详细的同步诊断信息, so that 我能够快速定位和修复音视频不同步的问题。

#### Acceptance Criteria

1. WHEN 启用 `--debug-sync` 参数 THEN the System SHALL 输出详细的同步诊断日志
2. WHEN 输出诊断日志 THEN the System SHALL 包含每个片段的原始时间、新时间、TTS 时长、拉伸比例、累计偏差
3. WHEN 检测到拉伸比例异常（ratio < 0.3 或 ratio > 3.0）THEN the System SHALL 输出警告信息
4. WHEN 处理完成 THEN the System SHALL 输出总时长对比（原始 vs 新）和整体拉伸比例

### Requirement 5: 间隙处理策略

**User Story:** As a 视频制作者, I want 字幕间隙被正确处理, so that 视频中的静默部分不会被错误地压缩或拉伸。

#### Acceptance Criteria

1. WHEN 检测到字幕间隙（gap > 100ms）THEN the System SHALL 提取该间隙对应的视频片段
2. WHEN 处理间隙视频片段 THEN the System SHALL 保持原始时长不进行拉伸
3. WHEN 处理间隙音频 THEN the System SHALL 生成对应时长的静音音频
4. WHEN 拼接视频 THEN the System SHALL 按照 [片段1] [间隙1] [片段2] [间隙2] ... 的顺序拼接
5. WHEN 间隙时长 < 100ms THEN the System SHALL 忽略该间隙，直接拼接相邻片段
