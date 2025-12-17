import os
import tempfile
import pytest
from pyvideotrans.core.subtitle import read_srt

def test_invalid_srt_raises(tmp_path):
    p = os.path.join(tmp_path, "bad.srt")
    with open(p, "w", encoding="utf-8") as f:
        f.write("not an srt file\nno timestamps here\n")
    with pytest.raises(Exception):
        read_srt(p)

