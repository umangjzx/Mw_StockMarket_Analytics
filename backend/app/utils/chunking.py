"""
Transcript chunking — splits transcript segments into overlapping token windows
suitable for embedding and RAG citation.

Strategy:
- Group consecutive TranscriptSegment rows into chunks of ~500 tokens
- Overlap adjacent chunks by ~100 tokens so context at chunk boundaries is not lost
- Each chunk tracks its start/end segment IDs and start/end timestamps
  so the RAG layer can cite exact timestamps

Token counting uses a simple word-based approximation (1 token ≈ 0.75 words)
to avoid requiring a tokenizer at runtime. This is accurate enough for chunking;
actual API token counts are measured by the OpenAI response.
"""

from dataclasses import dataclass, field
from decimal import Decimal


# ~500 tokens ≈ 375 words; ~100 token overlap ≈ 75 words
CHUNK_TOKEN_TARGET = 500
OVERLAP_TOKENS = 100
WORDS_PER_TOKEN = 0.75


def _word_count(text: str) -> int:
    return len(text.split())


def _tokens(text: str) -> int:
    """Rough token estimate from word count."""
    return int(_word_count(text) / WORDS_PER_TOKEN)


@dataclass
class TranscriptChunk:
    """A window of transcript text ready for embedding."""
    text: str
    start_seconds: Decimal
    end_seconds: Decimal
    segment_ids: list[int] = field(default_factory=list)  # DB IDs of covered segments
    sequence_no: int = 0                                    # chunk index within the transcript


def chunk_transcript(segments: list) -> list[TranscriptChunk]:
    """
    Split a list of TranscriptSegment ORM objects into overlapping chunks.

    Args:
        segments: ordered list of TranscriptSegment ORM objects
                  (must have: id, text, start_seconds, end_seconds, sequence_no)

    Returns:
        List of TranscriptChunk objects ordered by start_seconds.
    """
    if not segments:
        return []

    chunks: list[TranscriptChunk] = []
    chunk_no = 0

    i = 0
    n = len(segments)
    overlap_start: int | None = None  # index where the next chunk should start for overlap

    while i < n:
        chunk_segs: list = []
        token_budget = CHUNK_TOKEN_TARGET

        # Start with overlap segments from the previous chunk
        start_i = overlap_start if overlap_start is not None else i

        j = start_i
        while j < n and token_budget > 0:
            seg = segments[j]
            seg_tokens = _tokens(seg.text)
            chunk_segs.append(seg)
            token_budget -= seg_tokens
            j += 1

        if not chunk_segs:
            break

        # Build chunk text
        chunk_text = " ".join(s.text for s in chunk_segs)
        chunk = TranscriptChunk(
            text=chunk_text,
            start_seconds=chunk_segs[0].start_seconds,
            end_seconds=chunk_segs[-1].end_seconds,
            segment_ids=[s.id for s in chunk_segs],
            sequence_no=chunk_no,
        )
        chunks.append(chunk)
        chunk_no += 1

        # This chunk already reached the end of the transcript — nothing left
        # to build an overlapping follow-up chunk from. Stop here, otherwise
        # the loop below can get stuck re-emitting this same final chunk
        # forever (when the tail's token count is under OVERLAP_TOKENS).
        if j >= n:
            break

        # Advance i past the non-overlap portion
        # Find where we need to start the next chunk for OVERLAP_TOKENS worth of context
        overlap_tokens_remaining = OVERLAP_TOKENS
        overlap_start = j  # default: no overlap, start right after current chunk
        for k in range(len(chunk_segs) - 1, -1, -1):
            overlap_tokens_remaining -= _tokens(chunk_segs[k].text)
            if overlap_tokens_remaining <= 0:
                overlap_start = start_i + k
                break
        else:
            overlap_start = start_i  # whole chunk is overlap → push forward to avoid infinite loop

        # Advance i past the current chunk's non-overlap head
        i = j if overlap_start is None else max(start_i + 1, overlap_start)

        # Safety: always advance
        if i <= start_i:
            i = start_i + len(chunk_segs)

    return chunks
