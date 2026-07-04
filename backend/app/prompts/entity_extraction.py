"""Prompt template for company and ticker entity extraction."""

SYSTEM = """\
You are a financial entity extractor. Identify all companies and their stock tickers \
mentioned in a video transcript. Respond with valid JSON only.
"""

def build_user_prompt(transcript: str, title: str) -> str:
    return f"""\
Video title: {title}

TRANSCRIPT:
{transcript[:12000]}

Extract all companies and tickers mentioned. Return JSON:
{{
  "entities": [
    {{
      "company_name": "Full legal or common company name",
      "ticker": "TICKER",
      "exchange": "NYSE|NASDAQ|NSE|BSE|OTHER|null",
      "mention_count": 3,
      "sector": "Technology|Finance|Healthcare|Energy|Consumer|Industrials|Materials|Utilities|Real Estate|Communication|null"
    }}
  ]
}}

Rules:
- Include only publicly traded companies with identifiable tickers
- Use the most common ticker format (e.g. AAPL, not Apple Inc.)
- mention_count is how many times the company is meaningfully referenced
- exchange: use null if uncertain
- Sort by mention_count descending
- Max 20 entities
"""
