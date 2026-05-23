/**
 * SoapBoxx V1 API client — paste into Lovable as src/lib/soapboxx-api.ts
 *
 * Default: Railway production (no Lovable Secrets required).
 * Local: add .env with VITE_API_URL=http://127.0.0.1:8000 (see .env.lovable.example).
 * Or change SOAPBOXX_API_BASE below to LOCAL_API before pasting.
 */

/// <reference path="./vite-env.d.ts" />

export const PRODUCTION_API = "https://soapboxx-production.up.railway.app";
export const LOCAL_API = "http://127.0.0.1:8000";

/** Active base URL — swap to LOCAL_API for local-only testing without .env */
export const SOAPBOXX_API_BASE =
  (import.meta.env.VITE_API_URL?.trim() || PRODUCTION_API).replace(/\/$/, "");

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
  episodes: unknown[];
  activity: ActivityEvent[];
  patterns: WeeklyPatterns;
};

export const soapboxxApi = {
  health: () => api<{ status: string }>("/health"),
  /** One round-trip for library home (faster than 5+ separate GETs). */
  libraryHome: (activityLimit = 20, episodesLimit = 25) =>
    api<LibraryHome>(
      `/library/home?activity_limit=${activityLimit}&episodes_limit=${episodesLimit}`
    ),
  libraryStats: () => api<LibraryStats>("/library/stats"),
  libraryTree: () => api<unknown[]>("/library/tree"),
  libraryEpisodes: (limit = 20) =>
    api<unknown[]>(`/library/episodes?limit=${limit}`),
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
    }>("/ingest/rss", {
      method: "POST",
      body: JSON.stringify({ rss_url }),
    }),
  episodeState: (id: number) => api<unknown>(`/episodes/${id}/state`),
  /** Transcribe → 7 metrics → template insight (one episode). */
  processEpisode: (
    id: number,
    body?: { transcript?: string; force_retranscribe?: boolean }
  ) =>
    api<{
      episode_id: number;
      status: string;
      template_id?: string;
      insight_preview?: string;
      steps: unknown[];
    }>(`/episodes/${id}/process`, {
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
