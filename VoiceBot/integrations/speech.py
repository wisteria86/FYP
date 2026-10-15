"""Local STT/TTS integration implementing the domain speech capability."""
class LocalSpeechAdapter:
    def __init__(self, stt, tts): self.stt, self.tts = stt, tts
    def transcribe(self, audio, language=None):
        return self.stt.transcribe_detailed(audio, language)
    def synthesize(self, text): return self.tts.synthesize_streaming(text)
