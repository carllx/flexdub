import os
from flexdub.cli.__main__ import main


def _write_srt(path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("""1
00:00:00,000 --> 00:00:02,000
你好，世界。

""")


async def _raise_async(*args, **kwargs):
    raise Exception("edge_tts failure")


def test_strict_edge_no_fallback(monkeypatch, tmp_path):
    srt_path = os.path.join(tmp_path, "a.srt")
    _write_srt(srt_path)
    from flexdub.backends.tts.edge import EdgeTTSBackend
    monkeypatch.setattr(EdgeTTSBackend, "synthesize", _raise_async)
    rc = main([
        "merge",
        srt_path,
        os.path.join(tmp_path, "v.mp4"),
        "--backend",
        "edge_tts",
        "--voice",
        "zh-CN-YunjianNeural",
        "--no-fallback",
        "--no-progress",
    ])
    assert rc == 1

