# 效能與問題紀錄

長期日誌：記錄載入／查詢變慢的現象、根因、驗證方式與解法，方便之後回頭對照。

## 怎麼寫新的一筆

每次遇到效能問題，請用以下格式追加一節：

```markdown
## YYYY-MM-DD — 標題

### 現象

### 為什麼會慢（根因）

### 怎麼驗證

### 解法

### 結果／後續
```

原則：

- 先寫**使用者感受到的慢**，再寫技術根因
- 根因要能對到具體程式路徑（檔案／API）
- 解法寫「改了什麼」與「為什麼這樣改」
- 有數字更好（請求次數、粗估延遲）

---

## 2026-07-11 — 文法／單字庫頁載入慢、語意關聯點擊轉移慢

### 現象

- 開啟 **文法** 或 **單字庫** 頁面要等很久才出現列表
- 在單字詳情點「語意關聯」近義單字跳轉時，也要再等很久

### 為什麼會慢（根因）

主因不是「缺少搜尋索引」，而是 **遠端 Supabase 的 N+1 round-trip**：

1. `GET /api/v1/vocab?limit=100` / `GET /api/v1/grammar?limit=100` 先查出約 100 筆 id
2. 後端對**每一筆**再呼叫 `_load_vocab_out` / `_load_grammar_out`
3. 每個 loader 又各自查主表 + usages／definitions（每筆至少 2 次 HTTP 到 PostgREST）
4. 合計常達 **200+ 次** 遠端查詢，才組成一個 list response

對應程式（改動前）：

- `backend/app/services/grammar_service.py` → `list_grammar`
- `backend/app/services/vocab_service.py` → `list_vocab`

前端加劇問題：

- `VocabPage` 一次載入 100 筆**完整**單字（含全部釋義／例句）
- 語意關聯變更 `location.state` 時會**整表重抓** list，目標不在當頁再 `getVocab`

### 怎麼驗證

- 瀏覽器 Network：一個 list 請求後端耗時很長；後端 log／Supabase 儀表可見大量 table select
- 對照：改成「2～3 次批次查詢」後，同 limit 的 list 延遲應明顯下降
- 點近義單字：理想上只多一次 `GET /vocab/{id}`，不重打 list

### 解法

1. **List API 輕量化 + 批次查詢**
   - List 只回摘要（列表夠用的欄位）
   - 用 `.in_(...)` 一次撈 definitions／usage counts，禁止 per-row `_load_*`
2. **詳情仍走** `GET /vocab/{id}`、`GET /grammar/{id}`
3. **前端列表／詳情分離**
   - 左側用摘要；選中或關聯跳轉只 fetch 單筆詳情
   - 已在 `/vocab` 時不因 `location.state` 重載整表

### 結果／後續

- List API 改為摘要 + `.in_()` 批次查詢（約 2～3 次 DB round-trip）
- 前端 `VocabPage` / `GrammarPage`：列表用摘要；選中與語意關聯跳轉只 `GET /{id}`，不因 `location.state` 重抓整表
- 若之後資料量再成長，可再考慮：cursor 分頁、列表快取、PostgREST embed (`select=*,definitions(*)`) 進一步合併查詢
- 語意向量／embedding 查詢慢是另一條線，見知識圖譜相關紀錄，勿與此 N+1 混淆
