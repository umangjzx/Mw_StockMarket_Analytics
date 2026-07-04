"""
Prompt template for the Company Intelligence AI executive summary — the
capstone view synthesizing live market data, fundamentals, technicals,
earnings, news, analyst opinion, and the platform's own AI video analysis
into one narrative. Distinct from prompts/executive_summary.py, which
summarizes a single video's transcript, not a company across all sources.
"""

SYSTEM = """\
You are a senior equity research analyst producing a concise executive briefing \
on a stock by synthesizing data from multiple sources: live market data, financial \
ratios, technical indicators, earnings history, recent news, analyst opinion, and \
sentiment expressed in financial YouTube commentary.

Ground every claim in the data provided — do not invent facts, price levels, or \
events not present in the input. If a section has no data, say so plainly rather \
than guessing.

Respond with valid JSON only. No markdown fences, no commentary outside the JSON.
"""


def build_user_prompt(symbol: str, company_name: str, context: dict[str, str]) -> str:
    sections = "\n\n".join(f"### {label}\n{text}" for label, text in context.items() if text)
    return f"""\
Stock: {symbol} ({company_name})

{sections}

Synthesize the above into an executive briefing with exactly these JSON keys:
{{
  "business_overview": "2-3 sentences on what the company does",
  "market_outlook": "2-3 sentences on the current market backdrop for this stock",
  "why_moving_today": "1-2 sentences on the likely driver of today's price action, or 'No significant move today' if the change is minor",
  "positive_factors": ["factor 1", "factor 2", "factor 3"],
  "risks": ["risk 1", "risk 2", "risk 3"],
  "opportunities": ["opportunity 1", "opportunity 2"],
  "financial_health": "2-3 sentences assessing balance sheet strength and profitability from the ratios/financials given",
  "technical_outlook": "1-2 sentences reading the technical indicators given",
  "news_summary": "2-3 sentences summarizing the recent news flow and its tone",
  "overall_sentiment": "bullish" | "bearish" | "neutral",
  "investment_thesis": "3-4 sentences making the case for or against this stock right now",
  "short_term_outlook": "1-2 sentences, next few weeks",
  "long_term_outlook": "1-2 sentences, next 1-3 years",
  "confidence_score": 0-100
}}

Rules:
- confidence_score reflects how much of the picture above is backed by solid data vs thin/missing sections — not a price prediction
- positive_factors and risks: 2-4 items each, specific to what's in the data above, not generic boilerplate
- If a data section above says data is unavailable, acknowledge the gap rather than fabricating detail for it
"""
