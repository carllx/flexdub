import re
import sys
from pathlib import Path

def parse_time(s):
    h, m, rest = s.split(":")
    sec, ms = rest.split(",")
    return int(h) * 3600000 + int(m) * 60000 + int(sec) * 1000 + int(ms)

def fmt_time(ms):
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def read_srt(path):
    items = []
    idx = None
    start = None
    end = None
    text_lines = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip("\ufeff")
        if re.match(r"^\d+$", line):
            if idx is not None:
                items.append((idx, start, end, " ".join(text_lines).strip()))
            idx = int(line)
            start = None
            end = None
            text_lines = []
        elif "-->" in line:
            a, b = [p.strip() for p in line.split("-->")]
            start = parse_time(a)
            end = parse_time(b)
        elif line == "":
            continue
        else:
            text_lines.append(line)
    if idx is not None:
        items.append((idx, start, end, " ".join(text_lines).strip()))
    return items

def write_srt(path, items):
    out = []
    for i, (idx, start, end, text) in enumerate(items, 1):
        out.append(str(i))
        out.append(f"{fmt_time(start)} --> {fmt_time(end)}")
        out.append(text)
        out.append("")
    Path(path).write_text("\ufeff" + "\n".join(out), encoding="utf-8")

_han = "[\u4e00-\u9fff]"
_pun = "[。！？!?，、；;：:,.]"

def _strip_meta(t):
    t = re.sub(r"\[[^\]]*\]", "", t)
    t = re.sub(r"【[^】]*】", "", t)
    t = re.sub(r"\([^)]*\)", "", t)
    return t

def clean_display(t):
    t = _strip_meta(t)
    t = t.replace("\u3000", " ")
    t = re.sub(r"\s+", " ", t)
    t = re.sub(rf"(?<={_han})\s+(?={_han})", "", t)
    t = re.sub(rf"(?<={_han})\s+(?={_pun})", "", t)
    t = re.sub(rf"(?<={_pun})\s+(?={_han})", "", t)
    t = re.sub(r"\s+([:;,.!?，、；：。！？])", r"\1", t)
    t = t.strip()
    return t

def clean_audio(t):
    t = _strip_meta(t)
    t = t.replace("\u3000", " ")
    t = re.sub(r"\s+", " ", t)
    t = re.sub(rf"(?<={_han})\s+(?={_han})", "", t)
    t = re.sub(rf"(?<={_han})\s+(?={_pun})", "", t)
    t = re.sub(rf"(?<={_pun})\s+(?={_han})", "", t)
    t = re.sub(r"\s+([:;,.!?，、；：。！？])", r"\1", t)
    t = t.strip()
    if t and not re.search(r"[。！？.!?，、；;：:]$", t):
        t += "。"
    return t

def is_speaker_boundary(t):
    return bool(re.match(r"^\s*[-—]\s*", t))

def is_terminal(t):
    return bool(re.search(r"[。！？.!?]$", t))

def build_display(items):
    cleaned = []
    for idx, start, end, text in items:
        ct = clean_display(text)
        cleaned.append((idx, start, end, ct))
    return cleaned

def split_long_text(text, start, end):
    if len(text) <= 250 and (end - start) <= 15000:
        return [(start, end, text)]
    parts = re.split(r"([，；;,])", text)
    chunks = []
    buf = ""
    for i in range(0, len(parts), 2):
        seg = parts[i]
        sep = parts[i + 1] if i + 1 < len(parts) else ""
        buf = (buf + seg + sep).strip()
        if len(buf) >= 80 or sep in ("；", ";"):
            chunks.append(buf)
            buf = ""
    if buf:
        chunks.append(buf)
    total = sum(len(c) for c in chunks) or 1
    dur = end - start
    acc = start
    out = []
    for i, c in enumerate(chunks):
        share = len(c) / total
        seg_dur = int(round(dur * share))
        seg_end = acc + seg_dur
        if i == len(chunks) - 1:
            seg_end = end
        out.append((acc, seg_end, c))
        acc = seg_end
    return out

def build_audio(items):
    out = []
    buf_text = ""
    buf_start = None
    last_end = None
    for idx, start, end, text in items:
        t = clean_audio(text)
        if buf_text == "":
            buf_text = t
            buf_start = start
            last_end = end
        else:
            if is_speaker_boundary(t):
                for s, e, tt in split_long_text(buf_text, buf_start, last_end):
                    out.append((0, s, e, tt))
                buf_text = t
                buf_start = start
                last_end = end
            else:
                buf_text = (buf_text + " " + t).strip()
                last_end = end
            if is_terminal(t):
                for s, e, tt in split_long_text(buf_text, buf_start, last_end):
                    out.append((0, s, e, tt))
                buf_text = ""
                buf_start = None
                last_end = None
    if buf_text:
        for s, e, tt in split_long_text(buf_text, buf_start, last_end):
            out.append((0, s, e, tt))
    audio_items = []
    for i, (_, s, e, t) in enumerate(out, 1):
        audio_items.append((i, s, e, t))
    return audio_items

def main():
    if len(sys.argv) != 3:
        print("usage: dual_srt_llm_clean.py <input_srt> <output_dir>")
        sys.exit(1)
    in_srt = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    base = in_srt.stem
    items = read_srt(in_srt)
    display_items = build_display(items)
    audio_items = build_audio(items)
    write_srt(out_dir / f"{base}.display.srt", display_items)
    write_srt(out_dir / f"{base}.audio.srt", audio_items)

if __name__ == "__main__":
    main()
