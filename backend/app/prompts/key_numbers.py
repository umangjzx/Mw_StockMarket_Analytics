"""Prompt template for financial figure extraction."""

SYSTEM = """\
You are a financial data extractor. Pull out every specific numeric figure \
mentioned in a video transcript that has investment relevance. Respond with valid JSON only.
"""

def build_user_prompt(transcript: str, title: str) -> str:
    return f"""\
Video title: {title}

TRANSCRIPT:
{transcript[:12000]}

Extract all key financial figures. Return JSON:
{{
  "key_numbers": [
    {{
      "ticker": "AAPL or null",
      "metric_type": "revenue|eps|growth_pct|margin|pe_ratio|market_cap|price_target|date|percentage|other",
      "value_text": "$61.2B",
      "value_numeric": 61200000000.0,
      "context": "The surrounding sentence for provenance",
      "start_seconds_hint": null
    }}
  ]
}}

Rules:
- Include: revenue, EPS, margins, PE ratios, price targets, growth rates, market cap, dates
- value_numeric: parsed numeric value (strip $, B/M/K multipliers); null if not parseable
- context: the exact sentence where the number appears (max 150 chars)
- ticker: the company the number refers to, or null if macro/general
- Max 30 figures
"""
