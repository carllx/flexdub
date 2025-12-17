import os
import shutil
import subprocess
import tempfile

from .interfaces import TTSBackend


class SayBackend(TTSBackend):
    async def synthesize(self, text: str, voice: str, ar: int) -> str:
        if not shutil.which("say"):
            raise RuntimeError("macOS say not available")
        aiff = tempfile.mktemp(suffix=".aiff")
        subprocess.run(["say", text, "-v", voice, "-o", aiff], check=True)
        wav = tempfile.mktemp(suffix=".wav")
        if shutil.which("ffmpeg"):
            subprocess.run([
                "ffmpeg",
                "-y",
                "-i",
                aiff,
                "-ar",
                str(ar),
                wav,
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.remove(aiff)
            return wav
        os.replace(aiff, wav)
        return wav