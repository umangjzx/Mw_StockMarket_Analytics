"use client";

import { cn } from "@/lib/utils";

interface MetricCardProps {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  trend?: "up" | "down" | "neutral";
  className?: string;
  accent?: string;
}

export function MetricCard({ label, value, sub, trend, className, accent }: MetricCardProps) {
  return (
    <div className={cn("metric-card", className)}>
      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
        {label}
      </p>
      <p
        className="text-xl font-bold font-mono leading-none"
        style={{ color: accent ?? "var(--text-primary)" }}
      >
        {value ?? "—"}
      </p>
      {sub && (
        <p
          className={cn(
            "text-xs mt-1.5 font-medium",
            trend === "up"   ? "text-green-400" :
            trend === "down" ? "text-red-400"   : "text-slate-500",
          )}
        >
          {sub}
        </p>
      )}
    </div>
  );
}

interface MetricGridCellProps {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  valueColor?: string; // for conditional coloring, e.g. RSI overbought/oversold
  valueClassName?: string; // override the value text's size, e.g. a cell needing more emphasis
  className?: string;
}

// Sized for a dense grid of small stats (Key Ratios, Technicals) — MetricCard
// above is built for hero-sized single metrics and is too large for that case.
// Replaces 2+ previously-inline "metric cell" implementations that duplicated
// this same visual job with slightly different markup per callsite.
export function MetricGridCell({ label, value, sub, valueColor, valueClassName, className }: MetricGridCellProps) {
  return (
    <div className={cn("bg-elevated/50 rounded-token-sm p-2.5", className)}>
      <p className="text-[10px] text-muted-fg uppercase tracking-wider font-semibold">{label}</p>
      <p className={cn("font-mono font-bold mt-0.5", valueClassName ?? "text-sm")} style={{ color: valueColor ?? "var(--text-primary)" }}>
        {value ?? "—"}
      </p>
      {sub && <p className="text-[10px] text-muted-fg mt-0.5">{sub}</p>}
    </div>
  );
}

interface StatRowProps {
  label: string;
  value: React.ReactNode;
  className?: string;
}

export function StatRow({ label, value, className }: StatRowProps) {
  return (
    <div className={cn("flex items-center justify-between py-2.5 border-b border-white/5 last:border-none", className)}>
      <span className="text-slate-500 text-xs font-medium">{label}</span>
      <span className="text-slate-200 text-xs font-mono font-semibold">{value ?? "—"}</span>
    </div>
  );
}
