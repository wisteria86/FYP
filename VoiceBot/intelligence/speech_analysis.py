"""Reusable observable speech metrics; missing audio stays unavailable."""
import re
from domain.ports import VoiceMetrics


class TranscriptSpeechAnalysis:
    def analyze_audio(self, transcript, spoken_seconds):
        words = re.findall(r"[\w'-]+", transcript.lower())
        return VoiceMetrics(
            len(words) / spoken_seconds * 60 if spoken_seconds >= 1 else None,
            sum(words.count(w) for w in ('um', 'uh', 'like', 'basically', 'actually')),
            spoken_seconds,
        )
