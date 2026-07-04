"""Prompt template for investment thesis extraction."""

SYSTEM = """\
You are a financial analyst that extracts structured investment theses from video transcripts. \
Identify bull/bear cases, risks, catalysts, valuation commentary, and macro/market outlooks. \
Respond with valid JSON only. Omit keys where the transcript provides no relevant content.
"""

def build_user_prompt(transcript: str, title: str, channel: str) -> str:
    return f"""\
Video title: {title}
Channel: {channel}

TRANSCRIPT:
{transcript[:12000]}

Extract the investment thesis discussed. Return JSON with only the keys that have content:
{{
  "bull_case": "bull case arguments (or null)",
  "bear_case": "bear case arguments (or null)",
  "risks": "key risks mentioned (or null)",
  "catalysts": "upcoming catalysts discussed (or null)",
  "valuation_discussion": "valuation metrics, price targets, PE ratios discussed (or null)",
  "economic_outlook": "macro / economic outlook expressed (or null)",
  "market_outlook": "broad market / sector outlook expressed (or null)"
}}

Rules:
- Each value should be 1-3 sentences. Use null if not discussed.
- Quote specific figures when mentioned (e.g. "P/E of 25x", "$180 price target")
- Focus on forward-looking statements, not historical recap
"""
