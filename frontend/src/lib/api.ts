import {
  ApiWakeError,
  fetchWithRetry,
  formatApiError,
  formatUserFacingError,
} from "./apiTransport";

export { ApiWakeError, formatUserFacingError };

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export type ExampleSentence = {
  japanese: string;
  reading?: string;
  chinese?: string;
  /** Legacy single substring of japanese that is the target grammar form. */
  highlight?: string;
  /** Substrings of japanese that are the target grammar form(s). */
  highlights?: string[];
};

export type MeaningBlock = {
  text: string;
  variant: "emphasis" | "note" | "caution" | "default";
};

export type SupplementaryBlock = {
  title: string;
  summary_zh: string;
  example_sentences: ExampleSentence[];
};

export type VocabDefinition = {
  id: string;
  sort_order: number;
  part_of_speech: string;
  meaning_zh: string;
  example_sentences: ExampleSentence[];
  notes_zh?: string | null;
};

export type Vocabulary = {
  id: string;
  word: string;
  reading?: string;
  jlpt_level: string;
  definitions: VocabDefinition[];
  review_score?: number | null;
};

/** Lightweight list row from GET /vocab */
export type VocabularySummary = {
  id: string;
  word: string;
  reading?: string;
  jlpt_level: string;
  meaning_zh?: string | null;
  review_score?: number | null;
};

export type ReviewScoreResult = {
  vocabulary_id: string;
  review_score: number;
  review_points: number;
  score_delta: number;
  points_delta: number;
  viewed_bonus_applied: boolean;
};

export type ExamAttemptResult = {
  id: string;
  subject: string;
  mode: string;
  correct_count: number;
  total_count: number;
  score_percent: number;
  completed_at: string;
};

export type VocabularyWriteInput = {
  word: string;
  reading?: string;
  jlpt_level: string;
  meaning_zh: string;
  part_of_speech: string;
  example_sentences: ExampleSentence[];
  notes_zh?: string;
};

export type GrammarUsage = {
  id: string;
  sort_order: number;
  semantic_concept: string;
  connection_rule: string;
  meaning_zh?: string;
  meaning_blocks?: MeaningBlock[];
  example_sentences: ExampleSentence[];
};

export type Grammar = {
  id: string;
  grammar_point: string;
  jlpt_level: string;
  usages: GrammarUsage[];
  image_urls?: string[];
  supplementary_blocks?: SupplementaryBlock[];
  sync_status?: "synced" | "needs_ai" | "archived";
  needs_enrichment?: boolean;
  manual_edited?: boolean;
};

/** Lightweight list row from GET /grammar */
export type GrammarSummary = {
  id: string;
  grammar_point: string;
  jlpt_level: string;
  usage_count?: number;
  image_count?: number;
  sync_status?: "synced" | "needs_ai" | "archived";
  needs_enrichment?: boolean;
  manual_edited?: boolean;
};

export type GrammarUsageWrite = {
  semantic_concept: string;
  connection_rule: string;
  meaning_zh?: string;
  example_sentences: ExampleSentence[];
};

export type GrammarWriteInput = {
  grammar_point: string;
  jlpt_level: string;
  usages: GrammarUsageWrite[];
};

export type ReviewBatchResponse = {
  items: Vocabulary[];
  has_more: boolean;
  next_offset: number;
  total: number;
};

// ── Quiz types ──

export type ChoiceOption = {
  id: string;
  text: string;
};

export type FourChoiceQuestion = {
  question_id: string;
  word: string;
  reading?: string;
  prompt: string;
  mode: string;
  options: ChoiceOption[];
  correct_option_id: string;
};

export type QuizBatchResponse = {
  questions: FourChoiceQuestion[];
  total_available: number;
};

export type TranslationPrompt = {
  question_id: string;
  source_zh: string;
  source_en?: string;
  hint_word: string;
  hint_reading?: string;
};

export type TranslationBatchResponse = {
  prompts: TranslationPrompt[];
  total_available: number;
};

export type ClozeQuestion = {
  question_id: string;
  subject: "vocab" | "grammar" | string;
  entity_id: string;
  sentence_blanked: string;
  sentence_full: string;
  sentence_reading?: string | null;
  sentence_zh?: string | null;
  blank_answer: string;
  prompt: string;
  options: ChoiceOption[];
  correct_option_id: string;
};

export type ClozeBatchResponse = {
  questions: ClozeQuestion[];
  total_available: number;
};

export type TranslationGradeResult = {
  score: number;
  feedback: string;
  correction?: string;
  grammar_notes?: string;
};

export type PracticeHint = {
  kind: "vocab" | "grammar" | string;
  label: string;
  detail?: string | null;
};

export type PracticePrompt = {
  mode: "speak" | "hint_translate" | string;
  topic: string;
  prompt_zh?: string | null;
  prompt_ja?: string | null;
  hints: PracticeHint[];
  daily_ai_limit_reached?: boolean;
  forced_grammar?: string | null;
};

export type PracticeGradeResult = {
  id: string;
  score: number;
  feedback_zh: string;
  model_answer?: string | null;
  daily_ai_limit_reached?: boolean;
};

export type PracticeDialogue = {
  id: string;
  mode: string;
  topic?: string | null;
  prompt_zh?: string | null;
  prompt_ja?: string | null;
  user_answer: string;
  score?: number | null;
  feedback_zh?: string | null;
  model_answer?: string | null;
  hints_json?: PracticeHint[];
  created_at: string;
};

export type SongCandidate = {
  marumaru_id: string;
  title: string;
  artist: string;
  source_url: string;
  release_date?: string | null;
  category?: string | null;
  cached_song_id?: string | null;
  cached_status?: string | null;
};

export type SongLine = {
  id?: string | null;
  line_no: number;
  text_ja: string;
  text_zh?: string | null;
  grammar_zh?: string | null;
  note_zh?: string | null;
  jlpt_hints?: string[];
};

export type SongDetail = {
  id: string;
  title: string;
  artist: string;
  release_date?: string | null;
  marumaru_id?: string | null;
  source_url?: string | null;
  category?: string | null;
  difficulty?: number | null;
  youtube_url?: string | null;
  status: string;
  lyrics_source?: string | null;
  zh_source?: string | null;
  overview_zh?: string | null;
  error_message?: string | null;
  fetched_at?: string | null;
  enriched_at?: string | null;
  created_at?: string | null;
  lines: SongLine[];
};

export type SongListItem = {
  id: string;
  title: string;
  artist: string;
  status: string;
  marumaru_id?: string | null;
  source_url?: string | null;
  enriched_at?: string | null;
  updated_at?: string | null;
  line_count: number;
};

export type SongHistoryItem = {
  song_id: string;
  title: string;
  artist: string;
  status: string;
  last_opened_at: string;
};

export type SyncReport = {
  vocab_source_rows: number;
  vocab_new: number;
  vocab_updated: number;
  vocab_skipped: number;
  vocab_dedupe_removed: number;
  grammar_source_rows: number;
  grammar_new: number;
  grammar_updated: number;
  grammar_skipped: number;
  grammar_dedupe_removed: number;
};

export type IngestionResponse = {
  ingestion_id: string;
  content_hash: string;
  cached: boolean;
  vocabulary_count: number;
  grammar_count: number;
  report?: SyncReport | null;
};

export type TextParsePreview = {
  parsed: unknown;
  content_hash: string;
  vocabulary_count: number;
  grammar_count: number;
};

export type NotionGrammarItem = {
  grammar_point: string;
  jlpt_level?: string;
  image_urls?: string[];
  notion_block_id?: string;
  source_content_hash?: string;
  sync_change?: "new" | "updated" | "unchanged";
  force_overwrite?: boolean;
  usages: Array<{
    semantic_concept: string;
    connection_rule: string;
    meaning_zh?: string;
    example_sentences?: ExampleSentence[];
  }>;
};

export type NotionVocabItem = {
  word: string;
  reading?: string;
  sync_change?: "new" | "updated" | "unchanged";
  vocab_id?: string;
  current_meaning_zh?: string;
  current_notes_zh?: string;
  current_example_sentences?: ExampleSentence[];
  definitions: Array<{
    part_of_speech?: string;
    meaning_zh: string;
    example_sentences?: ExampleSentence[];
    notes_zh?: string;
  }>;
};

export type NotionOrphanedGrammar = {
  id: string;
  grammar_point: string;
  notion_block_id?: string;
  notion_page_id?: string;
};

export type NotionOrphanedVocab = {
  id: string;
  word: string;
  reading?: string;
  notion_page_id?: string;
};

export type NotionUnclassifiedHeading = {
  notion_block_id: string;
  heading_text: string;
};

export type NotionPageSource = {
  focus: "vocabulary" | "grammar";
  page_id: string;
  page_title: string;
  content_hash: string;
  last_edited_time?: string;
  image_count: number;
  section_count: number;
};

export type NotionSyncPreview = {
  focus: "vocabulary" | "grammar" | "both";
  page_id: string;
  page_title: string;
  content_hash: string;
  last_edited_time?: string;
  parsed: {
    vocabularies: NotionVocabItem[];
    grammars: NotionGrammarItem[];
  };
  vocabulary_count: number;
  grammar_count: number;
  image_count: number;
  section_count: number;
  orphan_image_count: number;
  unchanged: boolean;
  grammar_new_count: number;
  grammar_updated_count: number;
  grammar_unchanged_count: number;
  vocab_new_count: number;
  vocab_updated_count: number;
  vocab_unchanged_count: number;
  orphaned_grammars: NotionOrphanedGrammar[];
  orphaned_vocabularies: NotionOrphanedVocab[];
  unclassified_headings: NotionUnclassifiedHeading[];
  sources: NotionPageSource[];
};

export type NotionScheduledCheck = {
  checked_at: string;
  has_changes: boolean;
  grammar_new_count: number;
  grammar_updated_count: number;
  vocab_new_count: number;
  vocab_updated_count: number;
  orphaned_grammar_count: number;
  orphaned_vocab_count: number;
  unclassified_count: number;
  error: string | null;
};

export type NotionSyncStatus = {
  synced: boolean;
  last_synced_at?: string;
  pages?: Array<{
    page_id: string;
    page_title?: string;
    focus?: string;
    last_synced_at?: string;
    grammar_count?: number;
    vocabulary_count?: number;
    image_count?: number;
  }>;
  scheduled_check?: NotionScheduledCheck | null;
};

export type DashboardStats = {
  vocab_total: number;
  grammar_total: number;
  vocab_due_count: number;
  grammar_due_count: number;
  streak_days: number;
  daily_goal: number;
  reviewed_today: number;
  review_points: number;
  review_score_avg: number;
  exam_vocab_avg: number | null;
  exam_grammar_avg: number | null;
  exam_vocab_count: number;
  exam_grammar_count: number;
};

export type DailyReviewCount = {
  date: string;
  count: number;
};

export type JlptMastery = {
  jlpt_level: string;
  total: number;
  reviewed: number;
  avg_score: number;
};

export type DashboardTrends = {
  daily_counts: DailyReviewCount[];
  vocab_jlpt: JlptMastery[];
  grammar_jlpt: JlptMastery[];
};

export type GrammarReviewBatchResponse = {
  items: Grammar[];
  has_more: boolean;
  next_offset: number;
  total: number;
};

export type JlptSuggestion = {
  entity: "vocab" | "grammar";
  id: string;
  label: string;
  detail?: string;
  current: string;
  suggested_jlpt: string;
};

export type JlptPreviewResponse = {
  items: JlptSuggestion[];
  remaining_unknown: number;
};

// ── Knowledge graph ──

export type LinkEntityType = "grammar" | "vocabulary" | "concept";

export type LinkRelationType =
  | "same_meaning"
  | "contrast"
  | "confusable"
  | "prerequisite"
  | "derived";

export type GraphNode = {
  id: string;
  type: LinkEntityType;
  label: string;
  jlpt_level?: string;
  group?: string;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  relation_type: LinkRelationType;
  label_zh?: string;
  note_zh?: string;
  confidence?: number;
};

export type RelationGraph = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  center_id: string;
};

export type SuggestedLink = {
  target_type: LinkEntityType;
  target_id?: string;
  target_label: string;
  relation_type: LinkRelationType;
  label_zh?: string;
  note_zh?: string;
  confidence: number;
};

export type SuggestLinksResponse = {
  suggestions: SuggestedLink[];
  center_id: string;
  center_label: string;
};

export type ContentLinkCreate = {
  source_type: LinkEntityType;
  source_id: string;
  target_type: LinkEntityType;
  target_id: string;
  relation_type: LinkRelationType;
  label_zh?: string;
  note_zh?: string;
  confidence?: number;
  origin?: string;
  bidirectional?: boolean;
};

export type ContentLink = ContentLinkCreate & {
  id: string;
};

async function request<T>(
  path: string,
  init?: RequestInit,
  transportOpts?: { timeoutMs?: number; maxAttempts?: number; wakeMessage?: string },
): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!headers.has("Content-Type") && init?.body) {
    headers.set("Content-Type", "application/json");
  }
  const token = localStorage.getItem("access_token");
  // AUTH_ENABLED=false skips per-user JWT verification, but every /api/v1
  // route still sits behind the site-wide login gate (see /auth/login) —
  // this same header carries that gate's token too.
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const res = await fetchWithRetry(`${API_BASE}${path}`, { ...init, headers }, transportOpts);
  // A 401 from the login call itself just means "wrong password" — let it fall
  // through to the normal error path below instead of bouncing back to /login.
  if (res.status === 401 && path !== "/api/v1/auth/login") {
    localStorage.removeItem("access_token");
    if (!window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
    throw new Error("請重新登入");
  }
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(formatApiError(detail, res.statusText));
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export const api = {
  login: (password: string) =>
    request<{ token: string }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),
  dashboardStats: () => request<DashboardStats>("/api/v1/dashboard/stats"),
  dashboardTrends: (days = 14) =>
    request<DashboardTrends>(`/api/v1/dashboard/trends?days=${days}`),
  listVocab: (params?: { jlpt?: string; q?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.jlpt) q.set("jlpt", params.jlpt);
    if (params?.q) q.set("q", params.q);
    if (params?.limit) q.set("limit", String(params.limit));
    if (params?.offset) q.set("offset", String(params.offset));
    const qs = q.toString();
    return request<{
      items: VocabularySummary[];
      total: number;
      limit: number;
      offset: number;
    }>(`/api/v1/vocab${qs ? `?${qs}` : ""}`);
  },
  getVocab: (id: string) => request<Vocabulary>(`/api/v1/vocab/${id}`),
  updateVocab: (id: string, payload: VocabularyWriteInput) =>
    request<Vocabulary>(`/api/v1/vocab/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  aiEnrichVocab: (id: string) =>
    request<Vocabulary>(
      `/api/v1/vocab/${id}/ai-enrich`,
      { method: "POST" },
      // Structured Gemini generation can legitimately take longer than the
      // default 45s; a retry here just restarts the same slow call.
      { timeoutMs: 5 * 60_000, maxAttempts: 1 },
    ),
  addVocabExampleFromPractice: (id: string, japanese: string, chinese?: string | null) =>
    request<Vocabulary>(`/api/v1/vocab/${id}/examples/from-practice`, {
      method: "POST",
      body: JSON.stringify({ japanese, chinese: chinese ?? null }),
    }),
  deleteVocab: (id: string) =>
    request<void>(`/api/v1/vocab/${id}`, { method: "DELETE" }),
  dueVocab: (limit = 10, offset = 0) =>
    request<ReviewBatchResponse>(
      `/api/v1/vocab/review/due?limit=${limit}&offset=${offset}`,
    ),
  submitReview: (vocabulary_id: string, rating: string) =>
    request<{
      next_review_date: string;
      persisted?: boolean;
      review_score?: number;
      review_points?: number;
      score_delta?: number;
      points_delta?: number;
    }>("/api/v1/vocab/review", {
      method: "POST",
      body: JSON.stringify({ vocabulary_id, rating }),
    }),
  randomVocab: (params?: { exclude_id?: string; jlpt?: string }) => {
    const q = new URLSearchParams();
    if (params?.exclude_id) q.set("exclude_id", params.exclude_id);
    if (params?.jlpt) q.set("jlpt", params.jlpt);
    const qs = q.toString();
    return request<Vocabulary>(`/api/v1/vocab/random${qs ? `?${qs}` : ""}`);
  },
  recordVocabView: (id: string) =>
    request<ReviewScoreResult>(`/api/v1/vocab/${id}/view`, { method: "POST" }),
  listGrammar: (params?: { jlpt?: string; q?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.jlpt) q.set("jlpt", params.jlpt);
    if (params?.q) q.set("q", params.q);
    if (params?.limit) q.set("limit", String(params.limit));
    const qs = q.toString();
    return request<{ items: GrammarSummary[]; total: number }>(
      `/api/v1/grammar${qs ? `?${qs}` : ""}`,
    );
  },
  dueGrammar: (limit = 10, offset = 0) =>
    request<GrammarReviewBatchResponse>(
      `/api/v1/grammar/review/due?limit=${limit}&offset=${offset}`,
    ),
  randomGrammar: (params?: { exclude_id?: string; jlpt?: string }) => {
    const q = new URLSearchParams();
    if (params?.exclude_id) q.set("exclude_id", params.exclude_id);
    if (params?.jlpt) q.set("jlpt", params.jlpt);
    const qs = q.toString();
    return request<Grammar>(`/api/v1/grammar/random${qs ? `?${qs}` : ""}`);
  },
  submitGrammarReview: (grammar_id: string, rating: string) =>
    request<{
      next_review_date: string;
      persisted?: boolean;
      review_score?: number;
      review_points?: number;
      score_delta?: number;
      points_delta?: number;
    }>("/api/v1/grammar/review", {
      method: "POST",
      body: JSON.stringify({ grammar_id, rating }),
    }),
  getGrammar: (id: string) => request<Grammar>(`/api/v1/grammar/${id}`),
  createGrammar: (payload: GrammarWriteInput) =>
    request<Grammar>("/api/v1/grammar", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateGrammar: (id: string, payload: GrammarWriteInput) =>
    request<Grammar>(`/api/v1/grammar/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteGrammar: (id: string) =>
    request<void>(`/api/v1/grammar/${id}`, { method: "DELETE" }),
  enrichGrammar: (id: string, dryRun = true) =>
    request<Grammar>(
      `/api/v1/grammar/${id}/enrich-image?dry_run=${dryRun ? "true" : "false"}`,
      { method: "POST" },
      { timeoutMs: 5 * 60_000, maxAttempts: 1 },
    ),
  aiExplainGrammar: (id: string, dryRun = true) =>
    request<Grammar>(
      `/api/v1/grammar/${id}/ai-explain?dry_run=${dryRun ? "true" : "false"}`,
      { method: "POST" },
      { timeoutMs: 5 * 60_000, maxAttempts: 1 },
    ),
  addGrammarExampleFromPractice: (id: string, japanese: string, chinese?: string | null) =>
    request<Grammar>(`/api/v1/grammar/${id}/examples/from-practice`, {
      method: "POST",
      body: JSON.stringify({ japanese, chinese: chinese ?? null }),
    }),

  // ── Quiz ──
  quiz4Choice: (count = 10) =>
    request<QuizBatchResponse>(`/api/v1/quiz/vocab?count=${count}`),
  quizGrammar4Choice: (count = 10) =>
    request<QuizBatchResponse>(`/api/v1/quiz/grammar?count=${count}`),
  quizCloze: (count = 10, subject: "vocab" | "grammar" | "both" = "both") =>
    request<ClozeBatchResponse>(
      `/api/v1/quiz/cloze?count=${count}&subject=${subject}`,
    ),
  translationPrompts: (count = 5) =>
    request<TranslationBatchResponse>(
      `/api/v1/quiz/translation/prompts?count=${count}`,
    ),
  jlptPreview: (entity: "vocab" | "grammar" | "both" = "both", limit = 20) =>
    request<JlptPreviewResponse>("/api/v1/jlpt/preview", {
      method: "POST",
      body: JSON.stringify({ entity, limit }),
    }),
  jlptApply: (
    items: Array<{ entity: "vocab" | "grammar"; id: string; jlpt_level: string }>,
  ) =>
    request<{ updated: number }>("/api/v1/jlpt/apply", {
      method: "POST",
      body: JSON.stringify({ items }),
    }),
  gradeTranslation: (source_zh: string, user_answer: string, hint_word?: string) =>
    request<TranslationGradeResult>("/api/v1/quiz/translation/grade", {
      method: "POST",
      body: JSON.stringify({ source_zh, user_answer, hint_word }),
    }),
  submitQuizResult: (payload: {
    subject: "vocab" | "grammar";
    mode: string;
    correct_count: number;
    total_count: number;
    detail?: Record<string, unknown>;
  }) =>
    request<ExamAttemptResult>("/api/v1/quiz/results", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // ── Upload ──
  uploadFile: async (
    file: File,
    focus: "vocabulary" | "grammar" | "both" = "both",
  ): Promise<IngestionResponse> => {
    const form = new FormData();
    form.append("file", file);

    const headers = new Headers();
    const token = localStorage.getItem("access_token");
    if (token) headers.set("Authorization", `Bearer ${token}`);

    const res = await fetchWithRetry(
      `${API_BASE}/api/v1/ingestion/upload?focus=${focus}`,
      { method: "POST", headers, body: form },
    );
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(detail || res.statusText);
    }
    return res.json() as Promise<IngestionResponse>;
  },

  parseText: (text: string, focus: "vocabulary" | "grammar" | "both" = "both") =>
    request<TextParsePreview>("/api/v1/ingestion/text/parse", {
      method: "POST",
      body: JSON.stringify({ text, focus }),
    }),

  confirmTextImport: (parsed: unknown, content_hash: string, focus: "vocabulary" | "grammar" | "both" = "both") =>
    request<IngestionResponse>("/api/v1/ingestion/text/confirm", {
      method: "POST",
      body: JSON.stringify({ parsed, content_hash, focus }),
    }),

  notionSync: (
    focus: "vocabulary" | "grammar" | "both" = "both",
    pageId?: string,
    uploadImages = true,
    forceRefresh = false,
  ) =>
    request<NotionSyncPreview | IngestionResponse>(
      "/api/v1/notion/sync",
      {
        method: "POST",
        body: JSON.stringify({
          focus,
          page_id: pageId || null,
          upload_images: uploadImages,
          force_refresh: forceRefresh,
        }),
      },
      {
        // Notion pages with thousands of blocks are rate-limited on Notion's
        // side and can take minutes to fetch in full; one long attempt beats
        // three short ones that all restart the same expensive work.
        timeoutMs: 30 * 60_000,
        maxAttempts: 1,
        wakeMessage:
          "同步逾時。若 Notion 頁面資料量很大，首次或有大量變更時可能需要數分鐘，請稍後再試一次；若持續逾時請確認後端狀態。",
      },
    ),

  notionConfirm: (
    parsed: NotionSyncPreview["parsed"],
    content_hash: string,
    page_id: string,
    page_title?: string,
    focus: "vocabulary" | "grammar" | "both" = "both",
    options?: {
      force?: boolean;
      force_overwrite_grammar_block_ids?: string[];
      archive_grammar_ids?: string[];
      archive_vocab_ids?: string[];
      vocab_field_overwrites?: Record<string, string[]>;
    },
  ) =>
    request<IngestionResponse>(
      "/api/v1/notion/confirm",
      {
        method: "POST",
        body: JSON.stringify({
          parsed,
          content_hash,
          page_id,
          page_title,
          focus,
          force: options?.force ?? false,
          force_overwrite_grammar_block_ids:
            options?.force_overwrite_grammar_block_ids ?? [],
          archive_grammar_ids: options?.archive_grammar_ids ?? [],
          archive_vocab_ids: options?.archive_vocab_ids ?? [],
          vocab_field_overwrites: options?.vocab_field_overwrites ?? {},
        }),
      },
      {
        timeoutMs: 30 * 60_000,
        maxAttempts: 1,
        wakeMessage:
          "匯入逾時。項目較多時可能需要數分鐘，請稍後再試一次；若持續逾時請確認後端狀態。",
      },
    ),

  notionStatus: () => request<NotionSyncStatus>("/api/v1/notion/status"),

  // ── Knowledge graph ──
  getGrammarRelations: (id: string, depth = 1) =>
    request<RelationGraph>(`/api/v1/grammar/${id}/relations?depth=${depth}`),
  getVocabRelations: (id: string, depth = 1) =>
    request<RelationGraph>(`/api/v1/vocab/${id}/relations?depth=${depth}`),
  getGlobalGraph: (params?: {
    entity_types?: string;
    jlpt?: string;
    relation_types?: string;
    limit?: number;
    min_confidence?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.entity_types) q.set("entity_types", params.entity_types);
    if (params?.jlpt) q.set("jlpt", params.jlpt);
    if (params?.relation_types) q.set("relation_types", params.relation_types);
    if (params?.limit) q.set("limit", String(params.limit));
    if (params?.min_confidence != null) {
      q.set("min_confidence", String(params.min_confidence));
    }
    const qs = q.toString();
    return request<RelationGraph>(`/api/v1/graph${qs ? `?${qs}` : ""}`);
  },
  pruneWeakLinks: (min_confidence?: number) => {
    const q = new URLSearchParams();
    if (min_confidence != null) q.set("min_confidence", String(min_confidence));
    const qs = q.toString();
    return request<{
      ok: boolean;
      min_confidence: number;
      scanned: number;
      removed: number;
    }>(`/api/v1/graph/prune-weak${qs ? `?${qs}` : ""}`, { method: "POST" });
  },
  recomputeSemanticLinks: (params?: {
    entity_types?: string;
    limit?: number;
    force?: boolean;
    scope?: "recent" | "all_new";
  }) => {
    const q = new URLSearchParams();
    if (params?.entity_types) q.set("entity_types", params.entity_types);
    if (params?.limit) q.set("limit", String(params.limit));
    if (params?.force) q.set("force", "true");
    if (params?.scope) q.set("scope", params.scope);
    const qs = q.toString();
    return request<{
      ok: boolean;
      scope: string;
      threshold: number;
      entities: number;
      links_created: number;
      links_updated: number;
      links_removed: number;
      failed: number;
    }>(
      `/api/v1/graph/recompute-semantic${qs ? `?${qs}` : ""}`,
      { method: "POST" },
      // "all_new" can process many entities in one call — give it real headroom.
      params?.scope === "all_new" ? { timeoutMs: 10 * 60_000, maxAttempts: 1 } : undefined,
    );
  },
  suggestGrammarLinks: (id: string) =>
    request<SuggestLinksResponse>(`/api/v1/grammar/${id}/suggest-links`, {
      method: "POST",
    }),
  syncGrammarSemanticLinks: (id: string) =>
    request<{
      ok: boolean;
      links_created?: number;
      links_updated?: number;
      links_removed?: number;
      skipped_embed?: boolean;
      reason?: string;
    }>(`/api/v1/grammar/${id}/sync-semantic-links`, { method: "POST" }),
  syncVocabSemanticLinks: (id: string) =>
    request<{
      ok: boolean;
      links_created?: number;
      links_updated?: number;
      links_removed?: number;
    }>(`/api/v1/vocab/${id}/sync-semantic-links`, { method: "POST" }),
  getForceGraph: (params?: {
    entity_types?: string;
    jlpt?: string;
    limit?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.entity_types) q.set("entity_types", params.entity_types);
    if (params?.jlpt) q.set("jlpt", params.jlpt);
    if (params?.limit) q.set("limit", String(params.limit));
    const qs = q.toString();
    return request<{
      nodes: Array<{ id: string; label: string; group?: string }>;
      links: Array<{ source: string; target: string; value: number }>;
    }>(`/api/v1/graph/force${qs ? `?${qs}` : ""}`);
  },
  createLink: (payload: ContentLinkCreate) =>
    request<ContentLink>("/api/v1/graph/links", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  confirmLinks: (source_type: LinkEntityType, source_id: string, links: ContentLinkCreate[]) =>
    request<{ created: ContentLink[]; skipped: number }>("/api/v1/graph/links/confirm", {
      method: "POST",
      body: JSON.stringify({ source_type, source_id, links }),
    }),
  deleteLink: (id: string) =>
    request<void>(`/api/v1/graph/links/${id}`, { method: "DELETE" }),

  // ── AI practice ──
  practiceSession: (
    mode: "speak" | "hint_translate",
    topic: "daily" | "academic" | "travel" | "work" | "random" = "random",
    grammarId?: string,
    vocabId?: string,
  ) =>
    request<PracticePrompt>("/api/v1/practice/session", {
      method: "POST",
      body: JSON.stringify({
        mode,
        topic,
        grammar_id: grammarId ?? null,
        vocab_id: vocabId ?? null,
      }),
    }),
  practiceGrade: (payload: {
    mode: "speak" | "hint_translate" | string;
    topic?: string | null;
    prompt_zh?: string | null;
    prompt_ja?: string | null;
    user_answer: string;
    hints?: PracticeHint[];
  }) =>
    request<PracticeGradeResult>("/api/v1/practice/grade", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  practiceHistory: (limit = 20) =>
    request<PracticeDialogue[]>(`/api/v1/practice/history?limit=${limit}`),

  // ── Songs (MARUMARU + AI) ──
  searchSongs: (q: string, limit = 12) =>
    request<SongCandidate[]>(`/api/v1/songs/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  recommendSongs: (limit = 10) =>
    request<SongCandidate[]>(`/api/v1/songs/recommend?limit=${limit}`),
  listSongs: (limit = 30) => request<SongListItem[]>(`/api/v1/songs?limit=${limit}`),
  songHistory: (limit = 15) =>
    request<SongHistoryItem[]>(`/api/v1/songs/history?limit=${limit}`),
  getSong: (id: string) => request<SongDetail>(`/api/v1/songs/${id}`),
  selectSong: (payload: {
    marumaru_id?: string | null;
    source_url?: string | null;
    title?: string | null;
    artist?: string | null;
    paste_ja?: string | null;
    paste_zh?: string | null;
    enrich?: boolean;
  }) =>
    request<SongDetail>("/api/v1/songs/select", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // ── Backup ──
  /** URL for the full-data JSON backup; browser handles the download natively
   * (Content-Disposition: attachment), so a multi-MB payload never needs to
   * pass through a JS fetch/blob round trip. */
  exportBackupUrl: () => `${API_BASE}/api/v1/export`,

  // ── Speech ──
  /** Gemini-generated speech, cached in Supabase Storage by (voice, text) hash. */
  getSpeechUrl: (text: string, voice?: string) =>
    request<{ url: string }>("/api/v1/speech", {
      method: "POST",
      body: JSON.stringify({ text, voice }),
    }),
  listVoices: () =>
    request<{ voices: { name: string; style: string }[] }>("/api/v1/speech/voices"),
};
