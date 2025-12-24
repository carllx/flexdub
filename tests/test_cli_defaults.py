from flexdub.cli.__main__ import _parse_args

def test_defaults_rebalance():
    args = _parse_args(["rebalance", "dummy.srt", "-o", "out.srt"])
    assert args.target_cpm == 180
    assert args.panic_cpm == 300
    assert args.max_shift == 1000

def test_defaults_merge():
    args = _parse_args(["merge", "dummy.srt", "dummy.mp4", "--backend", "edge_tts"])
    assert args.target_cpm == 180
    assert args.panic_cpm == 300
    assert args.ar == 48000

def test_defaults_json_merge():
    args = _parse_args(["json_merge", "dummy.json", "dummy.mp4", "--backend", "edge_tts"])
    assert args.target_cpm == 180
    assert args.panic_cpm == 300
    assert args.ar == 48000

def test_defaults_project_merge():
    args = _parse_args(["project_merge", "/tmp/project", "--backend", "edge_tts"])
    assert args.target_cpm == 180
    assert args.panic_cpm == 300
    assert args.ar == 48000
