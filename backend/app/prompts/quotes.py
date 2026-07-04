"""Prompt template for notable quote extraction."""

SYSTEM = """\
You are a financial journalist assistant. Extract the most impactful, quotable statements \
from a video transcript. Respond with valid JSON only.
"""

def build_user_prompt(transcript: str, title: str, channel: str) -> str:
    return f"""\
Video title: {title}
Channel: {channel}

TRANSCRIPT:
{transcript[:12000]}

Extract the top 10 most notable quotes. Return JSON:
{{
  "quotes": [
    {{
      "quote_text": "Exact or near-exact quote from the transcript",
      "speaker": "Speaker name or null if unknown",
      "importance_rank": 1,
      "start_seconds_hint": 120.5
    }}
  ]
}}

Rules:
- importance_rank: 1 = most important, 10 = least
- Prioritize: price targets, bold market calls, earnings guidance, surprising claims
- quote_text: keep verbatim or minimally edited for clarity (max 200 chars)
- start_seconds_hint: approximate timestamp in seconds from context clues; use null if unknown
- speaker: the person saying it, null if not identified
- Return exactly 10 quotes, or fewer if the transcript has less notable content
"""
