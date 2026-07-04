"""
Technical analysis service — computes indicators from the daily price bars
already persisted by Phase 1's market data pipeline. No external API call,
no caching needed: this is a pure numeric computation over ~250 floats,
comfortably sub-10ms, so it's recomputed fresh on every request.

Formulas follow the standard (Wilder-smoothed) definitions used by most
charting platforms, implemented directly in pandas rather than pulling in a
third-party TA library — pandas is already a transitive dependency via
yfinance, so this adds no new dependency and no external maintenance risk.
"""

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.market_data_repository import MarketDataRepository


class TechnicalAnalysisService:

    def __init__(self, session: AsyncSession) -> None:
        self._repo = MarketDataRepository(session)

    async def get_technicals(self, ticker_id: int) -> dict:
        bars = await self._repo.get_daily_bars(ticker_id)
        if len(bars) < 20:
            return {"status": "unavailable", "reason": "not enough price history yet (need 20+ daily bars)"}

        df = pd.DataFrame(
            [{"ts": b.ts, "open": float(b.open), "high": float(b.high),
              "low": float(b.low), "close": float(b.close), "volume": b.volume} for b in bars]
        ).set_index("ts").sort_index()

        close, high, low = df["close"], df["high"], df["low"]
        n = len(df)

        macd_line, signal_line, histogram = _macd(close)
        bb_upper, bb_middle, bb_lower = _bollinger_bands(close)

        return {
            "as_of": df.index[-1].isoformat(),
            "bars_used": n,
            "sma": {
                "sma_20": _last(_sma(close, 20)),
                "sma_50": _last(_sma(close, 50)) if n >= 50 else None,
                "sma_200": _last(_sma(close, 200)) if n >= 200 else None,
            },
            "ema": {
                "ema_12": _last(_ema(close, 12)),
                "ema_26": _last(_ema(close, 26)) if n >= 26 else None,
            },
            "rsi_14": _last(_rsi(close, 14)) if n >= 15 else None,
            "macd": {
                "macd_line": _last(macd_line),
                "signal_line": _last(signal_line),
                "histogram": _last(histogram),
            } if n >= 26 else None,
            "bollinger_bands": {
                "upper": _last(bb_upper),
                "middle": _last(bb_middle),
                "lower": _last(bb_lower),
            } if n >= 20 else None,
            "atr_14": _last(_atr(high, low, close, 14)) if n >= 15 else None,
            "stochastic_rsi_14": _last(_stochastic_rsi(close, 14)) if n >= 28 else None,
            "support_resistance": _support_resistance(high, low),
            "trend": _detect_trend(close),
            "status": "computed",
        }


def _sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    # Wilder's smoothing (alpha = 1/period), the standard RSI definition
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def _macd(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    macd_line = _ema(close, 12) - _ema(close, 26)
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _bollinger_bands(close: pd.Series, window: int = 20, num_std: float = 2.0):
    middle = close.rolling(window).mean()
    std = close.rolling(window).std()
    return middle + num_std * std, middle, middle - num_std * std


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    true_range = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return true_range.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def _stochastic_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    rsi = _rsi(close, period)
    lowest = rsi.rolling(period).min()
    highest = rsi.rolling(period).max()
    return ((rsi - lowest) / (highest - lowest).replace(0, float("nan"))) * 100


def _support_resistance(high: pd.Series, low: pd.Series) -> dict:
    """Recent swing high/low over two windows — a simple, transparent
    approach rather than pivot-point clustering, which needs more history
    than most tickers will have on first load."""
    result = {}
    for label, window in (("20d", 20), ("60d", 60)):
        if len(high) >= window:
            result[f"resistance_{label}"] = round(float(high.tail(window).max()), 4)
            result[f"support_{label}"] = round(float(low.tail(window).min()), 4)
        else:
            result[f"resistance_{label}"] = None
            result[f"support_{label}"] = None
    return result


def _detect_trend(close: pd.Series) -> str:
    """Heuristic classification from SMA alignment — not a prediction, just
    a plain-language read of where price sits relative to its moving averages."""
    n = len(close)
    last = close.iloc[-1]
    sma20 = _last(_sma(close, 20))
    sma50 = _last(_sma(close, 50)) if n >= 50 else None
    sma200 = _last(_sma(close, 200)) if n >= 200 else None

    if sma50 is None:
        return "insufficient_history"
    if sma200 is not None and sma20 > sma50 > sma200 and last > sma20:
        return "strong_uptrend"
    if sma200 is not None and sma20 < sma50 < sma200 and last < sma20:
        return "strong_downtrend"
    if last > sma50:
        return "uptrend"
    if last < sma50:
        return "downtrend"
    return "sideways"


def _last(series: pd.Series) -> float | None:
    if series is None or series.empty:
        return None
    value = series.iloc[-1]
    return round(float(value), 4) if pd.notna(value) else None
