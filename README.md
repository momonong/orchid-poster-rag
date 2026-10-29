# 蘭花花紋研究・海報 RAG 導覽

手機優先的一頁導覽：一分鐘介紹、Clue 1–3、真實海報圖材、有來源的研究問答。FastAPI 只綁定 `127.0.0.1:8000`；生成經同機 selfhost-models，embedding 與 hybrid retrieval 使用 CPU。本專案不會啟停模型、切換 backend 或管理其他專案的 GPU 工作。

## 目前交付與驗證界線

- 官方更正後論文、2024-08-17 correction 與研究日海報已整理成 21 筆校對摘要及可回溯原文，CPU 索引為 **33 chunks**；原始 PDF、模型、向量與程序狀態排除 Git。
- 工程整合驗證為 **41 tests 通過**，Ruff 與 `git diff --check` 通過。實作與驗證分層見[實作報告](docs/implementation-report.md)。
- RTX 5090 Laptop 的同版固定 21 題實際 API 測試：可回答題 **16/17（94.1%）**、不可回答題 **4/4 正確拒答**。G07 仍因生成措辭未通過範圍檢查而拒答，已計為失敗。逐題證據與部署條件見[實機測試紀錄](docs/laptop-live-test.md)。
- 本次暖機後序列測試完整 API 等待為 **2.75–6.078 秒，中位數 3.75 秒**；這是固定題組的代理語意審查，並非研究作者／使用者人工驗收，也不保證其他問題或負載有相同品質與速度。
- 模型未就緒時仍可閱讀導覽與來源，問答明確顯示 unavailable。瀏覽器與手機 viewport 核對見[瀏覽器驗證](docs/browser-validation.md)；實體手機行動網路掃碼、人工接受與展場長時間穩定性仍待驗收。

## 安裝與啟動（Windows PowerShell）

需要 Python 3.12、uv。從本專案根目錄執行：

```powershell
$env:PYTHONUTF8 = '1'
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.cache/uv'
uv sync --locked

# 原始 PDF 位於專案根目錄，不覆寫使用者檔案。
uv run --locked orchid prepare --poster '理學院研究日.pdf' --paper 's12870-024-05305-z.pdf'

# 首次下載固定 revision 的官方 multilingual-e5-small；只使用 CPU。
$env:HF_HUB_DISABLE_XET = '1'
uv run --locked orchid index --download

# 模型服務由既有 selfhost-models 的擁有者準備。
$env:SELFHOST_MODEL_BASE_URL = 'http://127.0.0.1:18080'
$env:SELFHOST_MODEL_API_KEY_FILE = 'D:\projects\selfhost-models\.state\api-key'
$env:SELFHOST_MODEL_EXPECTED_ID = 'Qwen/Qwen3.5-4B'
# 只有部署者已核對 context 為 8192，但 /v1/models 未宣告時才設定：
$env:SELFHOST_MODEL_CONTEXT_TOKENS = '8192'

uv run --locked orchid serve
```

瀏覽器開啟 `http://127.0.0.1:8000`。首次模型載入與 embedding 暖機可能需要數秒。模型拒絕連線不阻止網頁閱讀。

另可用背景程序命令：

```powershell
uv run --locked orchid start
uv run --locked orchid status
uv run --locked orchid stop
```

`stop` 僅停止本 CLI 登錄、instance UUID 相符的應用程序及同 instance Python 子程序，不停止模型或 ngrok。`serve/start/status --port 8001` 可選擇其他 loopback port；不支援對外 bind。應用 access log 關閉，`.orchid/app.log` 只存程序診斷，不記錄問題與回答。背景記錄不等於 HTTP 就緒，請用 `status` 確認。

## 公開網址與 QR

只讓 ngrok 指向 app port，模型端點保持 loopback。沿用原有帳號認證，不把 token 貼進指令或儲存庫。工具存在時可執行：

```powershell
.tools/ngrok/ngrok.exe http http://127.0.0.1:8000 --config "$env:LOCALAPPDATA/ngrok/ngrok.yml" --inspect=false --log=false
# 從 ngrok 取得本次真正的 HTTPS URL，再填入：
$env:ORCHID_PUBLIC_URL = 'https://你的實際網址.ngrok-free.app'
uv run --locked orchid qr
```

QR 產於 `output/guide-qr.png`。網址合法不代表可達；請另驗證 HTTPS、帳號／interstitial，以及實際手機行動網路。CLI 不自動建立 tunnel 或發布內容。

停止本次由目標對話記錄的 ngrok 時，先核對 `.orchid/ngrok.json` 的 PID 與本專案官方執行檔完整路徑；以下僅停止吻合的程序：

```powershell
$ngrokState = Get-Content -Raw .orchid/ngrok.json | ConvertFrom-Json
$ngrokProcess = Get-Process -Id $ngrokState.pid -ErrorAction Stop
$ngrokExpectedExe = (Resolve-Path .tools/ngrok/ngrok.exe).Path
if ($ngrokProcess.Path -ne $ngrokExpectedExe) { throw 'PID/執行檔不符，拒絕停止' }
Stop-Process -InputObject $ngrokProcess -ErrorAction Stop
$ngrokProcess.WaitForExit()
Remove-Item -LiteralPath .orchid/ngrok.json
```

這會關閉目前公開入口，保留 app 與模型服務；不要用 `taskkill /IM ngrok.exe` 或 killall 影響其他 tunnel。

## 來源與資料更新

- 論文：[Lu et al. 2024, BMC Plant Biology 24, 681](https://link.springer.com/article/10.1186/s12870-024-05305-z)，CC BY 4.0。
- [官方圖號 correction](https://link.springer.com/article/10.1186/s12870-024-05475-w)：舊 2→新 10、舊 3→新 11、舊 4–11→新 2–9。海報圖 1–4 是獨立圖號。
- `data/evidence.json`：中文導覽摘要、英文 PDF 原文擷取、證據種類、版本、頁碼／區域與來源 SHA-256；摘要不是逐字引文。
- `data/excerpt-map.json`：目前更正後論文的頁碼與文字 block 索引。更換 PDF 後必須人工重新核對，不能假定 block 索引仍相同。
- `data/sources.json`：原始 PDF 位置、SHA-256、海報裁切區域。`prepare` 只產出衍生資料，不改原始 PDF。
- `data/guide.json`：導覽文案與來源連結。更新文案時也核對來源。

更新步驟：保留原始檔 → 核對新版本與圖號 → 更新摘要、原文 block/region 對應與 golden cases → `orchid prepare --accept-reviewed` → `orchid index` → `orchid eval --mode retrieval` → 重新啟動 app 載入新索引 → 以 live 模型與手機核對。`--accept-reviewed` 代表操作人已完成校對，不會自動驗證科學語意。原始 PDF 指紋不符或語料變更時索引拒絕宣稱 ready。

特別保留的研究條件：µ_A 是 PeMYB11 活化系統降解率，降低 miR858 表達以降低 µ_A 代理；摘要的相反措辭另列校註。論文 100×100／periodic／rdsolver 與海報新增 petal-shaped FEM／Neumann 必須分開。模型中的 PeMYB11/PeMYBx 代表整體生物過程，D_H>D_A 不是單獨充分條件，預測仍需實驗驗證。

## 檢索、生成與容量

CPU `intfloat/multilingual-e5-small` revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`。embedding 使用 `query:`／`passage:` 前綴、正規化向量，含標題前綴的 chunk 最多 480 tokenizer tokens，超長明確分塊，不默默截斷。NumPy 向量與 BM25 透過 RRF 融合，每題送前四筆，每個 chunk 在生成時都帶完整父摘要以保留條件；短追問可用最近 user 問題消歧，歷史最多兩輪且不是證據。query 含前綴若超過 512 embedding tokens 會明確提示縮短，不會默默截斷。原文與校對摘要一併入庫。

生成前檢查 `/health/ready`、`/v1/models`、實際模型 ID／文字能力與 context。單次生成：temperature 0、top_p 1、max_tokens 512、thinking false；只用嚴格 Chat Completions 子集，不使用 embeddings API 或 response_format。使用目標固定 revision 的官方 Qwen tokenizer JSON 計算文字 token，另留 1024 tokens 給模板與最多 512 tokens 輸出；超限明確拒絕，不裁切證據。tokenizer 可由 orchid index --download 下載，或 --tokenizer-dir 使用已核對固定 revision 的本機目錄；只複製 tokenizer 小檔，不執行模型。

一題 active、最多兩題 pending，等候最多 35 秒，單次 API 等待最多 44 秒；不自動重試。離開／清除頁面不釋放仍在運作的模型名額。transport timeout、502/未知 503/504 進入 quarantine；下一次 health 或請求以有限 probe 確認 inflight/detached/uncertain 全為 0 後才解除，沒有背景重送。清除對話使前端忽略舊回應。一般回覆需完整 JSON、finish_reason=stop 與當次檢索引用 ID 通過檢查才顯示。

`confidence` 是狀態標籤，沒有偽造機率。引用 ID 驗證不能證明語意忠實，應以人工驗收確認。

## API

- `POST /api/chat`：`{"question":"問題","history":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}`。question 最多 600 字，history 最多 4 則、每則 1000 字，body 最多 16 KiB。回傳 `answer/status/citations/poster_sections/confidence`。
- `status`：`answered`（引用 ID 已驗證）、`unknown`（證據不足／格式不符／結果未知）、`busy`、`unavailable`。
- `GET /api/health`：app／index／model readiness 與有限容量狀態，不含秘密。
- `GET /api/guide`：已校對導覽 manifest。
- `GET /api/sources/{id}`：摘要、英文原文、版本、頁碼與區域 metadata。
- `GET /api/documents/poster`、`/paper`：只提供已登錄、位於專案內的兩份 PDF，無任意檔案瀏覽。

UI 以 `textContent` 顯示模型文字，無 Markdown／HTML 執行。無帳號、上傳管理、永久對話、語音、雲端生成或自動網路檢索。公開入口不設使用者認證，僅適合授權展覽情境的 1–3 位訪客；若要大規模公開，另定存取與資源契約。

## 驗證

```powershell
uv run --locked pytest -q
uv run --locked ruff check orchid tests
node --check orchid/static/app.js
uv run --locked orchid eval --mode retrieval
# app、索引與既有模型都已就緒，且當次允許推論時；序列執行，不與手動生成並行：
uv run --locked orchid eval --mode live
# 小批檢查可沿用 --limit；改 app port 時設定 loopback origin：
$env:ORCHID_APP_BASE_URL = 'http://127.0.0.1:8000'
uv run --locked orchid eval --mode live --limit 6
```

`data/golden.json` 有 21 題：17 題可回答、4 題證據不足／注入／不存在的寄信操作／無關餐廳推薦。retrieval 模式是真實 CPU 檢索；live 模式先檢查產品 health，再序列呼叫實際 `/api/chat`，完整經過與 UI 相同的引用／數字／佇列／unknown 驗證。每題只送一次，遇 transport 結果未知、busy、unavailable，或 unknown 後無法確認服務 idle 即停止，沒有 fixture fallback 或自動重送。

每次 live run 保留獨立 `output/evaluation-live-時間-隨機ID.json`，並以 `output/evaluation-live.json` 作最新副本；每題送出前及收到結果後都原子保存 checkpoint，中途失敗仍保留前題。`product_response` 是產品實際完整 JSON；`state=complete` 只表示這批 HTTP 評估流程完成，`blocked/stopped` 或 `in_progress` 不算完整結果。`completed_cases` 是已收到產品回覆的題數，不是答對題數。字面關鍵字檢查只是診斷，≥90% 正確率、零數字／引用語意錯誤與拒答品質仍須人工核對。Windows sandbox 若卡在 asyncio socketpair，需在允許本機 loopback 的正式執行環境跑同一份測試，不改測試假裝通過。

實作檔：`orchid/corpus.py`、`retrieval.py`、`generation.py`、`app.py`、`cli.py`、`evaluation.py` 與 `orchid/static/`。驗證與未完成項目列於 `docs/implementation-report.md`。
