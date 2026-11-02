# 訪客問答、回饋與首次使用說明

2026-11-01。需求：展後能取出訪客問題、模型回覆與回饋；初次使用時先選語言，再了解導覽、提問與回饋。使用者授權直接實作，儲存方式由實作者決定。沿用既有 FastAPI、原生雙語網頁與已核對研究來源。

## 設計與選擇

選 SQLite 作本機資料保存，CSV 作展後交換格式。相較直接 append CSV，SQLite 提供交易與唯一 ID，能處理重複點擊及多人短時間寫入；不增加資料庫服務或第三方依賴。以 WAL、有限 busy timeout、每次操作獨立連線及短交易處理 1–3 人試用；並行寫入驗證仍須實測，不能將 WAL 當成無限並行寫入。

- 問答保存接受時間、語言、海報區塊、隨機會話／請求 ID、問題、最終產品回覆、狀態、引用及有限版本資訊。儲存通過原有來源檢查後的答案與正式拒答，不保存未通過檢查的 raw 模型內容。history 僅協助生成及請求去重，不重複保存完整歷史。
- 回饋有「清楚／部分不清楚／不易理解」可選評價及最多 1500 字的意見；至少填一項。不新增姓名、Email、IP、User-Agent 等欄位。
- 問答先記 pending 再生成，完成後更新；持久化失敗不假稱成功。已接受請求即使前端離開仍完成記錄；服務重啟時未完成項標示 interrupted，不補造回答或自動重送模型。
- 同 ID 同內容回傳原收據，不重複推論／新增；異內容拒絕。前端不自動重送，回饋失敗保留草稿及同一提交 ID 以供手動重試。
- 本機資料檔預設 `.orchid/visitor-records.sqlite3`，可用部署端 `ORCHID_RECORDS_FILE` 指定持久位置。部署使用主專案的 `.orchid`，避免 worktree 更替遺失資料。
- 僅部署者可在本機匯出；公開網站不提供列表、匯出或 SQLite 下載 API。SQLite、WAL／SHM、CSV 與備份都不進 Git。

首次使用卡片以 English 為首次預設，保留既有語言偏好。選語言後用三段短說明介紹：完整海報可聽也可讀／點框看細節、隨時問整體或當前區塊、留下回饋。單一「開始探索」按鈕；不自動播放。以 sessionStorage 記本次已看，另可從右上「Menu／選單」重開「使用說明」。回饋入口位於選單內與閱讀區末端。沿用海報配色、18px 文字、至少 44px 操作目標與原生 dialog 的焦點管理。

問答、回饋與初次卡片都告知資料將保存於部署機供展後檢視，並提醒勿輸入個資。「清除此畫面」只移除目前顯示與後續生成 history，已保存的展覽紀錄仍保留。這不是作者已看過或已收到通知；系統不代寄信。

## 實作與驗證步驟

1. 真 SQLite 測試：並行提交、重新開啟仍可讀、同 ID 去重、異 payload 衝突、寫入失敗、交易回復與 CSV／backup 匯出。
2. API 整合：先記問題、保留原答案驗證、各種狀態的最終保存、斷線後完成、健康檢查及沒有公開紀錄讀取路由。
3. 手機 UI：首次說明、語言切換／偏好、重開、回饋成功／失敗／防連點，保留既有海報／音訊／問答操作。
4. 原有 Python／Node suite、必要真瀏覽器與有限公開研究問答 smoke；測試資料使用獨立 tmp SQLite，不混入正式訪客紀錄。
5. 核對正式 SQLite 位置及匯出結果，更新試用網站後回報實測與界線。

## 使用說明截圖與按鈕（2026-11-01）

三段使用說明各搭配網站實際畫面的截圖：播放／閱讀與海報區塊、提問表單、回饋表單。English 與繁體中文各三張，跟隨所選語言；點圖片可放大，關閉後回到原說明卡與操作位置。首次仍預設英文，已保存的語言偏好沿用。說明內容可捲動，「開始探索」固定在卡片底部；圖片載入失敗仍保留文字說明與開始按鈕。

目前導覽頁的頁首及說明卡語言選項使用分開的 2px 深藍外框、48px 以上高度與明確選取底色，保留鍵盤焦點及 `aria-pressed`。這次沒有改動舊首頁的介面。

截圖由開發用的獨立 Edge context 拍攝真實 DOM，沒有帶入既有訪客問答或回饋。提問草稿與所選評價只是未送出的示範；沒有模型回答或保存收據。截圖建置使用固定 health 顯示資料，攔截所有非 GET 請求，既不啟動服務，也不呼叫 RAG／TTS 或寫入 SQLite。

在應用已運行、Node／Playwright／Microsoft Edge 已可用的開發環境，從專案根目錄執行：

```powershell
node scripts/build_help_screenshots.cjs --base-url http://127.0.0.1:8000
```

建置只接受 loopback HTTP origin。六張 PNG 與包含來源網址、尺寸及示範邊界的 `manifest.json` 位於 `.orchid/assets/tour-preview/help/`，沿用既有素材的 Git 排除設定。新 checkout 或操作介面變動後需重建；建置失敗應先處理原因，不能把舊圖當成已更新。這些截圖是操作指引，不代表真實後端問答或回饋驗收。

本次圖文介面更新的 Node 全套 32/32 通過、0 skipped（10.73s）；涵蓋中英文六張圖、放大與原解析度、關閉回原按鈕、圖片失敗後仍可開始、固定開始鍵，以及 320／390／430px 和桌面排版。網站 JS 與截圖腳本語法檢查通過；design-taste app lint 為 0 FAIL、2 項既有 padStart 警告。真實 ngrok HTTPS 已核對中英文切換、六張圖載入、放大及返回焦點；沒有送出訪客問題／回饋或啟動音訊。

此介面修改沒有重跑 Python、模型品質或語音測試，沿用上次已通過的資料保存證據。390px 截圖為開發瀏覽器證據，不等同本次實體手機或年長參觀者操作驗收。`output/visitor-help-node-check.txt`、`output/tour-help-welcome-en.png` 與 `output/tour-help-welcome-zh-TW.png` 位於開發 worktree；主專案的 `output/visitor-help-images-20261101/welcome-live-en.jpg` 為實際 HTTPS 畫面。沒有提交、合併或推送。


## 取出資料

從部署程式的專案根目錄執行：

```powershell
# 若應用指定持久 DB，匯出時沿用同一路徑（不含密碼）。
$env:ORCHID_RECORDS_FILE = '<部署時實際使用的 visitor-records.sqlite3 完整路徑>'
uv run --locked --offline orchid export-records --output output/visitor-export-20261101
```

匯出目錄包含 `questions.csv`、`feedback.csv` 及一致的 SQLite 備份。CSV 使用 UTF-8 BOM 方便 Excel；可能被試算表解讀為公式的文字加上安全前綴，原始文字由 SQLite 備份完整保留。取出後不自動刪除原紀錄。匯出既有目錄或找不到來源 DB 應明確拒絕，不能覆寫資料或建立空檔冒充成功。

目前沒有管理後台、帳號、定時清理或自動通知作者。資料保留在部署機，展後由研究團隊決定保留或刪除；移機或合併程式前先做一次匯出備份。日常 access log 仍關閉，研究資料／問題不寫入一般診斷日誌。

## 實測紀錄

- Windows／Python 3.12：完整 Python 123 項通過（4.03s），其中新增 19 項 real-SQLite／API／匯出測試；Ruff 通過。測試以獨立 tmp DB 執行，沒有訪客資料混入。
- Node 全套 31/31 通過，0 skipped；新增首次說明、評價／文字回饋、失敗保留草稿、同 ID 明確重試、切語言、去重及 320–430px dialog／操作目標檢查。最後的按鈕名稱說明文字微調另通過對應 browser test，沒有重跑無關測試。
- 正式部署設定 `ORCHID_RECORDS_FILE` 指向主專案的 `.orchid/visitor-records.sqlite3`；重啟或更換程式 worktree 時必須沿用同一路徑。SQLite schema=1、WAL，應用／索引／Qwen／語音／recording 均 ready。
- 現有 ngrok HTTPS 上的真實瀏覽器：初次說明、English／繁中切換、進入導覽、提問、保存收據、回饋成功收據與「清除此畫面」均已核對。
- 一題帶明確測試標記的公開研究問答取得 answered，產品回答和引用實際寫入；一筆同會話的合成回饋實際保存。清除畫面後資料仍存在；相同 request/submission ID 重送回原收據，沒有新增紀錄。
- 使用本機 `export-records` 真實匯出 questions.csv／feedback.csv／records.sqlite3，逐項核對文字、回答、BOM 與備份中的原文。核對後只清除本次兩筆自建 UUID 測試紀錄，正式資料開始收集時沒有混入這兩筆。
- `/api/records`、GET `/api/feedback`、SQLite 與 sidecar 路由均不可公開讀取；本機匯出沒有對外下載入口。
- 本機主專案 `output/visitor-feature-20261101/verification.json` 保存整合收據，`export-validation/` 保存上述合成資料匯出，`welcome-live.png` 是實際 HTTPS 的說明卡。前端手機截圖與原始 TAP 在工作目錄的 `output/tour-onboarding-en.png`、`output/tour-feedback-zh.png`、`output/visitor-ui-node-check.txt`。
- 工程與瀏覽器檢查不代表年長參觀者已接受操作；實體手機行動網路本輪未重測。沒有重新評估整套研究答案品質或發音，研究內容沿用既有新版海報。

時間戳保存 UTC 與時區偏移，臺灣時間為 UTC+8。沒有新增依賴、啟停模型／ngrok、提交、合併或推送。

2026-11-02：語言、使用說明與回饋已收進右上 Menu／選單；既有首次說明卡、回饋草稿、保存告知與 SQLite 契約不變。由選單開啟的說明／回饋關閉後，焦點返回可見的 Menu 觸發鈕；鍵盤 Tab 可自然離開選單。實作與受影響回歸見 [海報網頁試作](poster-web-preview.md#menu-正式整合2026-11-02)。
