# 第一版實作報告

**後續狀態更新：**已在這台 RTX 5090 Laptop 啟動真實 Qwen3.5-4B，網站、索引、模型與 HTTPS 已接通。最終固定題組可答題 16/17（94.1%）、不可答題 4/4 正確拒答；暖機後序列等待中位數 3.75 秒。完整證據、保守拒答與語意限制見 [laptop-live-test.md](laptop-live-test.md)。下方保留第一版離線階段記錄，其中 model unavailable／19 tests 為當時狀態；本輪最終工程測試為 41 項通過。

核對日期：2026-10-29。工作分支 `feat/orchid-poster-guide`，基線 `86269781c9d6d2ccdca852e26234a391fb7c512b`。本輪未 commit、push、merge；使用者原始 PDF 未修改。

## 交付狀態

產品程式、真實資料入庫、CPU hybrid retrieval、selfhost HTTP adapter、有界佇列、手機介面、操作 CLI、README 與 21 題 golden cases 已完成。程式及離線驗證通過；live Qwen 回答品質未通過驗收，因模型服務目前未就緒。

現場入口由目標負責對話啟動及驗證：

- HTTPS：`https://6e1b-140-116-158-107.ngrok-free.app`，實際網址另保留於 `.orchid/public-url.txt`，可能隨 tunnel 重啟改變。
- QR：`output/guide-qr.png`，由實際 HTTPS URL 產生。
- 最終 app 程序：wrapper PID 126628、uvicorn PID 112880，由 `.orchid/app.json` 記錄 instance 身分。PID 是當次快照，操作前需再核對。
- ngrok 當次 PID 83116，記於 `.orchid/ngrok.json`；不使用 killall 或以模糊名稱停止程序。
- 最終 health：app ready、index ready、model unavailable。模型端點仍保持 loopback。
- root 的實際桌面／390×844 手機 viewport、來源／海報／清除／離線問答與 HTTPS 驗證見 [browser-validation.md](browser-validation.md)。首次 ngrok 入口出現 `ERR_NGROK_6024`，經 Visit Site 後正常；app 啟動暖機期間曾短暫 `8012`，暖機後恢復。

以上瀏覽器證據不等於實體手機行動網路或使用者人工接受。未停止／重啟 NeuroAI，未變更 selfhost-models 的程式、模型、容器或部署。

## 來源與索引

- 來源為使用者提供的研究日海報、12 頁更正後論文，以及 2024-08-17 官方 correction；原始 PDF、模型與 cache 排除 Git。
- 21 筆人工校對摘要，含英文原文擷取、文件版本、證據種類、頁碼／區域座標與來源 SHA-256。前端明確區分「導覽摘要」與「核對英文原文」，附原始 PDF／官方來源。
- 原文按論文文字 block／海報區域擷取，與圖材裁切區域分開。PDF 擷取保留換行及部分分字符號；公式排版以原始 PDF 為準，不把中文摘要冒稱逐字引文。
- 已保留摘要 miR858 措辭衝突的校註、µ_A 的實際定義、海報 FEM／Neumann 與論文 periodic／rdsolver 的差異、海報與論文獨立圖號、整體生物過程的模型角色，以及預測仍需實驗驗證的限制。
- CPU encoder：`intfloat/multilingual-e5-small`，固定 revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`。實際索引 32 chunks，含標題及 passage 前綴最多 480 embedding tokens；向量正規化，BM25 + dense 經 RRF 取前四筆。
- 生成端每個 chunk 同時攜帶完整父摘要與原文 part，避免後半 chunk 遺失參數與條件。query 含前綴與追問前文超過 512 embedding tokens 時明確拒絕，不默默截斷。
- 官方固定 Qwen revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` 的 tokenizer 從已核對的本機部署唯讀重用至專案 cache，記錄 revision 與 tokenizer SHA-256。17 題可回答問題的真實檢索 prompt 加 1024 tokens 模板／輸出保留量，最高 4151 tokens；此項只證明 token 預算，沒有執行 GPU 生成。

## 工程驗證

最終驗證環境：Windows、Python 3.12.14、專案 uv 環境與 `uv.lock`。CPU encoder 確實執行。Windows sandbox 在建立 asyncio socketpair 時阻擋 accept，因此 API／queue 測試經正式 elevation 在允許本機 loopback 的同機環境執行，沒有改測試繞過行為。

| 驗證 | 結果與界線 |
| --- | --- |
| `pytest -q` | **19 passed，0.68s**。含引用異常、數字捏造、超長 query、來源指紋、3 位獨立 HTTP client／history、queue 容量、取消保留 active、timeout quarantine、未宣告 context、錯誤 JSON 與畸形 502 error body。 |
| `ruff check orchid tests` | All checks passed。 |
| `node --check orchid/static/app.js` | 通過。 |
| `git diff --check` | 通過。 |
| `orchid eval --mode retrieval` | 真實 CPU 檢索 21 題；17 題可回答問題在前四筆命中預期來源，17/17。4 題不可回答案例不把檢索命中當成拒答成功。 |
| `orchid eval --mode live --limit 1` | 明確以「live 評估未執行：無法確認本機模型狀態」停止，沒有生成請求、沒有 fixture fallback。 |
| token budget | 17 題保留完整摘要及原文後，最大 4151/8192 tokens；證據在 `output/token-budget.json`。 |
| Windows lifecycle | root 真實 stop/start 最終版成功；核對 wrapper、同 instance Python 子程序及系統 conhost，child 自然退出不會略過 root 停止。 |
| 瀏覽器／HTTPS | 由 root 核對，詳見獨立瀏覽器驗證檔；實體手機行動網路未驗證。 |

重要防護採聚焦 red → green：最初套件／API 缺少、錯誤引用、S03 原文空裁切、超長 query 會進 embedding、非物件模型 JSON、畸形 gateway error 皆先看到失敗，再修正並跑完整套件。HTTP 模型 fixture 僅供契約／故障測試，沒有包裝為 live RAG 展示。

## 模型與容量契約

依 selfhost-models 固定 commit `45ebfd57db5313292ae8f38e733f3e2894a99e5f` 的 client/API 契約接入。每次生成前核對 ready、實際模型 ID／revision／能力；context 未宣告時必須由部署者依實際契約明確設定 `SELFHOST_MODEL_CONTEXT_TOKENS`，不默認已驗證 8192。

單次生成、temperature 0、top_p 1、max_tokens 512、thinking false；不使用不支援的 response_format、embedding 或 JSON schema constrained decoding。完整 JSON、finish_reason=stop、當次引用 ID 與數字字面值檢查通過後才交付。數字存在於證據、引用 ID 合法，都不能證明語意／因果／數字對應正確。

一次一題 active、最多兩題 pending，admission 在 CPU retrieval 前執行，pending 等候上限 35 秒，API 等待上限 44 秒。取消已啟動的請求仍保留工作名額；timeout 或未知 502/503/504 立即顯示未知並 quarantine，有限健康 probe 確認 inflight/detached/uncertain 皆 0 才解除。沒有自動重送、背景無限 retry 或未驗證部分輸出。

訪客問題／回答不寫入伺服器日誌或永久儲存；前端使用 textContent，清除對話會忽略舊回應；body、question、history 有界。來源與文件僅由已登錄 allowlist 提供。

## 操作與資料更新

完整命令、模型 key file 設定、ngrok 既有 config 與 `--inspect=false --log=false`、QR 產生、API 契約及更新流程見 [README.md](../README.md)。

常用命令均從本專案根目錄執行：

```powershell
uv sync --locked
uv run --locked orchid prepare
uv run --locked orchid index --download
# 已核對固定 revision 的本機 tokenizer 也可使用：
uv run --locked orchid index --tokenizer-dir D:/hf_models/Qwen3.5-4B
uv run --locked orchid eval --mode retrieval
uv run --locked orchid start
uv run --locked orchid status
uv run --locked orchid stop
uv run --locked orchid qr --url '本次實際HTTPS網址'
```

替換 PDF 後先人工更新摘要／原文 block 對應與 golden cases，再 `prepare --accept-reviewed`、`index`、retrieval eval、重新載入 app。未校對的新 PDF 不會自動變成可信語料。原始 PDF 指紋或 corpus hash 不符時，不報 index ready。

## 主要檔案

- `pyproject.toml`、`uv.lock`、`.gitignore`：Python 3.12、CPU 依賴與本機產物邊界。
- `orchid/config.py`、`corpus.py`、`retrieval.py`、`token_budget.py`：設定、來源完整性、分塊、CPU 索引與精確 tokenizer 預算。
- `orchid/generation.py`、`app.py`：selfhost 介面、佇列／quarantine、輸入輸出驗證及 FastAPI routes。
- `orchid/cli.py`、`evaluation.py`：prepare/index/eval/serve/start/status/stop/QR。
- `orchid/static/index.html`、`style.css`、`app.js`：繁中手機介面、三條線索、問答／來源／海報視窗與 clear 行為。
- `data/evidence.json`、`excerpt-map.json`、`sources.json`、`guide.json`、`golden.json`：可追溯語料、導覽與 21 題案例。
- `tests/test_contract.py`、`test_api.py`、`test_failures.py`、`test_data.py`：聚焦行為與故障回歸。

設計採 design-taste-frontend 的 Editorial greeting（seed 1096759354）及 ui-ux-pro-max 的手機／無障礙規則：研究自身的紫色、實際花紋照片與模擬圖、清楚的來源摘錄。沒有生成科學花圖或捏造示範資料。設計 lint 無 FAIL；保留的 eyebrow 與 01–03 警告對應研究引導句及海報真實三條線索，不是虛構 KPI。

## 尚未驗證／待人工接受

1. 真實 Qwen 模型逐題回答品質、≥90% 正確重點、零數字／引用語意錯誤，以及所有不可回答案例的拒答品質。
2. 真實暖機後單題 ≤30 秒、多人實際推論表現與模型中斷後 terminal 確認；本輪僅有契約／故障 fixture 與真實 CPU 檢索證據。
3. 實體手機經行動網路掃 QR、首次 ngrok interstitial 與長時間展場可用性。
4. 使用者人工接受。工程通過、公開入口可達及手機 viewport 不代表以上項目通過。

## 5090 Laptop 效果測試前的評估工具修正

使用者授權先在這台 5090 Laptop 測試效果後，修正 live eval 路徑，讓它直接呼叫正在運作的產品 `/api/chat`，完整經過與 UI 相同的 queue、引用／數字驗證與 unknown 回覆。沒有修改 app、generation、retrieval，也沒有重啟服務。

每次 live run 有獨立時間／ID 報告與 latest 副本，逐題送出前及回覆後原子 checkpoint；transport timeout 後保留已完成題目並停止，不自動重送。模型／索引／app 未就緒或已有 active/pending 工作時，保存 blocked 狀態且不送生成。API unknown 後只做一次 health 確認，不能確認 idle 就停止。`product_response` 保留實際產品 JSON，沒有把原始模型未驗證內容列為成功。

聚焦測試先 red 後 green：產品 unknown 原樣保存、第二題 timeout 保留第一題且不重試／不送第三題、preflight unavailable 無生成且有 checkpoint。完整測試共 **22 passed，0.75s**。這些是 fixture HTTP 契約驗證；本次修正期間未送真實生成，待目標負責對話核對模型 ready 後序列執行代表題與完整 golden cases。
