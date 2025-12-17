import os
import shutil
import tempfile

import numpy as np
import pytest
import soundfile as sf

from flexdub.core.audio import remove_silence as _remove_silence, time_stretch_rubberband as _time_stretch_rubberband, audio_duration_ms as _audio_duration_ms


def _write_wav(path: str, seconds: float, sr: int = 16000, tone: float = 440.0, leading_silence: float = 0.5):
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    sig = 0.1 * np.sin(2 * np.pi * tone * t)
    lead = np.zeros(int(leading_silence * sr))
    data = np.concatenate([lead, sig])
    sf.write(path, data, sr)


def test_remove_silence_skips_without_ffmpeg():
    tmp = tempfile.mktemp(suffix=".wav")
    _write_wav(tmp, seconds=1.0, sr=16000, leading_silence=0.8)
    if shutil.which("ffmpeg") is None:
        out = _remove_silence(tmp)
        assert os.path.exists(out)
        assert _audio_duration_ms(out) >= 1000


def test_time_stretch_targets_duration():
    tmp_in = tempfile.mktemp(suffix=".wav")
    _write_wav(tmp_in, seconds=2.0, sr=16000, leading_silence=0.0)
    tmp_out = tempfile.mktemp(suffix=".wav")
    _time_stretch_rubberband(tmp_in, tmp_out, target_ms=1000)
    dur = _audio_duration_ms(tmp_out)
    assert abs(dur - 1000) <= 200