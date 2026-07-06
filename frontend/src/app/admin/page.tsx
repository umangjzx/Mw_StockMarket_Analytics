"use client";

import { useState } from "react";
import {
  Settings, RefreshCw, AlertTriangle, CheckCircle, Clock,
  Play, Zap, BarChart2, Activity, Database, Cpu, Loader2,
  ChevronDown, ChevronUp, ExternalLink,
} from "lucide-react";
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
} from "recharts";
import {
  usePipelineStatus, usePipelineFailures, useSchedulerJobs, useQuota,
} from "@/lib/hooks";
import { adminApi } from "@/lib/api";
import { fmtDateTime, fmtLarge } from "@/lib/utils";
import { pipelineStatusColorValue } from "@/lib/constants";
import { PipelineBadge } from "@/components/ui/Badge";
import { Skeleton, SkeletonCard } from "@/components/ui/Skeleton";
import { ErrorState, EmptyState } from "@/components/ui/ErrorState";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { useSWRConfig } from "swr";

// ── Pipeline Status Donut ──────────────────────────────────────────────────────
function PipelineStatusDonut() {
  const { data, isLoading, error, mutate } = usePipelineStatus();

  if (isLoading) return <SkeletonCard rows={4} />;
  if (error) return <ErrorState compact message="Could not load pipeline status" onRetry={mutate} />;

  const counts: any[] = (data as any)?.counts ?? [];
  const total: number = (data as any)?.total ?? 0;

  const chartData = counts.map((c: any) => ({
    name: c.status.replace(/_/g, " "),
    value: c.count,
    status: c.status,
    color: pipelineStatusColorValue(c.status),
  }));

  return (
    <div className="glass-card p-5">
      <SectionHeader
        icon={BarChart2}
        iconColor="blue"
        title="Pipeline Status"
        action={
          <button onClick={() => mutate()} className="btn-ghost p-1.5 rounded-lg" title="Refresh">
            <RefreshCw size={13} />
          </button>
        }
      />
      <div className="flex items-center gap-4">
        <ResponsiveContainer width={140} height={140}>
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={42}
              outerRadius={65}
              dataKey="value"
              paddingAngle={2}
            >
              {chartData.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              formatter={(val: any, name: any) => [val, name]}
              contentStyle={{ background: "#1e2d45", border: "1px solid #1e3a5f", borderRadius: 8, fontSize: 12 }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="flex-1 space-y-1.5">
          {chartData.map((d) => (
            <div key={d.status} className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: d.color }} />
                <span className="text-slate-400">{d.name}</span>
              </div>
              <span className="font-mono font-semibold text-white">{d.value}</span>
            </div>
          ))}
          <div className="mt-2 pt-2 border-t border-white/5 flex items-center justify-between text-xs">
            <span className="text-slate-500">Total Videos</span>
            <span className="font-mono font-bold text-white">{total}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Failure Table ──────────────────────────────────────────────────────────────
function FailuresTable() {
  const { data, isLoading, error, mutate } = usePipelineFailures();
  const { mutate: globalMutate } = useSWRConfig();
  const [retrying, setRetrying] = useState<Record<number, boolean>>({});

  async function retry(id: number) {
    setRetrying((prev) => ({ ...prev, [id]: true }));
    try {
      await adminApi.retry(id);
      mutate();
      globalMutate("pipeline-status");
    } finally {
      setRetrying((prev) => ({ ...prev, [id]: false }));
    }
  }

  if (isLoading) return <SkeletonCard rows={5} />;
  if (error) return <ErrorState compact message="Could not load failures" onRetry={mutate} />;

  const failures: any[] = (data as any)?.items ?? (Array.isArray(data) ? data : []);

  return (
    <div className="glass-card p-5">
      <SectionHeader
        icon={AlertTriangle}
        iconColor="red"
        title={
          <>
            Failed Videos
            {failures.length > 0 && (
              <span className="badge-bear text-[10px] px-2 py-0.5 rounded-full font-bold">{failures.length}</span>
            )}
          </>
        }
        action={
          <button onClick={() => mutate()} className="btn-ghost p-1.5 rounded-lg" title="Refresh">
            <RefreshCw size={13} />
          </button>
        }
      />
      {failures.length === 0 ? (
        <div className="flex items-center gap-2 py-4 text-sm text-green-400">
          <CheckCircle size={16} />
          No failed videos — pipeline is healthy!
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Video</th>
                <th>Status</th>
                <th className="hidden md:table-cell">Reason</th>
                <th className="hidden sm:table-cell">Retries</th>
                <th className="hidden md:table-cell">Updated</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {failures.map((v: any) => (
                <tr key={v.id}>
                  <td className="max-w-[220px]">
                    <a
                      href={v.video_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:text-blue-300 flex items-center gap-1 truncate text-sm"
                    >
                      {v.title ?? v.external_video_id}
                      <ExternalLink size={11} className="flex-shrink-0" />
                    </a>
                  </td>
                  <td><PipelineBadge status={v.pipeline_status} /></td>
                  <td className="max-w-[200px] hidden md:table-cell">
                    <span className="text-xs text-red-400 truncate block">{v.pipeline_failure_reason ?? "—"}</span>
                  </td>
                  <td className="font-mono text-center hidden sm:table-cell">{v.pipeline_retry_count ?? 0}</td>
                  <td className="text-slate-500 text-xs hidden md:table-cell">{fmtDateTime(v.updated_at)}</td>
                  <td>
                    <button
                      id={`retry-btn-${v.id}`}
                      onClick={() => retry(v.id)}
                      disabled={retrying[v.id]}
                      className="btn-ghost text-xs py-1 px-3 disabled:opacity-50"
                    >
                      {retrying[v.id] ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />}
                      Retry
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Scheduler Table ─────────────────────────────────────────────────────────────
function SchedulerTable() {
  const { data, isLoading, error, mutate } = useSchedulerJobs();
  const [triggering, setTriggering] = useState<Record<string, boolean>>({});

  async function triggerJob(name: string) {
    setTriggering((prev) => ({ ...prev, [name]: true }));
    try {
      await adminApi.triggerJob(name);
    } finally {
      setTriggering((prev) => ({ ...prev, [name]: false }));
      mutate();
    }
  }

  if (isLoading) return <SkeletonCard rows={4} />;
  if (error) return <ErrorState compact message="Could not load scheduler" onRetry={mutate} />;

  const jobs: any[] = Array.isArray(data) ? data : (data as any)?.jobs ?? [];

  return (
    <div className="glass-card p-5">
      <SectionHeader
        icon={Clock}
        iconColor="purple"
        title="Scheduler Jobs"
        action={
          <button onClick={() => mutate()} className="btn-ghost p-1.5 rounded-lg" title="Refresh">
            <RefreshCw size={13} />
          </button>
        }
      />
      {jobs.length === 0 ? (
        <EmptyState icon={Clock} title="No jobs found" description="Scheduler jobs will appear here" />
      ) : (
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Job Name</th>
                <th className="hidden md:table-cell">Schedule</th>
                <th className="hidden lg:table-cell">Last Run</th>
                <th className="hidden sm:table-cell">Next Run</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job: any) => (
                <tr key={job.name ?? job.id}>
                  <td>
                    <span className="font-mono text-blue-400 text-xs">{job.name}</span>
                  </td>
                  <td className="text-slate-400 text-xs font-mono hidden md:table-cell">{job.schedule ?? job.cron ?? "—"}</td>
                  <td className="text-slate-500 text-xs hidden lg:table-cell">{fmtDateTime(job.last_run_at) ?? "Never"}</td>
                  <td className="text-slate-400 text-xs hidden sm:table-cell">{fmtDateTime(job.next_run_at) ?? "—"}</td>
                  <td>
                    <button
                      id={`trigger-job-${job.name}`}
                      onClick={() => triggerJob(job.name)}
                      disabled={triggering[job.name]}
                      className="btn-ghost text-xs py-1 px-3 text-amber-400 border-amber-500/30 hover:bg-amber-500/10 disabled:opacity-50"
                    >
                      {triggering[job.name] ? <Loader2 size={11} className="animate-spin" /> : <Zap size={11} />}
                      Trigger
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Quota & Usage Card ─────────────────────────────────────────────────────────
function QuotaCard() {
  const { data, isLoading, error } = useQuota();

  if (isLoading) return <SkeletonCard rows={3} />;
  if (error) return null; // non-critical

  const quota: any = data ?? {};

  const meters = [
    { label: "Groq Transcriptions", used: quota.groq_requests_today, limit: quota.groq_daily_limit, color: "var(--green)" },
    { label: "LLM Inferences", used: quota.ollama_requests_today, limit: quota.ollama_daily_limit, color: "var(--accent)" },
    { label: "Videos Processed (7d)", used: quota.videos_processed_7d, limit: null, color: "var(--purple)" },
  ];

  return (
    <div className="glass-card p-5">
      <SectionHeader icon={Cpu} iconColor="teal" title="Resource Usage" />
      <div className="space-y-4">
        {meters.map((m) => (
          <div key={m.label}>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-slate-400">{m.label}</span>
              <span className="font-mono font-semibold text-white">
                {m.used != null ? fmtLarge(m.used) : "—"}
                {m.limit != null && <span className="text-slate-500"> / {fmtLarge(m.limit)}</span>}
              </span>
            </div>
            {m.limit != null && m.used != null && (
              <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.min(100, (m.used / m.limit) * 100)}%`,
                    background: m.color,
                  }}
                />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Task Logs Accordion ────────────────────────────────────────────────────────
function TaskLogs() {
  const [open, setOpen] = useState(false);
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadLogs() {
    if (open) { setOpen(false); return; }
    setOpen(true);
    setLoading(true);
    setError(null);
    try {
      const data = await adminApi.taskLogs();
      setLogs(Array.isArray(data) ? data : (data as any)?.items ?? []);
    } catch (err: any) {
      setError(err.message ?? "Failed to load logs");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="glass-card overflow-hidden">
      <button
        id="task-logs-toggle"
        onClick={loadLogs}
        className="w-full flex items-center justify-between p-5 text-sm font-semibold text-white hover:bg-white/[0.02] transition-colors"
      >
        <div className="flex items-center gap-2">
          <Activity size={15} className="text-green-400" />
          Recent Task Logs
        </div>
        {open ? <ChevronUp size={15} className="text-slate-500" /> : <ChevronDown size={15} className="text-slate-500" />}
      </button>
      {open && (
        <div className="border-t border-white/5 p-5">
          {loading ? (
            <div className="space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-8" />)}</div>
          ) : error ? (
            <p className="text-sm text-red-400">{error}</p>
          ) : logs.length === 0 ? (
            <p className="text-sm text-slate-500">No recent logs found.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Task Name</th>
                    <th>Status</th>
                    <th className="hidden sm:table-cell">Runtime</th>
                    <th className="hidden md:table-cell">Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.slice(0, 20).map((log: any, i) => (
                    <tr key={i}>
                      <td className="font-mono text-xs text-blue-400">{log.name ?? log.task_name ?? "—"}</td>
                      <td>
                        <span className={`text-xs font-semibold ${
                          log.status === "SUCCESS" ? "text-green-400" :
                          log.status === "FAILURE" ? "text-red-400" :
                          "text-amber-400"
                        }`}>
                          {log.status ?? "—"}
                        </span>
                      </td>
                      <td className="text-slate-500 text-xs font-mono hidden sm:table-cell">
                        {log.runtime_ms != null ? `${log.runtime_ms}ms` : "—"}
                      </td>
                      <td className="text-slate-500 text-xs hidden md:table-cell">{fmtDateTime(log.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Admin Page ────────────────────────────────────────────────────────────
export default function AdminPage() {
  return (
    <div className="p-6 max-w-7xl mx-auto fade-in">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center">
          <Settings size={18} className="text-slate-300" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white">Admin Panel</h1>
          <p className="text-sm text-slate-500">Pipeline monitoring, scheduler, and system health</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <div className="live-dot" />
          <span className="text-xs text-green-400">Live</span>
        </div>
      </div>

      {/* Top row — Donut + Quota */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-5">
        <PipelineStatusDonut />
        <QuotaCard />
      </div>

      {/* Failures */}
      <div className="mb-5">
        <FailuresTable />
      </div>

      {/* Scheduler */}
      <div className="mb-5">
        <SchedulerTable />
      </div>

      {/* Task Logs */}
      <TaskLogs />
    </div>
  );
}
