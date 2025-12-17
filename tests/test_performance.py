import time
import tempfile

import numpy as np
import soundfile as sf

from flexdub.core.audio import time_stretch_rubberband as _time_stretch_rubberband


def _write_wav(path: str, seconds: float, sr: int = 16000, tone: float = 440.0):
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    sig = 0.1 * np.sin(2 * np.pi * tone * t)
    sf.write(path, sig, sr)


def test_time_stretch_perf_small_clip():
    tmp_in = tempfile.mktemp(suffix=".wav")
    _write_wav(tmp_in, seconds=2.0, sr=16000)
    tmp_out = tempfile.mktemp(suffix=".wav")
    t0 = time.time()
    _time_stretch_rubberband(tmp_in, tmp_out, target_ms=1500)
    dt = time.time() - t0
    assert dt < 2.0