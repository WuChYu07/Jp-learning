# 產品待辦（個人用）與手機部署

**產品定位：只給自己用**（`AUTH_ENABLED=false` + 固定 singleton owner）。  
不規劃多使用者、不規劃正式 Auth 產品化。完成一項就改狀態；新想法用同一格式追加。

---

## 怎麼更新

```markdown
### YYYY-MM-DD — 標題
- 狀態：pending / in_progress / done / wontfix
- 說明：…
```

---

## 範圍決策（2026-07-16）

| 決定 | 說明 |
|------|------|
| Solo only | 進度綁 `a0000000-…0001`，不開多帳 |
| 不做 R4 / R8 | 個人用無 anonymous／多使用者問題 |
| 不做 R7（產品佇列） | 例句／補充已人工清零；之後缺欄用 Cursor／單筆手修即可 |
| 部署維持方案 A | Vercel + Render Free + Supabase |

---

## 待辦清單（個人用，2026-07-16）

### 建議優先（會直接影響你每天用）

| ID | 項目 | 狀態 | 說明 |
|----|------|------|------|
| P1 | 手機可穩定學習 | in_progress | 已上線 Vercel + Render；前端已加冷啟動提示／重試；待核對 CORS + 手機實測 |
| P2 | Notion 同步品質回報 | pending | Upload／同步結果顯示：來源列數、解析成功、去重、新寫入／更新／略過（原 R5） |
| P3 | 知識圖譜語意品質 | pending | 調門檻／重算，減少怪連線；個人瀏覽時不干擾學習（原 R6） |

### 有空再做

| ID | 項目 | 狀態 | 說明 |
|----|------|------|------|
| P4 | 匯出／備份 | pending | JSON／CSV 匯出單字、文法、SRS 進度，方便自己備份（原 R10） |
| P5 | 冷啟動體感 | pending | Render Free 喚醒提示（前端顯示「後端醒來中…」），減少以為壞掉 |

### 已完成

| ID | 項目 | 狀態 | 說明 |
|----|------|------|------|
| R1 | JLPT 分級補齊 | done | Upload「JLPT」preview → apply |
| R2 | 單字例句／補充覆蓋 | done | Cursor 老師視角 gap-fill；primary defs 缺欄 = 0 |
| R3 | 文法複習／測驗 | done | 文法閃卡 SRS + 文法四選一 |

### 明確不做（個人用）

| ID | 項目 | 狀態 | 說明 |
|----|------|------|------|
| R4 | SRS 綁定登入帳號 | wontfix | Solo owner 已夠穩定 |
| R7 | 批次 AI 補缺產品佇列 | wontfix | 資料已滿；不另做一鍵佇列 UI |
| R8 | Auth／多使用者 | wontfix | 不對外給別人各自帳號 |

---

## 已具備（對照用，勿當待辦）

- 單字庫／單字卡、文法中心、單字／文法四選一、翻譯測驗、Dashboard
- 單字＋文法閃卡 SRS（SM-2）、考試分寫入 `exam_attempts`
- Notion／CSV／文字匯入、JLPT unknown 批次、知識圖譜
- 單字／文法手修與 AI 草稿 → 確認小視窗才寫入
- List API 輕量化；Gemini 多 key failover
- Solo：`AUTH_ENABLED=false` + singleton owner

---

## 手機上使用要怎麼做？

目標：**用手機瀏覽器打開就能學**（必要時「加到主畫面」），不做原生 App。

```text
手機 Safari/Chrome
    → HTTPS 前端（Vercel）
    → HTTPS 後端 API（Render Free）
    → Supabase + Gemini（後端）
```

| 層 | 建議 | 說明 |
|----|------|------|
| 資料庫 | **Supabase** | 已在雲端 |
| 後端 | **Render Free** | 會休眠＋冷啟動 |
| 前端 | **Vercel** | 靜態站 |
| 體驗 | 響應式；PWA 可選 | 免上架 |

### 手機可用檢查清單（歸入 P1）

- [x] 前端指向**公開**後端 URL（`VITE_API_BASE` → Render）
- [ ] 後端 CORS 允許 `https://jp-learning-two.vercel.app`（Render 後台確認）
- [x] 全站 **HTTPS**（Vercel + Render）
- [ ] 單字卡／測驗在窄螢幕可點、可滑（手機實測）
- [ ] （選）PWA：`manifest` + service worker

### 不建議做

- App Store／Play 上架
- 自架 Postgres 取代 Supabase
- Kubernetes／重型多租戶

---

## 建議下一步順序（個人用）

1. **P1** — 手機開得出、學得了（部署核對 + 小螢幕摩擦）
2. **P2** — Notion 同步數字講清楚，減少自己懷疑資料丟了
3. **P3** — 圖譜連線變正常（有在用圖譜再做）
4. **P4／P5** — 備份與冷啟動提示，有痛點再做

細節部署步驟見 **[docs/deploy-a.md](deploy-a.md)**。

### 部署決策紀錄

- **2026-07-11** — 方案 A（託管拆分）；暫緩 VPS + Docker Compose。
- **2026-07-12** — 後端以 **Render Free** 為主；備 `backend/Dockerfile`、`render.yaml`。
- **2026-07-16** — 產品範圍改為**個人用 only**；砍 R4／R7／R8，待辦改編號 P1–P5。
