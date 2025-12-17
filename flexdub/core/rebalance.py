from dataclasses import dataclass
from typing import List


@dataclass
class Segment:
    start_ms: int
    end_ms: int
    text: str

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


def _cpm(text: str, duration_ms: int) -> float:
    chars = len(text.strip())
    if duration_ms <= 0:
        return float("inf") if chars > 0 else 0.0
    return chars / (duration_ms / 60000.0)


def rebalance_intervals(items: List[Segment], target_cpm: int = 260, max_shift_ms: int = 1000, panic_cpm: int = 350) -> List[Segment]:
    n = len(items)
    if n == 0:
        return items

    ideal_ms: List[float] = []
    for it in items:
        chars = len(it.text.strip())
        ideal = (chars / float(target_cpm)) * 60000.0
        ideal_ms.append(ideal)

    new_items: List[Segment] = [Segment(it.start_ms, it.end_ms, it.text) for it in items]

    for _ in range(3):
        changed = False
        for i in range(n):
            actual = new_items[i].duration_ms
            ideal = int(round(ideal_ms[i]))
            if actual >= ideal:
                continue
            deficit = ideal - actual

            left_surplus = 0
            right_surplus = 0
            if i - 1 >= 0:
                left_actual = new_items[i - 1].duration_ms
                left_ideal = int(round(ideal_ms[i - 1]))
                left_surplus = max(0, left_actual - left_ideal)
            if i + 1 < n:
                right_actual = new_items[i + 1].duration_ms
                right_ideal = int(round(ideal_ms[i + 1]))
                right_surplus = max(0, right_actual - right_ideal)

            borrow_left = min(deficit // 2, left_surplus)
            borrow_right = min(deficit - borrow_left, right_surplus)

            shift_cap = max_shift_ms
            seg_cpm = _cpm(new_items[i].text, new_items[i].duration_ms)
            panic = seg_cpm > float(panic_cpm)
            if panic:
                shift_cap = max_shift_ms * 2

            borrow_left = min(borrow_left, shift_cap)
            borrow_right = min(borrow_right, shift_cap)

            if borrow_left > 0 and i - 1 >= 0:
                new_items[i - 1].end_ms = max(new_items[i - 1].start_ms, new_items[i - 1].end_ms - borrow_left)
                new_items[i].start_ms = max(0, new_items[i].start_ms - borrow_left)
                changed = True

            if borrow_right > 0 and i + 1 < n:
                new_items[i].end_ms = new_items[i].end_ms + borrow_right
                new_items[i + 1].start_ms = new_items[i + 1].start_ms + borrow_right
                changed = True
        if not changed:
            break

    return new_items