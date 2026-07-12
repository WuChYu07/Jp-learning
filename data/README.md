# Komorebi 資料管線

功能開發暫緩，優先處理**筆記資料品質**。

## 流程

```
data/vocabulary.pdf ─┐
                       ├─► Agent 1 ─► data/extracted/*_raw.csv
data/grammar.pdf ─────┘
                              │
                              ▼
                         Agent 2 (teacher agent, 不用 Gemini)
                              │
                              ▼
                    data/curated/vocabulary.csv
                    data/curated/grammar.csv
                              │
                              ▼ (之後)
                         load_curated.py → Supabase
```

## 執行

```powershell
cd backend
.\.venv\Scripts\Activate.ps1

# 僅處理資料
python scripts/run_data_pipeline.py

# 清空 DB 學習內容 + 處理資料
python scripts/run_data_pipeline.py --clear-db
```

## Gemini 用途

- **不用於**筆記補齊（由 Agent 2 本機日文老師邏輯處理）
- **保留給**使用者測驗評分（Module 4）

## 欄位說明

見 `data/curated/*.csv` 表頭。`confidence < 0.6` 建議人工複查。

資料儲存邏輯

flowchart TD
    A[Notion 筆記更新] --> B{L1: 頁面 last_edited_time 變了?}
    B -->|否| Z[完全跳過]
    B -->|是| C[Fetch blocks 免費]
    C --> D[L2: 切分成文法單元<br/>每單元算 content_hash]
    D --> E{與 DB 比對}
    E -->|新| F[insert]
    E -->|內容變| G[update + 標記需 AI]
    E -->|不變| H[跳過]
    E -->|Notion 已刪| I[標記 archived]
    F --> J{L3: 需 AI?}
    G --> J
    H --> K[不呼叫 AI]
    J -->|新圖 / hash 變 / 未 enriched| L[只對這幾筆跑 AI]
    J -->|已 enriched 且內容同| K

L1 — 頁面級（最便宜）
用 Notion page 的 last_edited_time。

沒變 → 直接結束
有變 → 才 fetch blocks
這層幾乎零成本，我們 preview 裡已有類似邏輯。

L2 — 文法單元級（核心）
Parser 切出來的每個文法點，當成一個 sync unit，建議欄位：

notion_block_id     ← 標題那個 heading 的 block id（穩定主鍵）
grammar_point       ← 顯示用標題
source_page_id
block_ids[]         ← 此單元涵蓋的所有 block id
content_hash        ← hash(標題 + 內文 + 圖片 url 列表)
image_urls[]
sync_status         ← synced | needs_ai | archived
ai_content_hash     ← 上次送 AI 時的 hash（判斷要不要重跑）
content_hash 怎麼算：

hash(grammar_point + 所有 text_lines + image_urls 排序後拼接)

比對結果：

狀態	條件	DB 動作	AI
新增
notion_block_id 不在 DB
insert
要（若有圖或需補充）
更新
id 在，但 content_hash 變了
update 原文/圖
僅當 content_hash ≠ ai_content_hash
不變
hash 相同
跳過
不呼叫
刪除
DB 有但這次 parse 沒出現
archived
不呼叫
為什麼用 notion_block_id 而不是只用標題？
標題可能改（て形 → て形（活用）），block id 在 Notion 裡通常不變。
標題 hash（現有 grammar_entry_hash）適合去重，不適合追蹤更新。

L3 — AI 級（最貴，要最嚴格）
只有這些情況才送 Gemini：

新文法單元 且 jlpt_level 還是 unknown / 有圖待 OCR
content_hash 變了 且和 ai_content_hash 不同
使用者手動點「重新 AI 校正」
其餘（純文字微調、錯字）可選擇只更新 DB、不跑 AI。

圖片怎麼避免重複存？
image block id → 已上傳過？
  ├─ 是 → 重用 Supabase URL
  └─ 否 → 下載上傳，記錄 notion_image_id → storage_url
可加一張 notion_images 對照表，避免每次 sync 重傳 680 張圖。

