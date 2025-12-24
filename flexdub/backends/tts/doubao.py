"""Doubao TTS backend implementation."""

import os
import shutil
import subprocess
import tempfile

import aiohttp

from .interfaces import TTSBackend


class DoubaoTTSBackend(TTSBackend):
    """TTS backend using external doubao-tts-api HTTP service."""

    DEFAULT_SPEAKER = "温柔桃子"
    DEFAULT_TIMEOUT = 180  # Increased for long text segments

    def __init__(self, server_url: str = "http://localhost:3456"):
        """
        Initialize DoubaoTTSBackend.

        Args:
            server_url: Base URL of doubao-tts-api service
        """
        self.server_url = server_url

    async def synthesize(self, text: str, voice: str, ar: int) -> str:
        """
        Synthesize text using Doubao TTS service.

        Args:
            text: Text to synthesize
            voice: Speaker name (e.g., "磁性俊宇", "温柔桃子")
            ar: Target sample rate in Hz

        Returns:
            Path to WAV file (mono, specified sample rate)

        Raises:
            RuntimeError: If service unavailable or synthesis fails
        """
        speaker = voice if voice else self.DEFAULT_SPEAKER
        url = f"{self.server_url}/tts"
        payload = {"text": text, "speaker": speaker}

        tmp_aac = tempfile.mktemp(suffix=".aac")

        try:
            timeout = aiohttp.ClientTimeout(total=self.DEFAULT_TIMEOUT)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                try:
                    async with session.post(url, json=payload) as resp:
                        if resp.status != 200:
                            error_text = await resp.text()
                            raise RuntimeError(f"Doubao TTS failed: {error_text}")
                        data = await resp.read()
                        with open(tmp_aac, "wb") as f:
                            f.write(data)
                except aiohttp.ClientError as e:
                    raise RuntimeError(
                        f"Doubao TTS service connection failed: {self.server_url}"
                    ) from e
        except TimeoutError:
            raise RuntimeError("Doubao TTS request timeout")

        # Convert AAC to WAV
        wav = tempfile.mktemp(suffix=".wav")
        if shutil.which("ffmpeg"):
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        tmp_aac,
                        "-ar",
                        str(ar),
                        "-ac",
                        "1",
                        wav,
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if os.path.exists(tmp_aac):
                    os.remove(tmp_aac)
                return wav
            except subprocess.CalledProcessError:
                if os.path.exists(tmp_aac):
                    os.remove(tmp_aac)
                raise
        return tmp_aac
