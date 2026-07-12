# 從頭部署 Komorebi（方案 A）

目標：手機瀏覽器打開一個 `https://…` 網址就能用。

建議組合：**GitHub → Railway（後端）→ Vercel（前端）**

```text
你（手機） → Vercel 前端 → Railway API → Supabase / Gemini
```

整份做完大約 30–60 分鐘（含申請帳號）。

---

## 開始前檢查

| 項目 | 你這邊 |
|------|--------|
| GitHub repo | 已有：`WuChYu07/Jp-learning` |
| 本機能跑前後端 | 建議先確認 |
| Supabase | 已有專案與 Key |
| Gemini Key | 已有 |
| **程式碼已 push 到 GitHub** | ⚠ 若 `backend/`、`frontend/` 還在本機未推送，雲端讀不到，**一定要先做第 1 步** |

**絕對不要**把 `backend/.env`、`frontend/.env` 推上 GitHub（裡面有密鑰）。

---

## 第 1 步：把程式推上 GitHub

在專案根目錄（PowerShell）：

```powershell
cd D:\Dev\jp-learning
git status
```

若看到 `backend/`、`frontend/`、`docs/` 是未追蹤（`??`），需要先提交再推送。

可請 Cursor 幫你 commit，或自己執行（**不要** `git add` 任何 `.env`）：

```powershell
git add README.md docs backend frontend
git status
# 確認沒有 .env、.cursor 被加進去
git commit -m "Add app and Option A deploy scaffolding"
git push -u origin main
```

到瀏覽器打開：  
https://github.com/WuChYu07/Jp-learning  

確認看得到資料夾：`backend/`、`frontend/`、`docs/deploy-a.md`。

---

## 第 2 步：準備要貼的環境變數（先抄在記事本）

### 後端用（從本機 `backend/.env` 複製）

| 變數名 | 值從哪來 |
|--------|----------|
| `APP_ENV` | 填 `production` |
| `DEBUG` | 填 `false` |
| `CORS_ORIGINS` | **先**填 `http://localhost:5173`（第 4 步再改） |
| `SUPABASE_URL` | `backend/.env` |
| `SUPABASE_ANON_KEY` | `backend/.env` |
| `SUPABASE_SERVICE_ROLE_KEY` | `backend/.env`（只給後端） |
| `GEMINI_API_KEY` | `backend/.env` |
| `GEMINI_MODEL` | 例如 `gemini-2.5-flash` |
| `AUTH_ENABLED` | 單人可先 `false` |
| `SSL_VERIFY` | `true` |

選填：`DEV_USER_ID`、`NOTION_TOKEN`、`NOTION_VOCAB_PAGE_ID`、`NOTION_GRAMMAR_PAGE_ID`

### 前端用（從本機 `frontend/.env` 複製）

| 變數名 | 值從哪來 |
|--------|----------|
| `VITE_SUPABASE_URL` | `frontend/.env` |
| `VITE_SUPABASE_ANON_KEY` | `frontend/.env`（publishable／anon，**不是** service role） |
| `VITE_API_BASE` | **第 3 步做完才有**（Railway 網址，不要結尾 `/`） |

---

## 第 3 步：部署後端（Railway）

### 3.1 註冊並連 GitHub

1. 打開 https://railway.app → 用 **GitHub** 登入  
2. 授權 Railway 讀取 `Jp-learning`（或整個帳號）

### 3.2 建立專案

1. **New Project** → **Deploy from GitHub repo**  
2. 選 `WuChYu07/Jp-learning`  
3. 若問 Root Directory／哪個服務：選或稍後設定為 **`backend`**

### 3.3 確認用 Docker／正確目錄

在該 Service 的 **Settings**：

- **Root Directory**：`backend`  
- 有 `Dockerfile` 時 Railway 通常會自動用 Docker build  

若改成不用 Docker，Start Command 設：

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### 3.4 貼環境變數

**Variables** → 逐一新增第 2 步「後端用」那些（可 Raw Editor 一次貼多行 `KEY=value`）。

### 3.5 公開網址

1. **Settings → Networking → Generate Domain**  
2. 會得到類似：  
   `https://xxxxx.up.railway.app`  
3. 用電腦瀏覽器開：  
   `https://xxxxx.up.railway.app/health`  

成功應看到：

```json
{"status":"ok"}
```

若失敗：看 **Deployments → Logs**（常見：漏變數、Root Directory 不是 `backend`）。

**把這個後端網址記下來**（等下前端要用）。

---

## 第 4 步：部署前端（Vercel）

### 4.1 註冊並匯入

1. 打開 https://vercel.com → 用 **GitHub** 登入  
2. **Add New… → Project** → 選 `Jp-learning`  
3. 設定：

| 欄位 | 填什麼 |
|------|--------|
| Framework Preset | Vite |
| Root Directory | **`frontend`**（按 Edit 改） |
| Build Command | `npm run build`（預設即可） |
| Output Directory | `dist` |

### 4.2 環境變數（Build 前就要設好）

在 **Environment Variables** 新增：

| Name | Value |
|------|--------|
| `VITE_API_BASE` | 第 3 步的後端網址，例如 `https://xxxxx.up.railway.app`（**不要**最後的 `/`） |
| `VITE_SUPABASE_URL` | 同本機 frontend |
| `VITE_SUPABASE_ANON_KEY` | 同本機 frontend |

Environment 勾選 **Production**（預覽環境若要測也可勾 Preview）。

### 4.3 Deploy

按 **Deploy**，等完成。  
得到類似：`https://jp-learning-xxxx.vercel.app`

用電腦開這個網址，應看得到 Komorebi 畫面。

### 4.4 回頭改後端 CORS（很重要）

回到 **Railway → Variables**，把：

```text
CORS_ORIGINS=http://localhost:5173
```

改成（換成你的真實前端網址）：

```text
CORS_ORIGINS=https://jp-learning-xxxx.vercel.app
```

若本機還要打雲端 API，可寫兩個：

```text
CORS_ORIGINS=https://jp-learning-xxxx.vercel.app,http://localhost:5173
```

改完後觸發一次 **Redeploy**（或等它自動重啟）。

---

## 第 5 步：手機實測

1. 手機連網，瀏覽器打開 **Vercel 前端網址**（HTTPS）  
2. 依序試：首頁／Dashboard → 單字庫 → 單字卡 → 測驗一題  
3. iPhone：分享 → **加入主畫面**（之後可再做正式 PWA）

第一次若很慢：Railway 免費層可能在「睡」，等 10–30 秒再重新整理。

---

## 出問題怎麼查

| 現象 | 怎麼辦 |
|------|--------|
| GitHub 上沒有 `backend` 資料夾 | 回到第 1 步 push |
| `/health` 打不開 | Railway Logs；檢查 Root=`backend`、變數是否齊 |
| 網頁開了但資料全錯／CORS | `CORS_ORIGINS` 必須是前端完整 `https://…`（與網址列完全一致） |
| API 404 或打到錯地方 | `VITE_API_BASE` 錯了要改 Vercel 變數後 **Redeploy**（Vite 變數在 build 時寫死） |
| 重整 `/vocab` 變 404 | 確認 repo 有 `frontend/vercel.json` 且已 push |

---

## 之後改程式怎麼更新？

```powershell
git add …
git commit -m "…"
git push
```

Railway／Vercel 連著 GitHub 時通常會 **自動重新部署**。  
若只改了 Vercel 的 `VITE_*`，要在 Vercel 手動 **Redeploy**。

---

## 安全提醒

- Service Role Key、Gemini Key **只**放 Railway Variables  
- 前端只放 Supabase **publishable／anon** Key  
- 不要把 `.env` commit 進 git  

需要我幫你在本機執行「安全的第一次 commit + push」（排除 `.env`）的話，跟我說一聲即可。
