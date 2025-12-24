import asyncio
import tempfile
from typing import List, Optional, Tuple, Dict

from tqdm import tqdm

from flexdub.core.audio import remove_silence, audio_duration_ms, pad_silence, time_stretch_rubberband, split_wav_by_durations, split_wav_by_durations_smart
from flexdub.core.subtitle import SRTItem, extract_speaker
from flexdub.backends.tts.edge import EdgeTTSBackend
from flexdub.backends.tts.doubao import DoubaoTTSBackend


async def _synthesize_segment(text: str, voice: str, backend: str, ar: int) -> str:
    if backend == "edge_tts":
        b = EdgeTTSBackend()
    elif backend == "doubao":
        b = DoubaoTTSBackend()
    else:
        raise ValueError(f"unsupported backend: {backend}")
    tmp_wav = await b.synthesize(text, voice, ar)
    return tmp_wav


async def build_audio_from_srt(items: List[SRTItem], voice: str, backend: str, ar: int, jobs: int = 4, progress: bool = True) -> List[str]:
    total = len(items)
    out_paths: List[Optional[str]] = [None] * total
    sem = asyncio.Semaphore(max(1, jobs))

    async def worker(idx: int, it: SRTItem) -> Tuple[int, str]:
        async with sem:
            raw = await _synthesize_segment(it.text, voice, backend, ar)
        target_ms = max(0, it.end_ms - it.start_ms)
        chars = len(it.text.strip())
        cpm = chars / (max(1, target_ms) / 60000.0)
        use_clean = cpm <= 260 and target_ms >= 1200
        cleaned = remove_silence(raw) if use_clean else raw
        src_ms = audio_duration_ms(cleaned)
        out = tempfile.mktemp(suffix=".wav")
        if src_ms < target_ms:
            pad_silence(cleaned, out, target_ms)
        elif src_ms > target_ms:
            time_stretch_rubberband(cleaned, out, target_ms)
        else:
            import soundfile as sf
            data, sr = sf.read(cleaned)
            sf.write(out, data, sr)
        return idx, out

    tasks = [asyncio.create_task(worker(i, it)) for i, it in enumerate(items)]
    if progress:
        bar = tqdm(total=total, desc="Processing", unit="seg")
    for fut in asyncio.as_completed(tasks):
        idx, path = await fut
        out_paths[idx] = path
        if progress:
            bar.update(1)
    if progress:
        bar.close()
    return [p or "" for p in out_paths]


def _semantic_clusters(items: List[SRTItem]) -> List[List[Tuple[int, SRTItem]]]:
    terms = {".", "?", "!", "。", "？", "！"}
    def ends_with_term(t: str) -> bool:
        s = t.strip()
        return bool(s) and s[-1] in terms
    def starts_with_speaker(t: str) -> bool:
        s = t.strip()
        return s.startswith("- ") or s.startswith("— ") or s.startswith("-") or s.startswith("—")
    clusters: List[List[Tuple[int, SRTItem]]] = []
    buf: List[Tuple[int, SRTItem]] = []
    prev_speaker: Optional[str] = None
    for idx, it in enumerate(items):
        sp, _ = extract_speaker(it.text)
        if not buf:
            buf.append((idx, it))
            prev_speaker = sp
        else:
            if (sp is not None and sp != prev_speaker) or starts_with_speaker(it.text) or ends_with_term(buf[-1][1].text):
                clusters.append(buf)
                buf = [(idx, it)]
                prev_speaker = sp
            else:
                buf.append((idx, it))
    if buf:
        clusters.append(buf)
    return clusters


async def build_audio_from_srt_clustered(items: List[SRTItem], voice: str, backend: str, ar: int, jobs: int = 4, progress: bool = True, smart_split: bool = False, voice_map: Optional[Dict[str, str]] = None) -> List[str]:
    total = len(items)
    out_paths: List[Optional[str]] = [None] * total
    sem = asyncio.Semaphore(max(1, jobs))

    async def synth_cluster(cluster: List[Tuple[int, SRTItem]]) -> None:
        first_speaker, _ = extract_speaker(cluster[0][1].text)
        chosen_voice = voice
        if voice_map is not None:
            if first_speaker is not None and first_speaker in voice_map:
                chosen_voice = voice_map.get(first_speaker, chosen_voice)
                print(f"[SPEAKER_MAP] speaker={first_speaker} voice={chosen_voice}")
            else:
                chosen_voice = voice_map.get("DEFAULT", chosen_voice)
                if first_speaker is None:
                    print("[SPEAKER_MAP] speaker=NONE use DEFAULT")
                else:
                    print(f"[SPEAKER_MAP] speaker={first_speaker} not_mapped use DEFAULT={chosen_voice}")
        clean_texts = []
        for _, it in cluster:
            sp, ct = extract_speaker(it.text)
            clean_texts.append(ct.strip())
        text = " ".join(t for t in clean_texts if t).strip()
        async with sem:
            raw = await _synthesize_segment(text, chosen_voice, backend, ar)
        target_ms = sum(max(0, it.end_ms - it.start_ms) for _, it in cluster)
        src_ms = audio_duration_ms(raw)
        stretched = tempfile.mktemp(suffix=".wav")
        if src_ms < target_ms:
            pad_silence(raw, stretched, target_ms)
        elif src_ms > target_ms:
            time_stretch_rubberband(raw, stretched, target_ms)
        else:
            import soundfile as sf
            data, sr = sf.read(raw)
            sf.write(stretched, data, sr)
        durations = [max(0, it.end_ms - it.start_ms) for _, it in cluster]
        parts = split_wav_by_durations_smart(stretched, durations) if smart_split else split_wav_by_durations(stretched, durations)
        for (orig_idx, _), p in zip(cluster, parts):
            out_paths[orig_idx] = p

    clusters = _semantic_clusters(items)
    tasks = [asyncio.create_task(synth_cluster(c)) for c in clusters]
    if progress:
        bar = tqdm(total=len(tasks), desc="Clusters", unit="clu")
    for fut in asyncio.as_completed(tasks):
        await fut
        if progress:
            bar.update(1)
    if progress:
        bar.close()
    return [p or "" for p in out_paths]
