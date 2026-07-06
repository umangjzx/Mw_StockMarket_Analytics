"use client";

import { useState } from "react";
import { Search as SearchIcon, Zap, Clock, ExternalLink, Brain, Database, CheckCircle2, Play } from "lucide-react";
import { searchApi } from "@/lib/api";
import { PipelineBadge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState, EmptyState } from "@/components/ui/ErrorState";
import { fmtDateTime, fmt } from "@/lib/utils";

type Mode = "structured" | "semantic";

export default function SearchPage() {
  const [mode, setMode] = useState<Mode>("semantic");
  const [query, setQuery] = useState("");
  const [ticker, setTicker] = useState("");
  const [creator, setCreator] = useState("");
  const [topic, setTopic] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  async function doSearch(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSearched(true);
    try {
      let data: any;
      if (mode === "semantic") {
        data = await searchApi.semantic({ query, top_k: 15 });
        setResults(data?.results ?? []);
      } else {
        const params: Record<string, string | number> = { page_size: 20 };
        if (query)   params.q = query;
        if (ticker)  params.ticker = ticker;
        if (creator) params.creator = creator;
        if (topic)   params.topic = topic;
        data = await searchApi.structured(params);
        setResults(data?.items ?? []);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 max-w-[1000px] mx-auto fade-in">
      <div className="mb-8">
        <h1 className="text-2xl font-black tracking-tight flex items-center gap-2">
          <SearchIcon size={22} className="text-blue-400" />
          Intelligence <span className="gradient-text">Search</span>
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Search the entire video index using SQL or vector-based semantic search.
        </p>
      </div>

      {/* Mode toggle — Segmented Control */}
      <div className="flex p-1 rounded-xl bg-black/40 border border-white/5 inline-flex mb-6 backdrop-blur-md shadow-inner">
        {(["semantic", "structured"] as Mode[]).map((m) => (
          <button
            key={m}
            onClick={() => { setMode(m); setResults([]); setSearched(false); }}
            className={`flex items-center gap-2 px-6 py-2.5 rounded-lg text-xs font-bold transition-all ${
              mode === m
                ? "bg-white/10 text-white shadow-sm ring-1 ring-white/10"
                : "text-slate-500 hover:text-slate-300 hover:bg-white/5"
            }`}
            id={`search-mode-${m}`}
          >
            {m === "semantic" ? <Brain size={14} className={mode === m ? "text-purple-400" : ""} /> : <Database size={14} className={mode === m ? "text-blue-400" : ""} />}
            {m === "semantic" ? "Semantic (AI)" : "Structured (SQL)"}
          </button>
        ))}
      </div>

      {/* Search form */}
      <form onSubmit={doSearch} className={`glass-card p-6 mb-8 transition-colors ${mode === "semantic" ? "card-accent-purple" : "card-accent-blue"}`}>
        <div className="flex flex-col sm:flex-row gap-3 mb-4">
          <div className="relative flex-1 group">
            <SearchIcon size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-blue-400 transition-colors pointer-events-none" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={
                mode === "semantic"
                  ? "What did analysts say about Nvidia's upcoming earnings guidance?"
                  : "Enter keywords… (e.g. rate cuts, inflation)"
              }
              className="input-field pl-11 py-3 text-sm font-medium w-full"
              style={{ background: "rgba(0,0,0,0.3)" }}
              id="search-query"
              autoFocus
            />
          </div>
          <button type="submit" className="btn-primary px-8 py-3 flex-shrink-0" id="search-submit-btn">
            <Zap size={14} className="text-white" /> Search
          </button>
        </div>

        {mode === "structured" && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 border-t border-white/5">
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              placeholder="Ticker (e.g. AAPL)"
              className="input-field text-sm font-mono uppercase"
              id="search-filter-ticker"
            />
            <input
              type="text"
              value={creator}
              onChange={(e) => setCreator(e.target.value)}
              placeholder="Channel Name"
              className="input-field text-sm"
              id="search-filter-creator"
            />
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="Topic"
              className="input-field text-sm"
              id="search-filter-topic"
            />
          </div>
        )}

        {mode === "semantic" && (
          <div className="pt-2 border-t border-white/5 flex items-center gap-2">
            <CheckCircle2 size={12} className="text-purple-400" />
            <p className="text-[11px] text-slate-400 font-medium">
              Natural language search parses intent and matches against embedded video transcripts via pgvector.
            </p>
          </div>
        )}
      </form>

      {/* Results */}
      {loading && (
        <div className="space-y-4">
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div>
      )}

      {error && <ErrorState message={error} onRetry={() => setError(null)} />}

      {!loading && !error && searched && results.length === 0 && (
        <EmptyState title="No results found" description="Try adjusting your search terms or switching modes." />
      )}

      {!loading && !error && results.length > 0 && (
        <div className="space-y-4 fade-in">
          <p className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-2">
            {results.length} Result{results.length !== 1 ? "s" : ""}
          </p>
          {mode === "structured"
            ? results.map((v: any) => (
                <div key={v.id} className="glass-card glass-card-hover p-5 flex gap-4 group">
                  {v.thumbnail_url ? (
                    <img src={v.thumbnail_url} alt="" className="w-32 h-20 object-cover rounded-lg flex-shrink-0 bg-slate-900 border border-white/5" />
                  ) : (
                    <div className="w-32 h-20 rounded-lg flex-shrink-0 bg-slate-800 border border-white/5 flex items-center justify-center">
                       <Database size={20} className="text-slate-600" />
                    </div>
                  )}
                  <div className="flex-1 min-w-0 py-1 flex flex-col">
                    <p className="text-sm font-bold text-slate-200 line-clamp-2 group-hover:text-blue-400 transition-colors leading-snug">
                      {v.title}
                    </p>
                    <div className="flex items-center gap-3 mt-auto pt-2">
                      <PipelineBadge status={v.pipeline_status} />
                      <span className="text-[11px] text-slate-500 flex items-center gap-1.5 font-medium">
                        <Clock size={11} className="text-slate-600" />{fmtDateTime(v.published_at)}
                      </span>
                      <a
                        href={v.video_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[11px] font-bold text-blue-400 hover:text-blue-300 flex items-center gap-1 ml-auto bg-blue-500/10 px-2.5 py-1 rounded-md transition-colors"
                      >
                        Watch <ExternalLink size={10} />
                      </a>
                    </div>
                  </div>
                </div>
              ))
            : results.map((r: any) => (
                <div key={r.segment_id} className="glass-card glass-card-hover p-5 card-accent-purple group flex flex-col gap-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-bold text-slate-200 group-hover:text-purple-400 transition-colors truncate">
                        {r.video_title}
                      </p>
                      <p className="text-[11px] text-slate-500 mt-1 font-medium flex gap-2">
                        <span>{fmtDateTime(r.published_at)}</span>
                        <span>·</span>
                        <span className="text-purple-400/80 font-mono font-bold bg-purple-500/10 px-1.5 py-0.5 rounded">
                          {fmt(r.similarity * 100, 1)}% match
                        </span>
                      </p>
                    </div>
                    {r.start_seconds != null && (
                      <a
                        href={`https://youtube.com/watch?v=${r.external_video_id}&t=${Math.floor(r.start_seconds)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[11px] font-bold text-purple-400 hover:text-purple-300 flex items-center gap-1.5 flex-shrink-0 bg-purple-500/10 hover:bg-purple-500/20 px-3 py-1.5 rounded-lg border border-purple-500/20 transition-all"
                      >
                        <Play size={10} />
                        {Math.floor(r.start_seconds / 60)}:{String(Math.floor(r.start_seconds % 60)).padStart(2,"0")}
                        <ExternalLink size={10} className="ml-1 opacity-50" />
                      </a>
                    )}
                  </div>
                  <div className="relative">
                    <div className="absolute left-0 top-0 bottom-0 w-1 bg-purple-500/30 rounded-full" />
                    <p className="text-sm text-slate-300 leading-relaxed pl-4 font-serif italic">
                      "{r.text}"
                    </p>
                  </div>
                </div>
              ))
          }
        </div>
      )}
    </div>
  );
}
