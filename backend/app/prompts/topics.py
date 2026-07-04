"""Prompt template for topic classification."""

SYSTEM = """\
You are a financial content classifier. Identify the main topics discussed in a video transcript. \
Respond with valid JSON only.
"""

KNOWN_TOPICS = [
    "AI", "Semiconductors", "Inflation", "Interest Rates", "Federal Reserve",
    "Earnings", "IPO", "M&A", "China", "Oil & Gas", "Crypto", "Banking",
    "Retail", "Healthcare", "Defense", "Real Estate", "ETF", "Options",
    "Recession", "GDP", "Employment", "Consumer Spending", "Supply Chain",
    "Commodities", "Bonds", "Dividend", "Small Cap", "Large Cap", "Growth Stocks",
    "Value Investing", "Technical Analysis", "Geopolitics", "Cybersecurity",
    "Clean Energy", "Electric Vehicles", "Cloud Computing", "Biotech"
]

def build_user_prompt(transcript: str, title: str) -> str:
    return f"""\
Video title: {title}

TRANSCRIPT:
{transcript[:8000]}

Identify up to 8 topics from this list that are meaningfully discussed:
{", ".join(KNOWN_TOPICS)}

You may also add up to 2 new topics not in the list if clearly relevant.

Return JSON:
{{
  "topics": ["AI", "Semiconductors", "Earnings"]
}}

Rules:
- Only include topics with at least a paragraph of discussion
- Order by relevance (most discussed first)
- Use exact names from the list above for known topics
"""
