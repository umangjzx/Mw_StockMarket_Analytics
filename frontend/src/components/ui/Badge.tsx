"use client";

import { cn, sentimentClass } from "@/lib/utils";

interface BadgeProps {
  label: string;
  variant?: "bull" | "bear" | "neutral" | "blue" | "purple" | "default";
  className?: string;
  size?: "sm" | "md";
}

export function Badge({ label, variant = "default", className, size = "sm" }: BadgeProps) {
  const variantClass = {
    bull:    "badge-bull",
    bear:    "badge-bear",
    neutral: "badge-neutral",
    blue:    "badge-blue",
    purple:  "badge-purple",
    default: "bg-slate-800/60 text-slate-400 border border-slate-700/50",
  }[variant];

  return (
    <span
      className={cn(
        "inline-flex items-center font-semibold rounded-full whitespace-nowrap tracking-wide",
        size === "sm" ? "text-[10px] px-2 py-0.5" : "text-xs px-2.5 py-1",
        variantClass,
        className,
      )}
    >
      {label}
    </span>
  );
}

export function SentimentBadge({ sentiment, size }: { sentiment?: string | null; size?: "sm" | "md" }) {
  if (!sentiment) return null;
  const s = sentiment.toLowerCase();
  const variant =
    s === "bullish" || s === "positive" ? "bull" :
    s === "bearish" || s === "negative" ? "bear" : "neutral";
  const label = sentiment.charAt(0).toUpperCase() + sentiment.slice(1).toLowerCase();
  return <Badge label={label} variant={variant} size={size} />;
}

interface PipelineBadgeProps { status: string; }
export function PipelineBadge({ status }: PipelineBadgeProps) {
  const cls = {
    INDEXED:             "status-indexed",
    ANALYZED:            "status-analyzed",
    EMBEDDED:            "status-embedded",
    FAILED:              "status-failed",
    TRANSCRIPT_PENDING:  "status-pending",
    TRANSCRIPT_READY:    "status-ready",
    ANALYSIS_PENDING:    "status-pending",
    EMBEDDING_PENDING:   "status-pending",
    DISCOVERED:          "status-discovered",
  }[status] ?? "status-discovered";

  const label = status.replace(/_/g, " ");
  return (
    <span className={cn("inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded-full tracking-wide", cls)}>
      {label}
    </span>
  );
}
