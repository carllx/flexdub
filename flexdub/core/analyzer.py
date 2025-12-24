"""
Project Analyzer Module

从 agent_manual.md 的决策矩阵中提取的硬编码逻辑。
提供项目分析和模式推荐功能。

核心功能：
- get_video_metrics: 获取视频和字幕的指标
- recommend_mode: 根据指标推荐处理模式 (A/B)
- analyze_project: 完整的项目分析
"""

import glob
import os
from dataclasses import dataclass
from typing import Optional, List, Tuple

from flexdub.core.subtitle import read_srt, extract_speaker
from flexdub.core.audio import media_duration_ms
from flexdub.core.lang import detect_language


@dataclass
class ProjectMetrics:
    """项目指标数据"""
    project_dir: str
    video_path: str
    srt_path: str
    duration_ms: int
    segment_count: int
    avg_cpm: float
    max_cpm: float
    min_cpm: float
    detected_language: str
    speaker_count: int
    has_voice_map: bool
    high_density_segments: int = 0  # CPM > 300 的片段数
    extreme_density_segments: int = 0  # CPM > 900 的片段数


@dataclass
class ModeRecommendation:
    """模式推荐结果"""
    mode: str  # "A" (elastic-audio) 或 "B" (elastic-video)
    reason: str
    confidence: float  # 0.0 - 1.0
    suggested_params: dict
    warnings: List[str]


def calculate_cpm(text: str, duration_ms: int) -> float:
    """
    计算 CPM (Characters Per Minute)
    
    Args:
        text: 文本内容
        duration_ms: 时长（毫秒）
        
    Returns:
        CPM 值
    """
    if duration_ms <= 0:
        return 0.0
    chars = len(text.strip())
    return chars / (duration_ms / 60000.0)


def get_video_metrics(video_path: str, srt_path: str) -> Tuple[int, List[Tuple[int, float]]]:
    """
    获取视频和字幕的基础指标
    
    Args:
        video_path: 视频文件路径
        srt_path: SRT 文件路径
        
    Returns:
        Tuple of (duration_ms, [(segment_index, cpm), ...])
    """
    duration_ms = media_duration_ms(video_path)
    items = read_srt(srt_path)
    
    cpm_list = []
    for idx, item in enumerate(items):
        seg_duration = item.end_ms - item.start_ms
        cpm = calculate_cpm(item.text, seg_duration)
        cpm_list.append((idx, cpm))
    
    return duration_ms, cpm_list


def count_speakers(srt_path: str) -> int:
    """
    统计说话人数量
    
    Args:
        srt_path: SRT 文件路径
        
    Returns:
        说话人数量
    """
    items = read_srt(srt_path)
    speakers = set()
    
    for item in items:
        speaker, _ = extract_speaker(item.text)
        if speaker:
            speakers.add(speaker)
    
    return max(1, len(speakers))


def recommend_mode(metrics: ProjectMetrics) -> ModeRecommendation:
    """
    根据项目指标推荐处理模式
    
    决策逻辑（来自 agent_manual.md 第 2 章）：
    - CPM ≤ 300: Mode A (弹性音频) - 音频可压缩适配
    - CPM > 300: Mode B (弹性视频) - 需要自然语速
    - 高密度片段多: Mode B 更安全
    
    Args:
        metrics: 项目指标
        
    Returns:
        ModeRecommendation 包含推荐模式和参数
    """
    warnings = []
    suggested_params = {
        "backend": "edge_tts",
        "ar": 48000,
        "jobs": 4,
    }
    
    # 决策逻辑
    if metrics.max_cpm > 300:
        mode = "B"
        reason = f"最大 CPM ({metrics.max_cpm:.0f}) 超过 300，推荐 Mode B 以保持自然语速"
        confidence = 0.9
        suggested_params.update({
            "mode": "elastic-video",
            "no_rebalance": True,
            "max_chars": 100,
            "max_duration_ms": 6000,
        })
    elif metrics.avg_cpm > 250:
        mode = "A"
        reason = f"平均 CPM ({metrics.avg_cpm:.0f}) 较高但可接受，推荐 Mode A 配合 rebalance"
        confidence = 0.7
        suggested_params.update({
            "mode": "elastic-audio",
            "clustered": True,
            "target_cpm": 160,
            "max_shift": 3000,
        })
    else:
        mode = "A"
        reason = f"CPM 在正常范围内 (avg={metrics.avg_cpm:.0f})，推荐 Mode A"
        confidence = 0.95
        suggested_params.update({
            "mode": "elastic-audio",
            "clustered": True,
            "target_cpm": 180,
            "max_shift": 1000,
        })
    
    # 高密度警告
    if metrics.extreme_density_segments > 0:
        warnings.append(
            f"检测到 {metrics.extreme_density_segments} 个极高密度片段 (CPM > 900)，"
            "建议在 LLM 阶段进行分句处理"
        )
    
    if metrics.high_density_segments > metrics.segment_count * 0.2:
        warnings.append(
            f"超过 20% 的片段 CPM > 300，可能需要调整 target_cpm 参数"
        )
    
    # 多说话人处理
    if metrics.speaker_count > 1:
        suggested_params["voice_map"] = True
        suggested_params["keep_brackets"] = True
        if not metrics.has_voice_map:
            warnings.append("检测到多说话人但缺少 voice_map.json，需要先生成")
    
    return ModeRecommendation(
        mode=mode,
        reason=reason,
        confidence=confidence,
        suggested_params=suggested_params,
        warnings=warnings,
    )


def analyze_project(project_dir: str) -> ProjectMetrics:
    """
    完整分析项目目录
    
    Args:
        project_dir: 项目目录路径
        
    Returns:
        ProjectMetrics 包含所有分析结果
        
    Raises:
        FileNotFoundError: 如果找不到必需的文件
    """
    project_dir = os.path.abspath(project_dir)
    
    # 查找视频和字幕文件
    mp4s = glob.glob(os.path.join(project_dir, "*.mp4"))
    srts = glob.glob(os.path.join(project_dir, "*.srt"))
    
    if not mp4s:
        raise FileNotFoundError(f"No MP4 file found in {project_dir}")
    if not srts:
        raise FileNotFoundError(f"No SRT file found in {project_dir}")
    
    video_path = mp4s[0]
    srt_path = srts[0]
    
    # 获取基础指标
    duration_ms, cpm_list = get_video_metrics(video_path, srt_path)
    
    # 计算 CPM 统计
    if cpm_list:
        cpm_values = [cpm for _, cpm in cpm_list]
        avg_cpm = sum(cpm_values) / len(cpm_values)
        max_cpm = max(cpm_values)
        min_cpm = min(cpm_values)
        high_density = sum(1 for cpm in cpm_values if cpm > 300)
        extreme_density = sum(1 for cpm in cpm_values if cpm > 900)
    else:
        avg_cpm = max_cpm = min_cpm = 0.0
        high_density = extreme_density = 0
    
    # 检测语言
    items = read_srt(srt_path)
    texts = [item.text for item in items]
    detected_language = detect_language(texts)
    
    # 统计说话人
    speaker_count = count_speakers(srt_path)
    
    # 检查 voice_map.json
    voice_map_path = os.path.join(project_dir, "voice_map.json")
    has_voice_map = os.path.exists(voice_map_path)
    
    return ProjectMetrics(
        project_dir=project_dir,
        video_path=video_path,
        srt_path=srt_path,
        duration_ms=duration_ms,
        segment_count=len(cpm_list),
        avg_cpm=avg_cpm,
        max_cpm=max_cpm,
        min_cpm=min_cpm,
        detected_language=detected_language,
        speaker_count=speaker_count,
        has_voice_map=has_voice_map,
        high_density_segments=high_density,
        extreme_density_segments=extreme_density,
    )
