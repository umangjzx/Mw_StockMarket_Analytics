import useSWR, { type SWRConfiguration } from "swr";
import {
  companyApi, videoApi, channelApi, analyticsApi,
  watchlistApi, adminApi, reportApi,
} from "@/lib/api";

const opts: SWRConfiguration = { revalidateOnFocus: false, dedupingInterval: 30_000 };
const liveOpts: SWRConfiguration = { ...opts, refreshInterval: 60_000 };

// ── Company Intelligence ──────────────────────────────────────────────────────
export const useCompanyOverview = (ticker?: string) =>
  useSWR(ticker ? `company-overview-${ticker}` : null, () => companyApi.overview(ticker!), opts);

export const useQuote = (ticker?: string) =>
  useSWR(ticker ? `quote-${ticker}` : null, () => companyApi.quote(ticker!), liveOpts);

export const useChart = (ticker?: string, range = "1M") =>
  useSWR(ticker ? `chart-${ticker}-${range}` : null, () => companyApi.chart(ticker!, range), opts);

export const useProfile = (ticker?: string) =>
  useSWR(ticker ? `profile-${ticker}` : null, () => companyApi.profile(ticker!), opts);

export const useRatios = (ticker?: string) =>
  useSWR(ticker ? `ratios-${ticker}` : null, () => companyApi.ratios(ticker!), opts);

export const useFinancials = (ticker?: string, type = "income", period = "annual") =>
  useSWR(
    ticker ? `financials-${ticker}-${type}-${period}` : null,
    () => companyApi.financials(ticker!, type, period),
    opts,
  );

export const useEarnings = (ticker?: string) =>
  useSWR(ticker ? `earnings-${ticker}` : null, () => companyApi.earnings(ticker!), opts);

export const useTechnicals = (ticker?: string) =>
  useSWR(ticker ? `technicals-${ticker}` : null, () => companyApi.technicals(ticker!), opts);

export const useNews = (ticker?: string) =>
  useSWR(ticker ? `news-${ticker}` : null, () => companyApi.news(ticker!), opts);

export const useAnalyst = (ticker?: string) =>
  useSWR(ticker ? `analyst-${ticker}` : null, () => companyApi.analyst(ticker!), opts);

export const useExecutiveSummary = (ticker?: string) =>
  useSWR(ticker ? `exec-summary-${ticker}` : null, () => companyApi.executiveSummary(ticker!), opts);

export const useCompanyVideos = (ticker?: string) =>
  useSWR(ticker ? `company-videos-${ticker}` : null, () => companyApi.videos(ticker!), opts);

export const useIntelligence = (ticker?: string, q?: string) =>
  useSWR(
    ticker ? `intelligence-${ticker}-${q ?? ""}` : null,
    () => companyApi.intelligence(ticker!, q),
    opts,
  );

// ── Videos ──────────────────────────────────────────────────────────────────
export const useVideos = (params: Record<string, string | number>) =>
  useSWR(`videos-${JSON.stringify(params)}`, () => videoApi.list(params), opts);

export const useVideo = (id?: number) =>
  useSWR(id != null ? `video-${id}` : null, () => videoApi.get(id!), opts);

// ── Channels ─────────────────────────────────────────────────────────────────
export const useChannels = (page = 1) =>
  useSWR(`channels-${page}`, () => channelApi.list(page), opts);

export const useChannel = (id?: number) =>
  useSWR(id != null ? `channel-${id}` : null, () => channelApi.get(id!), opts);

// ── Analytics ─────────────────────────────────────────────────────────────────
export const useTrendingStocks = (window = "7d") =>
  useSWR(`trending-stocks-${window}`, () => analyticsApi.trendingStocks(window), opts);

export const useTrendingSectors = (window = "7d") =>
  useSWR(`trending-sectors-${window}`, () => analyticsApi.trendingSectors(window), opts);

export const useSectorHeatmap = (window = "7d") =>
  useSWR(`sector-heatmap-${window}`, () => analyticsApi.sectorHeatmap(window), opts);

export const useSentimentTicker = (ticker?: string) =>
  useSWR(ticker ? `sentiment-${ticker}` : null, () => analyticsApi.sentimentTicker(ticker!), opts);

export const useCreatorStats = (channelId?: number, window = "30d") =>
  useSWR(
    channelId != null ? `creator-stats-${channelId}-${window}` : null,
    () => analyticsApi.creator(channelId!),
    opts,
  );

// ── Watchlist ─────────────────────────────────────────────────────────────────
export const useWatchlists = () =>
  useSWR("watchlists", () => watchlistApi.list(), opts);

export const useWatchlist = (id?: number) =>
  useSWR(id != null ? `watchlist-${id}` : null, () => watchlistApi.get(id!), opts);

export const useWatchlistFeed = (id?: number) =>
  useSWR(id != null ? `watchlist-feed-${id}` : null, () => watchlistApi.feed(id!), opts);

// ── Admin ─────────────────────────────────────────────────────────────────────
export const usePipelineStatus = () =>
  useSWR("pipeline-status", () => adminApi.pipelineStatus(), { ...liveOpts, refreshInterval: 30_000 });

export const usePipelineFailures = () =>
  useSWR("pipeline-failures", () => adminApi.pipelineFailures(), opts);

export const useSchedulerJobs = () =>
  useSWR("scheduler-jobs", () => adminApi.schedulerJobs(), opts);

export const useQuota = () =>
  useSWR("quota", () => adminApi.quota(), opts);

// ── Reports ───────────────────────────────────────────────────────────────────
export const useLatestReport = () =>
  useSWR("latest-report", () => reportApi.latest(), opts);
