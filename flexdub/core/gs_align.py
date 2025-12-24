"""
gs.md 与 SRT 对齐模块

实现 gs.md（人工校对稿）与原始 SRT（精确时间轴）的语义对齐。

核心思路：
- gs.md 提供高质量翻译文本和粗略时间锚点
- 原始 SRT 提供精确时间轴
- 对齐算法将两者融合，生成 TTS 用的 audio.srt

设计决策：
- 使用语义解析识别 gs.md 文档结构
- 只提取"完整逐字稿"部分，排除图像说明、术语表、学习笔记
- 支持多说话人标签提取和传播
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from enum import Enum

from flexdub.core.subtitle import SRTItem
from flexdub.core.rebalance import Segment, rebalance_intervals


class SectionType(Enum):
    """gs.md 文档部分类型"""
    TRANSCRIPT = "transcript"      # 完整逐字稿（主要内容）
    IMAGE_DESC = "image_desc"      # 图像补充说明（排除）
    GLOSSARY = "glossary"          # 重要术语（排除）
    LEARNING = "learning"          # 学习收获（排除）
    INFO = "info"                  # 基本信息（排除）
    UNKNOWN = "unknown"            # 未知部分


@dataclass
class GSSegment:
    """gs.md 中的一个段落（增强版）"""
    start_ms: int           # 从 ### [MM:SS] 解析的时间锚点
    speaker: str            # 说话人名称
    text: str               # 翻译文本（可能是多个自然段）
    section_type: SectionType = SectionType.TRANSCRIPT  # 部分类型


# 保留旧的 GsParagraph 作为别名，保持向后兼容
@dataclass
class GsParagraph:
    """gs.md 中的一个段落（向后兼容）"""
    anchor_ms: int      # 从 ### [MM:SS] 解析的时间锚点
    speaker: str        # 说话人名称
    text: str           # 翻译文本（可能是多个自然段）
    

def parse_timestamp(ts_str: str) -> int:
    """
    解析时间戳字符串为毫秒
    支持格式: MM:SS 或 HH:MM:SS
    """
    parts = ts_str.strip().split(':')
    if len(parts) == 2:
        minutes, seconds = int(parts[0]), int(parts[1])
        return (minutes * 60 + seconds) * 1000
    elif len(parts) == 3:
        hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
        return (hours * 3600 + minutes * 60 + seconds) * 1000
    return 0


def identify_section_type(header: str) -> SectionType:
    """
    语义识别文档部分类型
    
    Args:
        header: 部分标题（如 "## 完整逐字稿"）
        
    Returns:
        SectionType 枚举值
    """
    header_lower = header.lower().strip()
    
    # 逐字稿部分（主要内容）
    transcript_markers = [
        '完整逐字稿', '逐字稿', 'transcript', 'full transcript',
        '继续', 'q&a', 'qa部分', '问答'
    ]
    for marker in transcript_markers:
        if marker in header_lower:
            return SectionType.TRANSCRIPT
    
    # 图像说明部分（排除）
    image_markers = ['图像', '画面', 'image', '补充说明', '🔍']
    for marker in image_markers:
        if marker in header_lower:
            return SectionType.IMAGE_DESC
    
    # 术语表部分（排除）
    glossary_markers = ['术语', '人物', 'glossary', 'terms', '📚']
    for marker in glossary_markers:
        if marker in header_lower:
            return SectionType.GLOSSARY
    
    # 学习收获部分（排除）
    learning_markers = ['学习', '收获', 'learning', '思考', '💡']
    for marker in learning_markers:
        if marker in header_lower:
            return SectionType.LEARNING
    
    # 基本信息部分（排除）
    info_markers = ['基本信息', 'info', '视频时长', '讲者']
    for marker in info_markers:
        if marker in header_lower:
            return SectionType.INFO
    
    return SectionType.UNKNOWN


def find_transcript_sections(content: str) -> List[Tuple[int, int, SectionType]]:
    """
    找到所有逐字稿部分的位置范围
    
    Args:
        content: gs.md 文件内容
        
    Returns:
        List of (start_pos, end_pos, section_type) tuples
    """
    # 匹配二级标题 ## xxx
    section_pattern = re.compile(r'^##\s+(.+)$', re.MULTILINE)
    
    sections = []
    matches = list(section_pattern.finditer(content))
    
    for i, match in enumerate(matches):
        header = match.group(1)
        section_type = identify_section_type(header)
        start_pos = match.end()
        
        # 确定部分结束位置（下一个二级标题或文件末尾）
        if i + 1 < len(matches):
            end_pos = matches[i + 1].start()
        else:
            end_pos = len(content)
        
        sections.append((start_pos, end_pos, section_type))
    
    return sections


def clean_text_for_tts(text: str, remove_english_in_parens: bool = True) -> str:
    """
    清理文本以适合 TTS 合成
    
    Args:
        text: 原始文本
        remove_english_in_parens: 是否移除括号中的英文原文
        
    Returns:
        清理后的文本
    """
    # 移除 Markdown 粗体
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    
    # 移除 Markdown 斜体
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    
    # 移除括号中的英文原文（如 "修辞学（Rhetoric）" → "修辞学"）
    # 但保留人名翻译（如 "Noah（诺亚）" 保留为 "诺亚"）
    if remove_english_in_parens:
        # 匹配中文词后跟括号中的英文
        text = re.sub(r'（[A-Za-z][A-Za-z\s\-\'\.]+）', '', text)
        text = re.sub(r'\([A-Za-z][A-Za-z\s\-\'\.]+\)', '', text)
        
        # 对于人名，保留中文翻译：Noah（诺亚）→ 诺亚
        # 匹配英文名后跟括号中的中文
        text = re.sub(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*（([^）]+)）', r'\2', text)
        text = re.sub(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\(([^)]+)\)', r'\2', text)
    
    # 移除图像描述行（如 "**[05:07]** 画面内容：..."）
    text = re.sub(r'\*\*\[\d{1,2}:\d{2}\]\*\*\s*画面内容[：:].+', '', text)
    
    # 移除列表标记
    text = re.sub(r'^[-*]\s+', '', text, flags=re.MULTILINE)
    
    # 移除多余空白
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def parse_gs_md(content: str) -> List[GsParagraph]:
    """
    语义解析 gs.md 文件内容
    
    只提取"完整逐字稿"部分的内容，排除：
    - 图像补充说明
    - 重要术语和人物
    - 学习收获
    - 基本信息
    
    格式示例:
    ### [00:00] Ian Bogost
    好的。Noah（诺亚）让我来谈谈...
    
    ### [01:18] Ian Bogost
    但如果我们回顾历史...
    
    Args:
        content: gs.md 文件的完整内容
        
    Returns:
        GsParagraph 列表，只包含逐字稿部分的段落
    """
    paragraphs: List[GsParagraph] = []
    
    # Step 1: 找到所有逐字稿部分
    sections = find_transcript_sections(content)
    transcript_sections = [
        (start, end) for start, end, stype in sections 
        if stype == SectionType.TRANSCRIPT
    ]
    
    if not transcript_sections:
        # 如果没有找到明确的逐字稿部分，使用旧的逻辑作为回退
        return _parse_gs_md_legacy(content)
    
    # Step 2: 合并所有逐字稿部分的内容
    transcript_content = ""
    for start, end in transcript_sections:
        transcript_content += content[start:end] + "\n"
    
    # Step 3: 在逐字稿内容中提取时间锚点和段落
    # 匹配 ### [MM:SS] Speaker 或 ### [HH:MM:SS] Speaker
    header_pattern = re.compile(r'^###\s*\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.+)$', re.MULTILINE)
    
    headers = list(header_pattern.finditer(transcript_content))
    
    for i, match in enumerate(headers):
        timestamp_str = match.group(1)
        speaker = match.group(2).strip()
        anchor_ms = parse_timestamp(timestamp_str)
        
        # 提取该段落的文本（从当前标题到下一个标题之间）
        start_pos = match.end()
        end_pos = headers[i + 1].start() if i + 1 < len(headers) else len(transcript_content)
        
        text = transcript_content[start_pos:end_pos].strip()
        
        # 清理文本
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        # 过滤掉以 ## 或 ### 开头的行（可能是其他标题）
        lines = [line for line in lines if not line.startswith('#')]
        # 过滤掉图像说明等元信息
        lines = [line for line in lines if not line.startswith('- **') and not line.startswith('**[')]
        
        # 合并并清理文本
        raw_text = ' '.join(lines)
        cleaned_text = clean_text_for_tts(raw_text)
        
        if cleaned_text:
            paragraphs.append(GsParagraph(
                anchor_ms=anchor_ms,
                speaker=speaker,
                text=cleaned_text
            ))
    
    return paragraphs


def _parse_gs_md_legacy(content: str) -> List[GsParagraph]:
    """
    旧版 gs.md 解析逻辑（作为回退）
    
    当无法识别文档结构时使用
    """
    paragraphs: List[GsParagraph] = []
    
    # 匹配 ### [MM:SS] Speaker 或 ### [HH:MM:SS] Speaker
    header_pattern = re.compile(r'^###\s*\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.+)$', re.MULTILINE)
    
    # 检测内容结束标记（学习收获、图像说明等非逐字稿部分）
    end_markers = [
        '## 📚', '## 💡', '## 🔍',  # Emoji 标题
        '## 重要术语', '## 我的学习', '## 图像补充',  # 中文标题
        '## Important', '## My Learning', '## Image',  # 英文标题
    ]
    
    # 找到内容结束位置
    content_end = len(content)
    for marker in end_markers:
        pos = content.find(marker)
        if pos > 0 and pos < content_end:
            content_end = pos
    
    # 只处理逐字稿部分
    transcript_content = content[:content_end]
    
    # 找到所有标题位置
    headers = list(header_pattern.finditer(transcript_content))
    
    for i, match in enumerate(headers):
        timestamp_str = match.group(1)
        speaker = match.group(2).strip()
        anchor_ms = parse_timestamp(timestamp_str)
        
        # 提取该段落的文本（从当前标题到下一个标题之间）
        start_pos = match.end()
        end_pos = headers[i + 1].start() if i + 1 < len(headers) else len(transcript_content)
        
        text = transcript_content[start_pos:end_pos].strip()
        
        # 清理文本：移除空行，合并为单段
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        # 过滤掉以 ## 或 ### 开头的行（可能是其他标题）
        lines = [line for line in lines if not line.startswith('#')]
        # 过滤掉图像说明等元信息
        lines = [line for line in lines if not line.startswith('- **') and not line.startswith('**[')]
        
        cleaned_text = ' '.join(lines)
        
        if cleaned_text:
            paragraphs.append(GsParagraph(
                anchor_ms=anchor_ms,
                speaker=speaker,
                text=cleaned_text
            ))
    
    return paragraphs


def extract_speakers(content: str) -> List[str]:
    """
    从 gs.md 中提取所有唯一的说话人名称
    
    Args:
        content: gs.md 文件内容
        
    Returns:
        唯一说话人名称列表
    """
    paragraphs = parse_gs_md(content)
    speakers = []
    seen = set()
    
    for p in paragraphs:
        if p.speaker not in seen:
            speakers.append(p.speaker)
            seen.add(p.speaker)
    
    return speakers


class SpeakerTracker:
    """
    说话人跟踪器
    
    跟踪当前说话人并管理说话人到音色的映射。
    """
    
    DEFAULT_VOICE = "DEFAULT"
    
    def __init__(self, voice_map_path: Optional[str] = None):
        """
        初始化说话人跟踪器
        
        Args:
            voice_map_path: voice_map.json 文件路径（可选）
        """
        self.voice_map: Dict[str, str] = {}
        self.current_speaker: str = self.DEFAULT_VOICE
        self._speaker_timestamps: List[Tuple[int, str]] = []  # (timestamp_ms, speaker)
        
        if voice_map_path:
            self.load_voice_map(voice_map_path)
    
    def load_voice_map(self, path: str) -> None:
        """
        从 JSON 文件加载说话人到音色的映射
        
        Args:
            path: voice_map.json 文件路径
        """
        import json
        from pathlib import Path
        
        voice_map_file = Path(path)
        if voice_map_file.exists():
            try:
                with open(voice_map_file, 'r', encoding='utf-8') as f:
                    self.voice_map = json.load(f)
            except json.JSONDecodeError as e:
                import warnings
                warnings.warn(f"voice_map.json 格式错误: {e}，使用默认映射")
                self.voice_map = {}
    
    def set_speaker_anchors(self, gs_paragraphs: List[GsParagraph]) -> None:
        """
        从 gs.md 段落设置说话人时间锚点
        
        Args:
            gs_paragraphs: 解析后的 gs.md 段落列表
        """
        self._speaker_timestamps = [
            (p.anchor_ms, p.speaker) for p in gs_paragraphs
        ]
        # 按时间排序
        self._speaker_timestamps.sort(key=lambda x: x[0])
        
        # 设置初始说话人
        if self._speaker_timestamps:
            self.current_speaker = self._speaker_timestamps[0][1]
    
    def update_speaker(self, timestamp_ms: int) -> str:
        """
        根据时间戳更新并返回当前说话人
        
        Args:
            timestamp_ms: 当前时间戳（毫秒）
            
        Returns:
            当前说话人名称
        """
        if not self._speaker_timestamps:
            return self.current_speaker
        
        # 找到最近的说话人锚点（不超过当前时间）
        for ts, speaker in reversed(self._speaker_timestamps):
            if ts <= timestamp_ms:
                self.current_speaker = speaker
                break
        
        return self.current_speaker
    
    def get_voice(self, speaker: str) -> str:
        """
        获取说话人对应的 TTS 音色
        
        Args:
            speaker: 说话人名称
            
        Returns:
            TTS 音色标识符，如果未找到则返回 DEFAULT 对应的音色
        """
        if speaker in self.voice_map:
            return self.voice_map[speaker]
        
        # 回退到 DEFAULT
        if self.DEFAULT_VOICE in self.voice_map:
            return self.voice_map[self.DEFAULT_VOICE]
        
        return self.DEFAULT_VOICE
    
    def generate_voice_map(self, speakers: List[str]) -> Dict[str, str]:
        """
        生成 voice_map.json 模板
        
        Args:
            speakers: 说话人名称列表
            
        Returns:
            包含所有说话人的音色映射字典（值为占位符）
        """
        voice_map = {self.DEFAULT_VOICE: "磁性俊宇"}  # 默认音色
        
        for speaker in speakers:
            if speaker not in voice_map:
                # 使用占位符，用户需要手动填写
                voice_map[speaker] = f"<请为 {speaker} 选择音色>"
        
        return voice_map
    
    def save_voice_map(self, path: str, speakers: List[str]) -> None:
        """
        保存 voice_map.json 文件
        
        Args:
            path: 保存路径
            speakers: 说话人名称列表
        """
        import json
        from pathlib import Path
        
        voice_map = self.generate_voice_map(speakers)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(voice_map, f, ensure_ascii=False, indent=2)
    
    def validate_speakers(self, speakers: List[str]) -> List[str]:
        """
        验证所有说话人是否都有对应的音色映射
        
        Args:
            speakers: 说话人名称列表
            
        Returns:
            缺失映射的说话人列表
        """
        missing = []
        for speaker in speakers:
            if speaker not in self.voice_map and speaker != self.DEFAULT_VOICE:
                missing.append(speaker)
        return missing


class TextSplitter:
    """
    文本分割器
    
    处理文本清理和 TTS 优化分割。
    """
    
    MAX_CHARS = 75  # Doubao TTS 字符限制
    
    # 口语填充词
    FILLERS = ['嗯', '啊', '呃', '额', '哦', '噢', '唔', '呢', '吧', '啦']
    
    def __init__(self, max_chars: int = 75):
        """
        初始化文本分割器
        
        Args:
            max_chars: 单段最大字符数
        """
        self.max_chars = max_chars
    
    def clean_markdown(self, text: str) -> str:
        """
        移除 Markdown 格式
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文本
        """
        # 移除粗体 **text**
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        
        # 移除斜体 *text*
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        
        # 移除标题 # ## ###
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
        
        # 移除列表标记 - * 
        text = re.sub(r'^[-*]\s+', '', text, flags=re.MULTILINE)
        
        # 移除链接 [text](url)
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        
        # 移除代码块 `code`
        text = re.sub(r'`([^`]+)`', r'\1', text)
        
        return text.strip()
    
    def remove_image_descriptions(self, text: str) -> str:
        """
        移除图像描述
        
        格式: **[MM:SS]** 画面内容：...
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文本
        """
        # 移除带时间戳的图像描述（到句号或换行为止）
        text = re.sub(r'\*\*\[\d{1,2}:\d{2}\]\*\*\s*画面内容[：:][^。\n]*[。]?', '', text)
        
        # 移除其他图像描述格式（到句号或换行为止）
        text = re.sub(r'画面内容[：:][^。\n]*[。]?', '', text)
        text = re.sub(r'屏幕显示[：:][^。\n]*[。]?', '', text)
        
        return text.strip()
    
    def remove_fillers(self, text: str) -> str:
        """
        移除口语填充词
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文本
        """
        for filler in self.FILLERS:
            # 移除句首的填充词
            text = re.sub(rf'^{filler}[，,、]?\s*', '', text)
            # 移除句中独立的填充词（前后有标点）
            text = re.sub(rf'[，,、]\s*{filler}\s*[，,、]', '，', text)
        
        # 清理多余的标点
        text = re.sub(r'[，,]{2,}', '，', text)
        
        return text.strip()
    
    def clean_all(self, text: str) -> str:
        """
        执行所有清理操作
        
        Args:
            text: 原始文本
            
        Returns:
            完全清理后的文本
        """
        text = self.clean_markdown(text)
        text = self.remove_image_descriptions(text)
        text = self.remove_fillers(text)
        
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def split_for_tts(self, text: str, max_chars: Optional[int] = None) -> List[str]:
        """
        按自然边界分割文本以适合 TTS
        
        优先在句号处分割，其次在逗号处分割。
        
        Args:
            text: 要分割的文本
            max_chars: 最大字符数（默认使用实例设置）
            
        Returns:
            分割后的文本列表
        """
        if max_chars is None:
            max_chars = self.max_chars
        
        if len(text) <= max_chars:
            return [text]
        
        # 句子终止符
        sentence_ends = re.compile(r'([。！？.!?])')
        # 次级分隔符
        clause_ends = re.compile(r'([，,；;：:])')
        
        result: List[str] = []
        
        # 首先尝试按句子拆分
        parts = sentence_ends.split(text)
        # 重新组合（保留标点）
        sentences = []
        i = 0
        while i < len(parts):
            if i + 1 < len(parts) and sentence_ends.match(parts[i + 1]):
                sentences.append(parts[i] + parts[i + 1])
                i += 2
            else:
                if parts[i].strip():
                    sentences.append(parts[i])
                i += 1
        
        # 合并短句，拆分长句
        current = ""
        for sent in sentences:
            if not sent.strip():
                continue
            if len(current) + len(sent) <= max_chars:
                current += sent
            else:
                if current:
                    result.append(current.strip())
                # 如果单个句子就超长，需要在逗号处拆分
                if len(sent) > max_chars:
                    sub_parts = clause_ends.split(sent)
                    sub_current = ""
                    j = 0
                    while j < len(sub_parts):
                        part = sub_parts[j]
                        punct = sub_parts[j + 1] if j + 1 < len(sub_parts) and clause_ends.match(sub_parts[j + 1]) else ""
                        if punct:
                            j += 2
                        else:
                            j += 1
                        
                        chunk = part + punct
                        if len(sub_current) + len(chunk) <= max_chars:
                            sub_current += chunk
                        else:
                            if sub_current:
                                result.append(sub_current.strip())
                            sub_current = chunk
                    if sub_current:
                        current = sub_current
                    else:
                        current = ""
                else:
                    current = sent
        
        if current.strip():
            result.append(current.strip())
        
        return result if result else [text]


def find_matching_srt_range(
    anchor_ms: int,
    next_anchor_ms: int,
    srt_items: List[SRTItem],
    fuzzy_window_ms: int = 2000
) -> Tuple[int, int]:
    """
    找到与 gs 段落对应的 SRT 条目范围
    
    Args:
        anchor_ms: 当前段落的时间锚点
        next_anchor_ms: 下一个段落的时间锚点（用于确定范围终点）
        srt_items: SRT 条目列表
        fuzzy_window_ms: 模糊匹配窗口（毫秒），处理人工标注的时间误差
        
    Returns:
        (start_idx, end_idx): SRT 条目的起止索引（包含 end_idx）
    """
    if not srt_items:
        return (0, 0)
    
    # Phase 1: 找到起始点（允许模糊匹配）
    start_idx = 0
    min_distance = float('inf')
    
    for i, item in enumerate(srt_items):
        # 计算 SRT 条目中点与锚点的距离
        item_mid = (item.start_ms + item.end_ms) // 2
        distance = abs(item_mid - anchor_ms)
        
        # 在锚点附近（±fuzzy_window）寻找最佳匹配
        if item.start_ms >= anchor_ms - fuzzy_window_ms:
            if distance < min_distance:
                min_distance = distance
                start_idx = i
            # 如果已经超过锚点太远，停止搜索
            if item.start_ms > anchor_ms + fuzzy_window_ms:
                break
    
    # Phase 2: 找到终止点
    end_idx = start_idx
    for i in range(start_idx, len(srt_items)):
        # 如果 SRT 条目的起始时间已经超过下一个锚点，停止
        if srt_items[i].start_ms >= next_anchor_ms - fuzzy_window_ms:
            break
        end_idx = i
    
    return (start_idx, end_idx)


def split_text_by_sentences(text: str, max_chars: int = 75) -> List[str]:
    """
    按句子拆分文本，确保每段不超过 max_chars
    
    优先在句号处拆分，其次在逗号处拆分
    """
    if len(text) <= max_chars:
        return [text]
    
    # 句子终止符
    sentence_ends = re.compile(r'([。！？.!?])')
    # 次级分隔符
    clause_ends = re.compile(r'([，,；;：:])')
    
    result: List[str] = []
    
    # 首先尝试按句子拆分
    parts = sentence_ends.split(text)
    # 重新组合（保留标点）
    sentences = []
    i = 0
    while i < len(parts):
        if i + 1 < len(parts) and sentence_ends.match(parts[i + 1]):
            sentences.append(parts[i] + parts[i + 1])
            i += 2
        else:
            if parts[i].strip():
                sentences.append(parts[i])
            i += 1
    
    # 合并短句，拆分长句
    current = ""
    for sent in sentences:
        if not sent.strip():
            continue
        if len(current) + len(sent) <= max_chars:
            current += sent
        else:
            if current:
                result.append(current.strip())
            # 如果单个句子就超长，需要在逗号处拆分
            if len(sent) > max_chars:
                sub_parts = clause_ends.split(sent)
                sub_current = ""
                j = 0
                while j < len(sub_parts):
                    part = sub_parts[j]
                    punct = sub_parts[j + 1] if j + 1 < len(sub_parts) and clause_ends.match(sub_parts[j + 1]) else ""
                    if punct:
                        j += 2
                    else:
                        j += 1
                    
                    chunk = part + punct
                    if len(sub_current) + len(chunk) <= max_chars:
                        sub_current += chunk
                    else:
                        if sub_current:
                            result.append(sub_current.strip())
                        sub_current = chunk
                if sub_current:
                    current = sub_current
                else:
                    current = ""
            else:
                current = sent
    
    if current.strip():
        result.append(current.strip())
    
    return result if result else [text]


def align_gs_to_srt(
    gs_paragraphs: List[GsParagraph],
    srt_items: List[SRTItem],
    max_chars: int = 75,
    max_duration_ms: int = 15000,
    target_cpm: int = 180,
    fuzzy_window_ms: int = 2000,
    include_speaker_tags: bool = True
) -> List[SRTItem]:
    """
    将 gs.md 的翻译文本与原始 SRT 的时间轴对齐
    
    **核心设计**：保持原始 SRT 条目数量不变，对每个原始条目：
    - 如果被 gs.md 覆盖，使用 gs.md 翻译
    - 如果未被覆盖（超出最后锚点），使用原始 SRT 文本作为回退
    
    Args:
        gs_paragraphs: 从 gs.md 解析的段落列表
        srt_items: 原始 SRT 条目列表
        max_chars: 单条字幕最大字符数（Doubao TTS 限制）
        max_duration_ms: 单条字幕最大时长
        target_cpm: 目标 CPM（用于 rebalance）
        fuzzy_window_ms: 锚点模糊匹配窗口
        include_speaker_tags: 是否包含说话人标签
        
    Returns:
        对齐后的 SRT 条目列表（保持原始条目数量）
    """
    if not srt_items:
        return srt_items
    
    if not gs_paragraphs:
        # 没有 gs.md 内容，直接返回原始 SRT
        return srt_items
    
    result: List[SRTItem] = []
    
    # 初始化说话人跟踪器
    speaker_tracker = SpeakerTracker()
    speaker_tracker.set_speaker_anchors(gs_paragraphs)
    
    # 获取 gs.md 的最后一个锚点时间（用于判断回退）
    last_anchor_ms = gs_paragraphs[-1].anchor_ms if gs_paragraphs else 0
    
    # 构建 gs 段落的时间范围映射
    gs_ranges: List[Tuple[int, int, GsParagraph]] = []
    for i, gs in enumerate(gs_paragraphs):
        start_ms = gs.anchor_ms
        # 下一个锚点作为结束时间，最后一个段落延伸到视频结束
        if i + 1 < len(gs_paragraphs):
            end_ms = gs_paragraphs[i + 1].anchor_ms
        else:
            # 最后一个段落：延伸到视频结束或一个合理的时间
            end_ms = srt_items[-1].end_ms + 10000
        gs_ranges.append((start_ms, end_ms, gs))
    
    # 为每个原始 SRT 条目找到对应的 gs.md 内容
    for srt_item in srt_items:
        sub_start_ms = srt_item.start_ms
        
        # 获取当前时间点的说话人
        current_speaker = speaker_tracker.update_speaker(sub_start_ms)
        
        # 查找覆盖此时间点的 gs 段落
        covering_gs: Optional[GsParagraph] = None
        for gs_start, gs_end, gs in gs_ranges:
            if gs_start <= sub_start_ms < gs_end:
                covering_gs = gs
                break
        
        if covering_gs:
            # 被 gs.md 覆盖，使用 gs.md 翻译
            # 注意：这里我们需要将 gs 段落的文本分配给多个 SRT 条目
            # 简化处理：使用 gs 段落的文本（后续会通过 distribute_text 优化）
            text = covering_gs.text
            
            # 如果文本太长，需要分割
            if len(text) > max_chars:
                # 使用 TextSplitter 分割
                splitter = TextSplitter(max_chars=max_chars)
                parts = splitter.split_for_tts(text)
                # 取第一部分（简化处理，实际应该按比例分配）
                text = parts[0] if parts else text[:max_chars]
        else:
            # 未被覆盖（超出 gs.md 范围），使用原始 SRT 文本作为回退
            text = srt_item.text
        
        # 添加说话人标签
        if include_speaker_tags:
            text = f"[Speaker: {current_speaker}] {text}"
        
        result.append(SRTItem(
            start_ms=srt_item.start_ms,
            end_ms=srt_item.end_ms,
            text=text
        ))
    
    return result


def align_gs_to_srt_v2(
    gs_paragraphs: List[GsParagraph],
    srt_items: List[SRTItem],
    max_chars: int = 75,
    include_speaker_tags: bool = True
) -> List[SRTItem]:
    """
    使用 gs.md 为原始 SRT 添加说话人标签
    
    核心逻辑：
    - gs.md 作为背景参考信息，提供说话人切换的时间点
    - 保留原始 SRT 的翻译文本不变
    - 根据 gs.md 的时间锚点，为每个 SRT 条目添加正确的说话人标签
    
    Args:
        gs_paragraphs: 从 gs.md 解析的段落列表（提供说话人信息）
        srt_items: 原始 SRT 条目列表（已翻译的文本）
        max_chars: 单条字幕最大字符数
        include_speaker_tags: 是否包含说话人标签
        
    Returns:
        添加说话人标签后的 SRT 条目列表（条目数量与原始 SRT 相同）
    """
    if not srt_items:
        return []
    
    if not gs_paragraphs:
        return srt_items
    
    result: List[SRTItem] = []
    
    # 初始化说话人跟踪器
    speaker_tracker = SpeakerTracker()
    speaker_tracker.set_speaker_anchors(gs_paragraphs)
    
    # 处理每个原始 SRT 条目
    for srt_item in srt_items:
        # 根据时间戳获取当前说话人
        current_speaker = speaker_tracker.update_speaker(srt_item.start_ms)
        
        # 保留原始 SRT 文本
        text = srt_item.text
        
        # 添加说话人标签
        if include_speaker_tags:
            text = f"[Speaker: {current_speaker}] {text}"
        
        result.append(SRTItem(
            start_ms=srt_item.start_ms,
            end_ms=srt_item.end_ms,
            text=text
        ))
    
    return result


def fix_overlaps_and_gaps(items: List[SRTItem], min_gap_ms: int = 50) -> List[SRTItem]:
    """
    修复时间轴重叠和过小间隙
    
    Args:
        items: SRT 条目列表
        min_gap_ms: 最小间隙（毫秒）
        
    Returns:
        修复后的 SRT 条目列表
    """
    if len(items) < 2:
        return items
    
    result = [items[0]]
    
    for i in range(1, len(items)):
        prev = result[-1]
        curr = items[i]
        
        # 检查重叠
        if curr.start_ms < prev.end_ms:
            # 有重叠，调整前一条的结束时间
            mid_point = (prev.end_ms + curr.start_ms) // 2
            result[-1] = SRTItem(prev.start_ms, mid_point, prev.text)
            curr = SRTItem(mid_point, curr.end_ms, curr.text)
        
        # 检查间隙是否过小（但不为零）
        gap = curr.start_ms - result[-1].end_ms
        if 0 < gap < min_gap_ms:
            # 间隙过小，扩展前一条来填充
            result[-1] = SRTItem(result[-1].start_ms, curr.start_ms, result[-1].text)
        
        result.append(curr)
    
    return result


def extract_glossary_from_gs(content: str) -> dict:
    """
    从 gs.md 中提取术语表
    
    识别格式: English（中文翻译）或 English (中文翻译)
    """
    glossary = {}
    
    # 匹配 English（中文） 或 English (中文) 格式
    pattern = re.compile(r'\b([A-Z][a-zA-Z\s]+?)（([^）]+)）|\b([A-Z][a-zA-Z\s]+?)\s*\(([^)]+)\)')
    
    for match in pattern.finditer(content):
        if match.group(1) and match.group(2):
            en, zh = match.group(1).strip(), match.group(2).strip()
        else:
            en, zh = match.group(3).strip(), match.group(4).strip()
        
        # 过滤掉太短的匹配
        if len(en) >= 2 and len(zh) >= 1:
            glossary[en] = zh
    
    return glossary


@dataclass
class CoverageStats:
    """覆盖率统计"""
    total_entries: int          # 总 SRT 条目数
    covered_entries: int        # 被 gs.md 覆盖的条目数
    fallback_entries: int       # 使用回退的条目数
    coverage_percent: float     # 覆盖率百分比
    last_anchor_time: str       # 最后一个锚点时间
    video_duration: str         # 视频总时长
    speakers: List[str]         # 说话人列表


def calculate_coverage(
    gs_paragraphs: List[GsParagraph],
    srt_items: List[SRTItem]
) -> CoverageStats:
    """
    计算 gs.md 对 SRT 的覆盖率
    
    Args:
        gs_paragraphs: gs.md 段落列表
        srt_items: 原始 SRT 条目列表
        
    Returns:
        CoverageStats 覆盖率统计
    """
    if not srt_items:
        return CoverageStats(
            total_entries=0,
            covered_entries=0,
            fallback_entries=0,
            coverage_percent=0.0,
            last_anchor_time="00:00",
            video_duration="00:00",
            speakers=[]
        )
    
    total = len(srt_items)
    video_end_ms = srt_items[-1].end_ms
    
    if not gs_paragraphs:
        return CoverageStats(
            total_entries=total,
            covered_entries=0,
            fallback_entries=total,
            coverage_percent=0.0,
            last_anchor_time="00:00",
            video_duration=f"{video_end_ms//60000}:{(video_end_ms//1000)%60:02d}",
            speakers=[]
        )
    
    # 最后一个锚点时间
    last_anchor_ms = gs_paragraphs[-1].anchor_ms
    
    # 计算覆盖的条目数（在最后一个锚点之前的条目）
    covered = sum(1 for item in srt_items if item.start_ms <= last_anchor_ms + 60000)  # 允许 1 分钟缓冲
    fallback = total - covered
    
    # 提取说话人
    speakers = list(set(p.speaker for p in gs_paragraphs))
    
    return CoverageStats(
        total_entries=total,
        covered_entries=covered,
        fallback_entries=fallback,
        coverage_percent=100.0 * covered / total if total > 0 else 0.0,
        last_anchor_time=f"{last_anchor_ms//60000}:{(last_anchor_ms//1000)%60:02d}",
        video_duration=f"{video_end_ms//60000}:{(video_end_ms//1000)%60:02d}",
        speakers=speakers
    )


def validate_speakers(
    gs_speakers: List[str],
    voice_map: Dict[str, str]
) -> List[str]:
    """
    验证所有说话人是否都有对应的音色映射
    
    Args:
        gs_speakers: gs.md 中的说话人列表
        voice_map: 音色映射字典
        
    Returns:
        缺失映射的说话人列表
    """
    missing = []
    for speaker in gs_speakers:
        if speaker not in voice_map and speaker != "DEFAULT":
            missing.append(speaker)
    return missing


def generate_audio_srt(
    aligned_subs: List[SRTItem],
    include_speaker_tags: bool = True
) -> str:
    """
    生成 audio.srt 内容
    
    Args:
        aligned_subs: 对齐后的 SRT 条目列表
        include_speaker_tags: 是否包含说话人标签
        
    Returns:
        SRT 格式的字符串
    """
    import srt
    from datetime import timedelta
    
    srt_subs = []
    for i, item in enumerate(aligned_subs):
        text = item.text
        
        # 如果不需要说话人标签，移除它
        if not include_speaker_tags and '[Speaker:' in text:
            text = text.split('] ', 1)[1] if '] ' in text else text
        
        srt_subs.append(srt.Subtitle(
            index=i + 1,
            start=timedelta(milliseconds=item.start_ms),
            end=timedelta(milliseconds=item.end_ms),
            content=text
        ))
    
    return srt.compose(srt_subs)
