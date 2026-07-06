"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Bookmark, Plus, X, TrendingUp, TrendingDown, ChevronRight,
  Play, Clock, Search, Trash2, Loader2, Star, AlertCircle, Sparkles
} from "lucide-react";
import { useWatchlists, useWatchlist, useWatchlistFeed } from "@/lib/hooks";
import { watchlistApi } from "@/lib/api";
import { fmtDateTime, fmtDuration, changeClass } from "@/lib/utils";
import { PipelineBadge } from "@/components/ui/Badge";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { ErrorState, EmptyState } from "@/components/ui/ErrorState";
import { useSWRConfig } from "swr";
import { Modal } from "@/components/ui/Modal";

// ── Create Watchlist Modal ─────────────────────────────────────────────────────
function CreateWatchlistModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { mutate } = useSWRConfig();

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await watchlistApi.create({ name: name.trim() });
      mutate("watchlists");
      onClose();
    } catch (err: any) {
      setError(err.message ?? "Failed to create watchlist");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal onClose={onClose} className="border-amber-500/20 shadow-[0_0_40px_rgba(245,158,11,0.1)]">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-black text-white flex items-center gap-2 tracking-tight">
          <Star size={20} className="text-amber-400" />
          New <span className="gradient-text-gold">Watchlist</span>
        </h2>
        <button onClick={onClose} className="btn-ghost p-2 rounded-full hover:bg-red-500/10 hover:text-red-400">
          <X size={16} />
        </button>
      </div>
      <form onSubmit={handleCreate} className="space-y-5">
        <div>
          <label className="text-xs font-bold text-slate-400 mb-1.5 block uppercase tracking-wider">Watchlist Name</label>
          <input
            id="watchlist-name-input"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. AI Winners, Semiconductors…"
            className="input-field py-2.5 text-sm"
            autoFocus
          />
        </div>
        {error && (
          <p className="text-xs font-medium text-red-400 flex items-center gap-1.5 bg-red-500/10 p-2 rounded-md">
            <AlertCircle size={14} /> {error}
          </p>
        )}
        <div className="flex gap-3 pt-2">
          <button type="submit" disabled={loading || !name.trim()} className="btn-primary flex-1 justify-center py-2.5 disabled:opacity-50 font-bold">
            {loading ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
            Create Watchlist
          </button>
        </div>
      </form>
    </Modal>
  );
}

// ── Add Ticker Form ────────────────────────────────────────────────────────────
function AddTickerForm({ watchlistId, onAdded }: { watchlistId: number; onAdded: () => void }) {
  const [ticker, setTicker] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    const t = ticker.trim().toUpperCase();
    if (!t) return;
    setLoading(true);
    setError(null);
    try {
      await watchlistApi.addItem(watchlistId, t);
      setTicker("");
      onAdded();
    } catch (err: any) {
      setError(err.message ?? "Failed to add ticker");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleAdd}>
      <div className="flex gap-2">
        <label htmlFor={`add-ticker-${watchlistId}`} className="sr-only">Ticker symbol to add</label>
        <input
          id={`add-ticker-${watchlistId}`}
          type="text"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          placeholder="AAPL, TSLA, NVDA…"
          className="input-field text-sm font-mono flex-1 h-10"
          style={{ textTransform: "uppercase" }}
        />
        <button
          type="submit"
          disabled={loading || !ticker.trim()}
          className="btn-primary px-5 flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed font-bold"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
          Add Ticker
        </button>
      </div>
      {error && <p className="text-xs text-red-400 mt-2">{error}</p>}
    </form>
  );
}

// ── Watchlist Detail Panel ─────────────────────────────────────────────────────
function WatchlistDetail({ id }: { id: number }) {
  const { data: wl, isLoading, error, mutate } = useWatchlist(id);
  const { data: feed, isLoading: feedLoading } = useWatchlistFeed(id);

  async function removeItem(tickerId: number) {
    try {
      await watchlistApi.removeItem(id, tickerId);
      mutate();
    } catch {}
  }

  if (isLoading) return <SkeletonCard rows={6} />;
  if (error) return <ErrorState message="Failed to load watchlist" onRetry={mutate} compact />;

  const items: any[] = (wl as any)?.items ?? [];
  const videos: any[] = (feed as any)?.items ?? [];

  return (
    <div className="space-y-6 fade-in">
      {/* Tickers */}
      <div className="glass-card card-accent-blue p-6">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <div className="icon-container icon-blue">
              <TrendingUp size={14} />
            </div>
            Tracked Tickers
          </h3>
          <span className="text-[10px] font-mono font-bold px-2.5 py-1 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
            {items.length} TICKERS
          </span>
        </div>

        {items.length === 0 ? (
          <EmptyState
            icon={Search}
            title="No tickers yet"
            description="Add tickers below to start tracking"
          />
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
            {items.map((item: any) => {
              const ticker = item.ticker?.symbol ?? item.symbol ?? "?";
              const chg = item.change_pct;
              const isPos = chg >= 0;
              return (
                <div
                  key={item.id ?? ticker}
                  className={`glass-card-hover relative overflow-hidden flex items-center justify-between p-4 group border ${
                    chg == null ? "border-white/5" :
                    isPos ? "border-green-500/20 bg-green-500/[0.02]" : "border-red-500/20 bg-red-500/[0.02]"
                  }`}
                >
                  <Link href={`/company/${ticker}`} className="flex-1 min-w-0 z-10">
                    <p className="font-mono font-black text-lg text-white group-hover:text-blue-400 transition-colors tracking-tight">
                      {ticker}
                    </p>
                    {chg != null && (
                      <p className={`text-[11px] font-bold mt-1 flex items-center gap-1 ${
                        isPos ? "text-green-400" : "text-red-400"
                      }`}>
                        {isPos ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                        {isPos ? "+" : ""}{chg.toFixed(2)}%
                      </p>
                    )}
                  </Link>
                  <button
                    onClick={() => removeItem(item.id ?? item.ticker_id)}
                    className="opacity-0 group-hover:opacity-100 transition-opacity z-10 p-2 rounded-md hover:bg-red-500/10 text-slate-500 hover:text-red-400 absolute right-2"
                    title="Remove"
                    id={`remove-ticker-${ticker}`}
                  >
                    <Trash2 size={14} />
                  </button>
                  
                  {/* Background ambient gradient based on sentiment */}
                  {chg != null && (
                    <div className={`absolute top-0 bottom-0 right-0 w-24 blur-xl opacity-20 pointer-events-none transition-opacity group-hover:opacity-30 ${
                      isPos ? "bg-green-500" : "bg-red-500"
                    }`} />
                  )}
                </div>
              );
            })}
          </div>
        )}

        <div className="relative mt-2">
          <AddTickerForm watchlistId={id} onAdded={() => mutate()} />
        </div>
      </div>

      {/* Feed */}
      <div className="glass-card card-accent-purple p-6">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <div className="icon-container icon-purple">
              <Sparkles size={14} />
            </div>
            Curated Intelligence Feed
          </h3>
        </div>
        
        {feedLoading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => <SkeletonCard key={i} rows={2} className="p-4" />)}
          </div>
        ) : videos.length === 0 ? (
          <EmptyState
            icon={Play}
            title="No intelligence found"
            description="Videos analyzing your tracked tickers will appear here automatically."
          />
        ) : (
          <div className="space-y-4">
            {videos.slice(0, 15).map((v: any) => (
              <div
                key={v.id}
                className="flex gap-4 p-4 rounded-xl border border-white/5 bg-black/20 hover:border-white/10 hover:bg-white/[0.04] transition-all group"
              >
                {v.thumbnail_url ? (
                  <img
                    src={v.thumbnail_url}
                    alt=""
                    className="w-28 h-20 object-cover rounded-lg flex-shrink-0 border border-white/5 shadow-sm"
                  />
                ) : (
                  <div className="w-28 h-20 rounded-lg flex-shrink-0 border border-white/5 bg-slate-900 flex items-center justify-center">
                    <Play size={20} className="text-slate-700" />
                  </div>
                )}
                <div className="min-w-0 flex-1 flex flex-col">
                  <p className="text-sm font-bold text-slate-200 line-clamp-2 group-hover:text-blue-400 transition-colors leading-snug">
                    {v.title}
                  </p>
                  <div className="flex items-center gap-3 mt-auto pt-2">
                    <span className="text-[11px] font-medium text-slate-500 flex items-center gap-1.5">
                      <Clock size={11} className="text-slate-600" />
                      {fmtDateTime(v.published_at)}
                    </span>
                    {v.duration_seconds && (
                      <span className="text-[11px] font-mono text-slate-500">{fmtDuration(v.duration_seconds)}</span>
                    )}
                    <PipelineBadge status={v.pipeline_status} />
                  </div>
                </div>
                <Link href={`/videos?id=${v.id}`} className="flex-shrink-0 self-center opacity-0 group-hover:opacity-100 transition-opacity bg-white/5 hover:bg-white/10 p-2.5 rounded-lg text-white border border-white/10">
                  <ChevronRight size={16} />
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Watchlist Page ────────────────────────────────────────────────────────
export default function WatchlistPage() {
  const { data, isLoading, error } = useWatchlists();
  const watchlists: any[] = (data as any)?.items ?? (Array.isArray(data) ? data : []);
  const [selected, setSelected] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  // Auto-select first watchlist
  const activeId = selected ?? watchlists[0]?.id ?? null;

  return (
    <div className="p-6 max-w-[1400px] mx-auto fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-black text-white flex items-center gap-3 tracking-tight">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500/20 to-orange-500/20 border border-amber-500/30 flex items-center justify-center shadow-[0_0_30px_rgba(245,158,11,0.15)]">
               <Bookmark className="text-amber-400" size={18} />
            </div>
            Watch<span className="gradient-text-gold">lists</span>
          </h1>
          <p className="text-sm text-slate-500 mt-2 font-medium">Track your custom portfolios and get tailored video intelligence feeds.</p>
        </div>
        <button
          id="create-watchlist-btn"
          onClick={() => setShowCreate(true)}
          className="btn-primary shadow-lg shadow-amber-900/20 font-bold px-5"
        >
          <Plus size={15} className="mr-1" />
          Create Watchlist
        </button>
      </div>

      {showCreate && <CreateWatchlistModal onClose={() => setShowCreate(false)} />}

      {isLoading ? (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <SkeletonCard rows={5} />
          <div className="lg:col-span-3 space-y-4">
            <SkeletonCard rows={8} />
          </div>
        </div>
      ) : error ? (
        <ErrorState message="Failed to load watchlists" />
      ) : watchlists.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-32 text-center fade-in glass-card">
          <div className="w-20 h-20 rounded-3xl bg-amber-500/10 flex items-center justify-center mb-6 shadow-xl border border-amber-500/20">
            <Star size={36} className="text-amber-400" />
          </div>
          <h2 className="text-2xl font-black text-white mb-3 tracking-tight">Create your first watchlist</h2>
          <p className="text-slate-400 text-sm max-w-md mx-auto leading-relaxed mb-8">
            Watchlists organize your favorite tickers and automatically assemble a curated intelligence feed of every video that mentions them.
          </p>
          <button onClick={() => setShowCreate(true)} className="btn-primary px-8 py-3 font-bold shadow-lg shadow-blue-900/20 text-[15px]">
            <Plus size={16} className="mr-1.5" />
            Create Watchlist
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Sidebar list */}
          <div className="space-y-2">
            <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest px-2 mb-4">
              Your Portfolios
            </p>
            <div className="space-y-1.5">
              {watchlists.map((wl: any) => (
                <button
                  key={wl.id}
                  id={`watchlist-${wl.id}`}
                  onClick={() => setSelected(wl.id)}
                  className={`w-full text-left px-5 py-4 rounded-xl border transition-all flex items-center justify-between group ${
                    activeId === wl.id
                      ? "bg-amber-500/10 border-amber-500/30 text-white shadow-inner"
                      : "bg-black/20 border-white/5 text-slate-400 hover:bg-white/[0.03] hover:border-white/10 hover:text-slate-200"
                  }`}
                >
                  <div>
                    <span className={`font-bold text-[15px] truncate block mb-1 transition-colors ${activeId === wl.id ? 'text-amber-400' : 'group-hover:text-white'}`}>{wl.name}</span>
                    <span className="text-[11px] font-medium text-slate-500 flex items-center gap-1.5">
                      <TrendingUp size={11} className="text-slate-600" />
                      {wl.item_count ?? 0} tickers
                    </span>
                  </div>
                  <ChevronRight size={16} className={`flex-shrink-0 transition-transform ${activeId === wl.id ? 'text-amber-400 translate-x-1' : 'opacity-0 group-hover:opacity-100 group-hover:translate-x-1'}`} />
                </button>
              ))}
            </div>
          </div>

          {/* Detail panel */}
          <div className="lg:col-span-3">
            {activeId != null ? (
              <>
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-xl font-black text-white tracking-tight">
                    {watchlists.find((w: any) => w.id === activeId)?.name}
                  </h2>
                </div>
                <WatchlistDetail id={activeId} />
              </>
            ) : (
              <EmptyState icon={Bookmark} title="Select a watchlist" description="Choose a watchlist from the left to view its tickers and feed" />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
