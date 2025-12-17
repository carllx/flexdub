import json
from typing import List, Dict, Any, Tuple

from flexdub.core.rebalance import Segment
from flexdub.core.adapters import segments_from_whisperx, segments_from_gemini, segments_from_dicts


def read_segments_json(path: str, source: str = "auto") -> List[Segment]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    items: List[Dict[str, Any]]
    if isinstance(data, dict) and "segments" in data:
        items = data["segments"]
    elif isinstance(data, list):
        items = data
    else:
        items = []
    if source == "whisperx":
        return segments_from_whisperx(items)
    if source == "gemini":
        return segments_from_gemini(items)
    return segments_from_dicts(items)


def write_segments_json(path: str, segments: List[Segment]) -> None:
    rows = [{"start_ms": s.start_ms, "end_ms": s.end_ms, "text": s.text} for s in segments]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def audit_rows_from_segments(segments: List[Segment]) -> List[Tuple[int, float, int, int, int, int]]:
    out: List[Tuple[int, float, int, int, int, int]] = []
    for idx, s in enumerate(segments, start=1):
        dur = max(1, s.end_ms - s.start_ms)
        chars = len(s.text.strip())
        cpm = chars / (dur / 60000.0)
        out.append((idx, cpm, dur, chars, s.start_ms, s.end_ms))
    return out