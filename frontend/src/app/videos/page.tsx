"use client";

import { useState } from "react";
import { useVideos } from "@/lib/hooks";
import { Play, Clock, Eye, Clock3, Filter, ChevronLeft, ChevronRight, Search, LayoutGrid } from "lucide-react";
import { PipelineBadge } from "@/components/ui/Badge";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { ErrorState, EmptyState } from "@/components/ui/ErrorState";
import { fmtDateTime, fmtDuration } from "@/lib/utils";
import Link from "next/link";

const STATUSES = ["All", "INDEXED", "ANALYZED", "EMBEDDED", "TRANSCRIPT_READY", "FAILED", "DISCOVERED"];
const SENTIMENTS = ["All", "bullish", "bearish", "neutral"];
const CONTENT_TYPES = ["All", "video", "short", "live"];

export default function VideosPage() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("All");
  const [sentiment, setSentiment] = useState("All");
  const [contentType, setContentType] = useState("All");
  const [ticker, setTicker] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [showFilters, setShowFilters] = useState(true);

  const params: Record<string, string | number> = {
    page, page_size: 12, sort: "-published_at",
    ...(status !== "All"      && { pipeline_status: status }),
    ...(sentiment !== "All"   && { sentiment }),
    ...(contentType !== "All" && { content_type: contentType }),
    ...(ticker      && { ticker }),
  };

  const { data, isLoading, error } = useVideos(params);
  const videos: any[] = (data as any)?.items ?? [];
  const total: number = (data as any)?.total ?? 0;
  const totalPages = Math.ceil(total / 12);

  return (
    <div className="p-6 max-w-[1400px] mx-auto fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-black tracking-tight flex items-center gap-2">
            <LayoutGrid size={22} className="text-blue-400" />
            Video <span className="gradient-text">Library</span>
          </h1>
          <p className="text-sm text-slate-500 mt-1">{total} videos indexed and ready for analysis</p>
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`btn-ghost text-xs transition-colors ${showFilters ? 'bg-white/10 text-white' : ''}`}
        >
          <Filter size={13} /> {showFilters ? 'Hide Filters' : 'Show Filters'}
        </button>
      </div>

      {/* Premium Filter Bar */}
      {showFilters && (
        <div className="glass-card p-5 mb-6 space-y-5 fade-in border border-white/10" style={{ background: 'var(--bg-surface)' }}>
          {/* Top Row: Search */}
          <div className="flex items-center gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value.toUpperCase())}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    setTicker(searchInput);
                    setPage(1);
                  }
                }}
                placeholder="Search by Ticker (e.g. AAPL) and press Enter"
                className="input-field pl-9 text-sm font-mono h-10 w-full"
                style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)' }}
              />
            </div>
            {ticker && (
              <button
                onClick={() => { setTicker(""); setSearchInput(""); setPage(1); }}
                className="text-[10px] uppercase font-bold text-slate-500 hover:text-red-400 tracking-wider transition-colors"
              >
                Clear Ticker
              </button>
            )}
          </div>

          {/* Bottom Row: Pill Toggles */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-5 border-t border-white/5">
            {/* Status */}
            <div>
              <p className="text-[10px] text-slate-500 uppercase tracking-widest font-bold mb-2">Pipeline Status</p>
              <div className="flex flex-wrap gap-1.5">
                {STATUSES.map(s => (
                  <button
                    key={s}
                    onClick={() => { setStatus(s); setPage(1); }}
                    className={`px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-all border ${
                      status === s
                        ? 'bg-blue-600/20 text-blue-400 border-blue-500/30'
                        : 'bg-transparent text-slate-400 border-white/5 hover:bg-white/5 hover:text-slate-200'
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Sentiment */}
            <div>
              <p className="text-[10px] text-slate-500 uppercase tracking-widest font-bold mb-2">Market Sentiment</p>
              <div className="flex flex-wrap gap-1.5">
                {SENTIMENTS.map(s => (
                  <button
                    key={s}
                    onClick={() => { setSentiment(s); setPage(1); }}
                    className={`px-3 py-1.5 rounded-lg text-[11px] font-semibold capitalize transition-all border ${
                      sentiment === s
                        ? s === 'bullish' ? 'bg-green-500/20 text-green-400 border-green-500/30'
                        : s === 'bearish' ? 'bg-red-500/20 text-red-400 border-red-500/30'
                        : s === 'neutral' ? 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                        : 'bg-blue-600/20 text-blue-400 border-blue-500/30'
                        : 'bg-transparent text-slate-400 border-white/5 hover:bg-white/5 hover:text-slate-200'
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Content Type */}
            <div>
              <p className="text-[10px] text-slate-500 uppercase tracking-widest font-bold mb-2">Content Type</p>
              <div className="flex flex-wrap gap-1.5">
                {CONTENT_TYPES.map(s => (
                  <button
                    key={s}
                    onClick={() => { setContentType(s); setPage(1); }}
                    className={`px-3 py-1.5 rounded-lg text-[11px] font-semibold capitalize transition-all border ${
                      contentType === s
                        ? 'bg-purple-500/20 text-purple-400 border-purple-500/30'
                        : 'bg-transparent text-slate-400 border-white/5 hover:bg-white/5 hover:text-slate-200'
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {(status !== "All" || sentiment !== "All" || contentType !== "All" || ticker !== "") && (
              <div className="col-span-full pt-2 flex justify-end">
                <button
                  onClick={() => { setStatus("All"); setSentiment("All"); setContentType("All"); setTicker(""); setSearchInput(""); setPage(1); }}
                  className="text-xs font-bold text-slate-400 hover:text-red-400 transition-colors tracking-wide flex items-center gap-1.5 bg-white/5 hover:bg-red-500/10 px-3 py-1.5 rounded-lg border border-white/5 hover:border-red-500/20"
                >
                  Clear All Filters
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
          {Array.from({ length: 12 }).map((_, i) => <SkeletonCard key={i} rows={3} />)}
        </div>
      ) : error ? (
        <ErrorState message="Could not load videos" />
      ) : videos.length === 0 ? (
        <EmptyState title="No videos found" description="Try adjusting your filters" />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
          {videos.map((v: any) => (
            <div key={v.id} className="glass-card glass-card-hover overflow-hidden group flex flex-col h-full hover:-translate-y-1 transition-all duration-300">
              {/* Thumbnail */}
              <div className="relative aspect-video bg-slate-900 overflow-hidden flex-shrink-0">
                {v.thumbnail_url ? (
                  <img src={v.thumbnail_url} alt={v.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <Play size={24} className="text-slate-700" />
                  </div>
                )}
                {/* Gradient overlay */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
                
                {v.duration_seconds && (
                  <div className="absolute bottom-2 right-2 bg-black/80 backdrop-blur text-white text-[10px] px-1.5 py-0.5 rounded-md font-mono font-semibold shadow border border-white/10">
                    {fmtDuration(v.duration_seconds)}
                  </div>
                )}
                <div className="absolute top-2 left-2 shadow-lg">
                  <PipelineBadge status={v.pipeline_status} />
                </div>
              </div>

              {/* Body */}
              <div className="p-4 flex flex-col flex-1">
                <p className="text-sm font-semibold text-slate-200 line-clamp-2 leading-snug mb-3 group-hover:text-blue-400 transition-colors">
                  {v.title}
                </p>
                <div className="mt-auto">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-[11px] text-slate-500 flex items-center gap-1.5 font-medium">
                      <Clock3 size={11} className="text-slate-600" /> {fmtDateTime(v.published_at)}
                    </span>
                    {v.view_count && (
                      <span className="text-[11px] text-slate-500 flex items-center gap-1.5 font-medium">
                        <Eye size={11} className="text-slate-600" /> {(v.view_count / 1000).toFixed(0)}K
                      </span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <Link
                      href={`/videos?id=${v.id}`}
                      className="btn-primary flex-1 justify-center py-2 text-xs font-bold"
                    >
                       Details
                    </Link>
                    <a
                      href={v.video_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn-ghost border border-white/5 flex-1 justify-center py-2 text-xs font-bold flex items-center gap-1.5 text-slate-300 hover:text-white"
                    >
                      <Play size={12} className="text-red-400" /> Watch
                    </a>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4 mt-8">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="btn-ghost text-xs px-4 py-2 disabled:opacity-30 flex items-center gap-1"
          >
            <ChevronLeft size={14} /> Prev
          </button>
          <div className="px-4 py-1.5 rounded-lg bg-black/20 border border-white/5">
            <span className="text-xs font-semibold text-slate-400">Page <span className="text-white">{page}</span> of {totalPages}</span>
          </div>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="btn-ghost text-xs px-4 py-2 disabled:opacity-30 flex items-center gap-1"
          >
            Next <ChevronRight size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
