---
name: video_download
description: 视频下载技能 - 使用 yt-dlp 从 YouTube 下载视频和字幕
triggers:
  - "下载"
  - "YouTube"
  - "yt-dlp"
  - "视频获取"
version: 1.0.0
---

# 技能：视频下载 (Video Download)

## 何时使用

当需要从 YouTube 下载视频和字幕作为配音项目的输入时激活此技能。

## 前置条件

- 安装 `yt-dlp`: `pip install yt-dlp` 或 `brew install yt-dlp`
- 安装 `ffmpeg`: `brew install ffmpeg`

## 推荐下载命令

### 完整下载（视频 + 字幕）

```bash
# 720p（推荐，适中质量，文件较小）
yt-dlp -f "bestvideo[height<=720]+bestaudio/best[height<=720]" \
  --merge-output-format mp4 \
  --restrict-filenames \
  -o "data/input/%(title)s/%(title)s.%(ext)s" \
  --write-auto-subs \
  --write-thumbnail \
  "https://www.youtube.com/watch?v=VIDEO_ID"

# 1080p（高质量，字体更清晰）
yt-dlp -f "bestvideo[height<=1080]+bestaudio/best[height<=1080]" \
  --merge-output-format mp4 \
  --restrict-filenames \
  -o "data/input/%(title)s/%(title)s.%(ext)s" \
  --write-auto-subs \
  --write-thumbnail \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

### 仅下载字幕

```bash
# 自动生成的字幕
yt-dlp --write-auto-subs --sub-lang en --skip-download \
  --restrict-filenames \
  -o "data/input/%(title)s/%(title)s" \
  "https://www.youtube.com/watch?v=VIDEO_ID"

# 手动字幕（如果有）
yt-dlp --write-subs --sub-lang en --skip-download \
  --restrict-filenames \
  -o "data/input/%(title)s/%(title)s" \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

## 关键参数说明

| 参数 | 说明 |
|------|------|
| `--restrict-filenames` | **必须**，将特殊字符替换为下划线 |
| `-o "data/input/%(title)s/..."` | 输出到标准项目目录 |
| `--write-auto-subs` | 下载自动生成的字幕 |
| `--sub-lang en` | 指定字幕语言 |
| `--merge-output-format mp4` | 合并为 MP4 格式 |

## 下载后处理

1. 检查项目目录结构：
   ```bash
   ls data/input/<ProjectName>/
   # 应该包含: *.mp4, *.srt (或 *.vtt)
   ```

2. 如果字幕是 VTT 格式，转换为 SRT：
   ```bash
   ffmpeg -i input.vtt output.srt
   ```

3. **清理 YouTube 自动字幕**（重要！）：
   ```bash
   python scripts/clean_youtube_srt.py <input.srt> [output.srt]
   ```
   
4. 验证项目：
   ```bash
   python -m flexdub validate_project data/input/<ProjectName>
   ```

## YouTube 自动字幕清理

### 问题背景

YouTube 自动生成的字幕使用"滚动式"格式：
- 每个 cue 显示 2 行（上一行 + 当前行）
- 大量 10ms 的过渡帧用于平滑滚动
- 同一文本在多个 cue 中重复出现

直接用 `ffmpeg -i input.vtt output.srt` 转换会保留这种结构，导致：
- 大量重复内容
- 超短时长条目（10ms）
- 不适合 TTS 处理

### 解决方案

使用 `scripts/clean_youtube_srt.py` 清理：

```bash
# 基本用法
python scripts/clean_youtube_srt.py data/input/Project/video.srt

# 指定输出文件
python scripts/clean_youtube_srt.py input.srt output.srt
```

脚本功能：
1. 过滤 <50ms 的过渡帧
2. 提取所有唯一文本行
3. 合并成自然段落（遵守 ≤250字符、≤15s 限制）

### 验证清理结果

```bash
# 检查是否符合安全限制
python -m flexdub audit <cleaned.srt> --min-cpm 100 --max-cpm 300
```

## 常见问题

### Q: 下载失败，提示 "Video unavailable"
**A:** 视频可能有地区限制，尝试使用 VPN 或代理。

### Q: 字幕文件是 .vtt 格式
**A:** 先用 ffmpeg 转换格式，再用清理脚本处理：
```bash
ffmpeg -i file.vtt file.srt
python scripts/clean_youtube_srt.py file.srt file.clean.srt
```

### Q: 转换后的 SRT 有大量重复内容
**A:** 这是 YouTube 自动字幕的滚动格式导致的，必须使用 `clean_youtube_srt.py` 清理。

### Q: 文件名包含特殊字符导致后续处理失败
**A:** 确保使用了 `--restrict-filenames` 参数。

### Q: 清理后的 SRT 条目超过 15s 或 250 字符
**A:** 脚本默认遵守这些限制。如果仍有问题，检查原始字幕是否有异常长的静音段。
