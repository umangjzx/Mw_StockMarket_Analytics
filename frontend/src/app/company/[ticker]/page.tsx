"use client";

import { use, useEffect, useState } from "react";
import {
  TrendingUp, TrendingDown, Globe, Users, Building,
  Calendar, ExternalLink, RefreshCw, ChevronUp, ChevronDown,
  Minus, AlertTriangle, CheckCircle, BarChart2, Activity,
  Newspaper, UserCheck, Brain, Video, MessageSquare, Target,
  ArrowUpRight, ArrowDownRight, Eye, Bookmark, Loader2, X,
} from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell, ReferenceLine,
} from "recharts";
import { CandlestickChart } from "@/components/charts/CandlestickChart";
import {
  useQuote, useChart, useProfile, useRatios, useFinancials,
  useEarnings, useTechnicals, useNews, useAnalyst, useExecutiveSummary,
  useIntelligence, useCompanyVideos, useWatchlists,
} from "@/lib/hooks";
import { chatApi, companyApi, watchlistApi } from "@/lib/api";
import {
  fmt, fmtLarge, fmtPct, fmtCurrency, fmtDate, fmtDateTime,
  changeClass, sentimentClass,
} from "@/lib/utils";
import { SentimentBadge, Badge } from "@/components/ui/Badge";
import { Skeleton, SkeletonCard, SkeletonTable } from "@/components/ui/Skeleton";
import { ErrorState, EmptyState } from "@/components/ui/ErrorState";
import { MetricCard, StatRow } from "@/components/ui/MetricCard";
import { Tabs } from "@/components/ui/Tabs";
import { useSWRConfig } from "swr";

// ── Quote Hero ─────────────────────────────────────────────────────────────────
function QuoteHero({ ticker }: { ticker: string }) {
  const { data, isLoading, error, mutate } = useQuote(ticker);
  if (isLoading) return (
    <div className="glass-card p-6">
      <div className="flex gap-6">
        <Skeleton className="h-10 w-32" />
        <div className="space-y-2 flex-1"><Skeleton className="h-6 w-48" /><Skeleton className="h-4 w-32" /></div>
      </div>
    </div>
  );
  if (error) return <ErrorState compact message="Could not load quote" />;

  const q: any = (data as any)?.quote ?? {};
  const isUp = (q.change_pct ?? 0) >= 0;

  return (
    <div className="glass-card p-6">
      <div className="flex flex-wrap items-start gap-6">
        <div>
          <div className="flex items-baseline gap-3">
            <span className="text-4xl font-bold font-mono text-white">
              {q.currency === "INR" ? "₹" : "$"}{fmt(q.price, 2)}
            </span>
            <div className={`flex items-center gap-1 text-sm font-semibold ${isUp ? "text-green-400" : "text-red-400"}`}>
              {isUp ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              {fmt(Math.abs(q.change_abs), 2)} ({fmtPct(q.change_pct)})
            </div>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <div className="live-dot" />
            <span className="text-[11px] text-slate-500">Live · {q.source ?? "yfinance"}</span>
          </div>
        </div>

        {/* Key stats row */}
        <div className="flex flex-wrap gap-4 flex-1">
          {[
            { label: "Open",       value: fmt(q.open, 2) },
            { label: "High",       value: fmt(q.high, 2) },
            { label: "Low",        value: fmt(q.low, 2) },
            { label: "Prev Close", value: fmt(q.prev_close, 2) },
            { label: "Volume",     value: fmtLarge(q.volume) },
            { label: "Mkt Cap",    value: fmtLarge(q.market_cap) },
            { label: "52W High",   value: fmt(q.week52_high, 2) },
            { label: "52W Low",    value: fmt(q.week52_low, 2) },
          ].map((s) => (
            <div key={s.label} className="min-w-[80px]">
              <p className="text-[10px] text-slate-600 uppercase tracking-wider font-semibold">{s.label}</p>
              <p className="text-sm font-mono font-semibold text-slate-200">{s.value}</p>
            </div>
          ))}
        </div>

        <button onClick={() => mutate()} className="btn-ghost text-xs self-start">
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      {/* 52-week range bar */}
      {q.week52_low != null && q.week52_high != null && q.price != null && (
        <div className="mt-5">
          <div className="flex justify-between text-[10px] text-slate-600 mb-1 font-mono">
            <span>52W Low: {fmt(q.week52_low, 2)}</span>
            <span>52W High: {fmt(q.week52_high, 2)}</span>
          </div>
          <div className="relative h-1.5 bg-slate-800 rounded-full overflow-visible">
            <div
              className="absolute h-full rounded-full"
              style={{
                left: 0,
                width: `${Math.min(100, Math.max(0, ((q.price - q.week52_low) / (q.week52_high - q.week52_low)) * 100))}%`,
                background: "linear-gradient(90deg, #ef4444, #22c55e)",
              }}
            />
            <div
              className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full border-2 border-blue-500 shadow"
              style={{
                left: `calc(${Math.min(100, Math.max(0, ((q.price - q.week52_low) / (q.week52_high - q.week52_low)) * 100))}% - 6px)`,
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

// ── Track This Stock? ────────────────────────────────────────────────────────────
function TrackTickerPrompt({ ticker }: { ticker: string }) {
  const { data } = useWatchlists();
  const { mutate } = useSWRConfig();
  const watchlists: any[] = (data as any)?.watchlists ?? [];
  const [dismissed, setDismissed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [added, setAdded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPicker, setShowPicker] = useState(false);

  useEffect(() => {
    setDismissed(sessionStorage.getItem(`track-dismissed-${ticker}`) === "1");
    setAdded(false);
    setError(null);
    setShowPicker(false);
  }, [ticker]);

  function dismiss() {
    setDismissed(true);
    sessionStorage.setItem(`track-dismissed-${ticker}`, "1");
  }

  async function addToList(watchlistId: number) {
    setBusy(true);
    setError(null);
    try {
      await watchlistApi.addItem(watchlistId, ticker);
      setAdded(true);
      setTimeout(dismiss, 1800);
    } catch (err: any) {
      setError(err?.message ?? "Couldn't add it — still resolving this ticker, try again in a moment");
    } finally {
      setBusy(false);
    }
  }

  async function quickTrack() {
    if (watchlists.length === 0) {
      setBusy(true);
      setError(null);
      try {
        const created: any = await watchlistApi.create({ name: "My Watchlist" });
        mutate("watchlists");
        await addToList(created.id);
      } catch (err: any) {
        setError(err?.message ?? "Couldn't create a watchlist");
        setBusy(false);
      }
      return;
    }
    if (watchlists.length === 1) {
      addToList(watchlists[0].id);
      return;
    }
    setShowPicker(true);
  }

  if (dismissed) return null;

  return (
    <div className="glass-card card-accent-purple p-4 flex flex-wrap items-center gap-3">
      <Eye size={16} className="text-purple-400 flex-shrink-0" />
      <p className="text-sm text-slate-300 flex-1 min-w-[220px]">
        {added
          ? `Added ${ticker} to your watchlist — you'll see it continuously from now on.`
          : `Viewing ${ticker}. Track it continuously in a watchlist, or just browsing this once?`}
      </p>
      {!added && (
        <div className="flex items-center gap-2 flex-wrap">
          <button onClick={quickTrack} disabled={busy} className="btn-primary text-xs px-4 disabled:opacity-50">
            {busy ? <Loader2 size={12} className="animate-spin" /> : <Bookmark size={12} />}
            Track continuously
          </button>
          <button onClick={dismiss} className="btn-ghost text-xs px-3">Just viewing</button>
        </div>
      )}
      {added && (
        <button onClick={dismiss} className="btn-ghost p-1.5 rounded-lg">
          <X size={13} />
        </button>
      )}
      {error && <p className="text-xs text-red-400 w-full">{error}</p>}
      {showPicker && (
        <div className="w-full flex flex-wrap gap-2 pt-2 border-t border-white/5">
          <span className="text-[11px] text-slate-500 self-center">Add to:</span>
          {watchlists.map((wl: any) => (
            <button
              key={wl.id}
              onClick={() => addToList(wl.id)}
              disabled={busy}
              className="btn-ghost text-xs px-3 disabled:opacity-50"
            >
              {wl.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Price Chart ────────────────────────────────────────────────────────────────
function PriceChart({ ticker }: { ticker: string }) {
  const [range, setRange] = useState("1M");
  const { data, isLoading } = useChart(ticker, range);
  const bars: any[] = (data as any)?.bars ?? [];

  // Must match backend CHART_RANGES exactly (app/providers/market_data/base.py)
  const RANGES = ["1D","1W","1M","3M","6M","1Y","5Y","MAX"];

  return (
    <div className="glass-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
          <Activity size={14} className="text-blue-400" /> Price Chart
        </h3>
        <div className="flex gap-1 flex-wrap justify-end">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`text-[10px] px-2 py-0.5 rounded font-semibold transition-all ${
                range === r ? "bg-blue-600/20 text-blue-400 border border-blue-500/30" : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {r.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <Skeleton className="h-56 w-full" />
      ) : !bars.length ? (
        <EmptyState title="No chart data" description="Chart data unavailable for this range" />
      ) : (
        <CandlestickChart bars={bars} height={260} />
      )}
    </div>
  );
}

// ── Profile ────────────────────────────────────────────────────────────────────
function ProfilePanel({ ticker }: { ticker: string }) {
  const { data, isLoading } = useProfile(ticker);
  const p: any = (data as any)?.profile ?? {};
  if (isLoading) return <SkeletonCard rows={5} />;
  return (
    <div className="glass-card p-5 space-y-4">
      <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
        <Building size={14} className="text-blue-400" /> Company Profile
      </h3>
      {p.description && (
        <p className="text-xs text-slate-400 leading-relaxed">{p.description}</p>
      )}
      <div className="space-y-0">
        {[
          { label: "CEO",           value: p.ceo,              icon: Users },
          { label: "HQ",            value: p.headquarters,     icon: Globe },
          { label: "Employees",     value: p.employees?.toLocaleString(), icon: Users },
          { label: "Exchange",      value: p.primary_exchange, icon: Building },
          { label: "IPO Date",      value: fmtDate(p.ipo_date), icon: Calendar },
        ].map(({ label, value, icon: Icon }) => (
          value ? (
            <StatRow key={label} label={label} value={
              <span className="flex items-center gap-1">{value}</span>
            } />
          ) : null
        ))}
      </div>
      {p.website && (
        <a
          href={p.website}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors"
        >
          <Globe size={12} /> {p.website}
          <ExternalLink size={10} />
        </a>
      )}
    </div>
  );
}

// ── Ratios ─────────────────────────────────────────────────────────────────────
function RatiosPanel({ ticker }: { ticker: string }) {
  const { data, isLoading } = useRatios(ticker);
  const r: any = (data as any)?.ratios ?? {};
  if (isLoading) return <SkeletonCard rows={6} />;

  const metrics = [
    { label: "P/E (Trailing)", value: fmt(r.pe_trailing) },
    { label: "P/E (Forward)",  value: fmt(r.pe_forward) },
    { label: "PEG Ratio",      value: fmt(r.peg_ratio) },
    { label: "P/B",            value: fmt(r.price_to_book) },
    { label: "EV/EBITDA",      value: fmt(r.ev_to_ebitda) },
    { label: "ROE",            value: r.roe != null ? fmtPct(r.roe * 100) : "—" },
    { label: "ROA",            value: r.roa != null ? fmtPct(r.roa * 100) : "—" },
    { label: "ROIC",           value: r.roic != null ? fmtPct(r.roic * 100) : "—" },
    { label: "D/E Ratio",      value: fmt(r.debt_to_equity) },
    // dividend_yield comes from the backend already scaled as a percent
    // (e.g. 0.35 means 0.35%), unlike roe/roa/roic which are fractions —
    // see yfinance_provider.get_ratios(). Do not multiply by 100 here.
    { label: "Div Yield",      value: r.dividend_yield != null ? fmtPct(r.dividend_yield) : "—" },
    { label: "Current Ratio",  value: fmt(r.current_ratio) },
    { label: "Beta",           value: fmt(r.beta) },
  ];

  return (
    <div className="glass-card p-5">
      <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
        <BarChart2 size={14} className="text-blue-400" /> Key Ratios
      </h3>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {metrics.map((m) => (
          <div key={m.label} className="bg-slate-900/50 rounded-lg p-2.5">
            <p className="text-[10px] text-slate-600 uppercase tracking-wider font-semibold">{m.label}</p>
            <p className="text-sm font-mono font-bold text-slate-200 mt-0.5">{m.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Technicals ─────────────────────────────────────────────────────────────────
function TechnicalsPanel({ ticker }: { ticker: string }) {
  const { data, isLoading } = useTechnicals(ticker);
  const t: any = (data as any)?.technicals ?? {};
  if (isLoading) return <SkeletonCard rows={6} />;

  const rsiColor = (v: number) => v > 70 ? "text-red-400" : v < 30 ? "text-green-400" : "text-amber-400";

  return (
    <div className="space-y-4">
      {/* Trend badge */}
      {t.trend && (
        <div className={`inline-flex items-center gap-2 text-sm font-bold px-3 py-1.5 rounded-lg ${
          (t.trend ?? "").toLowerCase().includes("up") ? "badge-bull" :
          (t.trend ?? "").toLowerCase().includes("down") ? "badge-bear" : "badge-neutral"
        }`}>
          {(t.trend ?? "").toLowerCase().includes("up") ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
          {t.trend}
        </div>
      )}

      {/* Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <div className="glass-card p-3">
          <p className="text-[10px] text-slate-600 uppercase tracking-wider font-semibold">RSI (14)</p>
          <p className={`text-xl font-bold font-mono mt-1 ${t.rsi_14 != null ? rsiColor(t.rsi_14) : "text-slate-400"}`}>
            {fmt(t.rsi_14, 1)}
          </p>
          <p className="text-[10px] text-slate-600 mt-0.5">
            {t.rsi_14 > 70 ? "Overbought" : t.rsi_14 < 30 ? "Oversold" : "Neutral"}
          </p>
        </div>

        <div className="glass-card p-3">
          <p className="text-[10px] text-slate-600 uppercase tracking-wider font-semibold">MACD</p>
          <p className={`text-sm font-bold font-mono mt-1 ${(t.macd?.histogram ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
            {fmt(t.macd?.macd_line)}
          </p>
          <p className="text-[10px] text-slate-600">Signal: {fmt(t.macd?.signal_line)}</p>
        </div>

        <div className="glass-card p-3">
          <p className="text-[10px] text-slate-600 uppercase tracking-wider font-semibold">ATR (14)</p>
          <p className="text-sm font-bold font-mono mt-1 text-slate-200">{fmt(t.atr_14)}</p>
          <p className="text-[10px] text-slate-600">Stoch RSI: {fmt(t.stochastic_rsi_14, 1)}</p>
        </div>
      </div>

      {/* SMAs */}
      <div className="glass-card p-4">
        <p className="text-[10px] text-slate-600 uppercase tracking-wider font-semibold mb-3">Moving Averages</p>
        <div className="space-y-0">
          {[
            { label: "SMA 20",  value: t.sma?.sma_20 },
            { label: "SMA 50",  value: t.sma?.sma_50 },
            { label: "SMA 200", value: t.sma?.sma_200 },
            { label: "EMA 12",  value: t.ema?.ema_12 },
            { label: "EMA 26",  value: t.ema?.ema_26 },
          ].map(({ label, value }) => (
            value != null ? <StatRow key={label} label={label} value={fmt(value)} /> : null
          ))}
        </div>
      </div>

      {/* Bollinger Bands */}
      {t.bollinger_bands && (
        <div className="glass-card p-4">
          <p className="text-[10px] text-slate-600 uppercase tracking-wider font-semibold mb-3">Bollinger Bands</p>
          <div className="space-y-0">
            <StatRow label="Upper" value={<span className="text-red-400">{fmt(t.bollinger_bands.upper)}</span>} />
            <StatRow label="Middle" value={fmt(t.bollinger_bands.middle)} />
            <StatRow label="Lower" value={<span className="text-green-400">{fmt(t.bollinger_bands.lower)}</span>} />
          </div>
        </div>
      )}

      {/* Support / Resistance */}
      {t.support_resistance && (
        <div className="glass-card p-4">
          <p className="text-[10px] text-slate-600 uppercase tracking-wider font-semibold mb-3">Support & Resistance</p>
          <div className="space-y-0">
            <StatRow label="Resistance 20d" value={<span className="text-red-400">{fmt(t.support_resistance.resistance_20d)}</span>} />
            <StatRow label="Support 20d"    value={<span className="text-green-400">{fmt(t.support_resistance.support_20d)}</span>} />
            <StatRow label="Resistance 60d" value={<span className="text-red-400">{fmt(t.support_resistance.resistance_60d)}</span>} />
            <StatRow label="Support 60d"    value={<span className="text-green-400">{fmt(t.support_resistance.support_60d)}</span>} />
          </div>
        </div>
      )}
    </div>
  );
}

// ── Financials ─────────────────────────────────────────────────────────────────
function FinancialsPanel({ ticker }: { ticker: string }) {
  const [type, setType] = useState("income");
  const [period, setPeriod] = useState("annual");
  const { data, isLoading } = useFinancials(ticker, type, period);
  const periods: any[] = (data as any)?.periods ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {["income", "balance", "cashflow"].map((t) => (
          <button
            key={t}
            onClick={() => setType(t)}
            className={`text-xs px-3 py-1.5 rounded-lg font-semibold transition-all ${
              type === t ? "bg-blue-600/20 text-blue-400 border border-blue-500/30" : "btn-ghost"
            }`}
          >
            {t === "income" ? "Income" : t === "balance" ? "Balance Sheet" : "Cash Flow"}
          </button>
        ))}
        <div className="ml-auto flex gap-1">
          {["annual", "quarterly"].map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`text-xs px-2.5 py-1.5 rounded-lg font-semibold transition-all ${
                period === p ? "bg-blue-600/20 text-blue-400 border border-blue-500/30" : "btn-ghost"
              }`}
            >
              {p === "annual" ? "Annual" : "Quarterly"}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? <SkeletonTable rows={8} /> : (
        <div className="glass-card overflow-x-auto">
          {periods.length === 0 ? (
            <EmptyState title="No financial data" description="Financial statements not yet available" />
          ) : (
            <table className="data-table min-w-full">
              <thead>
                <tr>
                  <th>Metric</th>
                  {periods.map((p: any) => <th key={p.period_end} className="text-right">{p.period_end?.split("-").slice(0,2).join("-")}</th>)}
                </tr>
              </thead>
              <tbody>
                {Object.keys(periods[0]?.line_items ?? {}).map((metric) => (
                  <tr key={metric}>
                    <td className="text-slate-400 text-xs capitalize">{metric.replace(/_/g, " ")}</td>
                    {periods.map((p: any) => (
                      <td key={p.period_end} className="text-right font-mono text-xs">
                        {fmtLarge(p.line_items[metric])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

// ── Earnings ──────────────────────────────────────────────────────────────────
function EarningsPanel({ ticker }: { ticker: string }) {
  const { data, isLoading } = useEarnings(ticker);
  const { data: quoteData } = useQuote(ticker); // dedupes against QuoteHero's request — no extra network call
  const e: any = (data as any)?.earnings ?? {};
  const history: any[] = e.history ?? [];
  const sym = (quoteData as any)?.quote?.currency === "INR" ? "₹" : "$";

  if (isLoading) return <SkeletonCard rows={5} />;

  return (
    <div className="space-y-4">
      {e.next_earnings_date && (
        <div className="glass-card p-4 flex items-center gap-4 border border-amber-500/20">
          <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center">
            <Calendar size={18} className="text-amber-400" />
          </div>
          <div>
            <p className="text-xs text-slate-500">Next Earnings</p>
            <p className="text-sm font-bold text-amber-400">{fmtDate(e.next_earnings_date)}</p>
          </div>
          {e.eps_estimate_avg != null && (
            <div className="ml-auto text-right">
              <p className="text-xs text-slate-500">EPS Estimate</p>
              <p className="text-sm font-bold font-mono text-slate-200">{sym}{fmt(e.eps_estimate_avg)}</p>
              <p className="text-[10px] text-slate-600">Range: {sym}{fmt(e.eps_estimate_low)} – {sym}{fmt(e.eps_estimate_high)}</p>
            </div>
          )}
        </div>
      )}

      {history.length > 0 && (
        <>
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">EPS History</h3>
          <div className="glass-card overflow-x-auto">
            <table className="data-table min-w-full">
              <thead>
                <tr>
                  <th>Date</th>
                  <th className="text-right">Estimate</th>
                  <th className="text-right">Reported</th>
                  <th className="text-right">Surprise</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h: any) => (
                  <tr key={h.earnings_date}>
                    <td>{fmtDate(h.earnings_date)}</td>
                    <td className="text-right font-mono">{fmt(h.eps_estimate)}</td>
                    <td className="text-right font-mono">{fmt(h.eps_reported)}</td>
                    <td className={`text-right font-mono font-semibold ${changeClass(h.surprise_pct)}`}>
                      {fmtPct(h.surprise_pct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

// ── News ──────────────────────────────────────────────────────────────────────
function NewsPanel({ ticker }: { ticker: string }) {
  const { data, isLoading } = useNews(ticker);
  const articles: any[] = (data as any)?.news?.articles ?? [];
  if (isLoading) return <div className="space-y-3">{Array.from({length:4}).map((_,i)=><SkeletonCard key={i} rows={2}/>)}</div>;

  return (
    <div className="space-y-3">
      {articles.length === 0 ? (
        <EmptyState title="No news found" description="No recent news articles available" />
      ) : articles.map((a: any, i: number) => (
        <a
          key={i}
          href={a.url}
          target="_blank"
          rel="noopener noreferrer"
          className="glass-card glass-card-hover p-4 block"
        >
          <div className="flex items-start gap-3">
            {a.thumbnail_url && (
              <img src={a.thumbnail_url} alt="" className="w-16 h-12 object-cover rounded-lg flex-shrink-0" />
            )}
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-slate-200 line-clamp-2 mb-1">{a.title}</p>
              <p className="text-[11px] text-slate-500 line-clamp-2">{a.summary}</p>
              <div className="flex items-center gap-2 mt-2">
                <SentimentBadge sentiment={a.sentiment} />
                {a.impact_score != null && (
                  <span className="text-[10px] text-slate-600">Impact: {fmt(a.impact_score, 1)}</span>
                )}
                <span className="text-[10px] text-slate-600 ml-auto">{a.source} · {fmtDate(a.published_at)}</span>
              </div>
            </div>
          </div>
        </a>
      ))}
    </div>
  );
}

// ── Analyst ───────────────────────────────────────────────────────────────────
function AnalystPanel({ ticker }: { ticker: string }) {
  const { data, isLoading } = useAnalyst(ticker);
  const { data: quoteData } = useQuote(ticker); // dedupes against QuoteHero's request
  const a: any = (data as any)?.analyst ?? {};
  const sym = (quoteData as any)?.quote?.currency === "INR" ? "₹" : "$";
  if (isLoading) return <SkeletonCard rows={6} />;

  const consensus = a.recommendation_key?.toLowerCase() ?? "";
  const consensusColor =
    consensus.includes("buy")  ? "text-green-400" :
    consensus.includes("sell") ? "text-red-400"   : "text-amber-400";

  return (
    <div className="space-y-4">
      {/* Consensus */}
      <div className="glass-card p-5 flex flex-wrap gap-6 items-center">
        <div>
          <p className="text-[10px] text-slate-600 uppercase tracking-wider">Consensus</p>
          <p className={`text-2xl font-bold uppercase mt-1 ${consensusColor}`}>
            {a.recommendation_key ?? "—"}
          </p>
          <p className="text-[10px] text-slate-600 mt-0.5">{a.num_analyst_opinions ?? 0} analysts</p>
        </div>
        <div>
          <p className="text-[10px] text-slate-600 uppercase tracking-wider">Price Targets</p>
          <p className="text-xl font-bold font-mono text-slate-200 mt-1">{sym}{fmt(a.target_mean)}</p>
          <p className="text-[10px] text-slate-600">{sym}{fmt(a.target_low)} – {sym}{fmt(a.target_high)}</p>
        </div>
        <div>
          <p className="text-[10px] text-slate-600 uppercase tracking-wider">Institutions</p>
          <p className="text-xl font-bold font-mono text-slate-200 mt-1">
            {a.held_pct_institutions != null ? fmtPct(a.held_pct_institutions * 100) : "—"}
          </p>
        </div>
      </div>

      {/* Actions table */}
      {a.actions?.length > 0 && (
        <div className="glass-card overflow-x-auto">
          <table className="data-table min-w-full">
            <thead><tr><th>Date</th><th>Firm</th><th>Action</th><th>From</th><th>To</th><th className="text-right">Target</th></tr></thead>
            <tbody>
              {a.actions.slice(0, 10).map((act: any, i: number) => (
                <tr key={i}>
                  <td>{fmtDate(act.grade_date)}</td>
                  <td className="font-medium">{act.firm}</td>
                  <td>
                    <Badge
                      label={act.action}
                      variant={act.action?.toLowerCase().includes("upgrade") ? "bull" : act.action?.toLowerCase().includes("downgrade") ? "bear" : "default"}
                    />
                  </td>
                  <td className="text-slate-500">{act.from_grade || "—"}</td>
                  <td>{act.to_grade}</td>
                  <td className="text-right font-mono">{act.current_price_target ? `${sym}${fmt(act.current_price_target)}` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Executive Summary ──────────────────────────────────────────────────────────
function ExecutiveSummaryPanel({ ticker }: { ticker: string }) {
  const { data, isLoading, mutate } = useExecutiveSummary(ticker);
  const s: any = (data as any)?.executive_summary ?? {};
  if (isLoading) return <SkeletonCard rows={8} />;

  const sentColor = (data as any)?.executive_summary?.overall_sentiment;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="glass-card p-5 border border-blue-500/15">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Brain size={16} className="text-purple-400" />
            <span className="text-sm font-semibold text-slate-200">AI Executive Summary</span>
          </div>
          <div className="flex items-center gap-3">
            {sentColor && <SentimentBadge sentiment={sentColor} />}
            {s.confidence_score != null && (
              // confidence_score is already 0-100 (see company_executive_summary
              // prompt spec) — not a fraction, so no *100 and no fmtPct's +/- sign
              <span className="text-[10px] text-slate-600">Confidence: {s.confidence_score.toFixed(0)}%</span>
            )}
            <button onClick={() => mutate()} className="btn-ghost text-xs py-1">
              <RefreshCw size={12} />
            </button>
          </div>
        </div>

        {s.business_overview && (
          <p className="text-sm text-slate-300 leading-relaxed">{s.business_overview}</p>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Positive Factors */}
        {s.positive_factors?.length > 0 && (
          <div className="glass-card p-4">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-green-500 mb-3 flex items-center gap-1.5">
              <CheckCircle size={11} /> Positive Factors
            </p>
            <ul className="space-y-2">
              {s.positive_factors.map((f: string, i: number) => (
                <li key={i} className="text-xs text-slate-300 flex gap-2">
                  <span className="text-green-500 flex-shrink-0 mt-0.5">↑</span>{f}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Risks */}
        {s.risks?.length > 0 && (
          <div className="glass-card p-4">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-red-400 mb-3 flex items-center gap-1.5">
              <AlertTriangle size={11} /> Risks
            </p>
            <ul className="space-y-2">
              {s.risks.map((r: string, i: number) => (
                <li key={i} className="text-xs text-slate-300 flex gap-2">
                  <span className="text-red-400 flex-shrink-0 mt-0.5">↓</span>{r}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Opportunities */}
        {s.opportunities?.length > 0 && (
          <div className="glass-card p-4">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-amber-400 mb-3 flex items-center gap-1.5">
              <Target size={11} /> Opportunities
            </p>
            <ul className="space-y-2">
              {s.opportunities.map((o: string, i: number) => (
                <li key={i} className="text-xs text-slate-300 flex gap-2">
                  <span className="text-amber-400 flex-shrink-0 mt-0.5">→</span>{o}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Investment Thesis */}
        {s.investment_thesis && (
          <div className="glass-card p-4">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-purple-400 mb-3">Investment Thesis</p>
            <p className="text-xs text-slate-300 leading-relaxed">{s.investment_thesis}</p>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {s.short_term_outlook && (
          <div className="glass-card p-4">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-2">Short-term</p>
            <p className="text-xs text-slate-300">{s.short_term_outlook}</p>
          </div>
        )}
        {s.long_term_outlook && (
          <div className="glass-card p-4">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-2">Long-term</p>
            <p className="text-xs text-slate-300">{s.long_term_outlook}</p>
          </div>
        )}
        {s.technical_outlook && (
          <div className="glass-card p-4">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-2">Technical</p>
            <p className="text-xs text-slate-300">{s.technical_outlook}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Company Chat ───────────────────────────────────────────────────────────────
function CompanyChat({ ticker }: { ticker: string }) {
  const [messages, setMessages] = useState<{ role: "user" | "ai"; content: string; citations?: any[] }[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function send() {
    if (!input.trim() || loading) return;
    const question = input.trim();
    setInput("");
    setMessages((m) => [...m, { role: "user", content: question }]);
    setLoading(true);
    try {
      const res: any = await companyApi.chat(ticker, { question, top_k: 8 });
      setMessages((m) => [...m, { role: "ai", content: res.answer, citations: res.citations }]);
    } catch (e: any) {
      setMessages((m) => [...m, { role: "ai", content: `Error: ${e.message}` }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="glass-card flex flex-col" style={{ height: 500 }}>
      <div className="flex items-center gap-2 p-4 border-b border-white/5">
        <MessageSquare size={14} className="text-blue-400" />
        <span className="text-sm font-semibold text-slate-200">Ask about {ticker}</span>
        <span className="text-[10px] text-slate-600 ml-auto">Powered by RAG + Ollama</span>
      </div>

      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
        {messages.length === 0 && (
          <div className="flex-1 flex items-center justify-center">
            <EmptyState
              title="Ask anything about this stock"
              description="Questions are answered using AI-analyzed YouTube video transcripts"
            />
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "chat-bubble-user" : "chat-bubble-ai"}>
            <p className="text-sm leading-relaxed">{m.content}</p>
            {(m.citations?.length ?? 0) > 0 && (
              <div className="mt-2 pt-2 border-t border-white/10 space-y-1">
                {m.citations?.map((c: any, ci: number) => (
                  <a
                    key={ci}
                    href={`https://youtube.com/watch?v=${c.video_id}&t=${Math.floor(c.start_seconds ?? 0)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block text-[10px] text-blue-400 hover:text-blue-300 truncate"
                  >
                    [{ci + 1}] {c.video_title} — {c.channel_name}
                  </a>
                ))}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="chat-bubble-ai">
            <div className="flex gap-1 items-center">
              <div className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce" style={{ animationDelay: "0ms" }} />
              <div className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce" style={{ animationDelay: "150ms" }} />
              <div className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce" style={{ animationDelay: "300ms" }} />
            </div>
          </div>
        )}
      </div>

      <div className="p-3 border-t border-white/5 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
          placeholder={`Ask about ${ticker}…`}
          className="input-field text-sm"
          id="company-chat-input"
          disabled={loading}
        />
        <button onClick={send} disabled={loading || !input.trim()} className="btn-primary flex-shrink-0 disabled:opacity-50">
          Send
        </button>
      </div>
    </div>
  );
}

// ── Video Intelligence ─────────────────────────────────────────────────────────
function VideoIntelligencePanel({ ticker }: { ticker: string }) {
  const [queryInput, setQueryInput] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const { data, isLoading } = useIntelligence(ticker, activeQuery || undefined);
  const bundles: any[] = (data as any)?.videos ?? [];

  function submitSearch(e: React.FormEvent) {
    e.preventDefault();
    setActiveQuery(queryInput.trim());
  }

  return (
    <div className="space-y-4">
      <form onSubmit={submitSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Brain size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-purple-400 pointer-events-none" />
          <input
            type="text"
            value={queryInput}
            onChange={(e) => setQueryInput(e.target.value)}
            placeholder={`Semantic search within ${ticker} video intelligence…`}
            className="input-field pl-9 text-xs w-full"
            id="video-intel-query"
          />
        </div>
        <button type="submit" className="btn-primary text-xs px-4" id="video-intel-search-btn">
          Search
        </button>
        {activeQuery && (
          <button
            type="button"
            className="btn-ghost text-xs px-3"
            onClick={() => { setQueryInput(""); setActiveQuery(""); }}
          >
            Clear
          </button>
        )}
      </form>

      {isLoading ? (
        <div className="space-y-3">{Array.from({length:3}).map((_,i)=><SkeletonCard key={i} rows={3}/>)}</div>
      ) : bundles.length === 0 ? (
        <EmptyState
          title="No video intelligence"
          description={activeQuery ? "No videos matched that query" : "No analyzed videos mention this ticker yet"}
        />
      ) : bundles.map((b: any) => (
        <div key={b.video.id} className="glass-card p-4">
          <div className="flex items-start gap-3 mb-3">
            <div className="flex-1 min-w-0">
              <a
                href={b.video.video_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-semibold text-slate-200 hover:text-blue-400 transition-colors line-clamp-1"
              >
                {b.video.title}
              </a>
              <p className="text-[10px] text-slate-600 mt-0.5">{b.video.channel_name} · {fmtDate(b.video.published_at)}</p>
            </div>
            {b.sentiment && <SentimentBadge sentiment={b.sentiment.overall_sentiment} />}
          </div>

          {b.summary?.executive_bullets?.length > 0 && (
            <ul className="space-y-1">
              {b.summary.executive_bullets.slice(0, 3).map((bullet: string, i: number) => (
                <li key={i} className="text-[11px] text-slate-400 flex gap-2">
                  <span className="text-blue-500 flex-shrink-0">•</span>{bullet}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Main Company Page ──────────────────────────────────────────────────────────
export default function CompanyPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = use(params);
  const upper = ticker.toUpperCase();

  const TABS = [
    { id: "overview",     label: "Overview" },
    { id: "financials",   label: "Financials" },
    { id: "earnings",     label: "Earnings" },
    { id: "technicals",   label: "Technicals" },
    { id: "news",         label: "News" },
    { id: "analyst",      label: "Analyst" },
    { id: "ai-summary",   label: "AI Summary" },
    { id: "videos",       label: "Video Intel" },
    { id: "chat",         label: "Chat" },
  ];

  return (
    <div className="p-6 space-y-5 max-w-[1400px] mx-auto fade-in">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-1">
          <span className="text-3xl font-bold font-mono gradient-text">{upper}</span>
          <Badge label="Company Intelligence" variant="blue" size="md" />
        </div>
      </div>

      {/* Track this stock? */}
      <TrackTickerPrompt ticker={upper} />

      {/* Quote Hero */}
      <QuoteHero ticker={upper} />

      {/* Price Chart */}
      <PriceChart ticker={upper} />

      {/* Tabbed Content */}
      <div className="glass-card p-0 overflow-hidden">
        <Tabs tabs={TABS} defaultTab="overview">
          {(active) => (
            <div className="px-5 pb-5">
              {active === "overview"   && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                  <ProfilePanel ticker={upper} />
                  <RatiosPanel ticker={upper} />
                </div>
              )}
              {active === "financials"  && <FinancialsPanel ticker={upper} />}
              {active === "earnings"    && <EarningsPanel ticker={upper} />}
              {active === "technicals"  && <TechnicalsPanel ticker={upper} />}
              {active === "news"        && <NewsPanel ticker={upper} />}
              {active === "analyst"     && <AnalystPanel ticker={upper} />}
              {active === "ai-summary"  && <ExecutiveSummaryPanel ticker={upper} />}
              {active === "videos"      && <VideoIntelligencePanel ticker={upper} />}
              {active === "chat"        && <CompanyChat ticker={upper} />}
            </div>
          )}
        </Tabs>
      </div>
    </div>
  );
}
