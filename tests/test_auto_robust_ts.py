import os
import numpy as np
import soundfile as sf

from pyvideotrans.cli import __main__ as cli_main
from pyvideotrans.cli.__main__ import main


def _write_srt(path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("""1
00:00:00,000 --> 00:00:02,000
测试自动稳健复用。

""")


async def _fake_build(items, voice, backend, ar, jobs=1, progress=True):
    p = os.path.join(os.getcwd(), "_fake.wav")
    sf.write(p, np.zeros((1000, 1), dtype=np.float32), 48000)
    return [p]


def test_auto_robust_ts_injection(monkeypatch, tmp_path):
    srt_path = os.path.join(tmp_path, "b.srt")
    _write_srt(srt_path)
    monkeypatch.setattr(cli_main, "detect_negative_ts", lambda _: True)
    captured = {"robust": None}

    def _fake_mux(video_path, audio_path, out_path, subtitle_path=None, subtitle_lang="zh", robust_ts=False):
        captured["robust"] = robust_ts
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("ok")

    monkeypatch.setattr(cli_main, "mux_audio_video", _fake_mux)
    import pyvideotrans.pipelines.dubbing as dubbing
    monkeypatch.setattr(dubbing, "build_audio_from_srt", _fake_build)

    rc = main([
        "merge",
        srt_path,
        os.path.join(tmp_path, "v.mp4"),
        "--backend",
        "macos_say",
        "--voice",
        "Ting-Ting",
        "--no-progress",
    ])
    assert rc == 0
    assert captured["robust"] is True

