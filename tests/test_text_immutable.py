import os
import tempfile
from flexdub.cli.__main__ import main

SRT_SAMPLE = """1\n00:00:01,000 --> 00:00:03,000\n[Intro] Hello * world\n\n2\n00:00:03,500 --> 00:00:05,000\nMeta: `Test` Content\n"""

def write_srt(tmp_path: str, content: str) -> str:
    p = os.path.join(tmp_path, "sample.srt")
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return p

def read_texts(path: str):
    with open(path, "r", encoding="utf-8") as f:
        t = f.read()
    lines = [l.strip() for l in t.splitlines()]
    texts = []
    buf = []
    for ln in lines:
        if ln and ln[0].isdigit() and ":" in ln and "-->" in ln:
            continue
        if ln.isdigit():
            continue
        if ln.strip() == "":
            if buf:
                texts.append(" ".join(buf).strip())
                buf = []
        else:
            buf.append(ln)
    if buf:
        texts.append(" ".join(buf).strip())
    return texts

def test_rebalance_text_immutable_default(tmp_path):
    srt_in = write_srt(tmp_path, SRT_SAMPLE)
    out = os.path.join(tmp_path, "out.srt")
    rc = main(["rebalance", srt_in, "-o", out])
    assert rc == 0
    in_texts = read_texts(srt_in)
    out_texts = read_texts(out)
    assert in_texts == out_texts

def test_rebalance_text_always_immutable(tmp_path):
    srt_in = write_srt(tmp_path, SRT_SAMPLE)
    out = os.path.join(tmp_path, "out2.srt")
    rc = main(["rebalance", srt_in, "-o", out])
    assert rc == 0
    in_texts = read_texts(srt_in)
    out_texts = read_texts(out)
    assert in_texts == out_texts
