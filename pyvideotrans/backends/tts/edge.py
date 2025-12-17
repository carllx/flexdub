import os
import shutil
import subprocess
import tempfile
from typing import Optional

try:
    import edge_tts
except Exception:
    edge_tts = None

from .interfaces import TTSBackend


class EdgeTTSBackend(TTSBackend):
    async def synthesize(self, text: str, voice: str, ar: int) -> str:
        if edge_tts is None:
            raise RuntimeError("edge-tts not available")
        tmp = tempfile.mktemp(suffix=".mp3")
        last_err: Optional[Exception] = None
        for _ in range(3):
            try:
                communicate = edge_tts.Communicate(text, voice=voice)
                await communicate.save(tmp)
                last_err = None
                break
            except Exception as e:
                last_err = e
                import asyncio
                await asyncio.sleep(0.8)
        if last_err is not None:
            raise last_err
        wav = tempfile.mktemp(suffix=".wav")
        if shutil.which("ffmpeg"):
            subprocess.run([
                "ffmpeg",
                "-y",
                "-i",
                tmp,
                "-ar",
                str(ar),
                "-ac",
                "1",
                wav,
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(tmp):
                os.remove(tmp)
            return wav
        return tmp
