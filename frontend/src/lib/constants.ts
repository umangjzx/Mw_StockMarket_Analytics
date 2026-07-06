// Single source of truth for sentiment and pipeline-status color VALUES.
// These are raw hex/rgba strings (not CSS var() references) because Recharts
// SVG props (fill, stroke, Cell color) and inline gradient/background styles
// need literal color values to render reliably in every context. Mirrors the
// hex values already defined in app/globals.css's :root block — if a value
// changes there, mirror the change here too.

export type Sentiment = "bullish" | "bearish" | "neutral" | "mixed";

export const SENTIMENT_COLORS: Record<Sentiment, string> = {
  bullish: "#4ade80", // var(--green-light)
  bearish: "#fb7185", // var(--red-light)
  neutral: "#fbbf24", // var(--amber-light)
  mixed: "#818cf8", // indigo-400 — no existing design token, kept as-is
};

export function sentimentColorValue(sentiment: string | null | undefined): string {
  const key = (sentiment ?? "").toLowerCase().replace("positive", "bullish").replace("negative", "bearish");
  return SENTIMENT_COLORS[key as Sentiment] ?? SENTIMENT_COLORS.neutral;
}

interface SentimentStyle {
  bg: string;
  border: string;
  text: string;
}

// bg/border/text triplet variant, for the sentiment-heatmap-cell style of
// consumer (dashboard's SectorHeatmap) that needs more than a single color.
const SENTIMENT_STYLES: Record<Sentiment, SentimentStyle> = {
  bullish: { bg: "rgba(34,197,94,0.14)", border: "rgba(34,197,94,0.3)", text: SENTIMENT_COLORS.bullish },
  bearish: { bg: "rgba(244,63,94,0.14)", border: "rgba(244,63,94,0.3)", text: SENTIMENT_COLORS.bearish },
  neutral: { bg: "rgba(245,158,11,0.12)", border: "rgba(245,158,11,0.25)", text: SENTIMENT_COLORS.neutral },
  mixed: { bg: "rgba(129,140,248,0.12)", border: "rgba(129,140,248,0.25)", text: SENTIMENT_COLORS.mixed },
};

export function sentimentStyle(sentiment: string | null | undefined): SentimentStyle {
  const key = (sentiment ?? "").toLowerCase().replace("positive", "bullish").replace("negative", "bearish");
  return SENTIMENT_STYLES[key as Sentiment] ?? SENTIMENT_STYLES.neutral;
}

export type PipelineStatus =
  | "INDEXED"
  | "ANALYZED"
  | "EMBEDDED"
  | "TRANSCRIPT_READY"
  | "TRANSCRIPT_PENDING"
  | "ANALYSIS_PENDING"
  | "EMBEDDING_PENDING"
  | "DISCOVERED"
  | "FAILED";

// NOTE: ANALYSIS_PENDING/EMBEDDING_PENDING/DISCOVERED/FAILED don't map to any
// existing green/red/amber/purple/teal design token — this drift already
// existed in the per-page copies this file replaces; consolidating surfaces
// it in one place rather than fixing it silently. Revisit if a full palette
// pass happens later.
export const PIPELINE_STATUS_COLORS: Record<PipelineStatus, string> = {
  INDEXED: "#22c55e", // var(--green)
  ANALYZED: "#3b82f6", // var(--accent)
  EMBEDDED: "#a855f7", // var(--purple)
  TRANSCRIPT_READY: "#14b8a6", // var(--teal)
  TRANSCRIPT_PENDING: "#f59e0b", // var(--amber)
  ANALYSIS_PENDING: "#f97316", // orange-500 — no existing token
  EMBEDDING_PENDING: "#8b5cf6", // violet-500 — no existing token
  DISCOVERED: "#64748b", // slate-500 — no existing token
  FAILED: "#ef4444", // red-500 — close to but not exactly var(--red) #f43f5e
};

export function pipelineStatusColorValue(status: string | null | undefined): string {
  return PIPELINE_STATUS_COLORS[status as PipelineStatus] ?? PIPELINE_STATUS_COLORS.DISCOVERED;
}
