"use client";

import { useState, useRef, useEffect } from "react";
import { Zap, Loader2 } from "lucide-react";
import { videoApi } from "@/lib/api";
import { PipelineBadge } from "@/components/ui/Badge";

const TERMINAL_STATUSES = new Set(["INDEXED", "FAILED"]);
const POLL_INTERVAL_MS = 4000;
const POLL_MAX_ATTEMPTS = 90; // ~6 minutes

// Submits a YouTube URL for processing and polls pipeline status until it
// reaches a terminal state. Used inside the Sidebar's "Process Video" modal —
// a global quick action rather than a dashboard-only feature.
export function ProcessVideoForm() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [trackedId, setTrackedId] = useState<string | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<string | null>(null);
  const attemptsRef = useRef(0);

  useEffect(() => {
    if (!trackedId) return;
    attemptsRef.current = 0;

    const interval = setInterval(async () => {
      attemptsRef.current += 1;
      try {
        const data: any = await videoApi.list({ external_video_id: trackedId, page_size: 1 });
        const video = data?.items?.[0];
        if (video?.pipeline_status) {
          setPipelineStatus(video.pipeline_status);
          if (TERMINAL_STATUSES.has(video.pipeline_status)) {
            clearInterval(interval);
          }
        }
      } catch {
        // transient — keep polling until max attempts
      }
      if (attemptsRef.current >= POLL_MAX_ATTEMPTS) {
        clearInterval(interval);
      }
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [trackedId]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    setLoading(true); setResult(null); setPipelineStatus(null); setTrackedId(null);
    try {
      const res: any = await videoApi.processUrl(url.trim());
      setResult("success");
      setUrl("");
      if (res?.external_video_id) {
        setTrackedId(res.external_video_id);
        setPipelineStatus("DISCOVERED");
      }
    } catch (err: any) {
      setResult(`error:${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <div className="flex gap-2">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://youtu.be/..."
          className="input-field text-sm"
          id="process-url-input"
          autoFocus
        />
        <button
          type="submit"
          disabled={loading || !url.trim()}
          className="btn-primary flex-shrink-0 disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none"
          id="process-url-btn"
        >
          {loading ? <Loader2 size={13} className="animate-spin" /> : <Zap size={13} />}
          {loading ? "Queuing…" : "Process"}
        </button>
      </div>
      {result === "success" && trackedId && (
        <div className="mt-3 flex items-center gap-2">
          {pipelineStatus && !TERMINAL_STATUSES.has(pipelineStatus) && (
            <Loader2 size={11} className="animate-spin" style={{ color: "var(--accent-light)" }} />
          )}
          <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
            {pipelineStatus === "INDEXED"
              ? "✓ Processing complete!"
              : pipelineStatus === "FAILED"
              ? "Processing failed — check Admin panel for details"
              : "Tracking pipeline progress…"}
          </span>
          {pipelineStatus && <PipelineBadge status={pipelineStatus} />}
        </div>
      )}
      {result?.startsWith("error:") && (
        <p className="mt-2 text-xs" style={{ color: "var(--red-light)" }}>
          {result.slice(6)}
        </p>
      )}
    </form>
  );
}
