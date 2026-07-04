"""Prompt template for actionable insight extraction."""

SYSTEM = """\
You are a financial analyst extracting actionable investment ideas and important events \
from a video transcript. Respond with valid JSON only.
"""

def build_user_prompt(transcript: str, title: str) -> str:
    return f"""\
Video title: {title}

TRANSCRIPT:
{transcript[:12000]}

Extract actionable insights and events. Return JSON:
{{
  "insights": [
    {{
      "insight_type": "buy_idea|sell_idea|watchlist|risk|catalyst|earnings_date|macro_event",
      "ticker": "AAPL or null",
      "description": "Clear description of the insight or event",
      "event_date": "YYYY-MM-DD or null"
    }}
  ]
}}

Rules:
- buy_idea: explicit buy/long recommendation
- sell_idea: explicit sell/short recommendation
- watchlist: stock to watch but no clear direction yet
- risk: a specific risk factor investors should know
- catalyst: an upcoming event that could move a stock
- earnings_date: a specific earnings release date mentioned
- macro_event: Fed meeting, CPI print, election, etc.
- description: 1-2 sentences, actionable and specific
- event_date: only when a specific date is mentioned
- Max 15 insights
"""
