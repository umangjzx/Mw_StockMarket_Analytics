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
