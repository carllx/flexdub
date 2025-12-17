#!/usr/bin/env python3
"""
将 gs.md 中的正确中文内容与 SRT 的精确时间轴对齐。

策略：
1. 从 gs.md 提取纯中文段落（按时间标记分段）
2. 从 SRT 提取时间轴锚点
3. 基于时间标记对齐，然后按比例分配中间内容
"""

import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Optional

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))
from flexdub.core.subtitle import SRTItem, read_srt, write_srt


@dataclass
class GsSegment:
    """gs.md 中的一个时间段"""
    time_marker: str  # 如 "00:00", "01:18"
    start_ms: int
    text: str


def parse_time_marker(marker: str) -> int:
    """将 MM:SS 格式转换为毫秒"""
    parts = marker.split(":")
    if len(parts) == 2:
        minutes, seconds = int(parts[0]), int(parts[1])
        return (minutes * 60 + seconds) * 1000
    return 0


def extract_gs_segments(gs_path: str) -> List[GsSegment]:
    """从 gs.md 提取中文内容段落"""
    with open(gs_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 匹配 ### [MM:SS] 主讲人 格式的段落
    pattern = r'### \[(\d{2}:\d{2})\] 主讲人\n(.*?)(?=### \[|\n## |$)'
    matches = re.findall(pattern, content, re.DOTALL)
    
    segments = []
    for time_marker, text in matches:
        # 清理文本：移除多余空白、保留纯中文内容
        text = text.strip()
        # 移除图像补充说明部分
        text = re.sub(r'## 🔍 图像补充说明.*?(?=###|\Z)', '', text, flags=re.DOTALL)
        text = text.strip()
        
        if text:
            segments.append(GsSegment(
                time_marker=time_marker,
                start_ms=parse_time_marker(time_marker),
                text=text
            ))
    
    return segments


def find_srt_anchor(srt_items: List[SRTItem], target_ms: int, tolerance_ms: int = 5000) -> Optional[int]:
    """找到最接近目标时间的 SRT 条目索引"""
    best_idx = None
    best_diff = float('inf')
    
    for i, item in enumerate(srt_items):
        diff = abs(item.start_ms - target_ms)
        if diff < best_diff and diff <= tolerance_ms:
            best_diff = diff
            best_idx = i
    
    return best_idx


def split_text_to_sentences(text: str) -> List[str]:
    """将文本分割成句子"""
    # 按中文句号、问号、感叹号分割
    sentences = re.split(r'(?<=[。？！])', text)
    # 过滤空句子并清理
    return [s.strip() for s in sentences if s.strip()]


def align_gs_to_srt(gs_segments: List[GsSegment], srt_items: List[SRTItem]) -> List[SRTItem]:
    """将 gs 内容与 SRT 时间轴对齐"""
    result = []
    
    for i, gs_seg in enumerate(gs_segments):
        # 找到这个段落对应的 SRT 起始位置
        start_idx = find_srt_anchor(srt_items, gs_seg.start_ms)
        if start_idx is None:
            print(f"警告: 无法找到 {gs_seg.time_marker} 的锚点")
            continue
        
        # 确定结束位置（下一个 gs 段落的起始位置或 SRT 末尾）
        if i + 1 < len(gs_segments):
            end_idx = find_srt_anchor(srt_items, gs_segments[i + 1].start_ms)
            if end_idx is None:
                end_idx = len(srt_items)
        else:
            end_idx = 