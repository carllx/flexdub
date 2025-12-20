---
name: auto_dub
description: 自动化配音技能 - 执行完整的 TTS 合成和音视频合流流程
triggers:
  - "配音"
  - "dub"
  - "TTS"
  - "合成语音"
version: 1.0.0
---

# 技能：自动化配音 (Auto-Dub Workflow)

## 何时使用

当用户请求执行完整配音流程时激活此技能。

## 前置条件

1. 项目目录包含 1 个 MP4 和 1 个 SRT 文件
2. 已完成语义重构（semantic_fixed.srt 存在）
3. 多人场景需要 voice_map.json

### Doubao TTS 服务（Agent 自动管理）

**Agent 必须主动启动服务**，不应要求用户手动操作：

```bash
# Agent 自动执行
node /Users/yamlam/Downloads/doubao-tts-api/cli/tts-server.js

# 验证服务就绪
curl http://localhost:3456/status
```

**注意**：Edge TTS 无需额外服务，开箱即用。

## 工作流程

```
1. 项目分析 → 获取指标和推荐模式
2. QA 检查 → 验证输入文件质量
3. TTS 合成 → 生成音频
4. 音视频合流 → 生成最终视频
5. 质量审计 → 验证同步性
```

## 模式选择

### Mode B (elastic-video) - 默认推荐
- 音频自然语速，听感最佳
- 视频被拉伸适配
- 适合：教程、知识百科、PPT 演示等
- 推荐参数：`--mode elastic-video --no-rebalance`

### Mode A (elastic-audio) - 时长固定场景
- 视频时长不变
- 音频被压缩/拉伸适配
- 适合：广告、短视频、有人脸出镜等时长刚性约束场景
- 推荐参数：`--clustered --mode elastic-audio`

## 错误处理

### TTS 失败
- 直接停止，返回错误码 1
- 不进行回退

### 同步偏差 > 180ms
- 检查是否使用了正确的字幕文件
- 考虑调整 rebalance 参数

## CLI 命令

### 默认配音（Mode B）- Edge TTS
```bash
python -m flexdub merge semantic_fixed.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --mode elastic-video \
  --no-rebalance \
  -o video.dub.mp4
```

### 默认配音（Mode B）- Doubao TTS
```bash
python -m flexdub merge semantic_fixed.srt video.mp4 \
  --backend doubao \
  --voice 磁性俊宇 \
  --mode elastic-video \
  --no-rebalance \
  -o video.dub.mp4
```

### 时长固定场景（Mode A）- Edge TTS
```bash
python -m flexdub merge semantic_fixed.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --clustered \
  -o video.dub.mp4
```

### 时长固定场景（Mode A）- Doubao TTS
```bash
python -m flexdub merge semantic_fixed.srt video.mp4 \
  --backend doubao \
  --voice 磁性俊宇 \
  --clustered \
  -o video.dub.mp4
```

### 多人场景 - Edge TTS
```bash
python -m flexdub merge semantic_fixed.srt video.mp4 \
  --backend edge_tts \
  --voice zh-CN-YunjianNeural \
  --voice-map voice_map.json \
  --keep-brackets \
  --clustered \
  -o video.dub.mp4
```

### 多人场景 - Doubao TTS
```bash
python -m flexdub merge semantic_fixed.srt video.mp4 \
  --backend doubao \
  --voice 温柔桃子 \
  --voice-map voice_map.json \
  --keep-brackets \
  --clustered \
  -o video.dub.mp4
```

## voice_map.json 格式

**⚠️ 重要：必须先获取有效音色列表**

```bash
# 在选择音色前必须执行
curl -s http://localhost:3456/speakers | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('Female:', d['byCategory']['female'])
print('Male:', d['byCategory']['male'])
"
```

**Doubao TTS（默认推荐）**：
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

**音色选择规则**：
1. **禁止凭记忆编造音色名**
2. 必须使用 `/speakers` API 返回的精确名称
3. 根据角色性别、性格选择差异明显的音色
4. `DEFAULT` 键必须存在，用于未标注说话人的片段

**推荐音色组合**（差异明显）：
| 场景 | 角色 A | 角色 B |
|------|--------|--------|
| 双女声 | 阳光甜妹 | 知性小棠 |
| 双男声 | 磁性俊宇 | 阳光阿辰 |
| 男女对话 | 磁性俊宇 | 温柔桃子 |

## 相关代码

- `flexdub.core.analyzer.analyze_project()` - 项目分析
- `flexdub.core.analyzer.recommend_mode()` - 模式推荐
- `flexdub.pipelines.dubbing.build_audio_from_srt_clustered()` - 聚类合成
- `flexdub.pipelines.elastic_video.build_elastic_video_from_srt()` - Mode B 管线
