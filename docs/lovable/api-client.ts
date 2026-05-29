/**
 * SoapBoxx V1 API client — paste into Lovable as src/lib/soapboxx-api.ts
 *
 * Default: Railway production (no Lovable Secrets required).
 * Local: add .env with VITE_API_URL=http://127.0.0.1:8000 (see .env.lovable.example).
 * Also copy vite-env.d.ts into src/lib/ (or remove the /// reference below if Vite types are global).
 */

/// <reference path="./vite-env.d.ts" />

export const PRODUCTION_API = "https://soapboxx-production.up.railway.app";
export const LOCAL_API = "http://127.0.0.1:8000";

/** Active base URL — swap to LOCAL_API for local-only testing without .env */
export const SOAPBOXX_API_BASE = (
  import.meta.env.VITE_API_URL?.trim() || PRODUCTION_API
).replace(/\/$/, "");

const API = SOAPBOXX_API_BASE;

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${path}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export type LibraryStats = {
  episodes_total: number;
  shows_total: number;
  domains_total: number;
  measured_count: number;
  measured_pct: number;
  queued_count: number;
  processing_count: number;
};

export type LibraryEpisode = {
  id: number;
  podcast_id: number;
  podcast_name: string;
  title: string;
  description?: string | null;
  audio_url?: string | null;
  published_at?: string | null;
  status: string;
};

export type ActivityEvent = {
  id: number;
  event_type: string;
  message: string;
  podcast_id?: number;
  episode_id?: number;
  created_at: string;
};

export type WeeklyPatterns = {
  period_days: number;
  episodes_ingested: number;
  episodes_measured: number;
  patterns: { id: string; label: string; detail: string }[];
  summary: string;
};

export type LibraryHome = {
  stats: LibraryStats;
  pipeline: { processing_count: number; by_status: Record<string, number> };
  tree: unknown[];
  episodes: LibraryEpisode[];
  activity: ActivityEvent[];
  patterns: WeeklyPatterns;
};

export type EpisodeState = {
  episode_id: number;
  podcast_id: number;
  podcast_name: string;
  title: string;
  status: string;
  pipeline_error?: string | null;
  steps: {
    ingested: boolean;
    transcribed: boolean;
    measured: boolean;
    insight_ready: boolean;
  };
  next_action?: string | null;
};

export type Podcast = {
  id: number;
  name: string;
  description?: string | null;
  rss_url?: string | null;
  created_at: string;
};

export type EpisodeDetail = {
  id: number;
  podcast_id: number;
  title: string;
  description?: string | null;
  audio_url?: string | null;
  full_transcript?: string | null;
  pipeline_status: string;
};

export type CoachingMetricRow = {
  metric: string;
  value: string;
  benchmark?: string | null;
  coaching?: string | null;
};

export type CoachingReport = {
  episode_structure: CoachingMetricRow[];
  conversation_dynamics: CoachingMetricRow[];
  listener_experience: string[];
  compared_with_library: string[];
  editorial_tradeoffs: string[];
  structural_variance: string[];
  what_this_means: string[];
  similar_to?: string | null;
  topic_shift_note?: string | null;
};

export type TranslationDetail = {
  episode_id: number;
  template_id: string;
  insight_text: string;
  report?: CoachingReport | null;
};

export type ProcessEpisodeResult = {
  episode_id: number;
  status: string;
  steps: Array<Record<string, unknown>>;
  transcript_length: number;
  segment_count: number;
  template_id?: string;
  insight_preview?: string;
  transcript_source?: "existing" | "stt" | "pasted";
};

export const soapboxxApi = {
  health: () => api<{ status: string; database?: unknown; redis?: unknown }>("/health"),

  /** One round-trip for library home (preferred for home screen). */
  libraryHome: (activityLimit = 20, episodesLimit = 25) =>
    api<LibraryHome>(
      `/library/home?activity_limit=${activityLimit}&episodes_limit=${episodesLimit}`
    ),

  libraryStats: () => api<LibraryStats>("/library/stats"),
  libraryTree: () => api<unknown[]>("/library/tree"),
  libraryEpisodes: (limit = 20) =>
    api<LibraryEpisode[]>(`/library/episodes?limit=${limit}`),

  pipelineStatus: () =>
    api<{ processing_count: number; by_status: Record<string, number> }>(
      "/pipeline/status"
    ),

  activity: (limit = 20) =>
    api<ActivityEvent[]>(`/system/activity?limit=${limit}`),

  weeklyPatterns: () => api<WeeklyPatterns>("/insights/patterns/weekly"),

  ingestRss: (rss_url: string) =>
    api<{
      podcast_id: number;
      episodes_created: number;
      episodes_skipped: number;
      episodes_dispatched: number;
      episode_ids: number[];
    }>("/ingest/rss", {
      method: "POST",
      body: JSON.stringify({ rss_url }),
    }),

  /** All shows (podcasts) — use for shows index when not using tree-only navigation. */
  listPodcasts: () => api<Podcast[]>("/podcasts"),

  getEpisode: (id: number) => api<EpisodeDetail>(`/episodes/${id}`),

  episodeState: (id: number) => api<EpisodeState>(`/episodes/${id}/state`),

  /** 404 if episode has not been translated yet. */
  getTranslation: (id: number) => api<TranslationDetail>(`/episodes/${id}/translation`),

  /**
   * Run pipeline: skip STT if transcript exists unless force_retranscribe.
   * Default body {} — Railway-safe (fast).
   */
  processEpisode: (id: number, body?: { transcript?: string; force_retranscribe?: boolean }) =>
    api<ProcessEpisodeResult>(`/episodes/${id}/process`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),

  /** Process up to `limit` episodes missing translation (max 10). */
  processQueued: (limit = 1) =>
    api<{
      requested: number;
      attempted: number;
      succeeded: number;
      failed: number;
      results: unknown[];
    }>(`/pipeline/process?limit=${limit}`, { method: "POST" }),
};
