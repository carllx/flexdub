"""
Elastic Video Pipeline (Mode B)

核心逻辑：
1. 为每个字幕生成自然语速的 TTS 音频（不压缩）
2. 检测字幕之间的间隙（gap > 100ms）
3. 计算每个字幕对应的视频片段需要拉伸/压缩的比例
4. 提取并拉伸视频片段，使其时长与 TTS 音频匹配
5. 间隙对应的视频片段保持原始时长不拉伸
6. 将所有视频片段按顺序拼接（片段 + 间隙 + 片段 + ...）
7. 将所有音频拼接（TTS + 静音 + TTS + ...）
8. 合并音视频

关键点：
- 视频片段按字幕时间戳提取（start_ms 到 end_ms）
- 视频片段拉伸比例 = TTS时长 / 原始字幕时长
- 间隙片段保持原始时长，生成对应的静音音频
- TTS 音频会缓存到项目目录，避免重复下载
"""

import asyncio
import hashlib
import os
import tempfile
import subprocess
from typing import List, Tuple, Optional, Dict

from tqdm import tqdm

from pyvideotrans.core.subtitle import SRTItem, Gap, SegmentInfo, SyncDiagnostics, extract_speaker, detect_gaps
from pyvideotrans.core.audio import audio_duration_ms, make_silence
from pyvideotrans.backends.tts.edge import EdgeTTSBackend
from pyvideotrans.backends.tts.say import SayBackend


def _get_tts_cache_path(cache_dir: str, text: str, voice: str, idx: int) -> str:
    """Generate a cache file path for TTS audio."""
    # Use hash of text + voice to create unique filename
    text_hash = hashlib.md5(f"{text}_{voice}".encode()).hexdigest()[:8]
    return os.path.join(cache_dir, f"tts_{idx:04d}_{text_hash}.wav")


async def _synthesize_natural_speed(text: str, voice: str, backend: str, ar: int) -> str:
    """Generate TTS audio at natural speed without time constraints."""
    if backend == "edge_tts":
        b = EdgeTTSBackend()
    elif backend == "macos_say":
        b = SayBackend()
    else:
        raise ValueError(f"unsupported backend: {backend}")
    
    tmp_wav = await b.synthesize(text, voice, ar)
    return tmp_wav


def _extract_video_segment(video_path: str, start_ms: int, end_ms: int, output_path: str) -> bool:
    """
    Extract a video segment from start_ms to end_ms.
    Returns True if successful, False if segment is too short.
    """
    start_sec = start_ms / 1000.0
    duration_sec = (end_ms - start_ms) / 1000.0
    
    if duration_sec <= 0.01:  # Skip very short segments
        return False
    
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_sec),
        "-i", video_path,
        "-t", str(duration_sec),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-an",  # Remove audio
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def _stretch_video_segment(input_path: str, output_path: str, ratio: float) -> bool:
    """
    Stretch or compress video segment by ratio.
    ratio > 1.0: slow down (stretch) - video becomes longer
    ratio < 1.0: speed up (compress) - video becomes shorter
    
    Returns True if successful.
    """
    if ratio <= 0:
        return False
    
    # setpts filter: PTS * ratio
    # ratio > 1: each frame displayed longer → video slows down
    # ratio < 1: each frame displayed shorter → video speeds up
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter:v", f"setpts={ratio}*PTS",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-an",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


async def build_elastic_video_from_srt(
    items: List[SRTItem],
    video_path: str,
    voice: str,
    backend: str,
    ar: int,
    jobs: int = 4,
    progress: bool = True,
    voice_map: Optional[Dict[str, str]] = None,
    cache_dir: Optional[str] = None,
    debug_sync: bool = False
) -> Tuple[List[str], List[SRTItem], List[str], Optional[SyncDiagnostics]]:
    """
    Build elastic video pipeline.
    
    核心流程：
    1. 为每个字幕生成 TTS 音频（支持缓存）
    2. 提取对应的视频片段
    3. 根据 TTS 时长拉伸视频片段
    4. 返回音频列表、新字幕时间轴、视频片段列表
    
    Args:
        cache_dir: TTS 缓存目录，如果提供则会缓存 TTS 音频避免重复下载
        debug_sync: 是否生成同步诊断信息
    
    Returns:
        Tuple of (audio_segments, new_subtitle_items, video_segments, diagnostics)
        diagnostics 仅在 debug_sync=True 时返回非 None 值
    """
    total = len(items)
    
    # Setup TTS cache directory
    if cache_dir is None:
        # Default: create tts_cache folder next to video
        video_dir = os.path.dirname(video_path)
        cache_dir = os.path.join(video_dir, "tts_cache")
    
    os.makedirs(cache_dir, exist_ok=True)
    if progress:
        print(f"[ELASTIC_VIDEO] TTS cache directory: {cache_dir}")
    
    # Storage
    tts_audio_paths: List[str] = []
    tts_durations: List[int] = [0] * total
    video_segments: List[str] = []
    new_items: List[SRTItem] = []
    
    # Diagnostics collection
    segment_infos: List[SegmentInfo] = []
    warnings: List[str] = []
    
    sem = asyncio.Semaphore(max(1, jobs))
    
    # Track blank segments (will use original video duration instead of TTS)
    blank_segments: set = set()
    
    # ========== Step 1: Generate TTS audio (with caching) ==========
    async def generate_audio(idx: int, it: SRTItem) -> Tuple[int, Optional[str], int, bool]:
        """
        Generate TTS audio for a segment.
        
        Returns:
            Tuple of (idx, audio_path, duration_ms, is_blank)
            - is_blank: True if segment text is empty/whitespace-only
        """
        speaker, clean_text = extract_speaker(it.text)
        chosen_voice = voice
        
        if voice_map is not None and speaker is not None:
            chosen_voice = voice_map.get(speaker, voice_map.get("DEFAULT", voice))
            if progress:
                print(f"[ELASTIC_VIDEO] speaker={speaker} voice={chosen_voice}")
        
        text_to_speak = clean_text if speaker else it.text
        
        # Check if text is blank (empty or whitespace-only)
        if not text_to_speak or not text_to_speak.strip():
            # Blank segment: skip TTS, use original video duration
            original_duration_ms = it.end_ms - it.start_ms
            if progress:
                print(f"[ELASTIC_VIDEO] Segment {idx+1} is blank, skipping TTS (using original duration: {original_duration_ms}ms)")
            return idx, None, original_duration_ms, True
        
        # Check cache first
        cache_path = _get_tts_cache_path(cache_dir, text_to_speak, chosen_voice, idx)
        
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
            # Use cached audio
            if progress:
                print(f"[ELASTIC_VIDEO] Using cached TTS for segment {idx+1}")
            duration = audio_duration_ms(cache_path)
            return idx, cache_path, duration, False
        
        # Generate new TTS
        async with sem:
            audio_path = await _synthesize_natural_speed(
                text_to_speak,
                chosen_voice,
                backend,
                ar
            )
        
        # Copy to cache
        import shutil
        shutil.copy2(audio_path, cache_path)
        
        duration = audio_duration_ms(cache_path)
        return idx, cache_path, duration, False
    
    # Temporary storage for async results
    temp_audio_paths: List[Optional[str]] = [None] * total
    
    tasks = [asyncio.create_task(generate_audio(i, it)) for i, it in enumerate(items)]
    
    if progress:
        bar = tqdm(total=total, desc="TTS Generation", unit="seg")
    
    for fut in asyncio.as_completed(tasks):
        idx, path, duration, is_blank = await fut
        temp_audio_paths[idx] = path
        tts_durations[idx] = duration
        if is_blank:
            blank_segments.add(idx)
        if progress:
            bar.update(1)
    
    if progress:
        bar.close()
        if blank_segments:
            print(f"[ELASTIC_VIDEO] {len(blank_segments)} blank segments will use original video duration")
    
    # ========== Step 2: Detect gaps between segments ==========
    gaps = detect_gaps(items, min_gap_ms=100)
    gap_map: Dict[int, Gap] = {g.prev_index: g for g in gaps}  # Map: prev_index -> gap
    
    if progress and gaps:
        print(f"[ELASTIC_VIDEO] Detected {len(gaps)} gaps (> 100ms)")
        for g in gaps:
            print(f"[ELASTIC_VIDEO]   gap after seg {g.prev_index+1}: {g.duration_ms}ms")
    
    # ========== Step 3: Process video segments with gap handling ==========
    if progress:
        print("[ELASTIC_VIDEO] Processing video segments...")
        bar2 = tqdm(total=total, desc="Video Segments", unit="seg")
    
    current_time_ms = 0  # New timeline position
    
    for idx, it in enumerate(items):
        # Original segment duration from subtitle
        original_duration_ms = it.end_ms - it.start_ms
        
        # Check if this is a blank segment
        is_blank = idx in blank_segments
        
        # TTS audio duration (for blank segments, this equals original duration)
        tts_duration_ms = tts_durations[idx]
        
        # Calculate stretch ratio
        # ratio = TTS时长 / 原始时长
        # 如果 TTS 比原始长，ratio > 1，视频需要拉伸（慢放）
        # 如果 TTS 比原始短，ratio < 1，视频需要压缩（快放）
        # 空白片段不拉伸，ratio = 1.0
        if is_blank:
            ratio = 1.0
            if progress:
                print(f"[ELASTIC_VIDEO] seg={idx+1} BLANK orig={original_duration_ms}ms (no stretch, silence audio)")
        else:
            ratio = tts_duration_ms / max(1, original_duration_ms)
            if progress:
                print(f"[ELASTIC_VIDEO] seg={idx+1} orig={original_duration_ms}ms tts={tts_duration_ms}ms ratio={ratio:.3f}")
        
        # Extract original video segment
        tmp_segment = tempfile.mktemp(suffix=".mp4")
        extract_ok = _extract_video_segment(video_path, it.start_ms, it.end_ms, tmp_segment)
        
        if not extract_ok:
            # If extraction failed, skip this segment
            if progress:
                print(f"[ELASTIC_VIDEO] WARNING: Failed to extract segment {idx+1}")
            bar2.update(1)
            continue
        
        # For blank segments: no stretching, keep original video
        if is_blank:
            video_segments.append(tmp_segment)
            # Generate silence audio for blank segment
            silence_audio = tempfile.mktemp(suffix=".wav")
            make_silence(silence_audio, original_duration_ms, sr=ar)
            tts_audio_paths.append(silence_audio)
        else:
            # Stretch/compress video if needed
            if abs(ratio - 1.0) > 0.01:  # Only stretch if difference > 1%
                stretched_segment = tempfile.mktemp(suffix=".mp4")
                stretch_ok = _stretch_video_segment(tmp_segment, stretched_segment, ratio)
                
                if stretch_ok:
                    video_segments.append(stretched_segment)
                    try:
                        os.unlink(tmp_segment)
                    except:
                        pass
                else:
                    # Fallback to original if stretch failed
                    video_segments.append(tmp_segment)
            else:
                video_segments.append(tmp_segment)
            
            # Add TTS audio (in order)
            tts_audio_paths.append(temp_audio_paths[idx])
        
        # Create new subtitle item with updated timeline
        new_item = SRTItem(
            start_ms=current_time_ms,
            end_ms=current_time_ms + tts_duration_ms,
            text=it.text
        )
        new_items.append(new_item)
        
        # Collect diagnostics for this segment
        if debug_sync:
            seg_info = SegmentInfo(
                index=idx,
                original_start_ms=it.start_ms,
                original_end_ms=it.end_ms,
                original_duration_ms=original_duration_ms,
                tts_duration_ms=tts_duration_ms,
                new_start_ms=current_time_ms,
                new_end_ms=current_time_ms + tts_duration_ms,
                stretch_ratio=ratio,
                is_gap=False,
                is_blank=is_blank,
                text=it.text[:50] + "..." if len(it.text) > 50 else it.text
            )
            segment_infos.append(seg_info)
            
            # Check for abnormal stretch ratio (< 0.3 or > 3.0)
            if not is_blank and (ratio < 0.3 or ratio > 3.0):
                warn_msg = f"Segment {idx+1}: abnormal stretch ratio {ratio:.3f}"
                warnings.append(warn_msg)
                if progress:
                    print(f"[ELASTIC_VIDEO] WARNING: {warn_msg}")
        
        # Move timeline forward
        current_time_ms += tts_duration_ms
        
        # ========== Handle gap after this segment ==========
        if idx in gap_map:
            gap = gap_map[idx]
            gap_duration_ms = gap.duration_ms
            
            if progress:
                print(f"[ELASTIC_VIDEO] Processing gap after seg {idx+1}: {gap_duration_ms}ms (no stretch)")
            
            # Extract gap video segment (no stretching - keep original duration)
            gap_video = tempfile.mktemp(suffix=".mp4")
            gap_extract_ok = _extract_video_segment(video_path, gap.start_ms, gap.end_ms, gap_video)
            
            if gap_extract_ok:
                video_segments.append(gap_video)
                
                # Generate silence audio for the gap
                gap_audio = tempfile.mktemp(suffix=".wav")
                make_silence(gap_audio, gap_duration_ms, sr=ar)
                tts_audio_paths.append(gap_audio)
                
                # Collect diagnostics for gap
                if debug_sync:
                    gap_info = SegmentInfo(
                        index=idx,
                        original_start_ms=gap.start_ms,
                        original_end_ms=gap.end_ms,
                        original_duration_ms=gap_duration_ms,
                        tts_duration_ms=gap_duration_ms,
                        new_start_ms=current_time_ms,
                        new_end_ms=current_time_ms + gap_duration_ms,
                        stretch_ratio=1.0,
                        is_gap=True,
                        is_blank=False,
                        text="[GAP]"
                    )
                    segment_infos.append(gap_info)
                
                # Move timeline forward by gap duration
                current_time_ms += gap_duration_ms
            else:
                if progress:
                    print(f"[ELASTIC_VIDEO] WARNING: Failed to extract gap video after seg {idx+1}")
        
        if progress:
            bar2.update(1)
    
    if progress:
        bar2.close()
        print(f"[ELASTIC_VIDEO] Total new duration: {current_time_ms}ms ({current_time_ms/1000:.2f}s)")
    
    # Build diagnostics if requested
    diagnostics: Optional[SyncDiagnostics] = None
    if debug_sync:
        total_original_ms = items[-1].end_ms if items else 0
        total_new_ms = current_time_ms
        overall_ratio = total_new_ms / max(1, total_original_ms)
        
        diagnostics = SyncDiagnostics(
            segments=segment_infos,
            total_original_ms=total_original_ms,
            total_new_ms=total_new_ms,
            overall_ratio=overall_ratio,
            warnings=warnings
        )
        
        if progress:
            print(f"[ELASTIC_VIDEO] Diagnostics: original={total_original_ms}ms new={total_new_ms}ms ratio={overall_ratio:.3f}")
            if warnings:
                print(f"[ELASTIC_VIDEO] {len(warnings)} warnings generated")
    
    return tts_audio_paths, new_items, video_segments, diagnostics


def concatenate_video_segments(segments: List[str], output_path: str) -> None:
    """Concatenate video segments using ffmpeg concat demuxer."""
    if not segments:
        raise ValueError("No video segments to concatenate")
    
    # Create concat file list
    concat_file = tempfile.mktemp(suffix=".txt")
    with open(concat_file, "w") as f:
        for seg in segments:
            escaped = seg.replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
    
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    
    os.unlink(concat_file)


def generate_mode_b_subtitle(
    items: List[SRTItem],
    tts_durations: List[int],
    gaps: List[Gap],
    output_path: str,
    keep_speaker_tags: bool = True
) -> str:
    """
    生成 Mode B 新时间轴字幕
    
    Args:
        items: 原始字幕片段列表
        tts_durations: 每个片段的 TTS 时长列表（毫秒）
        gaps: 间隙列表
        output_path: 输出路径
        keep_speaker_tags: 是否保留说话人标签
        
    Returns:
        生成的字幕文件路径
    """
    from pyvideotrans.core.subtitle import write_srt
    import re
    
    # Build gap map for quick lookup
    gap_map: Dict[int, Gap] = {g.prev_index: g for g in gaps}
    
    new_items: List[SRTItem] = []
    current_time_ms = 0
    
    for idx, it in enumerate(items):
        tts_duration_ms = tts_durations[idx] if idx < len(tts_durations) else (it.end_ms - it.start_ms)
        
        # Process text based on keep_speaker_tags setting
        text = it.text
        if not keep_speaker_tags:
            # Remove [Speaker:Name] or 【Speaker:Name】 tags
            text = re.sub(r'\[Speaker:[^\]]*\]\s*', '', text)
            text = re.sub(r'【Speaker:[^】]*】\s*', '', text)
            text = text.strip()
        
        # Create new subtitle item with updated timeline
        new_item = SRTItem(
            start_ms=current_time_ms,
            end_ms=current_time_ms + tts_duration_ms,
            text=text
        )
        new_items.append(new_item)
        
        # Move timeline forward
        current_time_ms += tts_duration_ms
        
        # Add gap duration if there's a gap after this segment
        if idx in gap_map:
            current_time_ms += gap_map[idx].duration_ms
    
    # Write the new subtitle file
    write_srt(output_path, new_items)
    
    return output_path
