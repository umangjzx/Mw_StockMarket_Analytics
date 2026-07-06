const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const ADMIN_KEY = process.env.NEXT_PUBLIC_ADMIN_KEY ?? "changeme-admin-key";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = j.detail ?? j.message ?? msg; } catch {}
    throw new ApiError(res.status, msg);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get:    <T>(path: string, init?: RequestInit) => request<T>(path, { method: "GET", ...init }),
  post:   <T>(path: string, body?: unknown, init?: RequestInit) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body), ...init }),
  patch:  <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

// Only admin/scheduler routes require this header — attach it explicitly
// per-call instead of on every request (it's a public NEXT_PUBLIC_ var).
const ADMIN_HEADERS: RequestInit = { headers: { "X-Admin-Key": ADMIN_KEY } };

// ── Typed API helpers ──────────────────────────────────────────────────────

// Company Intelligence
export const companyApi = {
  resolve:          (q: string)       => api.get(`/companies/resolve?q=${encodeURIComponent(q)}`),
  overview:         (ticker: string)  => api.get(`/companies/${ticker}`),
  quote:            (ticker: string)  => api.get(`/companies/${ticker}/quote`),
  chart:            (ticker: string, range = "1M") => api.get(`/companies/${ticker}/chart?range=${range}`),
  profile:          (ticker: string)  => api.get(`/companies/${ticker}/profile`),
  ratios:           (ticker: string)  => api.get(`/companies/${ticker}/ratios`),
  financials:       (ticker: string, type = "income", period = "annual") =>
    api.get(`/companies/${ticker}/financials?statement=${type}&period=${period}`),
  earnings:         (ticker: string)  => api.get(`/companies/${ticker}/earnings`),
  technicals:       (ticker: string)  => api.get(`/companies/${ticker}/technicals`),
  news:             (ticker: string)  => api.get(`/companies/${ticker}/news`),
  analyst:          (ticker: string)  => api.get(`/companies/${ticker}/analyst`),
  executiveSummary: (ticker: string)  => api.get(`/companies/${ticker}/executive-summary`),
  videos:           (ticker: string)  => api.get(`/companies/${ticker}/videos`),
  intelligence:     (ticker: string, q?: string) =>
    api.get(`/companies/${ticker}/intelligence${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  chat:             (ticker: string, body: { question: string; top_k?: number }) =>
    api.post(`/companies/${ticker}/chat`, body),
};

// Videos
export const videoApi = {
  list:       (params: Record<string, string | number>) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString();
    return api.get(`/videos?${qs}`);
  },
  get:        (id: number)    => api.get(`/videos/${id}`),
  processUrl: (url: string)   => api.post(`/videos/process-url?url=${encodeURIComponent(url)}`),
  summary:    (id: number)    => api.get(`/videos/${id}/summary`),
  thesis:     (id: number)    => api.get(`/videos/${id}/thesis`),
  sentiment:  (id: number)    => api.get(`/videos/${id}/sentiment`),
  quotes:     (id: number)    => api.get(`/videos/${id}/quotes`),
  keyNumbers: (id: number)    => api.get(`/videos/${id}/key-numbers`),
  insights:   (id: number)    => api.get(`/videos/${id}/insights`),
  companies:  (id: number)    => api.get(`/videos/${id}/companies`),
  reprocess:  (id: number, fromStage = "TRANSCRIPT_PENDING") =>
    api.post(`/videos/${id}/reprocess?from_stage=${fromStage}`, undefined, ADMIN_HEADERS),
};

// Channels
export const channelApi = {
  list: (page = 1) => api.get(`/channels?page=${page}`),
  get:  (id: number) => api.get(`/channels/${id}`),
};

// Search
export const searchApi = {
  structured: (params: Record<string, string | number>) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString();
    return api.get(`/search?${qs}`);
  },
  semantic: (body: { query: string; top_k?: number; filters?: Record<string, unknown> }) =>
    api.post("/search/semantic", body),
};

// Chat
export const chatApi = {
  createSession: (body: { ticker?: string; watchlist_id?: number }) =>
    api.post("/chat/sessions", body),
  sendMessage:   (sessionId: string, body: { question: string; top_k?: number }) =>
    api.post(`/chat/sessions/${sessionId}/messages`, body),
  getSession:    (sessionId: string) => api.get(`/chat/sessions/${sessionId}`),
  getMessages:   (sessionId: string) => api.get(`/chat/sessions/${sessionId}/messages`),
};

// Analytics
export const analyticsApi = {
  trendingStocks:  (window = "7d")     => api.get(`/analytics/trending-stocks?window=${window}`),
  trendingSectors: (window = "7d")     => api.get(`/analytics/trending-sectors?window=${window}`),
  sentimentTicker: (ticker: string)    => api.get(`/analytics/sentiment/${ticker}`),
  sectorHeatmap:   (window = "7d")     => api.get(`/analytics/sector-heatmap?window=${window}`),
  creator:         (channelId: number) => api.get(`/analytics/creator/${channelId}`),
};

// Reports
export const reportApi = {
  latest: () => api.get("/reports/daily"),
  byDate: (date: string) => api.get(`/reports/daily/${date}`),
};

// Watchlist
export const watchlistApi = {
  list:       ()                     => api.get("/watchlists"),
  get:        (id: number)           => api.get(`/watchlists/${id}`),
  create:     (body: { name: string }) => api.post("/watchlists", body),
  addItem:    (id: number, ticker: string) => api.post(`/watchlists/${id}/items`, { ticker }),
  removeItem: (id: number, tickerId: number) => api.delete(`/watchlists/${id}/items/${tickerId}`),
  feed:       (id: number)           => api.get(`/watchlists/${id}/feed`),
};

// Admin — every route below requires X-Admin-Key.
export const adminApi = {
  pipelineStatus:   ()             => api.get("/admin/pipeline/status", ADMIN_HEADERS),
  pipelineFailures: ()             => api.get("/admin/pipeline/failures", ADMIN_HEADERS),
  retry:            (id: number)   => api.post(`/admin/pipeline/retry/${id}`, undefined, ADMIN_HEADERS),
  quota:            ()             => api.get("/admin/quota", ADMIN_HEADERS),
  taskLogs:         ()             => api.get("/admin/task-logs", ADMIN_HEADERS),
  schedulerJobs:    ()             => api.get("/scheduler/jobs", ADMIN_HEADERS),
  triggerJob:       (name: string) => api.post(`/scheduler/jobs/${name}/trigger`, undefined, ADMIN_HEADERS),
};

export { ApiError };
export const BASE = BASE_URL;
