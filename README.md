# Komorebi Japanese — 日文學習 Web App

一個開源的日文學習工具，支援單字卡複習、四選一測驗、AI 翻譯批改、自訂學習資料匯入。

**設計理念：** 每個使用者帶自己的 Supabase 資料庫和 Gemini API Key，擁有自己的 Komorebi。

---

## Quick Start

### 1. 建立 Supabase 專案（免費）

1. 前往 [supabase.com](https://supabase.com) 建立帳號和專案
2. 進入 SQL Editor，執行 `backend/migrations/001_initial_schema.sql`
3. 從 Settings → API 取得：
   - **Project URL** (`https://xxx.supabase.co`)
   - **Anon Key** (`sb_publishable_...`)
   - **Service Role Key** (`sb_secret_...`)

### 2. 取得 Gemini API Key

1. 前往 [Google AI Studio](https://aistudio.google.com/apikey) 建立免費 API Key
2. 免費方案限制：15 RPM / 100 萬 tokens/天（[詳細額度](https://ai.google.dev/pricing)）
3. 也可以使用付費方案以獲得更高額度和更強的模型

### 3. 設定環境變數

```bash
# Backend
cp backend/.env.example backend/.env
# 編輯 backend/.env，填入你的 Supabase 和 Gemini 資訊

# Frontend
cp frontend/.env.example frontend/.env
# 編輯 frontend/.env，填入 Supabase URL 和 Anon Key
```

### 4. 啟動

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend（另一個 terminal）
cd frontend
npm install
npm run dev
```

- Frontend: http://localhost:5173
- Backend API docs: http://localhost:8000/docs

### 5. 匯入學習資料

```bash
# 匯入範例 CSV 資料（558 單字 + 280 文法）
cd backend
python scripts/load_curated.py

# 或只匯入種子測試資料（5 單字 + 4 文法）
python scripts/seed_test_data.py
```

---

## 功能總覽

| 功能 | 說明 |
|------|------|
| **單字卡複習** | 滑動式字卡，左滑不熟 / 右滑熟悉，SM-2 間隔重複演算法 |
| **文法中心** | 瀏覽文法句型、接續規則、多個用法與例句 |
| **四選一測驗** | 隨機出題，交替測讀音和意思 |
| **翻譯測驗** | 中文→日文翻譯，Gemini AI 即時批改評分 |
| **資料匯入** | 支援 CSV 上傳、文字貼上（AI 解析）、PDF/圖片上傳 |
| **Dashboard** | 學習統計、進度追蹤 |

---

## ⚠️ AI Token 消耗說明

本 App 使用 **Google Gemini API** 處理以下功能，每次呼叫都會消耗你的 API 額度：

| 功能 | 觸發時機 | 預估消耗 |
|------|----------|----------|
| **翻譯測驗批改** | 每次提交翻譯答案 | ~200-500 tokens/次 |
| **文字貼上解析** | 貼上筆記文字並送出解析 | ~500-2000 tokens/次（依文字量） |
| **PDF/圖片上傳** | 上傳檔案自動解析 | ~1000-5000 tokens/次（圖片更貴） |

**不消耗 Token 的功能：**
- 單字卡複習（純本地 / 資料庫操作）
- 四選一測驗（從資料庫出題）
- CSV 匯入（純格式解析，不呼叫 AI）
- 文法瀏覽
- Dashboard

### 免費額度建議

Gemini Free Tier（`gemini-2.0-flash`）每天約 100 萬 tokens，正常學習使用綽綽有餘。如果你大量上傳 PDF 或頻繁使用翻譯測驗，建議留意 [Google AI Studio](https://aistudio.google.com/) 的用量儀表板。

### 使用付費模型

如果你想使用更強的模型（如 `gemini-2.5-pro`），只需在 `backend/.env` 修改：

```env
GEMINI_API_KEY=your-paid-api-key
GEMINI_MODEL=gemini-2.5-pro
```

---

## 專案結構

```
komorebi/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API routes (vocab, grammar, quiz, ingestion, dashboard)
│   │   ├── core/            # Config, security, HTTP client
│   │   ├── db/              # Supabase client
│   │   ├── models/schemas/  # Pydantic models
│   │   └── services/        # Business logic (SRS, quiz, ingestion, Gemini)
│   ├── migrations/          # SQL schema
│   ├── scripts/             # CLI tools (seed, load CSV, data pipeline)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # SwipeFlashcard, Layout
│   │   ├── pages/           # Dashboard, Vocab, Grammar, Quiz, Upload
│   │   └── lib/             # API client, Supabase client
│   └── package.json
├── data/
│   ├── curated/             # Cleaned CSV data (vocabulary.csv, grammar.csv)
│   └── extracted/           # Raw extracted data
└── docs/ui-blueprints/      # Design system & HTML mockups
```

---

## 環境變數

### Backend (`backend/.env`)

| 變數 | 必填 | 說明 |
|------|------|------|
| `SUPABASE_URL` | ✅ | 你的 Supabase 專案 URL |
| `SUPABASE_ANON_KEY` | ✅ | Supabase Publishable Key |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | Supabase Secret Key（僅後端使用） |
| `GEMINI_API_KEY` | ✅ | Google Gemini API Key |
| `GEMINI_MODEL` | — | 預設 `gemini-2.0-flash`，可改為付費模型 |
| `AUTH_ENABLED` | — | `false`（單人模式） / `true`（多使用者） |
| `DEV_USER_ID` | — | 單人模式下的 Supabase User UUID（選填） |
| `SSL_VERIFY` | — | Windows 本地開發設 `false` |

### Frontend (`frontend/.env`)

| 變數 | 必填 | 說明 |
|------|------|------|
| `VITE_SUPABASE_URL` | — | 同 backend（登入功能用，目前未啟用） |
| `VITE_SUPABASE_ANON_KEY` | — | 同 backend |
| `VITE_API_BASE` | — | 留空即可（Vite proxy 到 :8000） |

---

## Tech Stack

- **Frontend:** React 19 + Vite 6 + Tailwind CSS 4
- **Backend:** Python FastAPI + Supabase (PostgreSQL)
- **AI:** Google Gemini API (使用者自帶 Key)
- **SRS:** SM-2 Spaced Repetition Algorithm

---

## 效能與問題紀錄

頁面載入慢、關聯跳轉慢等問題的根因與解法，集中寫在：

→ **[docs/performance.md](docs/performance.md)**

之後若再遇到效能議題，請依該檔頂部的格式追加一筆，方便回頭對照「遇過什麼、為什麼、怎麼解」。

## 產品待辦與手機部署

功能 backlog、優先順序，以及「要在手機上用」的部署建議：

→ **[docs/roadmap.md](docs/roadmap.md)**

**方案 A（已選定）上線步驟：**

→ **[docs/deploy-a.md](docs/deploy-a.md)**

---

## License

MIT
