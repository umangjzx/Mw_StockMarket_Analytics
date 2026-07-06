"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  BarChart2, TrendingUp, Activity, Layers, PieChart as PieIcon,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  Cell, LineChart, Line, CartesianGrid, Legend,
  PieChart, Pie,
} from "recharts";
import {
  useTrendingStocks, useSectorHeatmap, useTrendingSectors, useSentimentTicker,
} from "@/lib/hooks";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState, EmptyState } from "@/components/ui/ErrorState";

const SENT_COLORS: Record<string, string> = {
  bullish: "#4ade80",
  bearish: "#fb7185",
  neutral: "#fbbf24",
  mixed:   "#818cf8",
};

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="tooltip">
      <p className="text-[11px] mb-1.5 font-semibold" style={{ color: "var(--text-muted)" }}>{label}</p>
      {payload.map((p: any, i: number) => (
        <p key={i} style={{ color: p.color ?? p.fill }} className="text-xs font-mono">
          {p.name}: <span className="font-semibold">{typeof p.value === "number" ? p.value.toFixed(1) : p.value}</span>
        </p>
      ))}
    </div>
  );
}

// ── Trending Stocks Full Chart ─────────────────────────────────────────────
function TrendingFull({ window }: { window: string }) {
  const { data, isLoading, error } = useTrendingStocks(window);
  const router = useRouter();
  const items: any[] = (data as any)?.tickers ?? [];

  if (isLoading) return <Skeleton className="h-72" />;
  if (error) return <ErrorState compact message="Could not load data" />;
  if (!items.length) return <EmptyState title="No data yet" />;

  return (
    <ResponsiveContainer width="100%" height={290}>
      <BarChart data={items.slice(0, 15)} layout="vertical" margin={{ left: 12, right: 24, top: 4, bottom: 4 }}>
        <defs>
          <linearGradient id="trendGradA" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#1d4ed8" />
            <stop offset="100%" stopColor="#60a5fa" />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" horizontal={false} />
        <XAxis type="number" tick={{ fill: "#3d5070", fontSize: 10 }} tickLine={false} axisLine={false} />
        <YAxis
          type="category" dataKey="ticker"
          tick={{ fill: "#8899b4", fontSize: 11, fontFamily: "JetBrains Mono", fontWeight: 600, cursor: "pointer" }}
          width={62} tickLine={false} axisLine={false}
          onClick={(d) => router.push(`/company/${d.value}`)}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(59,130,246,0.05)" }} />
        <Bar dataKey="mentions" name="Mentions" radius={[0, 5, 5, 0]} maxBarSize={18} fill="url(#trendGradA)" fillOpacity={0.9} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Sector Heatmap Full ────────────────────────────────────────────────────
function SectorHeatmapFull({ window }: { window: string }) {
  const { data, isLoading, error } = useSectorHeatmap(window);
  const heatmap: Record<string, Record<string, number>> = (data as any)?.heatmap ?? {};
  const sectors: any[] = Object.entries(heatmap).map(([sector, counts]) => {
    const total = Object.values(counts).reduce((a, b) => a + b, 0);
    const dominant = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "neutral";
    return { sector, mention_count: total, sentiment: dominant };
  });

  if (isLoading) return (
    <div className="grid grid-cols-4 gap-2">
      {Array.from({ length: 11 }).map((_, i) => <Skeleton key={i} className="h-20" />)}
    </div>
  );
  if (error) return <ErrorState compact message="Could not load sectors" />;
  if (!sectors.length) return <EmptyState title="No sector data" />;

  const sentColor = (s: string) => {
    const sl = (s ?? "").toLowerCase();
    if (sl === "bullish") return { bg: "rgba(34,197,94,0.13)", border: "rgba(34,197,94,0.28)", text: "#4ade80" };
    if (sl === "bearish") return { bg: "rgba(244,63,94,0.13)", border: "rgba(244,63,94,0.28)", text: "#fb7185" };
    return { bg: "rgba(245,158,11,0.1)", border: "rgba(245,158,11,0.25)", text: "#fbbf24" };
  };

  return (
    <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-2.5 stagger-children">
      {sectors.map((s: any) => {
        const { bg, border, text } = sentColor(s.sentiment);
        return (
          <div key={s.sector} className="heatmap-cell text-center p-3"
            style={{ background: bg, border: `1px solid ${border}` }}>
            <p className="text-[10px] font-bold truncate leading-tight" style={{ color: text }}>{s.sector}</p>
            <p className="text-xl font-black font-mono mt-1 num-display" style={{ color: "var(--text-primary)" }}>{s.mention_count}</p>
            <p className="text-[9px] mt-0.5 capitalize" style={{ color: text }}>{s.sentiment}</p>
          </div>
        );
      })}
    </div>
  );
}

// ── Sentiment Donut ────────────────────────────────────────────────────────
function SentimentDonut({ window }: { window: string }) {
  const { data, isLoading, error } = useSectorHeatmap(window);
  const heatmap: Record<string, Record<string, number>> = (data as any)?.heatmap ?? {};

  // Aggregate all sectors into total counts per sentiment
  const totals: Record<string, number> = { bullish: 0, bearish: 0, neutral: 0, mixed: 0 };
  Object.values(heatmap).forEach((counts) => {
    Object.entries(counts).forEach(([k, v]) => {
      if (k in totals) totals[k] += v;
    });
  });
  const grand = Object.values(totals).reduce((a, b) => a + b, 0) || 1;
  const pieData = Object.entries(totals)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value, pct: ((value / grand) * 100).toFixed(1) }));

  const dominant = pieData.sort((a, b) => b.value - a.value)[0]?.name ?? "—";

  if (isLoading) return <Skeleton className="h-52" />;
  if (error) return <ErrorState compact message="Could not load" />;
  if (!pieData.length) return <EmptyState title="No sentiment data" />;

  return (
    <div className="flex flex-col items-center gap-4">
      {/* Donut */}
      <div className="relative h-[200px] flex items-center justify-center -mt-2">
        <ResponsiveContainer width={200} height={200} className="mx-auto">
          <PieChart>
            <Pie data={pieData} cx="50%" cy="50%"
              innerRadius={52} outerRadius={75}
              dataKey="value" strokeWidth={0} paddingAngle={2}>
              {pieData.map((entry, i) => (
                <Cell key={i} fill={SENT_COLORS[entry.name] ?? "#64748b"} fillOpacity={0.9} />
              ))}
            </Pie>
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload;
                return (
                  <div className="tooltip">
                    <p className="font-semibold text-xs capitalize" style={{ color: SENT_COLORS[d.name] }}>{d.name}</p>
                    <p className="text-xs font-mono" style={{ color: "var(--text-secondary)" }}>{d.value} · {d.pct}%</p>
                  </div>
                );
              }}
            />
          </PieChart>
        </ResponsiveContainer>
        {/* Center label */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <p className="text-[10px] uppercase tracking-widest" style={{ color: "var(--text-muted)" }}>Dominant</p>
          <p className="text-sm font-bold capitalize" style={{ color: SENT_COLORS[dominant] ?? "var(--text-primary)" }}>
            {dominant}
          </p>
        </div>
      </div>

      {/* Legend rows */}
      <div className="w-full space-y-2">
        {Object.entries(totals).filter(([, v]) => v > 0).map(([name, value]) => (
          <div key={name} className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: SENT_COLORS[name] }} />
            <span className="text-xs capitalize flex-1" style={{ color: "var(--text-secondary)" }}>{name}</span>
            <span className="text-xs font-mono font-semibold" style={{ color: SENT_COLORS[name] }}>{value}</span>
            <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
              {((value / grand) * 100).toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Stacked Sector Sentiment Bars ──────────────────────────────────────────
function SectorSentimentBars({ window }: { window: string }) {
  const { data, isLoading, error } = useSectorHeatmap(window);
  const heatmap: Record<string, Record<string, number>> = (data as any)?.heatmap ?? {};

  const chartData = Object.entries(heatmap)
    .map(([sector, counts]) => ({
      sector: sector.length > 10 ? sector.slice(0, 10) + "…" : sector,
      bullish: counts.bullish ?? 0,
      bearish: counts.bearish ?? 0,
      neutral: counts.neutral ?? 0,
      mixed:   counts.mixed   ?? 0,
    }))
    .sort((a, b) => (b.bullish + b.bearish + b.neutral + b.mixed) - (a.bullish + a.bearish + a.neutral + a.mixed));

  if (isLoading) return <Skeleton className="h-52" />;
  if (error) return <ErrorState compact message="Could not load" />;
  if (!chartData.length) return <EmptyState title="No sector data" />;

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={chartData} margin={{ left: 0, right: 8, top: 4, bottom: 20 }}>
        <XAxis
          dataKey="sector"
          tick={{ fill: "#3d5070", fontSize: 9 }}
          tickLine={false} axisLine={false}
          angle={-30} textAnchor="end" interval={0}
        />
        <YAxis hide />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
        <Legend
          wrapperStyle={{ fontSize: 10, color: "#8899b4", paddingTop: 8 }}
          formatter={(value) => <span style={{ color: SENT_COLORS[value] ?? "#8899b4", textTransform: "capitalize" }}>{value}</span>}
        />
        <Bar dataKey="bullish" name="bullish" stackId="a" fill="#4ade80" fillOpacity={0.85} maxBarSize={32} />
        <Bar dataKey="bearish" name="bearish" stackId="a" fill="#fb7185" fillOpacity={0.85} maxBarSize={32} />
        <Bar dataKey="neutral" name="neutral" stackId="a" fill="#fbbf24" fillOpacity={0.85} maxBarSize={32} />
        <Bar dataKey="mixed"   name="mixed"   stackId="a" fill="#818cf8" fillOpacity={0.85} maxBarSize={32} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Sentiment Timeseries ───────────────────────────────────────────────────
function SentimentTimeseries() {
  const [ticker, setTicker] = useState("RELIANCE");
  const [input, setInput] = useState("RELIANCE");
  const { data, isLoading, error } = useSentimentTicker(ticker);
  const points: any[] = (data as any)?.series ?? [];

  const chartData = points.map((p: any) => ({
    date: (p.date ?? p.period ?? "").split("T")[0],
    bullish: p.bullish_pct ?? p.bullish,
    bearish: p.bearish_pct ?? p.bearish,
    neutral: p.neutral_pct ?? p.neutral,
  }));

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <input
          type="text" value={input}
          onChange={(e) => setInput(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === "Enter" && setTicker(input)}
          placeholder="e.g. RELIANCE"
          className="input-field text-sm w-36"
          id="sentiment-ticker-input"
        />
        <button onClick={() => setTicker(input)} className="btn-ghost text-xs px-3">Load</button>
      </div>
      {isLoading && <Skeleton className="h-52" />}
      {error && <ErrorState compact message="No sentiment data" />}
      {!isLoading && !error && chartData.length === 0 && <EmptyState title="No sentiment data for this ticker" />}
      {!isLoading && !error && chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={chartData} margin={{ left: 0, right: 8 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.04)" />
            <XAxis dataKey="date" tick={{ fill: "#3d5070", fontSize: 10 }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fill: "#3d5070", fontSize: 10 }} tickLine={false} axisLine={false} width={28} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ fontSize: 11, color: "#8899b4" }} />
            <Line type="monotone" dataKey="bullish" stroke="#4ade80" strokeWidth={2} dot={false} name="Bullish %" />
            <Line type="monotone" dataKey="bearish" stroke="#fb7185" strokeWidth={2} dot={false} name="Bearish %" />
            <Line type="monotone" dataKey="neutral" stroke="#fbbf24" strokeWidth={2} dot={false} name="Neutral %" />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

// ── Sector Volume Bars ─────────────────────────────────────────────────────
function SectorBars({ window }: { window: string }) {
  const { data, isLoading } = useTrendingSectors(window);
  const sectors: any[] = (data as any)?.sectors ?? [];
  if (isLoading) return <Skeleton className="h-40" />;
  if (!sectors.length) return <EmptyState title={`No sector data in the last ${window}`} />;
  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={sectors.slice(0, 10)} margin={{ left: 0, right: 8 }}>
        <defs>
          <linearGradient id="sectorGradB" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor="#7c3aed" />
            <stop offset="100%" stopColor="#a855f7" />
          </linearGradient>
        </defs>
        <XAxis dataKey="sector" tick={{ fill: "#3d5070", fontSize: 9 }} tickLine={false} axisLine={false} />
        <YAxis hide />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(168,85,247,0.05)" }} />
        <Bar dataKey="mentions" name="Mentions" radius={[5, 5, 0, 0]} maxBarSize={36} fill="url(#sectorGradB)" fillOpacity={0.85} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────
export default function AnalyticsPage() {
  const [window, setWindow] = useState("7d");

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto fade-in">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black tracking-tight" style={{ letterSpacing: "-0.02em" }}>
            Analytics <span className="gradient-text-gold">Overview</span>
          </h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-muted)" }}>
            Market trends, sector heatmaps, and sentiment signals
          </p>
        </div>
        <div className="window-pill-group">
          {["24h", "7d", "30d"].map((w) => (
            <button key={w} onClick={() => setWindow(w)} className={`window-pill ${window === w ? "active" : ""}`}>{w}</button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">

        {/* Trending Stocks */}
        <div className="glass-card card-accent-blue p-5">
          <div className="section-header">
            <div className="section-title">
              <div className="icon-container icon-blue"><TrendingUp size={14} /></div>
              Trending Stocks
            </div>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full"
              style={{ background: "rgba(59,130,246,0.1)", color: "var(--accent-light)", border: "1px solid rgba(59,130,246,0.2)" }}>
              {window}
            </span>
          </div>
          <TrendingFull window={window} />
          <p className="text-[10px] mt-2" style={{ color: "var(--text-dim)" }}>Click ticker label to open Company Intelligence</p>
        </div>

        {/* Sentiment Timeseries */}
        <div className="glass-card card-accent-green p-5">
          <div className="section-header">
            <div className="section-title">
              <div className="icon-container icon-green"><Activity size={14} /></div>
              Sentiment Over Time
            </div>
          </div>
          <SentimentTimeseries />
        </div>

        {/* Sector Heatmap — full width */}
        <div className="glass-card card-accent-purple p-5 xl:col-span-2">
          <div className="section-header">
            <div className="section-title">
              <div className="icon-container icon-purple"><BarChart2 size={14} /></div>
              Sector Sentiment Heatmap
            </div>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full"
              style={{ background: "rgba(168,85,247,0.1)", color: "var(--purple-light)", border: "1px solid rgba(168,85,247,0.2)" }}>
              {window}
            </span>
          </div>
          <SectorHeatmapFull window={window} />
        </div>

        {/* Sentiment Distribution Donut — NEW */}
        <div className="glass-card card-accent-green p-5">
          <div className="section-header">
            <div className="section-title">
              <div className="icon-container icon-green"><PieIcon size={14} /></div>
              Sentiment Distribution
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full"
              style={{ background: "rgba(34,197,94,0.1)", color: "var(--green)", border: "1px solid rgba(34,197,94,0.2)" }}>
              {window}
            </span>
          </div>
          <SentimentDonut window={window} />
        </div>

        {/* Stacked Sector Sentiment — NEW, full width */}
        <div className="glass-card card-accent-purple p-5 xl:col-span-2">
          <div className="section-header">
            <div className="section-title">
              <div className="icon-container icon-purple"><BarChart2 size={14} /></div>
              Sector Sentiment Breakdown
            </div>
          </div>
          <SectorSentimentBars window={window} />
        </div>

        {/* Sector Volume */}
        <div className="glass-card card-accent-amber p-5">
          <div className="section-header">
            <div className="section-title">
              <div className="icon-container icon-amber"><Layers size={14} /></div>
              Sector Mention Volume
            </div>
            <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full"
              style={{ background: "rgba(245,158,11,0.1)", color: "var(--amber-light)", border: "1px solid rgba(245,158,11,0.2)" }}>
              {window}
            </span>
          </div>
          <SectorBars window={window} />
        </div>

      </div>
    </div>
  );
}
