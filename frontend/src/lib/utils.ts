import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmt(value: number | null | undefined, decimals = 2): string {
  if (value == null) return "—";
  return value.toFixed(decimals);
}

export function fmtLarge(value: number | null | undefined): string {
  if (value == null) return "—";
  if (Math.abs(value) >= 1e12) return `${(value / 1e12).toFixed(2)}T`;
  if (Math.abs(value) >= 1e9)  return `${(value / 1e9).toFixed(2)}B`;
  if (Math.abs(value) >= 1e6)  return `${(value / 1e6).toFixed(2)}M`;
  if (Math.abs(value) >= 1e3)  return `${(value / 1e3).toFixed(2)}K`;
  return value.toFixed(2);
}

export function fmtPct(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function fmtCurrency(value: number | null | undefined, currency = "USD"): string {
  if (value == null) return "—";
  const sym = currency === "INR" ? "₹" : "$";
  return `${sym}${fmtLarge(value)}`;
}

export function fmtDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short", day: "numeric", year: "numeric",
    });
  } catch { return dateStr; }
}

export function fmtDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleString("en-US", {
      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch { return dateStr; }
}

export function fmtDuration(seconds: number | null | undefined): string {
  if (!seconds) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function sentimentColor(sentiment: string | null | undefined): string {
  const s = (sentiment ?? "").toLowerCase();
  if (s === "bullish" || s === "positive") return "var(--green)";
  if (s === "bearish" || s === "negative") return "var(--red)";
  return "var(--amber)";
}

export function sentimentClass(sentiment: string | null | undefined): string {
  const s = (sentiment ?? "").toLowerCase();
  if (s === "bullish" || s === "positive") return "badge-bull";
  if (s === "bearish" || s === "negative") return "badge-bear";
  return "badge-neutral";
}

export function pipelineStatusClass(status: string): string {
  const s = status.toLowerCase();
  if (s === "indexed")  return "status-indexed";
  if (s === "analyzed") return "status-analyzed";
  if (s === "embedded") return "status-embedded";
  if (s.includes("fail")) return "status-failed";
  if (s.includes("pending") || s.includes("ready")) return "status-pending";
  return "status-discovered";
}

export function changeClass(value: number | null | undefined): string {
  if (value == null) return "text-slate-400";
  return value >= 0 ? "text-green-400" : "text-red-400";
}
