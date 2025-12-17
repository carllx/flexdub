import datetime
from dataclasses import dataclass
from typing import List, Tuple, Optional
import os
import json
import urllib.request
import urllib.error

import srt

from pyvideotrans.core.rebalance import Segment


@dataclass
class SRTItem:
    start_ms: int
    end_ms: int
    text: str


@dataclass
class Gap:
    """字幕间隙"""
    start_ms: int      # 间隙开始时间
    end_ms: int        # 间隙结束时间
    duration_ms: int   # 间隙时长
    prev_index: int    # 前一个片段的索引
    next_index: int    # 后一个片段的索引


@dataclass
class SegmentInfo:
    """片段处理信息"""
    index: int                 # 片段索引
    original_start_ms: int     # 原始开始时间
    original_end_ms: int       # 原始结束时间
    original_duration_ms: int  # 原始时长
    tts_duration_ms: int       # TTS 时长
    new_start_ms: int          # 新开始时间
    new_end_ms: int            # 新结束时间
    stretch_ratio: float       # 拉伸比例
    is_gap: bool               # 是否为间隙
    is_blank: bool             # 是否为空白片段
    text: str                  # 文本内容


@dataclass
class SyncDiagnostics:
    """同步诊断信息"""
    segments: List[SegmentInfo]        # 所有片段信息
    total_original_ms: int             # 原始总时长
    total_new_ms: int                  # 新总时长
    overall_ratio: float               # 整体拉伸比例
    warnings: List[str]                # 警告信息


def detect_gaps(items: List[SRTItem], min_gap_ms: int = 100) -> List[Gap]:
    """
    检测字幕片段之间的间隙
    
    Args:
        items: 字幕片段列表
        min_gap_ms: 最小间隙阈值（毫秒），小于等于此值的间隙将被忽略
        
    Returns:
        间隙列表，每个间隙包含 start_ms, end_ms, duration_ms, prev_index, next_index
    """
    gaps: List[Gap] = []
    
    if len(items) < 2:
        return gaps
    
    for i in range(len(items) - 1):
        current_end = items[i].end_ms
        next_start = items[i + 1].start_ms
        gap_duration = next_start - current_end
        
        if gap_duration > min_gap_ms:
            gaps.append(Gap(
                start_ms=current_end,
                end_ms=next_start,
                duration_ms=gap_duration,
                prev_index=i,
                next_index=i + 1
            ))
    
    return gaps


def read_srt(path: str) -> List[SRTItem]:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    subs = list(srt.parse(content))
    items: List[SRTItem] = []
    for s in subs:
        start_ms = int(s.start.total_seconds() * 1000)
        end_ms = int(s.end.total_seconds() * 1000)
        items.append(SRTItem(start_ms, end_ms, s.content))
    return items


def write_srt(path: str, items: List[SRTItem]) -> None:
    subs = []
    for i, it in enumerate(items, start=1):
        start_td = datetime.timedelta(milliseconds=it.start_ms)
        end_td = datetime.timedelta(milliseconds=it.end_ms)
        subs.append(srt.Subtitle(index=i, start=start_td, end=end_td, content=it.text))
    text = srt.compose(subs)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def parse_srt_text(text: str) -> List[SRTItem]:
    subs = list(srt.parse(text))
    items: List[SRTItem] = []
    for s in subs:
        start_ms = int(s.start.total_seconds() * 1000)
        end_ms = int(s.end.total_seconds() * 1000)
        items.append(SRTItem(start_ms, end_ms, s.content))
    return items


def compose_srt(items: List[SRTItem]) -> str:
    subs = []
    for i, it in enumerate(items, start=1):
        start_td = datetime.timedelta(milliseconds=it.start_ms)
        end_td = datetime.timedelta(milliseconds=it.end_ms)
        subs.append(srt.Subtitle(index=i, start=start_td, end=end_td, content=it.text))
    return srt.compose(subs)


def strip_meta(text: str) -> str:
    return text.replace("【", "").replace("】", "").replace("[", "").replace("]", "")


def remove_bracket_content(text: str) -> str:
    res = []
    skip = 0
    for ch in text:
        if ch in ("(", "【", "["):
            skip += 1
            continue
        if ch in (")", "】", "]"):
            if skip > 0:
                skip -= 1
            continue
        if skip == 0:
            res.append(ch)
    return "".join(res)


def _strip_noise(text: str) -> str:
    t = text
    t = t.replace("*", "").replace("`", "")
    t = t.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "").replace("\ufeff", "")
    while "  " in t:
        t = t.replace("  ", " ")
    return t.strip()


def apply_text_options(text: str, keep_brackets: bool, strip_meta_flag: bool, strip_noise_flag: bool = False) -> str:
    t = text
    if strip_noise_flag:
        t = _strip_noise(t)
    if not keep_brackets:
        t = remove_bracket_content(t)
    if strip_meta_flag:
        t = strip_meta(t)
    return t


def to_segments(items: List[SRTItem]) -> List[Segment]:
    return [Segment(i.start_ms, i.end_ms, i.text) for i in items]


def from_segments(items: List[Segment]) -> List[SRTItem]:
    return [SRTItem(i.start_ms, i.end_ms, i.text) for i in items]


def semantic_restructure(items: List[SRTItem], max_chars: int = 250, max_duration_ms: int = 15000) -> List[SRTItem]:
    terms = {".", "?", "!", "。", "？", "！"}
    pauses = {",", "，", ";", "；"}
    def ends_with_term(t: str) -> bool:
        s = t.strip()
        if not s:
            return False
        return s[-1] in terms
    def starts_with_speaker(t: str) -> bool:
        s = t.strip()
        return s.startswith("- ") or s.startswith("— ") or s.startswith("-") or s.startswith("—")
    out: List[SRTItem] = []
    buf: List[SRTItem] = []
    for it in items:
        if not buf:
            buf.append(it)
        else:
            if starts_with_speaker(it.text) or ends_with_term(buf[-1].text):
                start = buf[0].start_ms
                end = buf[-1].end_ms
                text = " ".join(b.text.strip() for b in buf).strip()
                if len(text) > max_chars or (end - start) > max_duration_ms:
                    split_idx = -1
                    for j in range(len(buf) - 1, -1, -1):
                        t = buf[j].text.strip()
                        if t and t[-1] in pauses:
                            split_idx = j
                            break
                    if split_idx >= 0:
                        left = buf[:split_idx + 1]
                        right = buf[split_idx + 1:]
                        left_text = " ".join(b.text.strip() for b in left).strip()
                        right_text = " ".join(b.text.strip() for b in right).strip()
                        out.append(SRTItem(left[0].start_ms, left[-1].end_ms, left_text))
                        out.append(SRTItem(right[0].start_ms, right[-1].end_ms, right_text))
                    else:
                        out.append(SRTItem(start, end, text))
                else:
                    out.append(SRTItem(start, end, text))
                buf = [it]
            else:
                buf.append(it)
    if buf:
        start = buf[0].start_ms
        end = buf[-1].end_ms
        text = " ".join(b.text.strip() for b in buf).strip()
        if len(text) > max_chars or (end - start) > max_duration_ms:
            split_idx = -1
            for j in range(len(buf) - 1, -1, -1):
                t = buf[j].text.strip()
                if t and t[-1] in pauses:
                    split_idx = j
                    break
            if split_idx >= 0:
                left = buf[:split_idx + 1]
                right = buf[split_idx + 1:]
                left_text = " ".join(b.text.strip() for b in left).strip()
                right_text = " ".join(b.text.strip() for b in right).strip()
                out.append(SRTItem(left[0].start_ms, left[-1].end_ms, left_text))
                out.append(SRTItem(right[0].start_ms, right[-1].end_ms, right_text))
            else:
                out.append(SRTItem(start, end, text))
        else:
            out.append(SRTItem(start, end, text))
    return out

def fluency_metrics(items: List[SRTItem]) -> Tuple[dict, List[Tuple[int, str, str]]]:
    terms = {".", "?", "!", "。", "？", "！"}
    def ends_with_term(t: str) -> bool:
        s = t.strip()
        return bool(s) and s[-1] in terms
    def starts_with_speaker(t: str) -> bool:
        s = t.strip()
        return s.startswith("- ") or s.startswith("— ") or s.startswith("-") or s.startswith("—")
    total = len(items)
    term_end = sum(1 for it in items if ends_with_term(it.text))
    breaks: List[Tuple[int, str, str]] = []
    for i in range(0, len(items) - 1):
        a = items[i]
        b = items[i + 1]
        if not ends_with_term(a.text) and not starts_with_speaker(b.text):
            breaks.append((i + 1, a.text.strip(), b.text.strip()))
    score = {
        "total": total,
        "terminal_end_ratio": (term_end / float(total)) if total > 0 else 0.0,
        "break_count": len(breaks),
    }
    return score, breaks


def extract_speaker(text: str) -> Tuple[Optional[str], str]:
    s = text.strip()
    if s.startswith("["):
        if s.lower().startswith("[speaker:") or s.startswith("[Speaker：") or s.startswith("[Speaker:"):
            end = s.find("]")
            if end > 0:
                tag = s[1:end]
                delim_pos = tag.find(":")
                if delim_pos < 0:
                    delim_pos = tag.find("：")
                if delim_pos > 0:
                    name = tag[delim_pos+1:].strip()
                    rest = s[end+1:].lstrip()
                    return (name or None), rest
    if s.startswith("【"):
        if s.startswith("【Speaker:") or s.startswith("【Speaker："):
            end = s.find("】")
            if end > 0:
                tag = s[1:end]
                delim_pos = tag.find(":")
                if delim_pos < 0:
                    delim_pos = tag.find("：")
                if delim_pos > 0:
                    name = tag[delim_pos+1:].strip()
                    rest = s[end+1:].lstrip()
                    return (name or None), rest
    return None, text


def _llm_request(messages: list, model: str, base_url: Optional[str], api_key: str) -> Optional[str]:
    url = base_url or "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            obj = json.loads(body)
            c = obj.get("choices") or []
            if not c:
                return None
            m = c[0].get("message") or {}
            return m.get("content")
    except urllib.error.URLError:
        return None
    except Exception:
        return None


def _extract_srt_blocks(text: str) -> Tuple[Optional[str], Optional[str]]:
    t = text or ""
    d1 = None
    d2 = None
    if "```srt" in t:
        parts = t.split("```srt")
        if len(parts) >= 3:
            b1 = parts[1].split("```", 1)[0]
            b2 = parts[2].split("```", 1)[0]
            d1 = b1.strip()
            d2 = b2.strip()
            return d1, d2
    if "[Output 1" in t and "[Output 2" in t:
        p1 = t.split("[Output 1", 1)[1]
        if "[Output 2" in p1:
            b1 = p1.split("[Output 2", 1)[0]
            p2 = t.split("[Output 2", 1)[1]
            d1 = b1.strip()
            d2 = p2.strip()
    return d1, d2


def llm_generate_dual_srt(items: List[SRTItem]) -> Tuple[List[SRTItem], List[SRTItem]]:
    provider = os.environ.get("PYVIDEOTRANS_LLM_PROVIDER", "openai")
    api_key = os.environ.get("PYVIDEOTRANS_LLM_API_KEY", "")
    base_url = os.environ.get("PYVIDEOTRANS_LLM_BASE_URL", "")
    model = os.environ.get("PYVIDEOTRANS_LLM_MODEL", "gpt-4o-mini")
    if not api_key:
        return items, semantic_restructure(items)
    srt_text = compose_srt(items)
    sys_prompt = (
        "你是一名资深的字幕本地化与语音合成脚本专家。"
        "你的任务是按阶段完成内容清洗与术语校对、生成显示版 SRT、生成语音版 SRT。"
        "严格保留专有名词与软件术语的原语言。"
        "显示版保持原有时间轴结构与适中行长，语音版合并碎片形成完整长句并重组时间轴为首行开始到末行结束。"
        "请只输出两个 SRT 代码块，分别为显示版与语音版。"
    )
    user_prompt = (
        "输入为原始 SRT。请按要求输出两个 SRT 代码块：\n"
        "[Output 1: Display SRT] 与 [Output 2: Audio SRT for Edge-TTS]。\n"
        "输入：\n```srt\n" + srt_text + "\n```"
    )
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ]
    content = _llm_request(messages, model, base_url if provider == "openai" else base_url, api_key)
    if not content:
        return items, semantic_restructure(items)
    d1, d2 = _extract_srt_blocks(content)
    if not d1 or not d2:
        return items, semantic_restructure(items)
    try:
        display_items = parse_srt_text(d1)
        audio_items = parse_srt_text(d2)
        return display_items or items, audio_items or semantic_restructure(items)
    except Exception:
        return items, semantic_restructure(items)
