# Implementation Plan

## 1. 修复 Mode B 音视频同步

- [x] 1.1 实现间隙检测功能
  - 在 `pyvideotrans/core/subtitle.py` 中添加 `detect_gaps()` 函数
  - 检测字幕片段之间 > 100ms 的间隙
  - 返回间隙列表，包含 start_ms, end_ms, duration_ms, prev_index, next_index
  - _Requirements: 5.1, 5.5_

- [ ]* 1.2 编写间隙检测属性测试
  - **Property 11: 间隙检测正确性**
  - **Validates: Requirements 5.1, 5.5**

- [x] 1.3 修改视频片段处理逻辑
  - 修改 `pyvideotrans/pipelines/elastic_video.py` 中的 `build_elastic_video_from_srt()` 函数
  - 添加间隙检测和处理逻辑
  - 间隙对应的视频片段保持原始时长不拉伸
  - 生成间隙对应的静音音频
  - _Requirements: 1.2, 5.2, 5.3, 5.4_

- [ ]* 1.4 编写间隙处理属性测试
  - **Property 2: 间隙片段不拉伸**
  - **Property 12: 静音音频时长正确性**
  - **Validates: Requirements 1.2, 5.2, 5.3**

- [x] 1.5 添加空白片段跳过逻辑
  - 修改 TTS 合成逻辑，跳过空白或仅包含空白字符的片段
  - 空白片段保留原始视频时长
  - _Requirements: 1.3_

- [ ]* 1.6 编写空白片段处理属性测试
  - **Property 3: 空白片段跳过**
  - **Validates: Requirements 1.3**

- [x] 1.7 确保从 TTS 缓存读取实际时长
  - 验证 `audio_duration_ms()` 函数正确读取缓存文件时长
  - 确保不使用估算值
  - _Requirements: 1.1_
  - **已实现**: `elastic_video.py` 中使用 `audio_duration_ms(cache_path)` 读取实际时长

- [ ]* 1.8 编写 TTS 时长读取属性测试
  - **Property 1: TTS 时长读取准确性**
  - **Validates: Requirements 1.1**

- [x] 1.9 添加同步诊断报告输出
  - 在处理完成后输出每个片段的详细信息
  - 包含原始时长、TTS 时长、拉伸比例、累计偏差
  - 检测异常拉伸比例并输出警告
  - 支持 `--debug-sync` 参数控制输出
  - _Requirements: 1.6, 4.1, 4.2, 4.3, 4.4_

- [ ]* 1.10 编写异常拉伸比例警告属性测试
  - **Property 10: 异常拉伸比例警告**
  - **Validates: Requirements 4.3**

- [x] 1.11 Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.

## 2. 实现 Mode B 自动生成新字幕

- [x] 2.1 实现新字幕生成函数
  - 在 `pyvideotrans/pipelines/elastic_video.py` 中添加 `generate_mode_b_subtitle()` 函数
  - 使用累计 TTS 时长计算新时间轴
  - 支持保留或移除说话人标签
  - _Requirements: 3.1, 3.2, 3.6_

- [ ]* 2.2 编写新字幕时间轴属性测试
  - **Property 8: 新字幕时间轴正确性**
  - **Validates: Requirements 3.1, 3.2**

- [ ]* 2.3 编写说话人标签保留/移除属性测试
  - **Property 9: 说话人标签保留/移除**
  - **Validates: Requirements 3.6**

- [x] 2.4 集成新字幕生成到 CLI
  - 修改 `pyvideotrans/cli/__main__.py` 中的 Mode B 处理逻辑
  - 自动生成 `*.mode_b.srt` 文件
  - 支持 `--embed-subtitle` 参数嵌入新字幕
  - _Requirements: 3.3, 3.4, 3.5_

- [x] 2.5 Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.

## 3. 添加 Agent Manual v2 QA 环节

- [x] 3.1 实现 QA 检查函数
  - 在 `pyvideotrans/core/qa.py` 中创建新模块
  - 实现 `check_speaker_coverage()` 函数
  - 实现 `check_timeline_completeness()` 函数
  - 实现 `check_block_limits()` 函数
  - 实现 `check_voice_map()` 函数
  - _Requirements: 2.3, 2.4_

- [ ]* 3.2 编写说话人覆盖率检查属性测试
  - **Property 6: 说话人标签覆盖率检查**
  - **Validates: Requirements 2.3**

- [ ]* 3.3 编写时间轴完整性检查属性测试
  - **Property 7: 时间轴完整性检查**
  - **Validates: Requirements 2.4**

- [x] 3.4 实现 QA 报告生成
  - 实现 `run_qa_checks()` 函数
  - 生成 QA 报告，包含所有检查项的结果
  - 支持输出到文件
  - _Requirements: 2.1, 2.6_

- [x] 3.5 添加 QA 命令到 CLI
  - 在 `pyvideotrans/cli/__main__.py` 中添加 `qa` 子命令
  - 支持 `--srt-path` 和 `--voice-map` 参数
  - 输出检查结果和报告
  - _Requirements: 2.1, 2.2_

- [x] 3.6 更新 Agent Manual v2
  - 在 `agent_manual_v2.md` 中添加强制 QA 环节
  - 添加 6 大类检查清单
  - 添加质量门禁标准
  - 添加强制复测流程
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [x] 3.7 Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.

## 4. 验证总时长一致性

- [x] 4.1 添加总时长验证逻辑
  - 在 Mode B 处理完成后验证输出视频时长
  - 验证时长等于所有 TTS 时长 + 间隙时长的总和
  - 输出时长对比信息
  - _Requirements: 1.5_

- [ ]* 4.2 编写总时长一致性属性测试
  - **Property 5: 总时长一致性**
  - **Validates: Requirements 1.5**

- [x] 4.3 Final Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.
