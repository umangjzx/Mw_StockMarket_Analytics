"""Prompt template for executive summary extraction."""

SYSTEM = """\
You are a financial analyst assistant that reads video transcripts of stock market commentary, \
earnings calls, and financial news. Extract a concise executive summary.

Respond with valid JSON only. No markdown fences, no commentary outside the JSON.
"""

def build_user_prompt(transcript: str, title: str, channel: str) -> str:
    return f"""\
Video title: {title}
Channel: {channel}

TRANSCRIPT:
{transcript[:12000]}

Extract an executive summary with these exact JSON keys:
{{
  "executive_bullets": ["bullet 1", "bullet 2", "bullet 3", "bullet 4", "bullet 5"],
  "detailed_summary": "3-5 paragraph detailed summary of the key points, arguments, and conclusions"
}}

Rules:
- executive_bullets: exactly 5 concise bullet points (max 20 words each), each starting with a capital letter
- detailed_summary: 200-400 words covering the main thesis, key data points, and conclusions
- Focus on investment-relevant information: price targets, earnings, macro views, sector themes
- If the transcript is not financial content, still summarize what was discussed
"""
