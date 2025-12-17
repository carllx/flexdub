from typing import List


def detect_language(texts: List[str]) -> str:
    zh = 0
    en = 0
    for t in texts:
        for ch in t:
            o = ord(ch)
            if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF:
                zh += 1
            elif ("a" <= ch.lower() <= "z") or ch in " ,.;:!?":
                en += 1
    if zh > en:
        return "zh"
    return "en"


def recommended_voice(lang: str) -> str:
    if lang == "zh":
        return "zh-CN-YunjianNeural"
    return "en-US-AriaNeural"