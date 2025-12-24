# Requirements Document

## Introduction

本功能为 FlexDub 添加豆包 TTS 后端支持。通过集成外部 doubao-tts-api HTTP 服务，FlexDub 可以使用豆包的 44 种高质量中文音色进行语音合成，作为 Edge TTS 的补充选择。

集成方式采用 HTTP Service 模式：doubao-tts-api 作为独立服务运行，FlexDub 通过 HTTP 调用其 API。这种架构保持两个项目的独立性，doubao-tts-api 无需修改。

## Glossary

- **FlexDub**: 弹性配音流水线，用于视频本地化
- **TTSBackend**: TTS 后端抽象接口，定义 `async synthesize(text, voice, ar) -> wav_path` 方法
- **doubao-tts-api**: 外部 Node.js 服务，通过 Puppeteer + WebSocket 调用豆包 TTS，提供 HTTP API
- **Speaker**: 豆包音色名称（如"磁性俊宇"、"温柔桃子"），共 44 种
- **AAC**: 豆包 TTS 输出的音频格式
- **WAV**: FlexDub 内部统一使用的音频格式（mono, 指定采样率）
- **dubbing.py**: FlexDub 的 TTS 调度模块，通过 `_synthesize_segment()` 函数选择后端
- **elastic_video.py**: Mode B 流水线，支持 Doubao TTS 后端
- **TTS_CHAR_THRESHOLD**: TTS 字符长度阈值，默认 75 字符
- **TTS Cache**: TTS 缓存目录，用于断点续传

## Requirements

### Requirement 1

**User Story:** As a FlexDub user, I want to use Doubao TTS for voice synthesis, so that I can access high-quality Chinese voices with more natural prosody.

#### Acceptance Criteria

1. WHEN a user specifies `--backend doubao` in the CLI, THE FlexDub System SHALL use the DoubaoTTSBackend for synthesis
2. WHEN a user specifies `--voice <speaker_name>` with Doubao backend, THE FlexDub System SHALL pass the speaker name to the Doubao service via HTTP POST body
3. WHEN no voice is specified with Doubao backend, THE FlexDub System SHALL use the default speaker "温柔桃子"
4. THE CLI argument parser SHALL accept "doubao" as a valid backend choice alongside "edge_tts"

### Requirement 2

**User Story:** As a FlexDub user, I want the Doubao backend to integrate seamlessly with existing pipelines, so that I can switch backends without changing my workflow.

#### Acceptance Criteria

1. THE DoubaoTTSBackend class SHALL inherit from TTSBackend and implement `async synthesize(text: str, voice: str, ar: int) -> str`
2. WHEN the Doubao backend synthesizes audio, THE FlexDub System SHALL return a WAV file path (mono channel, specified sample rate)
3. THE `_synthesize_segment()` function in dubbing.py SHALL instantiate DoubaoTTSBackend when backend parameter equals "doubao"
4. THE DoubaoTTSBackend SHALL be exported from `flexdub.backends.tts` module alongside EdgeTTSBackend

### Requirement 3

**User Story:** As a FlexDub user, I want clear error messages when the Doubao service is unavailable, so that I can troubleshoot connection issues.

#### Acceptance Criteria

1. IF the Doubao HTTP service connection fails, THEN THE FlexDub System SHALL raise RuntimeError with message containing service URL and "connection failed"
2. IF the Doubao service returns HTTP status code other than 200, THEN THE FlexDub System SHALL raise RuntimeError with the error message from response body
3. THE DoubaoTTSBackend constructor SHALL accept optional `server_url` parameter with default value "http://localhost:3456"
4. WHEN HTTP request times out after 180 seconds, THE FlexDub System SHALL raise RuntimeError indicating timeout

### Requirement 6

**User Story:** As a FlexDub user, I want the system to handle long text segments gracefully, so that TTS synthesis does not fail due to timeout.

#### Acceptance Criteria

1. THE FlexDub System SHALL define a TTS character threshold of 75 characters for Doubao backend
2. WHEN a segment exceeds the character threshold, THE FlexDub System SHALL warn the user before synthesis
3. THE CLI SHALL provide `--skip-length-check` option to bypass character length validation
4. THE `qa` command SHALL support `--tts-char-threshold` parameter to check segment lengths
5. WHEN calculating character length, THE FlexDub System SHALL exclude bracket content `[]【】()` from the count

### Requirement 7

**User Story:** As a FlexDub user, I want the system to filter non-speech content from TTS input, so that markers like [Music] are not spoken.

#### Acceptance Criteria

1. WHEN synthesizing text, THE FlexDub System SHALL remove content within `[]`, `【】`, and `()` brackets before sending to TTS
2. IF text becomes empty after bracket filtering, THEN THE FlexDub System SHALL generate silence instead of calling TTS
3. THE bracket filtering SHALL preserve text outside of brackets unchanged

### Requirement 8

**User Story:** As a FlexDub user, I want the system to retry failed TTS requests, so that transient failures do not abort the entire process.

#### Acceptance Criteria

1. WHEN a TTS request fails, THE FlexDub System SHALL retry up to 3 times with 2 second delay between attempts
2. THE FlexDub System SHALL log each retry attempt with attempt number
3. IF all retry attempts fail, THEN THE FlexDub System SHALL raise the final error

### Requirement 9

**User Story:** As a FlexDub user, I want TTS results to be cached, so that I can resume processing after failures without re-synthesizing completed segments.

#### Acceptance Criteria

1. THE FlexDub System SHALL cache TTS results in `<video_dir>/tts_cache/` directory
2. WHEN a cached result exists for a segment, THE FlexDub System SHALL skip TTS synthesis and use the cached file
3. THE cache key SHALL be based on segment index to ensure correct mapping

### Requirement 4

**User Story:** As a developer, I want the Doubao backend to handle temporary files properly, so that disk space is not wasted.

#### Acceptance Criteria

1. WHEN the Doubao backend converts AAC to WAV successfully, THE FlexDub System SHALL delete the intermediate AAC file
2. IF ffmpeg conversion fails, THEN THE FlexDub System SHALL delete the AAC file before raising the error
3. THE DoubaoTTSBackend SHALL use `tempfile.mktemp()` for temporary file paths consistent with EdgeTTSBackend

### Requirement 5

**User Story:** As a developer, I want the Doubao backend to follow the same patterns as EdgeTTSBackend, so that the codebase remains consistent.

#### Acceptance Criteria

1. THE DoubaoTTSBackend file SHALL be located at `flexdub/backends/tts/doubao.py`
2. THE DoubaoTTSBackend SHALL use aiohttp for async HTTP requests (consistent with async synthesize interface)
3. THE DoubaoTTSBackend SHALL use subprocess.run for ffmpeg conversion (consistent with EdgeTTSBackend)
4. THE DoubaoTTSBackend SHALL use shutil.which to check ffmpeg availability before conversion
