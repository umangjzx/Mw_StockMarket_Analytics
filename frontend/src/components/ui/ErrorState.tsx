"use client";

import { AlertTriangle, RefreshCw, InboxIcon } from "lucide-react";

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
  compact?: boolean;
}

export function ErrorState({ message = "Failed to load data", onRetry, compact }: ErrorStateProps) {
  if (compact) {
    return (
      <div
        className="flex items-center gap-2 text-sm py-2.5 px-3 rounded-lg"
        style={{
          background: "rgba(244,63,94,0.07)",
          border: "1px solid rgba(244,63,94,0.2)",
          color: "var(--red-light)",
        }}
      >
        <AlertTriangle size={13} className="flex-shrink-0" />
        <span className="text-xs">{message}</span>
        {onRetry && (
          <button
            onClick={onRetry}
            className="ml-auto p-1 rounded transition-colors"
            style={{ color: "var(--text-muted)" }}
            onMouseEnter={(e) => e.currentTarget.style.color = "var(--text-primary)"}
            onMouseLeave={(e) => e.currentTarget.style.color = "var(--text-muted)"}
          >
            <RefreshCw size={12} />
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="glass-card p-10 flex flex-col items-center gap-4 text-center">
      <div
        className="w-14 h-14 rounded-2xl flex items-center justify-center"
        style={{ background: "rgba(244,63,94,0.1)", border: "1px solid rgba(244,63,94,0.2)" }}
      >
        <AlertTriangle size={24} style={{ color: "var(--red-light)" }} />
      </div>
      <div>
        <p className="font-semibold mb-1" style={{ color: "var(--text-primary)" }}>Something went wrong</p>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>{message}</p>
      </div>
      {onRetry && (
        <button onClick={onRetry} className="btn-ghost text-sm">
          <RefreshCw size={13} /> Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  title = "No data found",
  description,
  icon: Icon,
}: {
  title?: string;
  description?: string;
  icon?: React.ComponentType<{ size?: number; className?: string }> | React.ReactNode;
}) {
  const iconEl = Icon && typeof Icon === "function"
    ? <Icon size={28} className="text-slate-600" />
    : Icon as React.ReactNode;

  return (
    <div className="flex flex-col items-center gap-3 py-14 text-center">
      <div
        className="w-12 h-12 rounded-xl flex items-center justify-center mb-1"
        style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}
      >
        {iconEl ?? <InboxIcon size={20} style={{ color: "var(--text-muted)" }} />}
      </div>
      <p className="font-medium text-sm" style={{ color: "var(--text-secondary)" }}>{title}</p>
      {description && (
        <p className="text-xs max-w-xs" style={{ color: "var(--text-muted)" }}>{description}</p>
      )}
    </div>
  );
}
