"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  TrendingUp, Play, Zap, Clock, ArrowUpRight,
  BarChart3, PlayCircle, Loader2, Database, Activity, Cpu,
  FileText, ChevronDown, ChevronUp,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip,
} from "recharts";
import { useTrendingStocks, useSectorHeatmap, useVideos, usePipelineStatus, useLatestReport } from "@/lib/hooks";
import { videoApi } from "@/lib/api";
import { fmtDateTime, changeClass } from "@/lib/utils";
import { SentimentBadge, PipelineBadge } from "@/components/ui/Badge";
import { Skeleton, SkeletonCard } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/ErrorState";

// ── Custom Recharts Tooltip ───────────────────────────────────────────────────
function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="tooltip">
      <p className="font-bold text-xs font-mono" style={{ color: "var(--accent-light)" }}>{d.ticker}</p>
      <p className="text-xs mt-0.5" style={{ color: "var(--text-secondary)" }}>{d.mentions ?? d.mention_count ?? 0} mentions</p>
    </div>
  );
}

// ── Daily Report Card ─────────────────────────────────────────────────────────
function DailyReportCard() {
  const { data, isLoading } = useLatestReport();
  const [open, setOpen] = useState(false);
  const report: any = data ?? {};

  const stockChips = (arr: any) => {
    const list: string[] = Array.isArray(arr) ? arr : (arr?.tickers ?? arr?.stocks ?? []);
    return list.slice(0, 6).map((t: any) => (
      <span
        key={typeof t === "string" ? t : t.ticker}
        className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-mono font-bold"
        style={{ background: "rgba(20,184,166,0.12)", color: "#2dd4bf", border: "1px solid rgba(20,184,166,0.25)" }}
      >
        {typeof t === "string" ? t : (t.ticker ?? t.symbol ?? t)}
      </span>
    ));
  };

  return (
    <div className="glass-card card-accent-teal p-5">
      <div className="flex items-center justify-between">
        <div className="section-title">
          <div className="icon-container icon-teal">
            <FileText size={14} />
          </div>
          <span>AI Daily Market Briefing</span>
          {report.report_date && (
            <span
              className="text-[10px] font-mono px-2 py-0.5 rounded-full ml-1"
              style={{ background: "rgba(20,184,166,0.1)", color: "var(--teal)", border: "1px solid rgba(20,184,166,0.2)" }}
            >
              {report.report_date}
            </span>
          )}
        </div>
        <button onClick={() => setOpen((o) => !o)} className="btn-ghost py-1 px-2 text-xs">
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          {open ? "Collapse" : "View Report"}
        </button>
      </div>

      {isLoading && <Skeleton className="h-6 w-64 mt-3" />}

      {!isLoading && !report.market_summary && (
        <p className="text-xs mt-3" style={{ color: "var(--text-muted)" }}>
          Daily report not yet generated.
        </p>
      )}

      {!isLoading && report.market_summary && !open && (
        <p className="text-xs mt-3 line-clamp-2 leading-relaxed" style={{ color: "var(--text-secondary)" }}>
          {report.market_summary}
        </p>
      )}

      {open && !isLoading && (
        <div className="mt-4 space-y-4 fade-in">
          {report.market_summary && (
            <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
              {report.market_summary}
            </p>
          )}
          {report.analyst_consensus && (
            <div
              className="p-3 rounded-xl"
              style={{ background: "rgba(20,184,166,0.06)", border: "1px solid rgba(20,184,166,0.15)" }}
            >
              <p className="text-[10px] font-bold uppercase tracking-widest mb-1" style={{ color: "var(--teal)" }}>
                Analyst Consensus
              </p>
              <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                {report.analyst_consensus}
              </p>
            </div>
          )}
          {report.interesting_insights && (
            <div
              className="p-3 rounded-xl"
              style={{ background: "rgba(168,85,247,0.06)", border: "1px solid rgba(168,85,247,0.15)" }}
            >
              <p className="text-[10px] font-bold uppercase tracking-widest mb-1" style={{ color: "var(--purple)" }}>
                Interesting Insights
              </p>
              <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                {report.interesting_insights}
              </p>
            </div>
          )}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 min-h-[140px]">
            {(
              [
                ["Most Mentioned", report.most_mentioned_stocks, "var(--accent-light)"],
                ["Most Bullish", report.most_bullish_stocks, "var(--green)"],
                ["Most Bearish", report.most_bearish_stocks, "var(--red-light)"],
              ] as [string, any, string][]
            ).map(
              ([title, arr, color]) =>
                arr && (
                  <div
                    key={title}
                    className="p-3 rounded-xl"
                    style={{ background: "rgba(0,0,0,0.25)", border: "1px solid var(--border)" }}
                  >
                    <p className="text-[10px] font-bold uppercase tracking-widest mb-2" style={{ color }}>
                      {title}
                    </p>
                    <div className="flex flex-wrap gap-1.5">{stockChips(arr)}</div>
                  </div>
                )
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Process URL Form ──────────────────────────────────────────────────────────
const TERMINAL_STATUSES = new Set(["INDEXED", "FAILED"]);
const POLL_INTERVAL_MS = 4000;
const POLL_MAX_ATTEMPTS = 90; // ~6 minutes

function ProcessUrlForm() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [trackedId, setTrackedId] = useState<string | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<string | null>(null);
  const attemptsRef = useRef(0);

  useEffect(() => {
    if (!trackedId) return;
    attemptsRef.current = 0;

    const interval = setInterval(async () => {
      attemptsRef.current += 1;
      try {
        const data: any = await videoApi.list({ external_video_id: trackedId, page_size: 1 });
        const video = data?.items?.[0];
        if (video?.pipeline_status) {
          setPipelineStatus(video.pipeline_status);
          if (TERMINAL_STATUSES.has(video.pipeline_status)) {
            clearInterval(interval);
          }
        }
      } catch {
        // transient — keep polling until max attempts
      }
      if (attemptsRef.current >= POLL_MAX_ATTEMPTS) {
        clearInterval(interval);
      }
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [trackedId]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    setLoading(true); setResult(null); setPipelineStatus(null); setTrackedId(null);
    try {
      const res: any = await videoApi.processUrl(url.trim());
      setResult("success");
      setUrl("");
      if (res?.external_video_id) {
        setTrackedId(res.external_video_id);
        setPipelineStatus(res.status === "reprocessing" ? "DISCOVERED" : "DISCOVERED");
      }
    } catch (err: any) {
      setResult(`error:${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="glass-card card-accent-red p-4 flex-shrink-0">
      <div className="flex items-center gap-2 mb-3">
        <div className="icon-container icon-red">
          <PlayCircle size={14} />
        </div>
        <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Process YouTube Video</h3>
      </div>
      <div className="flex gap-2">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://youtu.be/..."
          className="input-field text-sm"
          id="process-url-input"
        />
        <button
          type="submit"
          disabled={loading || !url.trim()}
          className="btn-primary flex-shrink-0 disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none"
          id="process-url-btn"
        >
          {loading ? <Loader2 size={13} className="animate-spin" /> : <Zap size={13} />}
          {loading ? "Queuing…" : "Process"}
        </button>
      </div>
      {result === "success" && trackedId && (
        <div className="mt-3 flex items-center gap-2">
          {pipelineStatus && !TERMINAL_STATUSES.has(pipelineStatus) && (
            <Loader2 size={11} className="animate-spin" style={{ color: "var(--accent-light)" }} />
          )}
          <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
            {pipelineStatus === "INDEXED"
              ? "✓ Processing complete!"
              : pipelineStatus === "FAILED"
              ? "Processing failed — check Admin panel for details"
              : "Tracking pipeline progress…"}
          </span>
          {pipelineStatus && <PipelineBadge status={pipelineStatus} />}
        </div>
      )}
      {result?.startsWith("error:") && (
        <p className="mt-2 text-xs" style={{ color: "var(--red-light)" }}>
          {result.slice(6)}
        </p>
      )}
    </form>
  );
}

// ── Pipeline Stats ────────────────────────────────────────────────────────────
function PipelineStats() {
  const { data, isLoading } = usePipelineStatus();
  const total    = (data as any)?.total ?? 0;
  const counts: any[] = (data as any)?.counts ?? [];
  const indexed  = counts.find((c: any) => c.status === "INDEXED")?.count ?? 0;
  const analyzed = counts.find((c: any) => c.status === "ANALYZED")?.count ?? 0;
  const failed   = counts.find((c: any) => c.status === "FAILED")?.count ?? 0;

  if (isLoading) return (
    <div className="flex gap-2">
      {[1,2,3].map(i => <Skeleton key={i} className="h-7 w-28 rounded-full" />)}
    </div>
  );

  return (
    <div className="flex flex-wrap gap-2">
      <div className="stat-chip">
        <Database size={11} style={{ color: "var(--accent-light)" }} />
        <span style={{ color: "var(--text-muted)" }}>Total</span>
        <span className="chip-value" style={{ color: "var(--text-primary)" }}>{total}</span>
      </div>
      <div className="stat-chip">
        <Activity size={11} style={{ color: "var(--green)" }} />
        <span style={{ color: "var(--text-muted)" }}>Indexed</span>
        <span className="chip-value" style={{ color: "var(--green)" }}>{indexed}</span>
      </div>
      <div className="stat-chip">
        <Cpu size={11} style={{ color: "var(--accent)" }} />
        <span style={{ color: "var(--text-muted)" }}>Analyzed</span>
        <span className="chip-value" style={{ color: "var(--accent-light)" }}>{analyzed}</span>
      </div>
      {failed > 0 && (
        <div className="stat-chip">
          <span style={{ color: "var(--text-muted)" }}>Failed</span>
          <span className="chip-value" style={{ color: "var(--red-light)" }}>{failed}</span>
        </div>
      )}
    </div>
  );
}

// ── Sector Heatmap ────────────────────────────────────────────────────────────
function SectorHeatmap() {
  const { data, error, isLoading } = useSectorHeatmap();

  const sentimentToColor = (s: string) => {
    const sl = (s ?? "").toLowerCase();
    if (sl === "bullish" || sl === "positive") return { bg: "rgba(34,197,94,0.14)", border: "rgba(34,197,94,0.3)", text: "#4ade80" };
    if (sl === "bearish" || sl === "negative") return { bg: "rgba(244,63,94,0.14)", border: "rgba(244,63,94,0.3)", text: "#fb7185" };
    return { bg: "rgba(245,158,11,0.12)", border: "rgba(245,158,11,0.25)", text: "#fbbf24" };
  };

  if (isLoading) return (
    <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
      {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-16" />)}
    </div>
  );
  if (error) return <ErrorState compact message="Could not load sector data" />;

  // Backend shape: { window, heatmap: { sectorName: {bullish, bearish, neutral, mixed} } }
  const heatmap: Record<string, Record<string, number>> = (data as any)?.heatmap ?? {};
  const sectors = Object.entries(heatmap).map(([sector, counts]) => {
    const total = Object.values(counts).reduce((a, b) => a + b, 0);
    const dominant = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "neutral";
    return { sector, mention_count: total, sentiment: dominant };
  });

  if (!sectors.length) return (
    <p className="text-sm py-4" style={{ color: "var(--text-muted)" }}>No sector data available yet.</p>
  );

  return (
    <div className="grid grid-cols-3 sm:grid-cols-4 gap-2 stagger-children">
      {sectors.slice(0, 12).map((s: any) => {
        const colors = sentimentToColor(s.sentiment);
        return (
          <div
            key={s.sector}
            className="heatmap-cell flex flex-col p-3 rounded-xl border border-white/5 min-h-[70px]"
            style={{ background: colors.bg, border: `1px solid ${colors.border}` }}
          >
            <p className="text-[10px] font-bold truncate" style={{ color: colors.text }}>
              {s.sector}
            </p>
            <p
              className="text-lg font-black font-mono mt-0.5 num-display"
              style={{ color: "var(--text-primary)" }}
            >
              {s.mention_count}
            </p>
            <p className="text-[9px] mt-0.5 capitalize" style={{ color: colors.text }}>
              {s.sentiment}
            </p>
          </div>
        );
      })}
    </div>
  );
}

// ── Trending Stocks Chart ─────────────────────────────────────────────────────
function TrendingStocksChart({ window }: { window: string }) {
  const { data, isLoading, error } = useTrendingStocks(window);
  // Backend shape: { window, tickers: [{ ticker, mentions }] }
  const items: any[] = (data as any)?.tickers ?? [];
  const chartData = items.slice(0, 10);

  if (isLoading) return (
    <div className="space-y-2.5 pt-1">
      {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-7" />)}
    </div>
  );
  if (error) return <ErrorState compact message="Could not load trending data" />;
  if (!items.length) return (
    <p className="text-sm py-8 text-center" style={{ color: "var(--text-muted)" }}>No trending stocks yet.</p>
  );

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart layout="vertical" data={chartData} margin={{ left: 0, right: 15, top: 0, bottom: 0 }}>
        <XAxis type="number" hide />
        <YAxis
          type="category" dataKey="ticker"
          width={55}
          tick={{ fill: "#3d5070", fontSize: 10, fontFamily: "var(--font-mono)", fontWeight: 600 }}
          tickLine={false} axisLine={false}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.02)" }} />
        <Bar dataKey="mentions" radius={[0, 4, 4, 0]} maxBarSize={16}>
          {chartData.map((_: any, i: number) => (
            <Cell
              key={i}
              fill={`url(#barGrad${i % 2})`}
              fillOpacity={0.9}
            />
          ))}
          <defs>
            <linearGradient id="barGrad0" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#1d4ed8" />
              <stop offset="100%" stopColor="#60a5fa" />
            </linearGradient>
            <linearGradient id="barGrad1" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#1d4ed8" />
              <stop offset="100%" stopColor="#818cf8" />
            </linearGradient>
          </defs>
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Recent Videos ─────────────────────────────────────────────────────────────
function RecentVideos() {
  const { data, isLoading, error } = useVideos({ page: 1, page_size: 6, sort: "-published_at" });

  if (isLoading) return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
      {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} rows={3} />)}
    </div>
  );
  if (error) return <ErrorState message="Could not load videos" />;

  const videos: any[] = (data as any)?.items ?? [];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 stagger-children">
      {videos.map((v: any) => (
        <Link
          key={v.id}
          href={`/videos?id=${v.id}`}
          className="glass-card glass-card-hover p-4 block group"
        >
          {v.thumbnail_url ? (
            <div
              className="relative mb-3 rounded-xl overflow-hidden aspect-video"
              style={{ background: "var(--bg-elevated)" }}
            >
              <img
                src={v.thumbnail_url}
                alt={v.title}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
              />
              {/* Dark overlay */}
              <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
              {/* Duration */}
              {v.duration_seconds && (
                <div
                  className="absolute bottom-2 right-2 text-white text-[10px] px-1.5 py-0.5 rounded-md font-mono font-semibold"
                  style={{ background: "rgba(0,0,0,0.85)" }}
                >
                  {Math.floor(v.duration_seconds / 60)}:{String(v.duration_seconds % 60).padStart(2, "0")}
                </div>
              )}
              {/* Play icon overlay */}
              <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                <div
                  className="w-10 h-10 rounded-full flex items-center justify-center"
                  style={{ background: "rgba(59,130,246,0.85)", boxShadow: "0 0 20px rgba(59,130,246,0.5)" }}
                >
                  <Play size={16} className="text-white ml-0.5" />
                </div>
              </div>
            </div>
          ) : (
            <div
              className="mb-3 rounded-xl aspect-video flex items-center justify-center"
              style={{ background: "var(--bg-elevated)" }}
            >
              <Play size={24} style={{ color: "var(--text-dim)" }} />
            </div>
          )}
          <p className="text-xs font-semibold line-clamp-2 mb-2.5 leading-snug" style={{ color: "var(--text-primary)" }}>
            {v.title}
          </p>
          <div className="flex items-center justify-between">
            <PipelineBadge status={v.pipeline_status} />
            <span className="text-[10px] flex items-center gap-1" style={{ color: "var(--text-muted)" }}>
              <Clock size={10} />
              {fmtDateTime(v.published_at)}
            </span>
          </div>
        </Link>
      ))}
    </div>
  );
}

// ── Dashboard Page ─────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const [window, setWindow] = useState("7d");

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto fade-in">
      {/* Daily Report */}
      <DailyReportCard />

      {/* Hero Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight leading-none" style={{ letterSpacing: "-0.03em" }}>
            Market{" "}
            <span className="gradient-text">Intelligence</span>
          </h1>
          <p className="text-sm mt-1.5 mb-3" style={{ color: "var(--text-muted)" }}>
            AI-powered stock market video analysis
          </p>
          <PipelineStats />
        </div>
        <div className="sm:max-w-xs w-full">
          <ProcessUrlForm />
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Left: Trending + Sectors */}
        <div className="xl:col-span-1 space-y-5">
          {/* Trending Stocks */}
          <div className="glass-card card-accent-blue p-5">
            <div className="section-header">
              <div className="section-title">
                <div className="icon-container icon-blue">
                  <TrendingUp size={14} />
                </div>
                Trending Stocks
              </div>
              <div className="window-pill-group">
                {["24h", "7d", "30d"].map((w) => (
                  <button
                    key={w}
                    onClick={() => setWindow(w)}
                    className={`window-pill ${window === w ? "active" : ""}`}
                  >
                    {w}
                  </button>
                ))}
              </div>
            </div>
            <TrendingStocksChart window={window} />
          </div>

          {/* Sector Heatmap */}
          <div className="glass-card card-accent-purple p-5">
            <div className="section-header">
              <div className="section-title">
                <div className="icon-container icon-purple">
                  <BarChart3 size={14} />
                </div>
                Sector Sentiment
              </div>
            </div>
            <SectorHeatmap />
          </div>
        </div>

        {/* Right: Recent Videos */}
        <div className="xl:col-span-2">
          <div className="section-header">
            <div className="section-title">
              <div className="icon-container icon-red">
                <Play size={14} />
              </div>
              Recent Videos
            </div>
            <Link
              href="/videos"
              className="flex items-center gap-1 text-xs font-medium transition-colors"
              style={{ color: "var(--accent-light)" }}
              onMouseEnter={(e) => e.currentTarget.style.color = "var(--accent-bright)"}
              onMouseLeave={(e) => e.currentTarget.style.color = "var(--accent-light)"}
            >
              View all <ArrowUpRight size={12} />
            </Link>
          </div>
          <RecentVideos />
        </div>
      </div>
    </div>
  );
}
