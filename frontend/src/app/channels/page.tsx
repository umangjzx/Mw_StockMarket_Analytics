"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Tv, TrendingUp, TrendingDown, BarChart2,
  Users, Video, ArrowUpRight, Star,
} from "lucide-react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { useChannels, useCreatorStats } from "@/lib/hooks";
import { Skeleton, SkeletonCard } from "@/components/ui/Skeleton";
import { ErrorState, EmptyState } from "@/components/ui/ErrorState";

// Sentiment mini donut for each creator card
function CreatorSentimentDonut({ bullish, bearish }: { bullish: number; bearish: number }) {
  const neutral = Math.max(0, 100 - bullish - bearish);
  const data = [
    { name: 'Bullish', value: bullish, color: '#4ade80' },
    { name: 'Bearish', value: bearish, color: '#fb7185' },
    { name: 'Neutral', value: neutral, color: '#fbbf24' },
  ].filter(d => d.value > 0);

  return (
    <div style={{ width: 64, height: 64 }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%" cy="50%"
            innerRadius={20} outerRadius={30}
            dataKey="value"
            strokeWidth={0}
          >
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.color} fillOpacity={0.9} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

// Single creator card — fetches creator stats
function CreatorCard({ channel }: { channel: any }) {
  const { data: statsData, isLoading } = useCreatorStats(channel.id);
  const stats: any = statsData ?? {};

  const bullish = stats.avg_bullish_pct ?? 0;
  const bearish = stats.avg_bearish_pct ?? 0;
  const isBull = bullish >= bearish;

  return (
    <div
      className="glass-card glass-card-hover p-5 flex flex-col gap-4"
      style={{ position: 'relative', overflow: 'hidden' }}
    >
      {/* Top accent strip color based on sentiment */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, height: 2,
        background: isBull
          ? 'linear-gradient(90deg, transparent, #22c55e, #4ade80, transparent)'
          : 'linear-gradient(90deg, transparent, #f43f5e, #fb7185, transparent)'
      }} />

      {/* Header */}
      <div className="flex items-start gap-3">
        {/* Avatar */}
        <div
          className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{
            background: 'linear-gradient(135deg, rgba(59,130,246,0.2), rgba(168,85,247,0.2))',
            border: '1px solid rgba(59,130,246,0.2)',
          }}
        >
          {channel.thumbnail_url ? (
            <img src={channel.thumbnail_url} alt={channel.name}
              className="w-full h-full rounded-xl object-cover" />
          ) : (
            <Tv size={20} style={{ color: 'var(--accent-light)' }} />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <p className="font-bold text-sm truncate" style={{ color: 'var(--text-primary)' }}>
            {channel.name ?? channel.channel_name ?? 'Unknown Channel'}
          </p>
          <p className="text-[10px] mt-0.5" style={{ color: 'var(--text-muted)' }}>
            {channel.subscriber_count
              ? `${(channel.subscriber_count / 1000).toFixed(0)}K subscribers`
              : 'Finance Channel'}
          </p>
        </div>

        {/* Donut */}
        {!isLoading && (bullish > 0 || bearish > 0) && (
          <CreatorSentimentDonut bullish={Math.round(bullish)} bearish={Math.round(bearish)} />
        )}
      </div>

      {/* Stats row */}
      {isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          {[
            { label: 'Videos (30d)', value: stats.video_count ?? 0, color: 'var(--accent-light)' },
            { label: 'Avg Bullish', value: `${bullish.toFixed(1)}%`, color: 'var(--green)' },
            { label: 'Avg Bearish', value: `${bearish.toFixed(1)}%`, color: 'var(--red-light)' },
          ].map(({ label, value, color }) => (
            <div key={label} className="text-center p-2 rounded-lg"
              style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)' }}>
              <p className="text-[9px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>{label}</p>
              <p className="text-sm font-bold font-mono mt-0.5" style={{ color }}>{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Top tickers */}
      {!isLoading && stats.top_tickers?.length > 0 && (
        <div>
          <p className="text-[9px] uppercase tracking-wider mb-1.5" style={{ color: 'var(--text-muted)' }}>Top Tickers Covered</p>
          <div className="flex flex-wrap gap-1">
            {stats.top_tickers.slice(0, 5).map((t: string) => (
              <Link key={t} href={`/company/${t}`}
                className="inline-flex px-2 py-0.5 rounded-md text-[10px] font-mono font-bold transition-colors"
                style={{
                  background: 'rgba(59,130,246,0.1)',
                  color: 'var(--accent-light)',
                  border: '1px solid rgba(59,130,246,0.2)',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(59,130,246,0.2)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(59,130,246,0.1)'; }}
              >
                {t}
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ChannelsPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading, error } = useChannels(page);

  const channels: any[] = (data as any)?.items ?? (Array.isArray(data) ? data : []);
  const totalPages: number = (data as any)?.pages ?? 1;

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto fade-in">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-black tracking-tight" style={{ letterSpacing: '-0.02em' }}>
          Creator <span className="gradient-text">Leaderboard</span>
        </h1>
        <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
          YouTube finance channels ranked by video output and sentiment signals
        </p>
      </div>

      {/* Summary stat bar */}
      <div className="flex flex-wrap gap-3">
        <div className="stat-chip">
          <Tv size={11} style={{ color: 'var(--red-light)' }} />
          <span style={{ color: 'var(--text-muted)' }}>Channels</span>
          <span className="chip-value" style={{ color: 'var(--text-primary)' }}>
            {isLoading ? '—' : channels.length}
          </span>
        </div>
        <div className="stat-chip">
          <Star size={11} style={{ color: 'var(--amber)' }} />
          <span style={{ color: 'var(--text-muted)' }}>Creator Intelligence</span>
          <span className="chip-value" style={{ color: 'var(--amber)' }}>30d</span>
        </div>
      </div>

      {/* Grid */}
      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 stagger-children">
          {Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} rows={4} />)}
        </div>
      )}

      {error && <ErrorState message="Could not load channels" />}

      {!isLoading && !error && channels.length === 0 && (
        <EmptyState title="No channels found" description="Add YouTube channels via the Admin pipeline" />
      )}

      {!isLoading && !error && channels.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 stagger-children">
          {channels.map((ch: any) => <CreatorCard key={ch.id} channel={ch} />)}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 pt-2">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="btn-ghost text-xs py-1.5 px-4 disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-xs px-3" style={{ color: 'var(--text-muted)' }}>Page {page} of {totalPages}</span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="btn-ghost text-xs py-1.5 px-4 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
