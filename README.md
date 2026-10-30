# 蘭花花紋研究・海報 RAG 導覽

手機優先的一頁導覽：一分鐘介紹、Clue 1–3、真實海報圖材、有來源的研究問答。FastAPI 只綁定 `127.0.0.1:8000`；生成經同機 selfhost-models，embedding 與 hybrid retrieval 使用 CPU。本專案不會啟停模型、切換 backend 或管理其他專案的 GPU 工作。

介面提供 **English / 繁體中文**，首次開啟預設英文，只以 localStorage 保存語言偏好。介紹、三條線索、建議問題與新回答跟隨所選語言；已有問答保留原語言，進行中的問題以送出時語言回答。上一條／下一條線索及各線索提問入口可繼續探索。

介紹、目前線索及通過來源檢查的回答可手動朗讀，共用暫停／繼續及停止控制。語音由同一 FastAPI 內的固定 Kokoro 模型在本機 CPU 合成，瀏覽器以 HTMLAudio 播放 WAV；不依賴已安裝的 OS 語音。靜態導覽預錄快取，回答音訊只短暫保留記憶體。切換語言／線索、清除對話或離頁會停止播放；一次只播一段，旁讀略過來源 ID，畫面保留引用。瀏覽器若阻擋非同步播放，可再按 Play 直接播放已備妥音訊。沒有麥克風、語音辨識、雲端 TTS 或自動重送。安裝、授權與實測見[本機雙語音訊](docs/local-speech.md)。

## 完整海報導覽 `/tour-preview/`

既有首頁 `/` 保留；`/tour-preview/` 提供完整英文海報 → 八個完整區塊 → 閱讀、聆聽與有來源提問。介面預設英文，可切換繁體中文；正文 18px，A+ 可切換 20／22px。八區探索的 `order` 與六段完整導覽的 `tour_order` 分開，既有十二段預製 WAV 約為英文 1:53、中文 1:56。使用者已於 2026-10-31 確認本輪 UI 並授權合併與推送；Git 完成狀態由實際整合結果另行核對。

在已安裝專案依賴的環境，先放入 `data/sources.json` 登錄且 SHA 相符的原海報 PDF，再從專案根目錄建置圖片：

```powershell
uv run --locked --offline python -B scripts/build_tour_assets.py
# 重建六段 × 兩語音訊：須已有語音服務就緒，且當次已授權語音生成；不會啟動服務。
uv run --locked --offline python -B scripts/build_tour_audio.py --base-url http://127.0.0.1:8000
```

衍生圖片、manifest 與 WAV 位於 `.orchid/assets/tour-preview/`，連同原 PDF、模型及索引都不入 Git；新 checkout 必須準備原素材並重建。References／海報補充說明新增的是閱讀與來源入口，沒有加入 RAG evidence 或索引，不保證所有補充細節都可問答。操作、解析度上限、音訊重建與驗證界線見[海報網頁試作](docs/poster-web-preview.md)及[按鈕與八區調整](docs/poster-visual-polish.md)。

## 目前交付與驗證界線

- 官方更正後論文、2024-08-17 correction 與研究日海報已整理成 21 筆校對摘要及可回溯原文，CPU 索引為 **33 chunks**；原始 PDF、模型、向量與程序狀態排除 Git。
- 原雙語音訊版的歷史工程驗證為 **103 pytest tests、21 Node tests 通過**，涵蓋語言契約、英文抽取式選段、譯文完整性／過期拒用、兩語錯誤／科學主張保護、英文術語檢索、音訊容量／ASGI 斷線取消／私密快取、播放器事件及跨語言舊回答播放。Node 中 1 項實際 Edge 回歸需已有 Playwright 與瀏覽器；其餘使用 Node 內建測試。整合發現的「H 自我活化」錯述另加拒絕保護，不更動生成 prompt 或英文選段。先前雙語科學版為 92 pytest、7 Node；中文單語版基線是 41 tests。詳細界線見[雙語驗證紀錄](docs/bilingual-validation.md)與[本機音訊實測](docs/local-speech.md)。
- RTX 5090 Laptop 實際 API 固定題組：英文抽取式 **17/17 可答題通過**，繁中 **16/17（94.1%）**；兩語各 **4/4 正確拒答**。繁中 G07 保守拒答仍計未通過。英文自由轉述的失敗歷史、最後審查與繁中原版輸入相同的證據見[雙語驗證紀錄](docs/bilingual-validation.md)。
- 暖機後單人序列 API 等待：英文 **0.55–1.75 秒，中位數 1.02 秒**；繁中 **3.203–8.737 秒，中位數 4.867 秒**。固定題組及代理審查不是研究作者／使用者人工接受，也不保證其他問題或負載相同。
- 模型未就緒仍可讀導覽與來源。公開 HTTPS、語言切換、來源開啟與窄螢幕已核對；英中本機 CPU WAV 與瀏覽器播放控制已實測。使用者已確認手機操作與本輪 UI；音訊人工聽感、實體手機行動網路掃碼及展場長時間穩定性仍待驗收。2026-10-31 發布前離線檢查為 **103 Python tests、29 Node tests 通過，0 skip**；新增建置腳本語法與 Ruff 通過。這輪未重跑真實模型／語音評估。

## 安裝與啟動（Windows PowerShell）

需要 Python 3.12、uv。從本專案根目錄執行：

```powershell
$env:PYTHONUTF8 = '1'
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.cache/uv'
uv sync --locked

# 首次下載固定官方雙語TTS模型（約365MB），驗證SHA並預錄八段導覽；CPU兩執行緒。
uv run --locked python scripts/provision_speech.py --download --smoke

# 原始 PDF 位於專案根目錄，不覆寫使用者檔案。
uv run --locked orchid prepare --poster '理學院研究日.pdf' --paper 's12870-024-05305-z.pdf'

# 首次下載固定 revision 的官方 multilingual-e5-small；只使用 CPU。
$env:HF_HUB_DISABLE_XET = '1'
uv run --locked orchid index --download

# 模型服務由既有 selfhost-models 的擁有者準備。
$env:SELFHOST_MODEL_BASE_URL = 'http://127.0.0.1:18080'
$env:SELFHOST_MODEL_API_KEY_FILE = '<依 selfhost-models 契約核對的 API key 檔案完整路徑>'
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
- `data/evidence.en.json`：21 筆校對摘要的英文譯文，canonical IDs 與 `evidence.json` 一一對應，並綁定其 corpus SHA-256。它是已校對摘要譯文，不是作者逐字引文；只供英文生成，不改檢索語料或索引。缺少、重複／漏 ID、空白或原語料 hash 不符時，英文問答明確 unavailable，不回退至其他語言。
- `data/excerpt-map.json`：目前更正後論文的頁碼與文字 block 索引。更換 PDF 後必須人工重新核對，不能假定 block 索引仍相同。
- `data/sources.json`：原始 PDF 位置、SHA-256、海報裁切區域。`prepare` 只產出衍生資料，不改原始 PDF。
- `data/guide.json`：導覽文案與來源連結。更新文案時也核對來源。
- `data/guide.en.json`：英文導覽；`data/source-labels.en.json`：英文來源標題與證據種類標籤。這兩份僅供呈現，不取代研究語料或重建索引。英文來源視窗優先顯示原始英文擷取，中文校對摘要明確標為繁體中文；原始 PDF 保持原樣。

更新步驟：保留原始檔 → 核對新版本與圖號 → 更新摘要、原文 block/region 對應與 golden cases → `orchid prepare --accept-reviewed` → `orchid index` → `orchid eval --mode retrieval` → 重新啟動 app 載入新索引 → 以 live 模型與手機核對。`--accept-reviewed` 代表操作人已完成校對，不會自動驗證科學語意。原始 PDF 指紋不符或語料變更時索引拒絕宣稱 ready。

特別保留的研究條件：µ_A 是 PeMYB11 活化系統降解率，降低 miR858 表達以降低 µ_A 代理；摘要的相反措辭另列校註。論文 100×100／periodic／rdsolver 與海報新增 petal-shaped FEM／Neumann 必須分開。模型中的 PeMYB11/PeMYBx 代表整體生物過程，D_H>D_A 不是單獨充分條件，預測仍需實驗驗證。

## 檢索、生成與容量

CPU `intfloat/multilingual-e5-small` revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`。embedding 使用 `query:`／`passage:` 前綴、正規化向量，含標題前綴的 chunk 最多 480 tokenizer tokens，超長明確分塊，不默默截斷。NumPy 向量與 BM25 透過 RRF 融合，每題送前四筆，每個 chunk 在生成時都帶完整父摘要以保留條件；短追問可用最近 user 問題消歧，歷史最多兩輪且不是證據。query 含前綴若超過 512 embedding tokens 會明確提示縮短，不會默默截斷。原文與校對摘要一併入庫。

英文請求在完整保留原 query 後，追加小型英中術語 alias，例如 micromolar→µM、anthocyanin→花青素、fused patterns→融合斑塊，以橋接既有中文校註。詞彙表位於 `retrieval.py`，不含固定題目、來源 ID、參數數值或答案，不改語料或向量索引；繁中路徑維持原 query。原 query 先通過 512-token 上限，再確認 alias 能否放入；放不下時使用完整原 query，不裁字或擴大額度。

英文採**抽取式 RAG**：Qwen 理解問題與 history，僅從當輪檢索來源的英文校對摘要中選一至兩個完整段落，回傳 `status` 與 `selections[{source_id,paragraph_index}]`；不重寫回答。候選保留 document／figure／page／section 與譯文標記。後端嚴格檢查當輪 ID、整數 index、重複 canonical 段落、數量、status 及欄位白名單，再以原段落原字組合回答並附引用。任意生成的 answer／text 或額外欄位不會進入產品。

英文顯示為 **Reviewed source summary**，代表已校對來源摘要，不表示每道訪客問題都經人工審稿。最多兩段完整文字含引用若超過固定 Qwen tokenizer 的 512 tokens，明確 unknown，不截斷或刪條件；實際組字仍通過引用、數值及科學範圍 guard。段落可能包含超出問題的相關條件，Qwen 也可能選錯相關性，因此仍需語意驗收。原 PDF／英文原文繼續由 sources 展示。繁中 system 和 evidence 欄位／順序／內容維持原版 `3900ee1` 路徑。

生成前檢查 `/health/ready`、`/v1/models`、實際模型 ID／文字能力與 context。單次生成：temperature 0、top_p 1、max_tokens 512、thinking false；只用嚴格 Chat Completions 子集，不使用 embeddings API 或 response_format。使用目標固定 revision 的官方 Qwen tokenizer JSON 計算文字 token，另留 1024 tokens 給模板與最多 512 tokens 輸出；超限明確拒絕，不裁切證據。tokenizer 可由 orchid index --download 下載，或 --tokenizer-dir 使用已核對固定 revision 的本機目錄；只複製 tokenizer 小檔，不執行模型。

一題 active、最多兩題 pending，等候最多 35 秒，單次 API 等待最多 44 秒；不自動重試。離開／清除頁面不釋放仍在運作的模型名額。transport timeout、502/未知 503/504 進入 quarantine；下一次 health 或請求以有限 probe 確認 inflight/detached/uncertain 全為 0 後才解除，沒有背景重送。清除對話使前端忽略舊回應。一般回覆需完整 JSON、finish_reason=stop 與當次檢索引用 ID 通過檢查才顯示。

`confidence` 是狀態標籤，沒有偽造機率。引用 ID 驗證不能證明語意忠實，應以人工驗收確認。

## API

- `POST /api/chat`：`{"question":"What does miR858 do?","language":"en","history":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}`。language 只接受 `en`／`zh-TW`，省略時為 `en`；指定語言位於 system prompt，問題、歷史與來源不能覆蓋。question 最多 600 字，history 最多 4 則、每則 1000 字，body 最多 16 KiB。回傳 `answer/status/language/citations/poster_sections/confidence`。
- `status`：`answered`（引用 ID 已驗證）、`unknown`（證據不足／格式不符／結果未知）、`busy`、`unavailable`。
- `GET /api/health`：app／index／model readiness 與有限容量狀態，不含秘密。
- `GET /api/guide?language=en`：導覽 manifest，預設英文，可選 `zh-TW`。
- `POST /api/speech`：`{"language":"en","guide_id":"intro"}`（或 `clue1`／`clue2`／`clue3`），由後端取對應導覽原文；回答用 `{"language":"zh-TW","text":"完整回答"}`。只接受兩語、text 最多 4000 字，不截斷。成功回傳 `audio/wav`、`Cache-Control: no-store`；422 無效、429 忙碌、503 未就緒／失敗、504 逾時。詳見[音訊契約](docs/local-speech.md)。
- `GET /api/sources/{id}?language=en`：摘要、英文原文、版本、頁碼與區域 metadata；語言切換只改呈現標籤，不翻譯原文或改研究內容。
- `GET /api/documents/poster`、`/paper`：只提供已登錄、位於專案內的兩份 PDF，無任意檔案瀏覽。

UI 以 `textContent` 顯示回答文字，無 Markdown／HTML 執行。無帳號、上傳管理、永久對話、雲端生成或自動網路檢索。公開入口不設使用者認證，僅適合授權展覽情境的 1–3 位訪客；若要大規模公開，另定存取與資源契約。

## 驗證

```powershell
uv run --locked pytest -q
uv run --locked ruff check orchid tests
node --check orchid/static/app.js
node --check orchid/static/locale.js
node --check orchid/static/speech.js
node --check orchid/static/tour-preview/tour.js
node --test tests/speech.test.cjs tests/locale.test.cjs
# 已有Playwright及Chromium/Edge時，可另跑真實瀏覽器的跨語言回答播放回歸：
node --test tests/app.browser.test.cjs
# 完整 Node suite：先依上節建置圖片素材，並具備 Playwright + Chromium/Edge：
node --test tests/app.browser.test.cjs tests/locale.test.cjs tests/speech.test.cjs tests/tour-preview.test.cjs
uv run --locked orchid eval --mode retrieval
# app、索引與既有模型都已就緒，且當次允許推論時；序列執行，不與手動生成並行：
uv run --locked orchid eval --mode live --language zh-TW
# 保留同一中文題組，改以英文回答；字面中文關鍵字不能直接作英文品質判斷：
uv run --locked orchid eval --mode live --language en
# 固定的英文題目＋英文回答，或 --language zh-TW / both；逐題保存，不自動重送：
uv run --locked python scripts/evaluate_bilingual.py --language en
# 小批檢查可沿用 --limit；改 app port 時設定 loopback origin：
$env:ORCHID_APP_BASE_URL = 'http://127.0.0.1:8000'
uv run --locked orchid eval --mode live --limit 6
```

`speech.test.cjs` 與 `locale.test.cjs` 是不需圖片或模型的純 Node 測試。完整 suite 的兩項瀏覽器測試使用離線 API fixtures，但仍須能 resolve 已安裝的 Playwright、啟動 Chromium／Edge，且 `tour-preview.test.cjs` 會讀取本機 `.orchid/assets/tour-preview/` 圖片與 manifest。已裝 Playwright 而缺素材時會失敗；fresh clone 並非零素材即可重現完整 suite。2026-10-31 發布檢查的 GPU 停用設定、命令及原始結果保留於本機 `output/release-poster-tour-check.txt`。

`data/golden.json` 有 21 題：17 題可回答、4 題證據不足／注入／不存在的寄信操作／無關餐廳推薦。retrieval 模式是真實 CPU 檢索；live 模式先檢查產品 health，再序列呼叫實際 `/api/chat`，完整經過與 UI 相同的引用／數字／佇列／unknown 驗證。每題只送一次，遇 transport 結果未知、busy、unavailable，或 unknown 後無法確認服務 idle 即停止，沒有 fixture fallback 或自動重送。

評估工具預設明確傳 `language=zh-TW`，保留既有中文 golden 基線，不隨產品預設英文而改變。`--language en` 可檢查同題組英文回答，但題目與字面 key points 仍是原中文，需另行語意核對。每份報告與逐題結果記錄語言。工程測試及播放器事件不等於人工聽感驗收；基因名稱、公式發音、實體手機聲音仍需人工確認。

每次 live run 保留獨立 `output/evaluation-live-時間-隨機ID.json`，並以 `output/evaluation-live.json` 作最新副本；每題送出前及收到結果後都原子保存 checkpoint，中途失敗仍保留前題。`product_response` 是產品實際完整 JSON；`state=complete` 只表示這批 HTTP 評估流程完成，`blocked/stopped` 或 `in_progress` 不算完整結果。`completed_cases` 是已收到產品回覆的題數，不是答對題數。字面關鍵字檢查只是診斷，≥90% 正確率、零數字／引用語意錯誤與拒答品質仍須人工核對。Windows sandbox 若卡在 asyncio socketpair，需在允許本機 loopback 的正式執行環境跑同一份測試，不改測試假裝通過。

實作檔：`orchid/corpus.py`、`retrieval.py`、`generation.py`、`app.py`、`cli.py`、`evaluation.py` 與 `orchid/static/`。驗證與未完成項目列於 `docs/implementation-report.md`。
