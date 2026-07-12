# 產品待辦與手機部署

長期紀錄：還沒做的功能、優先順序，以及「要在手機上用」的部署方向。  
完成一項就改狀態或移到「已完成」；新想法用同一格式追加。

---

## 怎麼更新

```markdown
### YYYY-MM-DD — 標題
- 狀態：pending / in_progress / done
- 說明：…
```

---

## 待辦清單（2026-07-11）

### 高優先 — 學習體感

| ID | 項目 | 狀態 | 說明 |
|----|------|------|------|
| R1 | JLPT 分級補齊 | pending | 大量 `unknown`，篩選幾乎無用；可批次 AI 或對照 JLPT 詞表 |
| R2 | 單字例句／補充覆蓋率 | pending | Notion 重同步 + 缺欄 AI 補充（確認小視窗流程已有） |
| R3 | 文法複習／測驗 | pending | 文法多半只能「看」；缺 SRS 或填空／翻譯練習 |
| R4 | SRS 綁定真實使用者 | pending | 複習進度需穩定對應登入帳號，避免 anonymous 漂移 |

### 中優先 — 資料與品質

| ID | 項目 | 狀態 | 說明 |
|----|------|------|------|
| R5 | Notion 同步品質回報 | pending | 顯示表格列數／解析成功／去重／新寫入，避免 500 vs 369 困惑 |
| R6 | 知識圖譜語意品質 | pending | 調整門檻／重算，減少怪連線 |
| R7 | 批次 AI 補缺佇列 | pending | 一鍵處理缺例句／缺補充的單字（仍建議可抽樣確認） |

### 低優先 — 產品化

| ID | 項目 | 狀態 | 說明 |
|----|------|------|------|
| R8 | Auth／多使用者打磨 | pending | 若要給別人各自使用 |
| R9 | 手機體驗強化 | pending | 見下方「手機使用」；含 PWA、觸控、小螢幕版面 |
| R10 | 匯出／備份 | pending | 筆記或學習進度匯出 |

### 已具備（對照用，勿當待辦）

- 單字庫／單字卡、文法中心、四選一、翻譯測驗、Dashboard
- Notion／CSV／文字匯入、知識圖譜、語意關聯
- 單字／文法手修與 AI 草稿 → 確認小視窗才寫入
- List API 輕量化（效能 N+1 已處理）

---

## 手機上使用要怎麼做？

目標：**用手機瀏覽器打開就能學**（必要時「加到主畫面」），不一定要做原生 App。

### 建議路線（優先）

```text
手機 Safari/Chrome
    → HTTPS 前端（Vite build 靜態站）
    → HTTPS 後端 API（FastAPI）
    → Supabase（已在雲端）
    → Gemini（你自己的 Key，跑在後端）
```

| 層 | 建議 | 說明 |
|----|------|------|
| 資料庫 | 維持 **Supabase** | 已在雲端，不必塞進 Docker |
| 後端 | **Railway / Render / Fly.io** 跑 FastAPI | 可 Docker，也可直接部署 Python |
| 前端 | **Cloudflare Pages / Vercel / Netlify** | `npm run build` 後丟靜態檔 |
| 手機體驗 | 先做 **響應式 + 可選 PWA** | 加到主畫面＝接近 App，免上架 |

**不一定要「整包 Docker 丟雲端」才是正解。**  
Docker 適合：自己有一台 VPS、想一次 `docker compose up` 管前後端。對「我自己手機用」來說，前後端分開託管通常更省事、也比較便宜。

### 什麼時候用 Docker？

適合：

- 想租一台小 VPS（例如 Oracle Free / Hetzner），自己控管
- 或之後 CI 要固定環境重現

示意（未來可做，尚未實作）：

```text
docker-compose:
  backend: FastAPI image + env（Supabase URL、Gemini Key）
  frontend: nginx 送出 Vite build
  # 不要把 Postgres 塞進同機當正式庫——繼續用 Supabase
```

### 手機可用的最低檢查清單

- [ ] 前端用相對／環境變數指向**公開**後端 URL（不要只寫 `localhost`）
- [ ] 後端 CORS 允許前端網域
- [ ] 全站 **HTTPS**（iOS 加到主畫面幾乎必要）
- [ ] 單字卡／測驗在窄螢幕可點、可滑
- [ ] （選）PWA：`manifest` + service worker，支援「加入主畫面」

### 不建議一開始做的

- 上架 App Store／Google Play（審核、憑證、維護成本高）
- 把 Supabase 換成自架 Postgres（除非有強理由）
- 只為了「看起來像雲端」硬上 Kubernetes

---

## 建議下一步順序

1. ~~選部署方式~~ → **已選 A**（前端 Pages／Vercel + 後端 Railway／Render）  
2. 依 **[docs/deploy-a.md](deploy-a.md)** 上線，手機實測單字卡與測驗  
3. 回頭做 R1–R3（JLPT、單字補充、文法複習）與 R9（PWA／版面）

### 部署決策紀錄

- **2026-07-11** — 採用 **方案 A**；方案 B（VPS + Docker Compose）暫緩。  
  後端已備 `backend/Dockerfile`，前端已備 Vercel／Cloudflare SPA fallback。
