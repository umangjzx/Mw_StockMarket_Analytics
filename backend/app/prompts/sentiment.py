"""Prompt template for sentiment scoring."""

SYSTEM = """\
You are a financial sentiment analyst. Score the overall tone of a video transcript \
and the per-ticker sentiment. Respond with valid JSON only.
"""

def build_user_prompt(transcript: str, title: str, tickers: list[str]) -> str:
    ticker_list = ", ".join(tickers) if tickers else "any mentioned"
    return f"""\
Video title: {title}
Key tickers to score: {ticker_list}

TRANSCRIPT:
{transcript[:12000]}

Return JSON:
{{
  "overall_sentiment": "bullish|bearish|neutral|mixed",
  "bullish_pct": 60.0,
  "bearish_pct": 20.0,
  "neutral_pct": 20.0,
  "confidence_score": 85.0,
  "ticker_sentiments": [
    {{
      "ticker": "AAPL",
      "sentiment": "bullish|bearish|neutral",
      "confidence_score": 80.0
    }}
  ]
}}

Rules:
- bullish_pct + bearish_pct + neutral_pct must sum to exactly 100.0
- confidence_score: 0-100, how confident you are in the classification
- ticker_sentiments: only include tickers explicitly discussed with a directional view
- overall_sentiment: "mixed" when the video discusses both bullish and bearish stocks
"""
