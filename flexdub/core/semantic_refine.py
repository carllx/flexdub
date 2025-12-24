"""
GS 语义矫正 SRT 翻译模块

使用 gs.md 作为语义背景上下文，通过 LLM 逐步矫正 SRT 翻译质量。
核心设计理念：
- gs.md 是背景参考信息，不是直接替换 SRT 的来源
- 使用语义理解而非机械对齐来矫正翻译
- 分段处理大文件，保持上下文连贯性
- 本地化审查确保中国人可理解
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import json
import os

from flexdub.core.subtitle import SRTItem


# =============================================================================
# 核心数据模型
# =============================================================================

@dataclass
class SpeakerProfile:
    """说话人档案"""
    name: str
    role: str = ""                      # 如：主讲人、观众提问
    speaking_style: str = ""            # 说话风格描述
    first_appearance_ms: int = 0        # 首次出现时间


@dataclass
class SemanticContext:
    """gs.md 提取的语义上下文"""
    core_topic: str = ""                # 核心主题
    domain: str = ""                    # 领域（如：游戏设计、修辞学）
    terminology: Dict[str, str] = field(default_factory=dict)  # 术语映射 {英文: 中文}
    speakers: List[SpeakerProfile] = field(default_factory=list)  # 说话人信息
    key_concepts: List[str] = field(default_factory=list)  # 关键概念列表
    translation_style: str = ""         # 翻译风格描述
    raw_content: str = ""               # 原始内容（供 LLM 参考）


@dataclass
class RefinedSRTItem:
    """矫正后的 SRT 条目（扩展 SRTItem）"""
    start_ms: int
    end_ms: int
    text: str
    speaker: Optional[str] = None
    is_refined: bool = False
    original_text: str = ""             # 原始文本（用于对比）
    
    @classmethod
    def from_srt_item(cls, item: SRTItem) -> "RefinedSRTItem":
        """从 SRTItem 创建"""
        return cls(
            start_ms=item.start_ms,
            end_ms=item.end_ms,
            text=item.text,
            original_text=item.text
        )
    
    def to_srt_item(self) -> SRTItem:
        """转换为 SRTItem"""
        return SRTItem(
            start_ms=self.start_ms,
            end_ms=self.end_ms,
            text=self.text
        )


@dataclass
class Chunk:
    """处理单元"""
    index: int
    items: List[RefinedSRTItem]
    start_ms: int
    end_ms: int
    context_summary: str = ""           # 前一个 chunk 的上下文摘要
    terminology_used: Dict[str, str] = field(default_factory=dict)  # 本 chunk 使用的术语
    
    @property
    def item_count(self) -> int:
        """条目数量"""
        return len(self.items)
    
    @property
    def duration_ms(self) -> int:
        """时长（毫秒）"""
        return self.end_ms - self.start_ms


class IssueSeverity(Enum):
    """问题严重程度"""
    WARNING = "warning"
    ERROR = "error"


@dataclass
class LocalizationIssue:
    """本地化问题"""
    index: int                          # SRT 条目索引
    issue_type: str                     # 问题类型
    original: str                       # 原文
    suggestion: str                     # 建议
    severity: IssueSeverity = IssueSeverity.WARNING


@dataclass
class ProcessingState:
    """处理状态（用于中断恢复）"""
    total_chunks: int
    completed_chunks: int
    current_chunk_index: int
    terminology: Dict[str, str] = field(default_factory=dict)
    last_context_summary: str = ""
    checkpoint_path: str = ""
    
    def to_dict(self) -> dict:
        """转换为字典（用于 JSON 序列化）"""
        return {
            "total_chunks": self.total_chunks,
            "completed_chunks": self.completed_chunks,
            "current_chunk_index": self.current_chunk_index,
            "terminology": self.terminology,
            "last_context_summary": self.last_context_summary,
            "checkpoint_path": self.checkpoint_path
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ProcessingState":
        """从字典创建"""
        return cls(
            total_chunks=data.get("total_chunks", 0),
            completed_chunks=data.get("completed_chunks", 0),
            current_chunk_index=data.get("current_chunk_index", 0),
            terminology=data.get("terminology", {}),
            last_context_summary=data.get("last_context_summary", ""),
            checkpoint_path=data.get("checkpoint_path", "")
        )
    
    def save(self, path: str) -> None:
        """保存到文件"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load(cls, path: str) -> Optional["ProcessingState"]:
        """从文件加载"""
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None


@dataclass
class RefineResult:
    """矫正结果"""
    items: List[RefinedSRTItem]
    terminology_used: Dict[str, str] = field(default_factory=dict)
    issues: List[LocalizationIssue] = field(default_factory=list)
    processing_log: str = ""
    
    @property
    def item_count(self) -> int:
        """条目数量"""
        return len(self.items)
    
    @property
    def refined_count(self) -> int:
        """已矫正的条目数量"""
        return sum(1 for item in self.items if item.is_refined)
    
    @property
    def issue_count(self) -> int:
        """问题数量"""
        return len(self.issues)
    
    def to_srt_items(self) -> List[SRTItem]:
        """转换为 SRTItem 列表"""
        return [item.to_srt_item() for item in self.items]


# =============================================================================
# 辅助函数
# =============================================================================

def srt_items_to_refined(items: List[SRTItem]) -> List[RefinedSRTItem]:
    """将 SRTItem 列表转换为 RefinedSRTItem 列表"""
    return [RefinedSRTItem.from_srt_item(item) for item in items]


def refined_to_srt_items(items: List[RefinedSRTItem]) -> List[SRTItem]:
    """将 RefinedSRTItem 列表转换为 SRTItem 列表"""
    return [item.to_srt_item() for item in items]


# =============================================================================
# Context Extractor（上下文提取器）
# =============================================================================

import re


def _parse_timestamp_to_ms(timestamp: str) -> int:
    """
    解析时间戳字符串为毫秒
    
    支持格式：
    - MM:SS
    - HH:MM:SS
    - MM:SS.mmm
    """
    timestamp = timestamp.strip()
    
    # 处理毫秒部分
    ms = 0
    if '.' in timestamp:
        timestamp, ms_str = timestamp.rsplit('.', 1)
        ms = int(ms_str.ljust(3, '0')[:3])
    
    parts = timestamp.split(':')
    if len(parts) == 2:
        minutes, seconds = int(parts[0]), int(parts[1])
        return (minutes * 60 + seconds) * 1000 + ms
    elif len(parts) == 3:
        hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
        return (hours * 3600 + minutes * 60 + seconds) * 1000 + ms
    return 0


class ContextExtractor:
    """
    从 gs.md 提取语义上下文
    
    支持不固定的 gs.md 结构，通过模式识别提取：
    - 核心主题和领域
    - 术语翻译对照
    - 说话人及其风格
    - 关键概念
    """
    
    # 时间戳+说话人格式：### [MM:SS] Speaker_Name 或 ### [HH:MM:SS] Speaker_Name
    SPEAKER_PATTERN = re.compile(
        r'^###\s*\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.+?)\s*$',
        re.MULTILINE
    )
    
    # 术语格式：英文（中文）或 英文 (中文)
    TERMINOLOGY_PATTERN = re.compile(
        r'\b([A-Za-z][A-Za-z\s\-\']+?)\s*[（(]([^）)]+)[）)]'
    )
    
    # 粗体术语格式：**术语**
    BOLD_TERM_PATTERN = re.compile(r'\*\*([^*]+)\*\*')
    
    def __init__(self, llm_client: Optional[Any] = None):
        """
        初始化上下文提取器
        
        Args:
            llm_client: 可选的 LLM 客户端，用于更智能的提取
        """
        self.llm = llm_client
    
    def extract(self, gs_content: str) -> SemanticContext:
        """
        从 gs.md 提取语义上下文
        
        Args:
            gs_content: gs.md 文件内容
            
        Returns:
            SemanticContext 对象
        """
        # 提取各部分
        core_topic = self._extract_core_topic(gs_content)
        domain = self._extract_domain(gs_content)
        terminology = self.extract_terminology(gs_content)
        speakers = self.extract_speakers(gs_content)
        key_concepts = self._extract_key_concepts(gs_content)
        translation_style = self._extract_translation_style(gs_content)
        
        return SemanticContext(
            core_topic=core_topic,
            domain=domain,
            terminology=terminology,
            speakers=speakers,
            key_concepts=key_concepts,
            translation_style=translation_style,
            raw_content=gs_content
        )
    
    def extract_terminology(self, content: str) -> Dict[str, str]:
        """
        提取术语映射
        
        识别模式：
        - 英文（中文）格式
        - 术语表部分
        - 首次出现的专业术语
        
        Args:
            content: gs.md 内容
            
        Returns:
            术语映射字典 {英文: 中文}
        """
        terminology: Dict[str, str] = {}
        
        # 1. 查找专门的术语表部分
        terminology.update(self._extract_terminology_section(content))
        
        # 2. 提取 英文（中文）格式的术语
        for match in self.TERMINOLOGY_PATTERN.finditer(content):
            eng = match.group(1).strip()
            chn = match.group(2).strip()
            # 过滤掉太短或太长的匹配
            if 2 <= len(eng) <= 50 and 1 <= len(chn) <= 30:
                # 避免覆盖已有的术语
                if eng not in terminology:
                    terminology[eng] = chn
        
        return terminology
    
    def _extract_terminology_section(self, content: str) -> Dict[str, str]:
        """从术语表部分提取术语"""
        terminology: Dict[str, str] = {}
        
        # 查找术语表部分（常见标题）
        section_patterns = [
            r'##\s*(?:📚\s*)?(?:重要)?术语(?:和人物|表)?.*?\n(.*?)(?=\n##|\n#\s|\Z)',
            r'##\s*(?:📚\s*)?(?:Important\s+)?Terms?.*?\n(.*?)(?=\n##|\n#\s|\Z)',
            r'##\s*Glossary.*?\n(.*?)(?=\n##|\n#\s|\Z)',
        ]
        
        for pattern in section_patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                section = match.group(1)
                # 解析列表项：- **术语 (翻译)**：解释
                list_pattern = re.compile(
                    r'-\s*\*\*([^*]+?)(?:\s*[（(]([^）)]+)[）)])?\*\*'
                )
                for item in list_pattern.finditer(section):
                    term = item.group(1).strip()
                    translation = item.group(2)
                    if translation:
                        terminology[term] = translation.strip()
                break
        
        return terminology
    
    def extract_speakers(self, content: str) -> List[SpeakerProfile]:
        """
        提取说话人信息
        
        识别模式：
        - ### [MM:SS] Speaker_Name 格式
        - 基本信息部分的讲者数量
        
        Args:
            content: gs.md 内容
            
        Returns:
            说话人档案列表
        """
        speakers: Dict[str, SpeakerProfile] = {}
        
        # 从时间戳标题提取说话人
        for match in self.SPEAKER_PATTERN.finditer(content):
            timestamp = match.group(1)
            speaker_name = match.group(2).strip()
            
            # 清理说话人名称（移除可能的标记）
            speaker_name = re.sub(r'\s*\(.*?\)\s*$', '', speaker_name)
            
            if speaker_name and speaker_name not in speakers:
                ms = _parse_timestamp_to_ms(timestamp)
                # 推断角色
                role = self._infer_speaker_role(speaker_name, content)
                speakers[speaker_name] = SpeakerProfile(
                    name=speaker_name,
                    role=role,
                    speaking_style="",
                    first_appearance_ms=ms
                )
        
        # 按首次出现时间排序
        return sorted(speakers.values(), key=lambda s: s.first_appearance_ms)
    
    def _infer_speaker_role(self, speaker_name: str, content: str) -> str:
        """推断说话人角色"""
        name_lower = speaker_name.lower()
        
        # 检查是否是主讲人
        if '主讲人' in content and speaker_name in content.split('主讲人')[1][:100]:
            return "主讲人"
        
        # 检查是否是观众提问
        if '观众' in name_lower or 'audience' in name_lower:
            return "观众提问"
        if '提问' in name_lower or 'question' in name_lower:
            return "观众提问"
        
        # 默认角色
        return ""
    
    def _extract_core_topic(self, content: str) -> str:
        """提取核心主题"""
        # 从标题提取
        title_match = re.search(r'^#\s+(.+?)(?:\s*[-–—]\s*.+)?$', content, re.MULTILINE)
        if title_match:
            return title_match.group(1).strip()
        
        # 从基本信息部分提取
        topic_match = re.search(r'主题[：:]\s*(.+?)(?:\n|$)', content)
        if topic_match:
            return topic_match.group(1).strip()
        
        return ""
    
    def _extract_domain(self, content: str) -> str:
        """提取领域"""
        # 从内容推断领域
        domain_keywords = {
            "游戏设计": ["游戏", "game", "玩家", "player"],
            "修辞学": ["修辞", "rhetoric", "说服", "persuasion"],
            "媒体理论": ["媒体", "media", "传播", "communication"],
            "教育": ["教育", "education", "学习", "learning"],
            "设计": ["设计", "design", "UX", "用户体验"],
            "数据可视化": ["可视化", "visualization", "数据", "data"],
        }
        
        content_lower = content.lower()
        for domain, keywords in domain_keywords.items():
            count = sum(1 for kw in keywords if kw.lower() in content_lower)
            if count >= 2:
                return domain
        
        return ""
    
    def _extract_key_concepts(self, content: str) -> List[str]:
        """提取关键概念"""
        concepts: List[str] = []
        
        # 从粗体文本提取
        for match in self.BOLD_TERM_PATTERN.finditer(content):
            term = match.group(1).strip()
            # 过滤掉太短或太长的
            if 2 <= len(term) <= 50 and term not in concepts:
                concepts.append(term)
        
        # 限制数量
        return concepts[:20]
    
    def _extract_translation_style(self, content: str) -> str:
        """提取翻译风格描述"""
        # 查找翻译风格相关的描述
        style_patterns = [
            r'翻译风格[：:]\s*(.+?)(?:\n|$)',
            r'风格[：:]\s*(.+?)(?:\n|$)',
        ]
        
        for pattern in style_patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1).strip()
        
        # 默认风格
        return "准确、自然、易于理解"


# =============================================================================
# Chunk Manager（分段管理器）
# =============================================================================


class ChunkManager:
    """
    管理大文件的分段处理，保持上下文连贯
    
    策略：
    1. 默认 30 条为一个 chunk
    2. 在自然断点（长停顿、说话人切换）处分割
    3. 避免在句子中间分割
    """
    
    DEFAULT_CHUNK_SIZE = 30
    MIN_CHUNK_SIZE = 20
    MAX_CHUNK_SIZE = 50
    
    # 句子结束标点
    SENTENCE_TERMINATORS = {'。', '！', '？', '.', '!', '?'}
    
    # 长停顿阈值（毫秒）
    LONG_PAUSE_MS = 2000
    
    def __init__(
        self,
        items: List[RefinedSRTItem],
        checkpoint_dir: Optional[str] = None
    ):
        """
        初始化分段管理器
        
        Args:
            items: SRT 条目列表
            checkpoint_dir: 检查点保存目录
        """
        self.items = items
        self.checkpoint_dir = checkpoint_dir
        self.chunks: List[Chunk] = []
        self.processed_results: Dict[int, List[RefinedSRTItem]] = {}
        self._terminology: Dict[str, str] = {}
        self._last_context_summary: str = ""
    
    def create_chunks(self) -> List[Chunk]:
        """
        创建处理 chunks
        
        Returns:
            Chunk 列表
        """
        if not self.items:
            return []
        
        # 如果条目数少于最小 chunk 大小，直接返回单个 chunk
        if len(self.items) <= self.MIN_CHUNK_SIZE:
            chunk = Chunk(
                index=0,
                items=self.items.copy(),
                start_ms=self.items[0].start_ms,
                end_ms=self.items[-1].end_ms
            )
            self.chunks = [chunk]
            return self.chunks
        
        # 找到所有可能的分割点
        split_points = self._find_split_points()
        
        # 根据分割点创建 chunks
        self.chunks = self._create_chunks_from_split_points(split_points)
        
        return self.chunks
    
    def _find_split_points(self) -> List[int]:
        """
        找到所有可能的分割点
        
        分割点优先级：
        1. 长停顿（>2秒）
        2. 句子结束
        3. 默认位置
        
        Returns:
            分割点索引列表
        """
        split_points: List[Tuple[int, int]] = []  # (index, priority)
        
        for i in range(len(self.items) - 1):
            current = self.items[i]
            next_item = self.items[i + 1]
            
            # 计算停顿时长
            pause_ms = next_item.start_ms - current.end_ms
            
            # 检查是否是句子结束
            text = current.text.strip()
            is_sentence_end = text and text[-1] in self.SENTENCE_TERMINATORS
            
            # 确定优先级（数字越小优先级越高）
            if pause_ms >= self.LONG_PAUSE_MS and is_sentence_end:
                priority = 1  # 最佳分割点
            elif pause_ms >= self.LONG_PAUSE_MS:
                priority = 2
            elif is_sentence_end:
                priority = 3
            else:
                priority = 4
            
            split_points.append((i, priority))
        
        return split_points
    
    def _create_chunks_from_split_points(
        self,
        split_points: List[Tuple[int, int]]
    ) -> List[Chunk]:
        """
        根据分割点创建 chunks
        
        Args:
            split_points: (索引, 优先级) 列表
            
        Returns:
            Chunk 列表
        """
        chunks: List[Chunk] = []
        start_idx = 0
        chunk_index = 0
        
        while start_idx < len(self.items):
            # 计算理想的结束位置
            ideal_end = start_idx + self.DEFAULT_CHUNK_SIZE - 1
            
            # 如果剩余条目不多，直接包含到当前 chunk
            if ideal_end >= len(self.items) - self.MIN_CHUNK_SIZE:
                end_idx = len(self.items) - 1
            else:
                # 在理想位置附近找最佳分割点
                end_idx = self._find_best_split_point(
                    split_points, start_idx, ideal_end
                )
            
            # 创建 chunk
            chunk_items = self.items[start_idx:end_idx + 1]
            chunk = Chunk(
                index=chunk_index,
                items=chunk_items,
                start_ms=chunk_items[0].start_ms,
                end_ms=chunk_items[-1].end_ms
            )
            chunks.append(chunk)
            
            # 移动到下一个 chunk
            start_idx = end_idx + 1
            chunk_index += 1
        
        return chunks
    
    def _find_best_split_point(
        self,
        split_points: List[Tuple[int, int]],
        start_idx: int,
        ideal_end: int
    ) -> int:
        """
        在指定范围内找到最佳分割点
        
        Args:
            split_points: 所有分割点
            start_idx: 当前 chunk 起始索引
            ideal_end: 理想结束索引
            
        Returns:
            最佳分割点索引
        """
        min_end = start_idx + self.MIN_CHUNK_SIZE - 1
        max_end = min(start_idx + self.MAX_CHUNK_SIZE - 1, len(self.items) - 1)
        
        # 确保范围有效
        min_end = max(min_end, start_idx)
        max_end = min(max_end, len(self.items) - 1)
        
        # 在范围内找优先级最高的分割点
        best_idx = ideal_end
        best_priority = 999
        
        for idx, priority in split_points:
            if min_end <= idx <= max_end:
                # 优先级相同时，选择更接近理想位置的
                if priority < best_priority or (
                    priority == best_priority and 
                    abs(idx - ideal_end) < abs(best_idx - ideal_end)
                ):
                    best_idx = idx
                    best_priority = priority
        
        return min(best_idx, max_end)
    
    def get_context_for_chunk(self, chunk_index: int) -> str:
        """
        获取当前 chunk 的上下文
        
        包含：
        - 前一个 chunk 的摘要
        - 已确定的术语映射
        - 当前说话人
        
        Args:
            chunk_index: chunk 索引
            
        Returns:
            上下文字符串
        """
        if chunk_index == 0:
            return ""
        
        context_parts = []
        
        # 添加前文摘要
        if self._last_context_summary:
            context_parts.append(f"前文摘要：{self._last_context_summary}")
        
        # 添加已使用的术语
        if self._terminology:
            terms = [f"{eng}={chn}" for eng, chn in list(self._terminology.items())[:10]]
            context_parts.append(f"已确定术语：{', '.join(terms)}")
        
        return "\n".join(context_parts)
    
    def update_context(
        self,
        chunk_index: int,
        context_summary: str,
        terminology_used: Dict[str, str]
    ) -> None:
        """
        更新上下文信息
        
        Args:
            chunk_index: chunk 索引
            context_summary: 本 chunk 的上下文摘要
            terminology_used: 本 chunk 使用的术语
        """
        self._last_context_summary = context_summary
        self._terminology.update(terminology_used)
        
        # 更新 chunk 的上下文信息
        if chunk_index < len(self.chunks):
            self.chunks[chunk_index].context_summary = context_summary
            self.chunks[chunk_index].terminology_used = terminology_used
    
    def save_checkpoint(
        self,
        chunk_index: int,
        result: List[RefinedSRTItem]
    ) -> None:
        """
        保存检查点，支持中断恢复
        
        Args:
            chunk_index: 已完成的 chunk 索引
            result: 该 chunk 的处理结果
        """
        self.processed_results[chunk_index] = result
        
        if not self.checkpoint_dir:
            return
        
        # 确保目录存在
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        
        # 保存处理状态
        state = ProcessingState(
            total_chunks=len(self.chunks),
            completed_chunks=chunk_index + 1,
            current_chunk_index=chunk_index + 1,
            terminology=self._terminology,
            last_context_summary=self._last_context_summary,
            checkpoint_path=self.checkpoint_dir
        )
        state.save(os.path.join(self.checkpoint_dir, "state.json"))
        
        # 保存已处理的结果
        results_data = {}
        for idx, items in self.processed_results.items():
            results_data[str(idx)] = [
                {
                    "start_ms": item.start_ms,
                    "end_ms": item.end_ms,
                    "text": item.text,
                    "speaker": item.speaker,
                    "is_refined": item.is_refined,
                    "original_text": item.original_text
                }
                for item in items
            ]
        
        with open(os.path.join(self.checkpoint_dir, "results.json"), "w", encoding="utf-8") as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2)
    
    def load_checkpoint(self) -> int:
        """
        加载检查点，返回下一个待处理的 chunk 索引
        
        Returns:
            下一个待处理的 chunk 索引，如果没有检查点则返回 0
        """
        if not self.checkpoint_dir:
            return 0
        
        state_path = os.path.join(self.checkpoint_dir, "state.json")
        results_path = os.path.join(self.checkpoint_dir, "results.json")
        
        # 加载状态
        state = ProcessingState.load(state_path)
        if not state:
            return 0
        
        self._terminology = state.terminology
        self._last_context_summary = state.last_context_summary
        
        # 加载已处理的结果
        if os.path.exists(results_path):
            try:
                with open(results_path, "r", encoding="utf-8") as f:
                    results_data = json.load(f)
                
                for idx_str, items_data in results_data.items():
                    idx = int(idx_str)
                    items = [
                        RefinedSRTItem(
                            start_ms=item["start_ms"],
                            end_ms=item["end_ms"],
                            text=item["text"],
                            speaker=item.get("speaker"),
                            is_refined=item.get("is_refined", False),
                            original_text=item.get("original_text", "")
                        )
                        for item in items_data
                    ]
                    self.processed_results[idx] = items
            except (json.JSONDecodeError, KeyError):
                pass
        
        return state.current_chunk_index
    
    def get_all_results(self) -> List[RefinedSRTItem]:
        """
        获取所有处理结果
        
        Returns:
            按顺序合并的所有 chunk 结果
        """
        all_items: List[RefinedSRTItem] = []
        
        for i in range(len(self.chunks)):
            if i in self.processed_results:
                all_items.extend(self.processed_results[i])
            else:
                # 未处理的 chunk，使用原始数据
                all_items.extend(self.chunks[i].items)
        
        return all_items
    
    @property
    def terminology(self) -> Dict[str, str]:
        """获取累积的术语映射"""
        return self._terminology.copy()
    
    @property
    def progress(self) -> float:
        """获取处理进度（0-100）"""
        if not self.chunks:
            return 0.0
        return len(self.processed_results) / len(self.chunks) * 100


# =============================================================================
# LLM Refiner（LLM 矫正器）
# =============================================================================

import urllib.request
import urllib.error
import time


class LLMRefiner:
    """
    使用 LLM 进行翻译矫正的核心组件
    
    支持的 LLM 提供商：
    - OpenAI API（包括兼容的 API）
    - Claude API
    """
    
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # 秒
    
    # 系统提示模板
    SYSTEM_PROMPT = """你是一位专业的中文翻译审校专家。你的任务是根据参考文档矫正字幕翻译，确保翻译准确、自然、对中国观众易于理解。

## 矫正要求
1. 保持原始序号不变
2. 使用术语表中的统一翻译
3. 确保翻译对中国人自然可理解
4. 避免生硬的直译
5. 保持说话人的语气风格
6. 每条字幕不超过 75 个字符
7. 如需分割长句，在自然断点处分割
8. 移除所有 Markdown 格式（**粗体**、# 标题等）

## 输出格式
请严格按以下格式输出矫正后的字幕，每行一条：
[序号] 矫正后的翻译

例如：
[1] 这是第一条矫正后的翻译。
[2] 这是第二条矫正后的翻译。"""

    def __init__(
        self,
        semantic_context: SemanticContext,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        初始化 LLM 矫正器
        
        Args:
            semantic_context: 语义上下文
            api_key: API 密钥（默认从环境变量读取）
            base_url: API 基础 URL（默认从环境变量读取）
            model: 模型名称（默认从环境变量读取）
        """
        self.context = semantic_context
        self.api_key = api_key or os.environ.get("FLEXDUB_LLM_API_KEY", "")
        self.base_url = base_url or os.environ.get(
            "FLEXDUB_LLM_BASE_URL", 
            "https://api.openai.com/v1/chat/completions"
        )
        self.model = model or os.environ.get("FLEXDUB_LLM_MODEL", "gpt-4o-mini")
    
    def refine_chunk(
        self,
        chunk: Chunk,
        previous_context: str = ""
    ) -> Tuple[List[RefinedSRTItem], str]:
        """
        矫正一个 chunk 的翻译
        
        Args:
            chunk: 待处理的 chunk
            previous_context: 前一个 chunk 的上下文摘要
            
        Returns:
            (矫正后的 SRT 条目列表, 本 chunk 的上下文摘要)
        """
        if not self.api_key:
            # 没有 API key，返回原始数据
            return chunk.items, ""
        
        # 构建 prompt
        prompt = self.build_prompt(chunk, previous_context)
        
        # 调用 LLM
        response = self._call_llm(prompt)
        
        if not response:
            # LLM 调用失败，返回原始数据
            return chunk.items, ""
        
        # 解析响应
        refined_items = self.parse_response(response, chunk.items)
        
        # 生成上下文摘要
        context_summary = self._generate_context_summary(refined_items)
        
        return refined_items, context_summary
    
    def build_prompt(self, chunk: Chunk, previous_context: str = "") -> str:
        """
        构建 LLM prompt
        
        Args:
            chunk: 待处理的 chunk
            previous_context: 前一个 chunk 的上下文摘要
            
        Returns:
            完整的 prompt 字符串
        """
        parts = []
        
        # 背景信息
        parts.append("## 背景信息")
        if self.context.core_topic:
            parts.append(f"主题：{self.context.core_topic}")
        if self.context.domain:
            parts.append(f"领域：{self.context.domain}")
        if self.context.key_concepts:
            concepts = ", ".join(self.context.key_concepts[:10])
            parts.append(f"关键概念：{concepts}")
        parts.append("")
        
        # 术语表
        if self.context.terminology:
            parts.append("## 术语表（必须统一使用）")
            for eng, chn in list(self.context.terminology.items())[:20]:
                parts.append(f"- {eng} = {chn}")
            parts.append("")
        
        # 前文摘要
        if previous_context:
            parts.append("## 前文摘要")
            parts.append(previous_context)
            parts.append("")
        
        # 待矫正的字幕
        parts.append("## 待矫正的字幕")
        for i, item in enumerate(chunk.items):
            parts.append(f"[{i + 1}] {item.text}")
        parts.append("")
        
        # 输出要求
        parts.append("请输出矫正后的字幕，格式为 [序号] 矫正后的翻译")
        
        return "\n".join(parts)
    
    def parse_response(
        self,
        response: str,
        original_items: List[RefinedSRTItem]
    ) -> List[RefinedSRTItem]:
        """
        解析 LLM 响应，提取矫正后的翻译
        
        Args:
            response: LLM 响应文本
            original_items: 原始条目列表
            
        Returns:
            矫正后的 SRT 条目列表
        """
        # 解析响应中的 [序号] 翻译 格式
        pattern = re.compile(r'\[(\d+)\]\s*(.+?)(?=\n\[|\n*$)', re.DOTALL)
        matches = pattern.findall(response)
        
        # 创建索引到翻译的映射
        translations: Dict[int, str] = {}
        for idx_str, text in matches:
            idx = int(idx_str) - 1  # 转换为 0-based 索引
            text = text.strip()
            # 清理 Markdown 格式
            text = self._clean_markdown(text)
            if text:
                translations[idx] = text
        
        # 创建结果列表
        result: List[RefinedSRTItem] = []
        for i, item in enumerate(original_items):
            if i in translations:
                refined = RefinedSRTItem(
                    start_ms=item.start_ms,
                    end_ms=item.end_ms,
                    text=translations[i],
                    speaker=item.speaker,
                    is_refined=True,
                    original_text=item.original_text or item.text
                )
            else:
                # 没有找到对应的翻译，保持原样
                refined = RefinedSRTItem(
                    start_ms=item.start_ms,
                    end_ms=item.end_ms,
                    text=item.text,
                    speaker=item.speaker,
                    is_refined=False,
                    original_text=item.original_text or item.text
                )
            result.append(refined)
        
        return result
    
    def _call_llm(self, prompt: str) -> Optional[str]:
        """
        调用 LLM API
        
        Args:
            prompt: 用户提示
            
        Returns:
            LLM 响应文本，失败返回 None
        """
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 4096
        }
        
        data = json.dumps(payload).encode("utf-8")
        
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                req = urllib.request.Request(
                    self.base_url,
                    data=data,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}"
                    }
                )
                
                with urllib.request.urlopen(req, timeout=120) as resp:
                    body = resp.read().decode("utf-8")
                    obj = json.loads(body)
                    choices = obj.get("choices", [])
                    if choices:
                        message = choices[0].get("message", {})
                        return message.get("content")
                    return None
                    
            except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
        
        return None
    
    def _clean_markdown(self, text: str) -> str:
        """清理 Markdown 格式"""
        # 移除粗体
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'__([^_]+)__', r'\1', text)
        # 移除斜体
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)
        # 移除代码块
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # 移除标题标记
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
        # 移除列表标记
        text = re.sub(r'^[-*]\s+', '', text, flags=re.MULTILINE)
        return text.strip()
    
    def _generate_context_summary(self, items: List[RefinedSRTItem]) -> str:
        """生成上下文摘要"""
        if not items:
            return ""
        
        # 取最后几条作为摘要
        last_items = items[-3:]
        texts = [item.text for item in last_items]
        return " ".join(texts)[:200]


# =============================================================================
# Localization Reviewer（本地化审查器）
# =============================================================================


class LocalizationReviewer:
    """
    审查翻译的中国人可理解性
    
    检查项：
    1. 不自然的直译
    2. 未解释的专业术语
    3. 过长的句子
    4. 不常用的表达方式
    5. 保留的英文是否必要
    """
    
    # TTS 字符长度限制（Doubao TTS）
    MAX_CHAR_LENGTH = 75
    
    # 常见的不自然直译模式（需要更长的上下文才能判断）
    LITERAL_TRANSLATION_PATTERNS = [
        (r'在\s*\d+\s*的末尾', '句末位置表达不自然'),
        (r'它是\s*一个\s*非常\s*\w+的', '可能是直译的 "It is a very..."'),
        (r'这是\s*一个\s*非常\s*\w+的', '可能是直译的 "This is a very..."'),
        (r'我认为这实际上', '可能是直译的 "I think this actually..."'),
    ]
    
    def __init__(self, llm_client: Optional[Any] = None):
        """
        初始化本地化审查器
        
        Args:
            llm_client: 可选的 LLM 客户端，用于更智能的审查
        """
        self.llm = llm_client
    
    def review(self, items: List[RefinedSRTItem]) -> List[LocalizationIssue]:
        """
        审查翻译的本地化质量
        
        Args:
            items: SRT 条目列表
            
        Returns:
            本地化问题列表
        """
        issues: List[LocalizationIssue] = []
        
        for i, item in enumerate(items):
            # 检查句子长度
            length_issue = self.check_sentence_length(item.text)
            if length_issue:
                issues.append(LocalizationIssue(
                    index=i,
                    issue_type="sentence_too_long",
                    original=item.text,
                    suggestion=length_issue,
                    severity=IssueSeverity.ERROR
                ))
            
            # 检查直译
            literal_issue = self._check_literal_translation(item.text)
            if literal_issue:
                issues.append(LocalizationIssue(
                    index=i,
                    issue_type="literal_translation",
                    original=item.text,
                    suggestion=literal_issue,
                    severity=IssueSeverity.WARNING
                ))
            
            # 检查未解释的英文术语
            english_issue = self._check_unexplained_english(item.text)
            if english_issue:
                issues.append(LocalizationIssue(
                    index=i,
                    issue_type="unexplained_english",
                    original=item.text,
                    suggestion=english_issue,
                    severity=IssueSeverity.WARNING
                ))
        
        return issues
    
    def check_sentence_length(self, text: str) -> Optional[str]:
        """
        检查句子长度是否适合 TTS
        
        Args:
            text: 文本内容
            
        Returns:
            问题描述，无问题返回 None
        """
        if len(text) > self.MAX_CHAR_LENGTH:
            # 建议分割点
            split_points = self._find_split_points(text)
            if split_points:
                return f"文本长度 {len(text)} 超过 {self.MAX_CHAR_LENGTH} 字符限制，建议在位置 {split_points[0]} 处分割"
            return f"文本长度 {len(text)} 超过 {self.MAX_CHAR_LENGTH} 字符限制，建议缩短或分割"
        return None
    
    def _find_split_points(self, text: str) -> List[int]:
        """找到自然的分割点"""
        split_chars = ['。', '！', '？', '，', '；', '.', '!', '?', ',', ';']
        points = []
        
        for i, char in enumerate(text):
            if char in split_chars and i > 20 and i < len(text) - 10:
                points.append(i + 1)
        
        # 按接近中点排序
        mid = len(text) // 2
        points.sort(key=lambda x: abs(x - mid))
        
        return points[:3]
    
    def _check_literal_translation(self, text: str) -> Optional[str]:
        """检查是否有生硬的直译"""
        for pattern, description in self.LITERAL_TRANSLATION_PATTERNS:
            if re.search(pattern, text):
                return description
        return None
    
    def _check_unexplained_english(self, text: str) -> Optional[str]:
        """检查是否有未解释的英文术语"""
        # 查找连续的英文单词（超过 2 个单词）
        english_phrases = re.findall(r'\b[A-Za-z]{3,}(?:\s+[A-Za-z]{3,}){1,}\b', text)
        
        if english_phrases:
            # 过滤掉常见的可接受英文
            acceptable = {'TED', 'OK', 'API', 'URL', 'AI', 'UI', 'UX', 'CEO', 'CTO'}
            unexpected = [p for p in english_phrases if p.upper() not in acceptable]
            
            if unexpected:
                return f"包含未翻译的英文短语：{', '.join(unexpected[:3])}"
        
        return None
    
    def split_long_text(self, text: str) -> List[str]:
        """
        分割过长的文本
        
        Args:
            text: 原始文本
            
        Returns:
            分割后的文本列表
        """
        if len(text) <= self.MAX_CHAR_LENGTH:
            return [text]
        
        # 找到分割点
        split_points = self._find_split_points(text)
        
        if not split_points:
            # 没有好的分割点，强制在中间分割
            mid = len(text) // 2
            return [text[:mid].strip(), text[mid:].strip()]
        
        # 使用第一个分割点
        point = split_points[0]
        first_part = text[:point].strip()
        second_part = text[point:].strip()
        
        # 递归处理仍然过长的部分
        result = []
        if len(first_part) > self.MAX_CHAR_LENGTH:
            result.extend(self.split_long_text(first_part))
        else:
            result.append(first_part)
        
        if len(second_part) > self.MAX_CHAR_LENGTH:
            result.extend(self.split_long_text(second_part))
        else:
            result.append(second_part)
        
        return result


# =============================================================================
# Output Generator（输出生成器）
# =============================================================================

import datetime
import yaml


class OutputGenerator:
    """
    生成最终输出文件
    
    输出格式：
    - SRT 格式字幕
    - YAML 格式术语表
    - 文本格式处理日志
    """
    
    DEFAULT_SPEAKER = "DEFAULT"
    SPEAKER_TAG_FORMAT = "[Speaker: {name}]"
    
    def generate_srt(
        self,
        items: List[RefinedSRTItem],
        include_speaker_tags: bool = False
    ) -> str:
        """
        生成 SRT 格式输出
        
        Args:
            items: SRT 条目列表
            include_speaker_tags: 是否包含说话人标签
            
        Returns:
            SRT 格式字符串
        """
        import srt
        
        subs = []
        for i, item in enumerate(items, start=1):
            text = item.text
            
            # 添加说话人标签
            if include_speaker_tags:
                speaker = item.speaker or self.DEFAULT_SPEAKER
                tag = self.SPEAKER_TAG_FORMAT.format(name=speaker)
                text = f"{tag} {text}"
            
            # 清理 Markdown 格式
            text = self._clean_markdown(text)
            
            start_td = datetime.timedelta(milliseconds=item.start_ms)
            end_td = datetime.timedelta(milliseconds=item.end_ms)
            subs.append(srt.Subtitle(index=i, start=start_td, end=end_td, content=text))
        
        return srt.compose(subs)
    
    def generate_terminology_report(
        self,
        terminology: Dict[str, str]
    ) -> str:
        """
        生成术语表报告（YAML 格式）
        
        Args:
            terminology: 术语映射字典
            
        Returns:
            YAML 格式字符串
        """
        report = {
            "terminology": terminology,
            "count": len(terminology),
            "generated_at": datetime.datetime.now().isoformat()
        }
        
        return yaml.dump(report, allow_unicode=True, default_flow_style=False, sort_keys=False)
    
    def generate_processing_log(
        self,
        chunks: List[Chunk],
        issues: List[LocalizationIssue],
        total_items: int = 0,
        refined_count: int = 0
    ) -> str:
        """
        生成处理日志
        
        Args:
            chunks: 处理的 chunk 列表
            issues: 本地化问题列表
            total_items: 总条目数
            refined_count: 已矫正条目数
            
        Returns:
            日志文本
        """
        lines = []
        lines.append("=" * 60)
        lines.append("GS 语义矫正处理日志")
        lines.append("=" * 60)
        lines.append(f"生成时间: {datetime.datetime.now().isoformat()}")
        lines.append("")
        
        # 统计信息
        lines.append("## 处理统计")
        lines.append(f"- 总条目数: {total_items}")
        lines.append(f"- 已矫正条目数: {refined_count}")
        lines.append(f"- Chunk 数量: {len(chunks)}")
        lines.append(f"- 发现问题数: {len(issues)}")
        lines.append("")
        
        # Chunk 详情
        lines.append("## Chunk 处理详情")
        for chunk in chunks:
            lines.append(f"- Chunk {chunk.index}: {chunk.item_count} 条目, "
                        f"{chunk.start_ms}ms - {chunk.end_ms}ms")
            if chunk.terminology_used:
                terms = list(chunk.terminology_used.items())[:5]
                terms_str = ", ".join(f"{k}={v}" for k, v in terms)
                lines.append(f"  术语: {terms_str}")
        lines.append("")
        
        # 问题列表
        if issues:
            lines.append("## 本地化问题")
            for issue in issues:
                severity = "⚠️" if issue.severity == IssueSeverity.WARNING else "❌"
                lines.append(f"{severity} [{issue.index}] {issue.issue_type}")
                lines.append(f"   原文: {issue.original[:50]}...")
                lines.append(f"   建议: {issue.suggestion}")
            lines.append("")
        
        lines.append("=" * 60)
        return "\n".join(lines)
    
    def _clean_markdown(self, text: str) -> str:
        """清理 Markdown 格式"""
        # 移除粗体
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'__([^_]+)__', r'\1', text)
        # 移除斜体
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)
        # 移除代码块
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # 移除标题标记
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
        # 移除列表标记
        text = re.sub(r'^[-*]\s+', '', text, flags=re.MULTILINE)
        return text.strip()
    
    def write_outputs(
        self,
        output_dir: str,
        basename: str,
        items: List[RefinedSRTItem],
        terminology: Dict[str, str],
        chunks: List[Chunk],
        issues: List[LocalizationIssue],
        include_speaker_tags: bool = False
    ) -> Dict[str, str]:
        """
        写入所有输出文件
        
        Args:
            output_dir: 输出目录
            basename: 基础文件名
            items: SRT 条目列表
            terminology: 术语映射
            chunks: chunk 列表
            issues: 问题列表
            include_speaker_tags: 是否包含说话人标签
            
        Returns:
            输出文件路径字典
        """
        os.makedirs(output_dir, exist_ok=True)
        
        paths = {}
        
        # 写入 SRT
        srt_path = os.path.join(output_dir, f"{basename}.refined.audio.srt")
        srt_content = self.generate_srt(items, include_speaker_tags)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
        paths["srt"] = srt_path
        
        # 写入术语表
        if terminology:
            term_path = os.path.join(output_dir, f"{basename}.terminology.yaml")
            term_content = self.generate_terminology_report(terminology)
            with open(term_path, "w", encoding="utf-8") as f:
                f.write(term_content)
            paths["terminology"] = term_path
        
        # 写入处理日志
        log_path = os.path.join(output_dir, f"{basename}.processing.log")
        refined_count = sum(1 for item in items if item.is_refined)
        log_content = self.generate_processing_log(
            chunks, issues, len(items), refined_count
        )
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(log_content)
        paths["log"] = log_path
        
        return paths


# =============================================================================
# SemanticRefiner（主流程）
# =============================================================================


class SemanticRefiner:
    """
    GS 语义矫正 SRT 翻译的主流程类
    
    整合所有组件：
    - ContextExtractor: 提取 gs.md 语义上下文
    - ChunkManager: 分段管理
    - LLMRefiner: LLM 翻译矫正
    - LocalizationReviewer: 本地化审查
    - OutputGenerator: 输出生成
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        checkpoint_dir: Optional[str] = None
    ):
        """
        初始化语义矫正器
        
        Args:
            api_key: LLM API 密钥
            base_url: LLM API 基础 URL
            model: LLM 模型名称
            checkpoint_dir: 检查点保存目录
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.checkpoint_dir = checkpoint_dir
        
        # 组件（延迟初始化）
        self._context_extractor: Optional[ContextExtractor] = None
        self._chunk_manager: Optional[ChunkManager] = None
        self._llm_refiner: Optional[LLMRefiner] = None
        self._localization_reviewer: Optional[LocalizationReviewer] = None
        self._output_generator: Optional[OutputGenerator] = None
        
        # 状态
        self._semantic_context: Optional[SemanticContext] = None
        self._progress_callback: Optional[callable] = None
    
    def set_progress_callback(self, callback: callable) -> None:
        """设置进度回调函数"""
        self._progress_callback = callback
    
    def _report_progress(self, progress: float, message: str) -> None:
        """报告进度"""
        if self._progress_callback:
            self._progress_callback(progress, message)
        else:
            print(f"[{progress:.1f}%] {message}")
    
    def refine(
        self,
        gs_path: str,
        srt_path: str,
        output_path: Optional[str] = None,
        include_speaker_tags: bool = False
    ) -> RefineResult:
        """
        执行语义矫正主流程
        
        Args:
            gs_path: gs.md 文件路径
            srt_path: SRT 文件路径
            output_path: 输出文件路径（可选）
            include_speaker_tags: 是否包含说话人标签
            
        Returns:
            RefineResult 对象
        """
        from flexdub.core.subtitle import read_srt
        
        self._report_progress(0, "开始处理...")
        
        # 1. 读取 gs.md
        self._report_progress(5, "读取 gs.md...")
        if not os.path.exists(gs_path):
            raise FileNotFoundError(f"gs.md 文件不存在: {gs_path}")
        
        with open(gs_path, "r", encoding="utf-8") as f:
            gs_content = f.read()
        
        # 2. 提取语义上下文
        self._report_progress(10, "提取语义上下文...")
        self._context_extractor = ContextExtractor()
        self._semantic_context = self._context_extractor.extract(gs_content)
        
        self._report_progress(15, f"提取到 {len(self._semantic_context.terminology)} 个术语, "
                             f"{len(self._semantic_context.speakers)} 个说话人")
        
        # 3. 读取 SRT
        self._report_progress(20, "读取 SRT 文件...")
        srt_items = read_srt(srt_path)
        refined_items = srt_items_to_refined(srt_items)
        
        self._report_progress(25, f"读取到 {len(refined_items)} 条字幕")
        
        # 4. 创建 chunks
        self._report_progress(30, "创建处理分段...")
        self._chunk_manager = ChunkManager(refined_items, self.checkpoint_dir)
        chunks = self._chunk_manager.create_chunks()
        
        # 尝试加载检查点
        start_chunk = self._chunk_manager.load_checkpoint()
        if start_chunk > 0:
            self._report_progress(35, f"从检查点恢复，跳过前 {start_chunk} 个 chunks")
        
        self._report_progress(35, f"共 {len(chunks)} 个 chunks")
        
        # 5. 初始化 LLM Refiner
        self._llm_refiner = LLMRefiner(
            self._semantic_context,
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model
        )
        
        # 6. 逐 chunk 处理
        for i, chunk in enumerate(chunks):
            if i < start_chunk:
                continue
            
            progress = 40 + (i / len(chunks)) * 40
            self._report_progress(progress, f"处理 Chunk {i + 1}/{len(chunks)}...")
            
            # 获取上下文
            previous_context = self._chunk_manager.get_context_for_chunk(i)
            
            # 矫正
            refined_chunk_items, context_summary = self._llm_refiner.refine_chunk(
                chunk, previous_context
            )
            
            # 更新上下文
            self._chunk_manager.update_context(i, context_summary, {})
            
            # 保存检查点
            self._chunk_manager.save_checkpoint(i, refined_chunk_items)
        
        # 7. 获取所有结果
        self._report_progress(80, "合并处理结果...")
        all_items = self._chunk_manager.get_all_results()
        
        # 8. 本地化审查
        self._report_progress(85, "执行本地化审查...")
        self._localization_reviewer = LocalizationReviewer()
        issues = self._localization_reviewer.review(all_items)
        
        self._report_progress(90, f"发现 {len(issues)} 个本地化问题")
        
        # 9. 生成输出
        self._output_generator = OutputGenerator()
        
        if output_path:
            self._report_progress(95, "写入输出文件...")
            output_dir = os.path.dirname(output_path) or "."
            basename = os.path.splitext(os.path.basename(output_path))[0]
            
            self._output_generator.write_outputs(
                output_dir=output_dir,
                basename=basename,
                items=all_items,
                terminology=self._chunk_manager.terminology,
                chunks=chunks,
                issues=issues,
                include_speaker_tags=include_speaker_tags
            )
        
        # 10. 构建结果
        self._report_progress(100, "处理完成!")
        
        log_content = self._output_generator.generate_processing_log(
            chunks, issues, len(all_items),
            sum(1 for item in all_items if item.is_refined)
        )
        
        return RefineResult(
            items=all_items,
            terminology_used=self._chunk_manager.terminology,
            issues=issues,
            processing_log=log_content
        )
    
    @property
    def semantic_context(self) -> Optional[SemanticContext]:
        """获取语义上下文"""
        return self._semantic_context
    
    @property
    def progress(self) -> float:
        """获取处理进度"""
        if self._chunk_manager:
            return self._chunk_manager.progress
        return 0.0
