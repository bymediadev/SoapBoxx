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

export type EpisodesPage = {
  episodes: LibraryEpisode[];
  total: number;
  limit: number;
  offset: number;
  podcast_id?: number | null;
  status?: string | null;
};

export type PodcastSearchHit = {
  collection_id: number;
  name: string;
  artist: string;
  rss_url: string;
  artwork_url?: string | null;
  genre?: string | null;
  episode_count?: number | null;
};

export type PodcastSearchResponse = {
  query: string;
  results: PodcastSearchHit[];
};

export type ProcessBatchResult = {
  requested: number;
  attempted: number;
  succeeded: number;
  failed: number;
  results: unknown[];
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

/** Seven Layer-1 metrics — same shape as GET /episodes/{id}/features */
export type EpisodeFeatures = {
  episode_id: number;
  hook_length_seconds?: number | null;
  intro_length_seconds?: number | null;
  question_count?: number | null;
  speaking_turns?: number | null;
  host_guest_ratio?: number | null;
  topic_shift_count?: number | null;
  cta_present?: boolean | null;
};

/** True when `api()` threw for HTTP 404 (optional GETs). */
export function isNotFoundError(err: unknown): boolean {
  return err instanceof Error && /\b404\b/.test(err.message);
}

export type CoachingMetricRow = {
  metric: string;
  value: string;
  benchmark?: string | null;
  coaching?: string | null;
};

export type TemplatePlaybook = {
  template_id: string;
  form: string;
  tagline: string;
  feels_like: string;
  review_these: string[];
  how_its_built: string[];
  trade_offs: string[];
  leverage_points: string[];
  similar_form: string;
};

export type NarrativeEngineMap = {
  timeline: {
    time_seconds: number;
    time_label: string;
    event_type: string;
    label: string;
    detail: string;
  }[];
  open_loops: {
    opened_at: number;
    opened_label: string;
    closed_at?: number | null;
    closed_label?: string | null;
    lifespan_seconds?: number | null;
    lifespan_label: string;
    snippet: string;
    status: string;
  }[];
  engine_notes: string[];
};

export type ProducerNotes = {
  bullets: string[];
  metrics: { metric: string; value: string; note?: string | null }[];
  edit_flags: string[];
};

export type AudioEventType =
  | "energy_spike"
  | "energy_drop"
  | "silence_cluster"
  | "pace_shift";

export type AudioEvent = {
  timestamp: number;
  type: AudioEventType;
  intensity: number;
  window_start?: number;
  window_end?: number;
  time_label?: string;
  label?: string;
};

export type ProducerView = {
  layers: string[];
  structural_identity: string[];
  leverage_points: string[];
  motion_track: AudioEvent[];
  motion_notes: string[];
  fusion_notes: string[];
  transcript_limitations: string[];
  audio_available: boolean;
};

export type MeasurementStamp = {
  feature_schema_version: string;
  extraction_version: string;
  aggregation_version: string;
};

export type CoachingReport = {
  structural_identity: string[];
  leverage_points: string[];
  episode_structure: CoachingMetricRow[];
  conversation_dynamics: CoachingMetricRow[];
  listener_experience: string[];
  compared_with_library: string[];
  editorial_tradeoffs: string[];
  structural_variance: string[];
  template_playbook?: TemplatePlaybook | null;
  what_this_means: string[];
  similar_to?: string | null;
  topic_shift_note?: string | null;
  measurement_stamp?: MeasurementStamp | null;
  measurement_cohort_note?: string | null;
  transcript_limitations?: string[];
  narrative_engine?: NarrativeEngineMap | null;
  producer_notes?: ProducerNotes | null;
  producer_view?: ProducerView | null;
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
  libraryEpisodes: (
    opts?: { limit?: number; offset?: number; podcast_id?: number; status?: string }
  ) => {
    const params = new URLSearchParams();
    params.set("limit", String(opts?.limit ?? 50));
    params.set("offset", String(opts?.offset ?? 0));
    if (opts?.podcast_id != null) params.set("podcast_id", String(opts.podcast_id));
    if (opts?.status) params.set("status", opts.status);
    return api<EpisodesPage>(`/library/episodes?${params.toString()}`);
  },

  processNextBatch: (limit = 10) =>
    api<ProcessBatchResult>(`/pipeline/process?limit=${limit}`, { method: "POST" }),

  pipelineStatus: () =>
    api<{ processing_count: number; by_status: Record<string, number> }>(
      "/pipeline/status"
    ),

  activity: (limit = 20) =>
    api<ActivityEvent[]>(`/system/activity?limit=${limit}`),

  weeklyPatterns: () => api<WeeklyPatterns>("/insights/patterns/weekly"),

  /** Search podcasts by name; each hit includes rss_url for ingestRss(). */
  searchPodcasts: (q: string, limit = 15) =>
    api<PodcastSearchResponse>(
      `/ingest/podcasts/search?q=${encodeURIComponent(q)}&limit=${limit}`
    ),

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

  /** 404 if features not extracted yet — do not call processEpisode just to read metrics. */
  getEpisodeFeatures: (id: number) => api<EpisodeFeatures>(`/episodes/${id}/features`),

  episodeState: (id: number) => api<EpisodeState>(`/episodes/${id}/state`),

  /** 404 if episode has not been translated yet. */
  getTranslation: (id: number) => api<TranslationDetail>(`/episodes/${id}/translation`),

  /** Layer 4A — curated producer view (no schema/cohort/percentile noise). */
  getProducerReport: (id: number) =>
    api<{
      episode_id: number;
      title: string;
      disclaimer: string;
      transcript_warning?: { code: string; message: string } | null;
      structure_label: string;
      template_id: string;
      measurements: EpisodeFeatures;
      editorial_readout: {
        what_happening: string[];
        why_it_matters: string[];
        what_to_try_next: string[];
      };
      transcript_limitations: string[];
    }>(`/episodes/${id}/report/producer`),

  /** Layer 4B — next-episode actions (editorial coach). */
  getActionsReport: (id: number) =>
    api<{
      episode_id: number;
      title: string;
      transcript_warning?: { code: string; message: string } | null;
      actions: { id: string; category: string; priority: string; text: string }[];
      keep_patterns: string[];
    }>(`/episodes/${id}/report/actions`),

  /**
   * Run pipeline: skip STT if transcript exists unless force_retranscribe.
   * Default body {} — Railway-safe (fast).
   */
  processEpisode: (id: number, body?: { transcript?: string; force_retranscribe?: boolean }) =>
    api<ProcessEpisodeResult>(`/episodes/${id}/process`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),

  /** Layer 2 — optional audio motion extraction (parallel to transcript pipeline). */
  extractAudioMotion: (id: number) =>
    api<void>(`/episodes/${id}/audio-motion`, { method: "POST" }),

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
