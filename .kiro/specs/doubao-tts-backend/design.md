# Design Document: Doubao TTS Backend

## Overview

本设计为 FlexDub 添加豆包 TTS 后端支持，通过 HTTP 调用外部 doubao-tts-api 服务实现语音合成。设计遵循现有 EdgeTTSBackend 的模式，确保架构一致性和无缝集成。

### 集成架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         FlexDub                                  │
│  ┌─────────────┐    ┌──────────────────┐    ┌────────────────┐  │
│  │   CLI       │───▶│   dubbing.py     │───▶│  TTSBackend    │  │
│  │ --backend   │    │ _synthesize_     │    │  (interface)   │  │
│  │   doubao    │    │   segment()      │    └───────┬────────┘  │
│  └─────────────┘    └──────────────────┘            │           │
│         │                                           │           │
│         │           ┌──────────────────┐            │           │
│         └──────────▶│ elastic_video.py │────────────┤           │
│                     │ (Mode B default) │            │           │
│                     │ + retry + cache  │            │           │
│                     └──────────────────┘            │           │
│                                                      │           │
│                     ┌────────────────────────────────┼───────┐  │
│                     │                                ▼       │  │
│                     │  ┌──────────────┐    ┌──────────────┐  │  │
│                     │  │EdgeTTSBackend│    │DoubaoTTSBackend│ │  │
│                     │  └──────────────┘    └───────┬──────┘  │  │
│                     │   backends/tts/              │         │  │
│                     └──────────────────────────────┼─────────┘  │
└────────────────────────────────────────────────────┼────────────┘
                                                     │ HTTP POST
                                                     ▼
                              ┌─────────────────────────────────┐
                              │      doubao-tts-api             │
                              │   (External Node.js Service)    │
                              │   POST /tts                     │
                              │   {"text": "...", "speaker": ""}│
                              └─────────────────────────────────┘
```

## Architecture

### 组件职责

| 组件 | 职责 |
|------|------|
| CLI (`__main__.py`) | 解析 `--backend doubao` 参数，传递给 pipeline |
| `dubbing.py` | 根据 backend 参数选择 DoubaoTTSBackend 或 EdgeTTSBackend |
| `DoubaoTTSBackend` | 实现 TTSBackend 接口，通过 HTTP 调用 doubao-tts-api |
| `doubao-tts-api` | 外部服务，提供豆包 TTS 能力（不在本项目范围内） |

### 数据流

1. CLI 接收 `--backend doubao --voice 磁性俊宇`
2. `dubbing.py._synthesize_segment()` 实例化 `DoubaoTTSBackend`
3. `DoubaoTTSBackend.synthesize()` 发送 HTTP POST 到 `http://localhost:3456/tts`
4. 接收 AAC 音频，通过 ffmpeg 转换为 WAV
5. 返回 WAV 文件路径给 pipeline

## Components and Interfaces

### TTSBackend Interface (existing)

```python
# flexdub/backends/tts/interfaces.py
class TTSBackend:
    async def synthesize(self, text: str, voice: str, ar: int) -> str:
        """
        Synthesize text to audio file.
        
        Args:
            text: Text to synthesize
            voice: Voice/speaker identifier
            ar: Sample rate in Hz
            
        Returns:
            Path to WAV file (mono, specified sample rate)
        """
        raise NotImplementedError
```

### DoubaoTTSBackend (new)

```python
# flexdub/backends/tts/doubao.py
class DoubaoTTSBackend(TTSBackend):
    def __init__(self, server_url: str = "http://localhost:3456"):
        self.server_url = server_url
    
    async def synthesize(self, text: str, voice: str, ar: int) -> str:
        """
        Synthesize text using Doubao TTS service.
        
        Args:
            text: Text to synthesize
            voice: Speaker name (e.g., "磁性俊宇", "温柔桃子")
            ar: Target sample rate in Hz
            
        Returns:
            Path to WAV file (mono, specified sample rate)
            
        Raises:
            RuntimeError: If service unavailable or synthesis fails
        """
```

### Module Export (update)

```python
# flexdub/backends/tts/__init__.py
from .edge import EdgeTTSBackend
from .doubao import DoubaoTTSBackend  # 新增
```

### Pipeline Integration (update)

```python
# flexdub/pipelines/dubbing.py
async def _synthesize_segment(text: str, voice: str, backend: str, ar: int) -> str:
    if backend == "edge_tts":
        b = EdgeTTSBackend()
    elif backend == "doubao":
        b = DoubaoTTSBackend()  # 新增
    else:
        raise ValueError(f"unsupported backend: {backend}")
    return await b.synthesize(text, voice, ar)
```

### CLI Update

```python
# flexdub/cli/__main__.py
# 更新所有 --backend 参数的 choices
m.add_argument("--backend", choices=["edge_tts", "doubao"], required=True)
```

## Data Models

### HTTP Request to doubao-tts-api

```json
POST /tts
Content-Type: application/json

{
    "text": "要合成的文本",
    "speaker": "磁性俊宇"
}
```

### HTTP Response from doubao-tts-api

```
Content-Type: audio/aac
Body: <binary AAC data>
```

### Error Response

```json
{
    "error": "error message"
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Based on the prework analysis, the following properties are identified:

### Property 1: Voice parameter passthrough

*For any* non-empty speaker name, when DoubaoTTSBackend.synthesize() is called, the HTTP request body SHALL contain the exact speaker name in the "speaker" field.

**Validates: Requirements 1.2**

### Property 2: WAV output format consistency

*For any* successful synthesis call with sample rate `ar`, the returned file SHALL be a valid WAV file with mono channel and sample rate equal to `ar`.

**Validates: Requirements 2.2**

### Property 3: Error status propagation

*For any* HTTP response with status code != 200, DoubaoTTSBackend SHALL raise RuntimeError containing the error message from the response body.

**Validates: Requirements 3.2**

## Error Handling

| 场景 | 处理方式 |
|------|----------|
| 服务连接失败 | 抛出 `RuntimeError(f"Doubao TTS service connection failed: {server_url}")` |
| HTTP 非 200 响应 | 抛出 `RuntimeError(f"Doubao TTS failed: {error_message}")` |
| 请求超时 (180s) | 抛出 `RuntimeError("Doubao TTS request timeout")` |
| ffmpeg 不可用 | 返回 AAC 文件路径（与 EdgeTTSBackend 行为一致） |
| ffmpeg 转换失败 | 清理临时文件后抛出原始异常 |
| 段落超过 75 字符 | 警告用户，可用 `--skip-length-check` 跳过 |
| 括号内容 | 自动过滤 `[]【】()` 内容后再合成 |
| TTS 失败 | 重试 3 次，每次间隔 2 秒 |

## Retry and Cache Mechanism

### Retry Logic (elastic_video.py)

```python
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

for attempt in range(1, MAX_RETRIES + 1):
    try:
        wav_path = await backend.synthesize(text, voice, ar)
        break
    except Exception as e:
        if attempt < MAX_RETRIES:
            logger.warning(f"Segment {idx} TTS failed (attempt {attempt}/{MAX_RETRIES}): {e}")
            await asyncio.sleep(RETRY_DELAY)
        else:
            raise
```

### TTS Cache

缓存目录: `<video_dir>/tts_cache/`

缓存文件命名: `segment_{idx:04d}.wav`

断点续传: 重新运行命令时自动跳过已缓存的段落

## Bracket Content Filtering

在 TTS 合成前自动过滤括号内容：

```python
from flexdub.core.subtitle import remove_bracket_content

text_to_speak = remove_bracket_content(text)
if not text_to_speak.strip():
    # Generate silence instead of calling TTS
    return generate_silence(duration_ms, ar)
```

支持的括号类型:
- `[Music]`, `[音乐]` → 过滤
- `【笑声】` → 过滤
- `(applause)` → 过滤

## Testing Strategy

### Dual Testing Approach

本功能采用单元测试和属性测试相结合的方式：

- **单元测试**: 验证具体行为和边界情况
- **属性测试**: 验证跨输入的通用属性

### Property-Based Testing Framework

使用 **hypothesis** 库进行属性测试（Python 生态标准 PBT 库）。

配置：每个属性测试运行 **100 次迭代**。

### Test Cases

#### Unit Tests

1. **Backend instantiation**: 验证 DoubaoTTSBackend 正确继承 TTSBackend
2. **Default server URL**: 验证默认 URL 为 `http://localhost:3456`
3. **Custom server URL**: 验证可配置自定义 URL
4. **CLI backend choice**: 验证 argparse 接受 "doubao" 选项
5. **Module export**: 验证 DoubaoTTSBackend 可从 `flexdub.backends.tts` 导入
6. **Temp file cleanup**: 验证成功转换后 AAC 文件被删除
7. **Error cleanup**: 验证失败时临时文件被清理

#### Property-Based Tests

1. **Property 1 test**: 生成随机 speaker 名称，验证 HTTP 请求包含正确的 speaker 字段
   - **Feature: doubao-tts-backend, Property 1: Voice parameter passthrough**
   
2. **Property 2 test**: 生成随机文本和采样率，验证输出 WAV 格式正确
   - **Feature: doubao-tts-backend, Property 2: WAV output format consistency**
   
3. **Property 3 test**: 生成随机 HTTP 错误状态码和消息，验证错误正确传播
   - **Feature: doubao-tts-backend, Property 3: Error status propagation**

### Test Dependencies

```
pytest
hypothesis
aiohttp
pytest-asyncio
```

### Mock Strategy

由于 doubao-tts-api 是外部服务，测试时需要 mock HTTP 调用：

- 使用 `aioresponses` 库 mock aiohttp 请求
- 提供预录制的 AAC 音频数据用于格式转换测试
