class TTSBackend:
    async def synthesize(self, text: str, voice: str, ar: int) -> str:
        raise NotImplementedError