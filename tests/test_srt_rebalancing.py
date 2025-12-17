import pytest

from flexdub.core.rebalance import Segment, rebalance_intervals


def test_rebalance_bidirectional_borrowing():
    items = [
        Segment(0, 4000, "短文本"),
        Segment(4000, 6000, "这是一个很长很长的中文句子，用来模拟高密度片段"),
        Segment(6000, 9000, "短文"),
    ]
    before = [it.duration_ms for it in items]
    out = rebalance_intervals(items, target_cpm=260, max_shift_ms=1000, panic_cpm=350)
    after = [it.duration_ms for it in out]
    assert after[1] >= before[1]
    assert out[0].end_ms <= 4000
    assert out[2].start_ms >= 6000