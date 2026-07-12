# Komorebi Japanese — 日文學習 Web App

自帶筆記、自帶資料庫、自帶 Gemini Key 的日文學習工具。  
單字／文法來自 **Notion 筆記或 CSV**，支援複習、測驗、語意關聯圖譜，以及 **AI 草稿 → 小視窗確認後才寫入**。

**設計理念：** 每個使用者擁有自己的 Supabase 與 Gemini API Key，資料與額度都在自己手上。

---

## 功能總覽

| 功能 | 說明 |
|------|------|
| **單字庫** | 列表摘要＋詳情（單字／發音／中文／例句／補充）；手修與 AI 補充皆經確認小視窗 |
| **單字卡複習** | 滑動字卡（不熟／熟悉），SM-2 間隔重複 |
| **文法中心** | 多用法、接續、例句、圖片；手修／AI 解釋／從圖片補全 → 確認後才套用 |
| **知識圖譜** | 文法／單字關聯網絡；語意向量（Gemini embedding）可重算連邊 |
| **四選一測驗** | 讀音／意思隨機出題 |
| **翻譯測驗** | 中文→日文，Gemini 批改評分 |
| **資料匯入** | Notion 同步（不耗 AI）、CSV、文字貼上（AI）、PDF／圖片上傳 |
| **Dashboard** | 學習統計與入口 |

---

## 本機 Quick Start

### 1. Supabase（免費）

1. 建立專案：[supabase.com](https://supabase.com)
2. SQL Editor **依序**執行 `backend/migrations/`：
   - `001_initial_schema.sql` … 到 `009_vocab_notes.sql`  
   （已有專案可只補尚未執行的 migration）
3. 取得 **Project URL**、**Publishable（anon）Key**、**Secret（service_role）Key**

### 2. Gemini API Key

1. [Google AI Studio](https://aistudio.google.com/apikey)
2. 建議模型：`gemini-2.5-flash`（見 `backend/.env.example`）

### 3. 環境變數

```powershell
# Backend
copy backend\.env.example backend\.env
# 填入 Supabase、Gemini；單人模式可 AUTH_ENABLED=false

# Frontend
copy frontend\.env.example frontend\.env
# VITE_SUPABASE_* ；本機 VITE_API_BASE 留空（走 Vite proxy）
```

### 4. 啟動

```powershell
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend（另一個 terminal）
cd frontend
npm install
npm run dev
```

| 服務 | URL |
|------|-----|
| Frontend | http://localhost:5173 |
| API docs | http://localhost:8000/docs |
| Health | http://localhost:8000/health |

### 5. 匯入資料（擇一）

```powershell
cd backend
# Notion：在 App「匯入」頁做同步預覽 → 確認（需 NOTION_*）
# 或 CSV 種子
python scripts/load_curated.py
# 或極小測試集
python scripts/seed_test_data.py
```

Notion 單字表預期欄位：**發音｜單字｜中文｜例句｜補充**（見 parser）。

---

## 雲端部署（手機可用）— 免費方案

**GitHub → Render Free（後端）→ Vercel（前端）**，Supabase 繼續用現有免費專案。

完整逐步教學：

→ **[docs/deploy-a.md](docs/deploy-a.md)**

重點：

1. 程式已在 GitHub（勿 push `.env`）
2. Render：Root = `backend`，Instance = **Free**，設環境變數，測 `/health`
3. Vercel：Root = `frontend`，設 `VITE_API_BASE`＝Render 網址
4. 後端 `CORS_ORIGINS` 改成前端 `https://…`
5. 第一次開啟可能較慢（Render 約 15 分鐘閒置會睡，冷啟動 30–60 秒）

產品方向與待辦：

→ **[docs/roadmap.md](docs/roadmap.md)**

---

## AI Token 消耗

| 功能 | 觸發 | 約略消耗 |
|------|------|----------|
| 翻譯測驗批改 | 提交答案 | 低～中 |
| 單字／文法 AI 補充或解釋 | 按 AI、產生草稿 | 中（確認前不寫 DB） |
| 語意關聯／embedding | 同步或重算 | 中～高（批次時） |
| 文字貼上／PDF／圖片解析 | 匯入 | 中～高 |

**通常不耗 Gemini：** 單字卡、四選一、CSV、Notion 規則解析、瀏覽列表／詳情、Dashboard。

額度請看 [Google AI Studio](https://aistudio.google.com/)。改模型只需在後端環境變數設 `GEMINI_MODEL`。

---

## 專案結構

```
jp-learning/
├── backend/
│   ├── app/
│   │   ├── api/v1/           # vocab, grammar, quiz, notion, links, …
│   │   ├── core/             # config, security, HTTP
│   │   ├── db/               # Supabase
│   │   ├── models/schemas/
│   │   └── services/         # SRS, Notion, enrichment, embeddings, …
│   ├── migrations/           # 001–009
│   ├── scripts/              # load_curated, seed, pipeline, backfill…
│   ├── Dockerfile            # Render / Railway 用
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/       # 字卡、關聯圖、編輯小視窗…
│   │   ├── pages/            # Dashboard, Vocab, Review, Grammar, Quiz, Map, Upload
│   │   └── lib/              # api.ts, supabase, vocabDisplay
│   ├── vercel.json
│   └── package.json
├── render.yaml               # （可選）Render Blueprint
├── data/
│   ├── curated/              # vocabulary.csv, grammar.csv（可 seed）
│   └── README.md             # 本機 PDF 管線說明（PDF 不進 git）
├── docs/
│   ├── deploy-a.md           # 雲端從頭部署
│   ├── roadmap.md            # 待辦與手機策略
│   ├── performance.md        # 效能問題日誌
│   └── ui-blueprints/        # 早期設計稿
└── README.md
```

---

## 環境變數摘要

### Backend（`backend/.env`）

| 變數 | 必填 | 說明 |
|------|------|------|
| `SUPABASE_URL` | ✅ | 專案 URL |
| `SUPABASE_ANON_KEY` | ✅ | Publishable key |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | Secret key（僅後端） |
| `GEMINI_API_KEY` | ✅ | Gemini |
| `GEMINI_MODEL` | — | 預設見 `.env.example` |
| `CORS_ORIGINS` | ✅（雲端） | 逗號分隔前端 origin |
| `AUTH_ENABLED` | — | `false`＝單人；`true`＝要 JWT |
| `DEV_USER_ID` | — | 可留空；單人模式自動用內建 owner id |
| `NOTION_TOKEN` / `NOTION_*_PAGE_ID` | — | Notion 同步 |

### Frontend（`frontend/.env`）

| 變數 | 必填 | 說明 |
|------|------|------|
| `VITE_SUPABASE_URL` | 建議 | 同後端 URL |
| `VITE_SUPABASE_ANON_KEY` | 建議 | Publishable only |
| `VITE_API_BASE` | 雲端必填 | 本機可空；正式站填後端 `https://…`（無結尾 `/`） |

完整範例見 `backend/.env.example`、`frontend/.env.example`。

---

## Tech Stack

| 層 | 技術 |
|----|------|
| Frontend | React 19 · Vite 6 · Tailwind CSS 4 · React Router |
| Backend | FastAPI · Uvicorn · Pydantic |
| Data | Supabase（PostgreSQL + Auth／Storage） |
| AI | Google Gemini（生成＋ embedding） |
| SRS | SM-2 |
| Deploy | **Render Free**（API）· **Vercel**（前端）· Supabase |

---

## 文件索引

| 文件 | 內容 |
|------|------|
| [docs/deploy-a.md](docs/deploy-a.md) | 免費雲端部署逐步教學（Render + Vercel） |
| [docs/roadmap.md](docs/roadmap.md) | 產品待辦、手機使用策略 |
| [docs/performance.md](docs/performance.md) | 效能問題紀錄（如 list N+1） |
| [data/README.md](data/README.md) | 本機 PDF→CSV 資料管線 |

---

## License

MIT
