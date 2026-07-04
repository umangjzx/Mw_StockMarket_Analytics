"""Prompt template for classifying news article sentiment/impact/related tickers."""

SYSTEM = """\
You are a financial analyst assistant that classifies news headlines and \
summaries for their relevance to a specific stock.

Respond with valid JSON only. No markdown fences, no commentary outside the JSON.
"""


def build_user_prompt(symbol: str, company_name: str, articles: list[str]) -> str:
    numbered = "\n".join(f"{i + 1}. {text}" for i, text in enumerate(articles))
    return f"""\
Stock: {symbol} ({company_name})

Classify each of these {len(articles)} news items with respect to this stock:

{numbered}

Return exactly this JSON shape:
{{
  "articles": [
    {{"sentiment": "bullish" | "bearish" | "neutral", "impact_score": 0-100, "related_tickers": ["TICKER1", "TICKER2"]}}
  ]
}}

Rules:
- Return exactly {len(articles)} entries in "articles", in the same order as the input list
- sentiment: how this news reads for {symbol} specifically, not the market in general
- impact_score: 0-100, how much this news is likely to move the stock (0 = irrelevant noise, 100 = major market-moving event)
- related_tickers: other stock tickers explicitly mentioned or clearly implicated by the article (empty list if none)
"""
