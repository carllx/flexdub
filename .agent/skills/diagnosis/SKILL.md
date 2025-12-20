---
name: diagnosis
description: 故障诊断技能 - 分析错误原因并提供修复建议
triggers:
  - "错误"
  - "失败"
  - "error"
  - "failed"
  - "诊断"
  - "超时"
  - "timeout"
version: 1.1.0
---

# 技能：故障诊断 (Troubleshooting)

## 何时使用

当遇到错误或异常情况时激活此技能。

## 错误类型与修复

### 1. TTS 合成失败

**症状**: `[ERROR] TTS synthesis failed`

**可能原因**:
- 网络连接问题
- Edge TTS 服务不可用
- Doubao TTS 服务未启动
- 文本包含不支持的字符
- 文本过长导致超时

**修复步骤**:
1. 检查网络连接
2. Edge TTS: 重试（可能是临时问题）
3. Doubao TTS: 确认服务已启动（见下方）
4. 检查文本是否包含特殊字符
5. 使用 `flexdub qa` 检查字符长度

---

### 1.1 Doubao TTS 服务未启动

**症状**: `Doubao TTS service connection failed: http://localhost:3456`

**原因**: doubao-tts-api 服务未运行

**修复步骤**:
```bash
# 1. 启动服务（路径根据实际安装位置调整）
node /path/to/doubao-tts-api/cli/tts-server.js

# 2. 验证服务状态
curl http://localhost:3456/status

# 3. 重新执行配音命令
```

---

### 1.2 Doubao TTS 超时

**症状**: 
- `Doubao TTS failed: {"error":"TTS 失败: Timeout"}`
- `Segment X TTS failed (attempt 1/3)`
- 某些段落反复失败

**原因**: 
- 文本过长（>75 字符），服务处理时间超过超时限制
- Doubao 服务端不稳定
- 中文引号等特殊字符（已自动处理）

**修复步骤**:
1. **预检查字符长度**：
   ```bash
   python -m flexdub qa <srt> --backend doubao --tts-char-threshold 75
   ```
2. 超过 75 字符的段落需要重新措辞缩短
3. 使用 `--jobs 1` 降低并发，减轻服务压力
4. 重启 doubao-tts-api 服务后重试
5. 如果确定要跳过检查：`--skip-length-check`

**字符长度建议**：
- Doubao TTS 对长文本敏感
- 建议每段 ≤75 字符
- 超过 80 字符的段落容易超时失败
- 保持语义不变的情况下精简表达

---

### 1.3 TTS 缓存机制

Mode B (elastic-video) 支持 TTS 缓存，失败后可断点续传：

**缓存位置**: `<video_dir>/tts_cache/`

**续传方式**: 直接重新运行命令，已缓存的段落会自动跳过

**清除缓存**: 删除 `tts_cache/` 目录后重新生成

---

### 2. 同步偏差过大

**症状**: `|delta_ms| > 180ms`

**可能原因**:
- 使用了错误的字幕文件
- rebalance 参数不合适
- 高密度片段处理不当

**修复步骤**:
1. 确认使用 rebalance.srt 而非原始 SRT
2. 调整 `--target-cpm` 和 `--max-shift` 参数
3. 对高密度片段进行手动分句

---

### 3. 文本不可变违规

**症状**: `RuntimeError: text mutated in script stage`

**原因**: 在 Script 阶段尝试修改文本内容

**修复步骤**:
1. 文本修改必须在 LLM 阶段完成
2. 使用 `rewrite` 命令进行文本清理
3. 然后再执行 `rebalance` 或 `merge`

---

### 4. QA 检查失败

**症状**: `ALL PASSED = False`

**常见问题**:

| 检查项 | 失败原因 | 修复方法 |
|--------|---------|---------|
| Speaker Coverage < 100% | 缺少说话人标签 | 补充 [Speaker:Name] |
| Max Chars Exceeded | 片段过长 | 在逗号/分号处分片 |
| Max Duration Exceeded | 时长超限 | 调整时间轴或分片 |
| Voice Map Invalid | JSON 格式错误 | 修正格式，添加 DEFAULT |
| TTS Char Threshold | 段落超过 75 字符 | 重新措辞缩短文本 |

---

### 5. FFmpeg 错误

**症状**: 视频处理失败

**常见问题**:
- 负 PTS 时间戳 → 使用 `--robust-ts`
- 编码不支持 → 检查视频格式

---

### 6. Mode B 拉伸比例异常

**症状**: `ratio < 0.3 或 > 3.0`

**原因**: 字幕分片过度合并

**修复步骤**:
1. Mode B 需要超细粒度分片
2. 每个句子独立成片
3. 片段数量应为原始 80%-120%

---

### 7. 括号内容未过滤

**症状**: TTS 朗读了 `[Music]`、`[音乐]` 等标记

**说明**: 已自动处理，`[]`、`【】`、`()` 内的内容会在 TTS 前自动过滤

**如果仍有问题**:
1. 检查是否使用了最新版本代码
2. 确认括号配对正确

## 诊断命令

```bash
# 检查 SRT 质量（包含 TTS 字符长度检查）
python -m flexdub qa <srt> --backend doubao --tts-char-threshold 75

# 检查同步性
python -m flexdub sync_audit video.dub.mp4 semantic_fixed.srt

# 检查 CPM 分布
python -m flexdub audit semantic_fixed.srt --save cpm.csv

# 验证 Doubao 服务状态
curl http://localhost:3456/status
```

## 相关代码

- `flexdub.core.qa.run_qa_checks()` - 质量检查
- `flexdub.core.audio.write_sync_audit()` - 同步审计
- `flexdub.pipelines.elastic_video.validate_segment_lengths()` - 字符长度验证
