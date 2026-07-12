# 從頭部署 Komorebi（免費方案）

目標：手機瀏覽器打開 `https://…` 就能用，**盡量 $0**。

建議組合：**GitHub → Render Free（後端）→ Vercel（前端）→ Supabase（已有）**

```text
你（手機） → Vercel 前端（免）
              → Render Free API（免，但會休眠）
              → Supabase / Gemini（你已有的免費額度）
```

整份約 30–60 分鐘。

### 免費要注意什麼

| 項目 | 說明 |
|------|------|
| Render Free | 約 **15 分鐘沒人用會睡**；下次打開可能要等 **30–60 秒** 才醒來 |
| 每月時數 | Free Web Service 有月用量上限（見 Render Billing）；個人學日文通常夠 |
| 不要用 | Render 免費 Postgres（會過期）— **繼續用 Supabase** |
| 不要用 Railway 當主方案 | 試用後幾乎要付錢；本文件以 Render 為主 |

---

## 開始前檢查

| 項目 | 狀態 |
|------|------|
| GitHub：`WuChYu07/Jp-learning` | 需已含 `backend/`、`frontend/` |
| Supabase、Gemini Key | 本機 `.env` 已有 |
| **不要** push `.env` | 密鑰只貼到 Render／Vercel 後台 |

程式若還沒上 GitHub，先 `git push`（排除 `.env`）。  
確認：https://github.com/WuChYu07/Jp-learning 看得到 `backend/`、`frontend/`。

---

## 第 1 步：準備環境變數（抄到記事本）

### 後端（從 `backend/.env`）

| 變數名 | 值 |
|--------|-----|
| `APP_ENV` | `production` |
| `DEBUG` | `false` |
| `CORS_ORIGINS` | 先填 `http://localhost:5173`（第 3 步再改成 Vercel 網址） |
| `SUPABASE_URL` | 同本機 |
| `SUPABASE_ANON_KEY` | 同本機 |
| `SUPABASE_SERVICE_ROLE_KEY` | 同本機（只給後端） |
| `GEMINI_API_KEY` | 同本機 |
| `GEMINI_MODEL` | 例如 `gemini-2.5-flash` |
| `AUTH_ENABLED` | `false`（單人） |
| `SSL_VERIFY` | `true` |

選填：`DEV_USER_ID`、`NOTION_TOKEN`、`NOTION_VOCAB_PAGE_ID`、`NOTION_GRAMMAR_PAGE_ID`

### 前端（從 `frontend/.env`）

| 變數名 | 值 |
|--------|-----|
| `VITE_SUPABASE_URL` | 同本機 |
| `VITE_SUPABASE_ANON_KEY` | publishable／anon（**不是** service role） |
| `VITE_API_BASE` | **第 2 步做完才有**（Render 網址，不要結尾 `/`） |

---

## 第 2 步：部署後端（Render Free）

### 2.1 註冊

1. 打開 https://render.com → 用 **GitHub** 登入  
2. 授權讀取 `Jp-learning`

### 2.2 建立 Web Service

1. **New +** → **Web Service**  
2. 連 `WuChYu07/Jp-learning`  
3. 設定：

| 欄位 | 填什麼 |
|------|--------|
| Name | 例如 `komorebi-api` |
| Region | 選離你近的（如 Singapore） |
| Root Directory | **`backend`** |
| Runtime | **Docker**（會用 repo 裡的 `backend/Dockerfile`） |
| Instance Type | **Free** |

若 Docker 建置失敗，可改 **Python**：

| 欄位 | 值 |
|------|-----|
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Root Directory | `backend` |

### 2.3 環境變數

**Environment** → 把第 1 步「後端」變數全部加上 → **Save**。

### 2.4 部署與健康檢查

1. 等第一次 Deploy 完成  
2. 上方會有網址，例如：  
   `https://komorebi-api.onrender.com`  
3. 瀏覽器開：  
   `https://komorebi-api.onrender.com/health`  

成功：

```json
{"status":"ok"}
```

失敗就看 **Logs**（常見：Root 不是 `backend`、漏環境變數）。

**把這個後端網址記下來。**  
若 `/health` 第一次很慢：多半是服務剛睡醒，等一下再重整。

---

## 第 3 步：部署前端（Vercel，免費）

### 3.1 匯入專案

1. https://vercel.com → GitHub 登入  
2. **Add New… → Project** → `Jp-learning`  
3. 設定：

| 欄位 | 值 |
|------|-----|
| Framework | Vite |
| Root Directory | **`frontend`** |
| Build Command | `npm run build` |
| Output Directory | `dist` |

### 3.2 環境變數（Build 前設定）

| Name | Value |
|------|--------|
| `VITE_API_BASE` | Render 網址，如 `https://komorebi-api.onrender.com`（無結尾 `/`） |
| `VITE_SUPABASE_URL` | 同本機 |
| `VITE_SUPABASE_ANON_KEY` | 同本機 |

勾選 **Production** → **Deploy**。

得到例如：`https://jp-learning-two.vercel.app/`

### 3.3 改後端 CORS（必做）

回 **Render → Environment**，把 `CORS_ORIGINS` 改成：

```text
CORS_ORIGINS=https://jp-learning-xxxx.vercel.app
```

（可同時保留本機：`https://….vercel.app,http://localhost:5173`）

存檔後觸發 **Manual Deploy → Clear build cache & deploy**（或等自動重啟）。

---

## 第 4 步：手機實測

1. 手機打開 **Vercel** 網址  
2. 測：Dashboard → 單字庫 → 單字卡 → 測驗  
3. iPhone：分享 → **加入主畫面**

**第一次很慢是正常的**（Render 冷啟動）。醒來後再操作會快很多。

---

## 出問題怎麼查

| 現象 | 怎麼辦 |
|------|--------|
| `/health` 一直轉圈 | 等 1 分鐘（冷啟動）；看 Render Logs |
| CORS error | `CORS_ORIGINS` 必須與網址列前端 origin 完全一致（含 `https://`） |
| 前端打不到 API | `VITE_API_BASE` 改完要在 Vercel **Redeploy** |
| 重整 `/vocab` 404 | 確認有 `frontend/vercel.json` |
| 月底服務被暫停 | Render Free 月時數用完；下月重置，或之後再考慮付費 |

---

## 之後更新程式

```powershell
git add …
git commit -m "…"
git push
```

Render／Vercel 連 GitHub 後通常會自動重新部署。  
只改 `VITE_*` 時，要在 Vercel 手動 **Redeploy**。

---

## 安全提醒

- Service Role、Gemini Key **只**放 Render Environment  
- 前端只放 Supabase publishable／anon  
- 不要 commit `.env`

---

## （可選）付費升級

若受不了冷啟動，再考慮：

- Render 付費 Instance（不休眠），或  
- Railway Hobby（約 $5／月）

目前以免費方案為準即可。
