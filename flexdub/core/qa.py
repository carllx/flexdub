"""
QA (Quality Assurance) Module for Mode B Pipeline

提供语义重构阶段的质量检查功能，包括：
- 说话人标签覆盖率检查
- 时间轴完整性检查
- 字符/时长限制检查
- voice_map.json 验证
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
import json
import os

from flexdub.core.subtitle import SRTItem, read_srt, extract_speaker


@dataclass
class QAReport:
    """质量检查报告"""
    srt_valid: bool                    # SRT 格式是否有效
    speaker_coverage: float            # 说话人标签覆盖率
    missing_speakers: List[int]        # 缺少标签的片段索引
    timeline_complete: bool            # 时间轴是否完整
    first_start_ms: int                # 第一个片段开始时间
    last_end_ms: int                   # 最后一个片段结束时间
    max_chars_exceeded: List[int]      # 超过字符限制的片段索引
    max_duration_exceeded: List[int]   # 超过时长限制的片段索引
    voice_map_valid: bool              # voice_map.json 是否有效
    voice_map_has_default: bool        # 是否包含 DEFAULT
    all_passed: bool                   # 是否所有检查通过


def check_speaker_coverage(items: List[SRTItem]) -> Tuple[float, List[int]]:
    """
    检查说话人标签覆盖率
    
    Args:
        items: 字幕片段列表
        
    Returns:
        Tuple of (coverage_ratio, missing_indices)
        - coverage_ratio: 0.0 到 1.0 之间的覆盖率
        - missing_indices: 缺少说话人标签的片段索引列表
    """
    if not items:
        return 1.0, []
    
    missing_indices: List[int] = []
    
    for idx, item in enumerate(items):
        speaker, _ = extract_speaker(item.text)
        if speaker is None:
            missing_indices.append(idx)
    
    coverage = (len(items) - len(missing_indices)) / len(items)
    return coverage, missing_indices


def check_timeline_completeness(
    items: List[SRTItem],
    video_duration_ms: Optional[int] = None,
    tolerance_ms: int = 1000
) -> Tuple[bool, int, int]:
    """
    检查时间轴完整性
    
    Args:
        items: 字幕片段列表
        video_duration_ms: 视频总时长（毫秒），如果提供则检查是否覆盖整个视频
        tolerance_ms: 允许的误差范围（毫秒）
        
    Returns:
        Tuple of (is_complete, first_start_ms, last_end_ms)
    """
    if not items:
        return False, 0, 0
    
    first_start_ms = items[0].start_ms
    last_end_ms = items[-1].end_ms
    
    # 如果提供了视频时长，检查是否覆盖整个视频
    if video_duration_ms is not None:
        # 第一个片段应该在视频开始附近
        start_ok = first_start_ms <= tolerance_ms
        # 最后一个片段应该在视频结束附近
        end_ok = abs(last_end_ms - video_duration_ms) <= tolerance_ms
        is_complete = start_ok and end_ok
    else:
        # 没有视频时长，只检查是否有内容
        is_complete = last_end_ms > first_start_ms
    
    return is_complete, first_start_ms, last_end_ms


def check_block_limits(
    items: List[SRTItem],
    max_chars: int = 250,
    max_duration_ms: int = 15000
) -> Tuple[List[int], List[int]]:
    """
    检查字符和时长限制
    
    Args:
        items: 字幕片段列表
        max_chars: 最大字符数限制
        max_duration_ms: 最大时长限制（毫秒）
        
    Returns:
        Tuple of (chars_exceeded_indices, duration_exceeded_indices)
    """
    chars_exceeded: List[int] = []
    duration_exceeded: List[int] = []
    
    for idx, item in enumerate(items):
        # 检查字符数
        if len(item.text) > max_chars:
            chars_exceeded.append(idx)
        
        # 检查时长
        duration = item.end_ms - item.start_ms
        if duration > max_duration_ms:
            duration_exceeded.append(idx)
    
    return chars_exceeded, duration_exceeded


def check_voice_map(voice_map_path: str) -> Tuple[bool, bool]:
    """
    检查 voice_map.json 是否有效
    
    Args:
        voice_map_path: voice_map.json 文件路径
        
    Returns:
        Tuple of (is_valid, has_default)
    """
    if not os.path.exists(voice_map_path):
        return False, False
    
    try:
        with open(voice_map_path, "r", encoding="utf-8") as f:
            voice_map = json.load(f)
        
        if not isinstance(voice_map, dict):
            return False, False
        
        has_default = "DEFAULT" in voice_map
        return True, has_default
    except (json.JSONDecodeError, IOError):
        return False, False


def run_qa_checks(
    srt_path: str,
    voice_map_path: Optional[str] = None,
    video_duration_ms: Optional[int] = None,
    max_chars: int = 250,
    max_duration_ms: int = 15000
) -> QAReport:
    """
    执行所有质量检查
    
    Args:
        srt_path: 字幕文件路径
        voice_map_path: voice_map.json 路径（可选）
        video_duration_ms: 视频总时长（毫秒，可选）
        max_chars: 最大字符数限制
        max_duration_ms: 最大时长限制（毫秒）
        
    Returns:
        QA 报告，包含所有检查项的结果
    """
    # 尝试读取 SRT 文件
    try:
        items = read_srt(srt_path)
        srt_valid = True
    except Exception:
        # SRT 文件无效
        return QAReport(
            srt_valid=False,
            speaker_coverage=0.0,
            missing_speakers=[],
            timeline_complete=False,
            first_start_ms=0,
            last_end_ms=0,
            max_chars_exceeded=[],
            max_duration_exceeded=[],
            voice_map_valid=False,
            voice_map_has_default=False,
            all_passed=False
        )
    
    # 检查说话人覆盖率
    speaker_coverage, missing_speakers = check_speaker_coverage(items)
    
    # 检查时间轴完整性
    timeline_complete, first_start_ms, last_end_ms = check_timeline_completeness(
        items, video_duration_ms
    )
    
    # 检查字符和时长限制
    max_chars_exceeded, max_duration_exceeded = check_block_limits(
        items, max_chars, max_duration_ms
    )
    
    # 检查 voice_map.json
    voice_map_valid = False
    voice_map_has_default = False
    if voice_map_path:
        voice_map_valid, voice_map_has_default = check_voice_map(voice_map_path)
    
    # 判断是否所有检查通过
    all_passed = (
        srt_valid and
        speaker_coverage == 1.0 and
        timeline_complete and
        len(max_chars_exceeded) == 0 and
        len(max_duration_exceeded) == 0 and
        (voice_map_path is None or (voice_map_valid and voice_map_has_default))
    )
    
    return QAReport(
        srt_valid=srt_valid,
        speaker_coverage=speaker_coverage,
        missing_speakers=missing_speakers,
        timeline_complete=timeline_complete,
        first_start_ms=first_start_ms,
        last_end_ms=last_end_ms,
        max_chars_exceeded=max_chars_exceeded,
        max_duration_exceeded=max_duration_exceeded,
        voice_map_valid=voice_map_valid,
        voice_map_has_default=voice_map_has_default,
        all_passed=all_passed
    )
