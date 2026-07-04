"""
Transcription provider interface.

All transcription adapters (YouTube captions, Whisper local, Whisper API) implement this.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class TranscriptSegment:
    """A single timestamped segment of a transcript."""
    text: str
    start_seconds: Decimal
    end_seconds: Decimal
    sequence_no: int = 0


@dataclass
class TranscriptResult:
    """Complete transcript with metadata."""
    segments: list[TranscriptSegment] = field(default_factory=list)
    source: str = "unknown"  # 'youtube_captions', 'whisper_local', 'whisper_api'
    language: str | None = None

    @property
    def full_text(self) -> str:
        """Join all segments into one string."""
        return " ".join(seg.text for seg in self.segments)

    @property
    def word_count(self) -> int:
        """Count total words across all segments."""
        return len(self.full_text.split())


class TranscriptionProvider(ABC):
    """Port that all transcription adapters must implement."""

    @abstractmethod
    async def transcribe(self, external_video_id: str, video_url: str) -> TranscriptResult:
        """
        Transcribe a video and return timestamped segments.
        Raises TranscriptionError if unavailable/failed.
        """
