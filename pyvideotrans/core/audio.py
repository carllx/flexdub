import os
import shutil
import subprocess
import tempfile
from typing import List, Optional, Tuple

import numpy as np
import soundfile as sf

try:
    import pyrubberband as rubberband
except Exception:
    rubberband = None


def remove_silence(wav_path: str) -> str:
    if not shutil.which("ffmpeg"):
        return wav_path
    out = tempfile.mktemp(suffix=".wav")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        wav_path,
        "-af",
        "silenceremove=start_periods=1:start_duration=0.15:start_threshold=-50dB:stop_periods=1:stop_duration=0.15:stop_threshold=-50dB",
        out,
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        if os.path.exists(out):
            try:
                probe = subprocess.check_output([
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    out,
                ], stderr=subprocess.DEVNULL)
                sec = float(probe.decode("utf-8").strip())
                if sec > 0:
                    return out
            except Exception:
                pass
        return wav_path
    return out


def audio_duration_ms(path: str) -> int:
    data, sr = sf.read(path)
    return int(round(len(data) / float(sr) * 1000.0))


def pad_silence(src_wav: str, dst_wav: str, target_ms: int) -> None:
    data, sr = sf.read(src_wav)
    cur_ms = int(round(len(data) / float(sr) * 1000.0))
    if cur_ms >= target_ms:
        sf.write(dst_wav, data, sr)
        return
    need_ms = target_ms - cur_ms
    pad_len = int(round(need_ms / 1000.0 * sr))
    pad = np.zeros((pad_len, data.shape[1] if len(data.shape) > 1 else 1), dtype=data.dtype)
    out = np.concatenate([data.reshape(-1, pad.shape[1]), pad], axis=0)
    sf.write(dst_wav, out, sr)


def ffmpeg_atempo_chain(ratio: float) -> str:
    chain = []
    r = ratio
    while r > 2.0:
        chain.append("atempo=2.0")
        r /= 2.0
    while r < 0.5:
        chain.append("atempo=0.5")
        r *= 2.0
    chain.append(f"atempo={r:.6f}")
    return ",".join(chain)


def time_stretch_rubberband(src_wav: str, dst_wav: str, target_ms: int) -> None:
    src_ms = audio_duration_ms(src_wav)
    if src_ms == 0:
        data, sr = sf.read(src_wav)
        sf.write(dst_wav, data, sr)
        return
    if rubberband is not None:
        data, sr = sf.read(src_wav)
        rate = src_ms / float(target_ms)
        try:
            stretched = rubberband.time_stretch(data, sr, rate)
            sf.write(dst_wav, stretched, sr)
            return
        except Exception:
            pass
    if shutil.which("ffmpeg"):
        tempo = src_ms / float(target_ms)
        chain = ffmpeg_atempo_chain(tempo)
        subprocess.run([
            "ffmpeg",
            "-y",
            "-i",
            src_wav,
            "-filter:a",
            chain,
            dst_wav,
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    data, sr = sf.read(src_wav)
    sf.write(dst_wav, data, sr)


def concat_wavs(paths: List[str], dst_wav: str) -> None:
    inputs = []
    for p in paths:
        inputs.extend(["-i", p])
    n = len(paths)
    filter_complex = "".join([f"[{i}:a]" for i in range(n)]) + f"concat=n={n}:v=0:a=1[out]"
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex, "-map", "[out]", dst_wav]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def mux_audio_video(video_path: str, audio_path: str, out_path: str, subtitle_path: Optional[str] = None, subtitle_lang: str = "zh", robust_ts: bool = False) -> None:
    cmd = ["ffmpeg", "-y", "-i", video_path, "-i", audio_path]
    if subtitle_path:
        cmd += ["-i", subtitle_path]
    cmd += [
        "-map", "0:v:0",
        "-map", "1:a:0",
    ]
    if subtitle_path:
        cmd += ["-map", "2:0", "-c:s", "mov_text", f"-metadata:s:s:0", f"language={subtitle_lang}"]
    cmd += [
        "-c:v", "copy",
        "-c:a", "aac",
        "-movflags", "+faststart",
    ]
    if robust_ts:
        cmd += ["-fflags", "+genpts", "-avoid_negative_ts", "make_zero", "-muxpreload", "0", "-muxdelay", "0"]
    cmd += [out_path]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def detect_negative_ts(video_path: str) -> bool:
    try:
        out = subprocess.check_output([
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=start_time",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ], stderr=subprocess.DEVNULL)
        val = float(out.decode("utf-8").strip())
        return val < 0.0
    except Exception:
        return False

def make_silence(dst_wav: str, ms: int, sr: int = 48000, channels: int = 1) -> None:
    if ms <= 0:
        import soundfile as sf
        sf.write(dst_wav, np.zeros((1, channels)), sr)
        return
    samples = int(round(ms / 1000.0 * sr))
    data = np.zeros((samples, channels), dtype=np.float32)
    import soundfile as sf
    sf.write(dst_wav, data, sr)

def media_duration_ms(path: str) -> int:
    try:
        out = subprocess.check_output([
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ], stderr=subprocess.DEVNULL)
        sec = float(out.decode("utf-8").strip())
        return int(round(sec * 1000.0))
    except Exception:
        return 0

def extract_audio_track(video_path: str, dst_wav: str, ar: int = 48000, mono: bool = True) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-map",
        "0:a:0",
        "-vn",
        "-ac",
        "1" if mono else "2",
        "-ar",
        str(ar),
        dst_wav,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def _read_pcm_envelope(wav_path: str, win_ms: int = 20) -> Tuple[List[float], int]:
    import wave
    import struct
    with wave.open(wav_path, "rb") as w:
        n_channels = w.getnchannels()
        sampwidth = w.getsampwidth()
        framerate = w.getframerate()
        n_frames = w.getnframes()
        raw = w.readframes(n_frames)
    total_samples = n_frames * n_channels
    if sampwidth == 3:
        # 24-bit decode
        samples = []
        for i in range(0, len(raw), 3):
            if i + 3 > len(raw):
                break
            v = int.from_bytes(raw[i:i+3] + (b"\x00" if raw[i+2] < 0x80 else b"\xff"), "little", signed=True)
            samples.append(v)
    else:
        fmt_map = {1: "b", 2: "h", 4: "i"}
        fmt = "<" + fmt_map.get(sampwidth, "h") * total_samples
        samples = list(struct.unpack(fmt, raw))
    if n_channels > 1:
        mono = []
        for i in range(0, len(samples), n_channels):
            s = 0
            for c in range(n_channels):
                s += samples[i+c]
            mono.append(s / n_channels)
    else:
        mono = samples
    win = max(1, int(framerate * win_ms / 1000))
    env: List[float] = []
    for i in range(0, len(mono), win):
        chunk = mono[i:i+win]
        if not chunk:
            break
        env.append(sum(abs(x) for x in chunk) / len(chunk))
    return env, framerate

def _detect_onset(env: List[float], start_ms: int, sr: int, win_ms: int = 20, search_ms: int = 500) -> int:
    idx_start = int(start_ms / win_ms)
    span = int(search_ms / win_ms)
    lo = max(0, idx_start - span)
    hi = min(len(env) - 1, idx_start + span)
    base_range_start = max(0, lo - span)
    base_range_end = lo
    base_vals = env[base_range_start:base_range_end] if base_range_end > base_range_start else [0.0]
    base = sum(base_vals) / max(1, len(base_vals))
    threshold = base * 3.0 if base > 0 else (max(env[lo:hi]) * 0.3 if hi > lo else 0.0)
    for j in range(lo, hi):
        if env[j] >= threshold:
            return int(j * win_ms)
    return int(idx_start * win_ms)

def write_sync_audit(wav_path: str, items: List["SRTItem"], csv_path: str, debug_log: str, win_ms: int = 20) -> None:
    env, sr = _read_pcm_envelope(wav_path, win_ms=win_ms)
    lines = ["index,start_ms,detected_ms,delta_ms"]
    dbg: List[str] = []
    for i, it in enumerate(items):
        detected = _detect_onset(env, it.start_ms, sr, win_ms=win_ms)
        delta = detected - it.start_ms
        lines.append(f"{i},{it.start_ms},{detected},{delta}")
        dbg.append(f"[{i}] start={it.start_ms} detected={detected} delta={delta}")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    with open(debug_log, "w", encoding="utf-8") as f:
        f.write("\n".join(dbg))

def split_wav_by_durations(src_wav: str, durations_ms: List[int]) -> List[str]:
    data, sr = sf.read(src_wav)
    total = len(data)
    channels = data.shape[1] if len(data.shape) > 1 else 1
    pos = 0
    out_paths: List[str] = []
    for i, dur in enumerate(durations_ms):
        n = int(round(dur / 1000.0 * sr))
        if i == len(durations_ms) - 1:
            n = max(0, total - pos)
        end = min(total, pos + n)
        chunk = data[pos:end]
        out = tempfile.mktemp(suffix=".wav")
        if end <= pos or len(chunk) == 0:
            silence = np.zeros((1, channels), dtype=np.float32)
            sf.write(out, silence, sr)
        else:
            sf.write(out, chunk.reshape(-1, channels) if len(chunk.shape) == 1 else chunk, sr)
        out_paths.append(out)
        pos = end
    return out_paths

def _build_envelope(wav_path: str, win_ms: int = 20) -> Tuple[List[float], int]:
    env, sr = _read_pcm_envelope(wav_path, win_ms=win_ms)
    return env, sr

def _nearest_low_energy_ms(env: List[float], target_ms: int, win_ms: int = 20, search_ms: int = 250) -> int:
    idx = int(target_ms / win_ms)
    span = int(search_ms / win_ms)
    lo = max(0, idx - span)
    hi = min(len(env) - 1, idx + span)
    if hi <= lo:
        return target_ms
    min_val = env[idx]
    min_pos = idx
    for j in range(lo, hi + 1):
        v = env[j]
        if v < min_val:
            min_val = v
            min_pos = j
    return int(min_pos * win_ms)

def split_wav_by_durations_smart(src_wav: str, durations_ms: List[int], win_ms: int = 20, search_ms: int = 250) -> List[str]:
    data, sr = sf.read(src_wav)
    total = len(data)
    channels = data.shape[1] if len(data.shape) > 1 else 1
    env, _ = _build_envelope(src_wav, win_ms=win_ms)
    pos = 0
    out_paths: List[str] = []
    for i, dur in enumerate(durations_ms):
        cur_ms = int(round(pos / float(sr) * 1000.0))
        tgt_ms = cur_ms + max(0, dur)
        cut_ms = _nearest_low_energy_ms(env, tgt_ms, win_ms=win_ms, search_ms=search_ms)
        n = int(round(cut_ms / 1000.0 * sr)) - pos
        if i == len(durations_ms) - 1:
            n = max(0, total - pos)
        end = min(total, pos + max(0, n))
        chunk = data[pos:end]
        out = tempfile.mktemp(suffix=".wav")
        if end <= pos or len(chunk) == 0:
            silence = np.zeros((1, channels), dtype=np.float32)
            sf.write(out, silence, sr)
        else:
            sf.write(out, chunk.reshape(-1, channels) if len(chunk.shape) == 1 else chunk, sr)
        out_paths.append(out)
        pos = end
    return out_paths
