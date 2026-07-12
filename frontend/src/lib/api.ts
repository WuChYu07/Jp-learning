const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export type ExampleSentence = {
  japanese: string;
  reading?: string;
  chinese?: string;
  /** Substring of japanese that is the target grammar form. */
  highlight?: string;
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
};

/** Lightweight list row from GET /vocab */
export type VocabularySummary = {
  id: string;
  word: string;
  reading?: string;
  jlpt_level: string;
  meaning_zh?: string | null;
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

export type TranslationGradeResult = {
  score: number;
  feedback: string;
  correction?: string;
  grammar_notes?: string;
};

export type IngestionResponse = {
  ingestion_id: string;
  content_hash: string;
  cached: boolean;
  vocabulary_count: number;
  grammar_count: number;
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
  definitions: Array<{
    part_of_speech?: string;
    meaning_zh: string;
  }>;
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
  sources: NotionPageSource[];
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
};

export type DashboardStats = {
  vocab_total: number;
  grammar_total: number;
  vocab_due_count: number;
  streak_days: number;
  daily_goal: number;
};

// ── Knowledge graph ──

export type LinkEntityType = "grammar" | "vocabulary" | "concept";

export type LinkRelationType =
  | "same_meaning"
  | "contrast"
  | "confusable"
  | "prerequisite"
  | "derived"
  | "example_vocab";

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

function formatApiError(body: string, statusText: string): string {
  try {
    const parsed = JSON.parse(body) as { detail?: string };
    if (typeof parsed.detail === "string") {
      return parsed.detail;
    }
  } catch {
    // not JSON
  }
  return body || statusText;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!headers.has("Content-Type") && init?.body) {
    headers.set("Content-Type", "application/json");
  }
  const token = localStorage.getItem("access_token");
  // Token optional — backend AUTH_ENABLED=false skips JWT verification
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
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
  dashboardStats: () => request<DashboardStats>("/api/v1/dashboard/stats"),
  listVocab: (params?: { jlpt?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.jlpt) q.set("jlpt", params.jlpt);
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
    request<Vocabulary>(`/api/v1/vocab/${id}/ai-enrich`, { method: "POST" }),
  dueVocab: (limit = 10, offset = 0) =>
    request<ReviewBatchResponse>(
      `/api/v1/vocab/review/due?limit=${limit}&offset=${offset}`,
    ),
  submitReview: (vocabulary_id: string, rating: string) =>
    request<{
      next_review_date: string;
      persisted?: boolean;
    }>("/api/v1/vocab/review", {
      method: "POST",
      body: JSON.stringify({ vocabulary_id, rating }),
    }),
  listGrammar: (params?: { jlpt?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.jlpt) q.set("jlpt", params.jlpt);
    if (params?.limit) q.set("limit", String(params.limit));
    const qs = q.toString();
    return request<{ items: GrammarSummary[]; total: number }>(
      `/api/v1/grammar${qs ? `?${qs}` : ""}`,
    );
  },
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
    ),
  aiExplainGrammar: (id: string, dryRun = true) =>
    request<Grammar>(
      `/api/v1/grammar/${id}/ai-explain?dry_run=${dryRun ? "true" : "false"}`,
      { method: "POST" },
    ),

  // ── Quiz ──
  quiz4Choice: (count = 10) =>
    request<QuizBatchResponse>(`/api/v1/quiz/vocab?count=${count}`),
  translationPrompts: (count = 5) =>
    request<TranslationBatchResponse>(
      `/api/v1/quiz/translation/prompts?count=${count}`,
    ),
  gradeTranslation: (source_zh: string, user_answer: string, hint_word?: string) =>
    request<TranslationGradeResult>("/api/v1/quiz/translation/grade", {
      method: "POST",
      body: JSON.stringify({ source_zh, user_answer, hint_word }),
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

    const res = await fetch(
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
  ) =>
    request<NotionSyncPreview | IngestionResponse>("/api/v1/notion/sync", {
      method: "POST",
      body: JSON.stringify({ focus, page_id: pageId || null, upload_images: uploadImages }),
    }),

  notionConfirm: (
    parsed: NotionSyncPreview["parsed"],
    content_hash: string,
    page_id: string,
    page_title?: string,
    focus: "vocabulary" | "grammar" | "both" = "both",
  ) =>
    request<IngestionResponse>("/api/v1/notion/confirm", {
      method: "POST",
      body: JSON.stringify({ parsed, content_hash, page_id, page_title, focus }),
    }),

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
  }) => {
    const q = new URLSearchParams();
    if (params?.entity_types) q.set("entity_types", params.entity_types);
    if (params?.jlpt) q.set("jlpt", params.jlpt);
    if (params?.relation_types) q.set("relation_types", params.relation_types);
    if (params?.limit) q.set("limit", String(params.limit));
    const qs = q.toString();
    return request<RelationGraph>(`/api/v1/graph${qs ? `?${qs}` : ""}`);
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
  syncExampleVocab: (grammarId: string) =>
    request<{ created: number; skipped: number; matched_words: string[] }>(
      `/api/v1/graph/sync-example-vocab/grammar/${grammarId}`,
      { method: "POST" },
    ),
};
