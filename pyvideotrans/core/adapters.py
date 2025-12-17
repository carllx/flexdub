from typing import List, Dict, Any

from pyvideotrans.core.rebalance import Segment


def segments_from_whisperx(items: List[Dict[str, Any]]) -> List[Segment]:
    out: List[Segment] = []
    for it in items:
        s = it.get("start", 0.0)
        e = it.get("end", 0.0)
        text = str(it.get("text", ""))
        start_ms = int(round(float(s) * 1000.0))
        end_ms = int(round(float(e) * 1000.0))
        out.append(Segment(start_ms, end_ms, text))
    return out


def segments_from_gemini(items: List[Dict[str, Any]]) -> List[Segment]:
    out: List[Segment] = []
    for it in items:
        s = it.get("start")
        e = it.get("end")
        text = str(it.get("text", ""))
        if s is None or e is None:
            s = it.get("start_ms", 0)
            e = it.get("end_ms", 0)
            start_ms = int(s)
            end_ms = int(e)
        else:
            start_ms = int(round(float(s) * 1000.0))
            end_ms = int(round(float(e) * 1000.0))
        out.append(Segment(start_ms, end_ms, text))
    return out


def segments_from_dicts(items: List[Dict[str, Any]]) -> List[Segment]:
    out: List[Segment] = []
    for it in items:
        text = str(it.get("text", ""))
        if "start_ms" in it and "end_ms" in it:
            start_ms = int(it["start_ms"])
            end_ms = int(it["end_ms"])
        elif "start" in it and "end" in it:
            s = float(it["start"])  # seconds
            e = float(it["end"])    # seconds
            start_ms = int(round(s * 1000.0))
            end_ms = int(round(e * 1000.0))
        else:
            start_ms = int(it.get("start", 0))
            end_ms = int(it.get("end", 0))
        out.append(Segment(start_ms, end_ms, text))
    return out