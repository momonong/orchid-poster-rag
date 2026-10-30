# 獨立海報導覽試作

入口為既有 FastAPI 的 `/tour-preview/`，不是 `/static/tour-preview/`。這個獨立試作新增導覽頁、素材建置腳本與 focused tests；首頁、backend、共用 `speech.js` 和既有資料契約均保留。2026-10-30 試作階段未提交、合併或推送；2026-10-31 使用者已確認本輪 UI 並授權合併與推送，實際 Git 結果另行核對，不由此文件預先宣稱完成。

## 內容與手機操作

- 英文預設，切換繁體中文只改介面與導覽文字；海報始終使用英文原版。只儲存 `orchid-language` 偏好，不儲存對話。
- 完整海報有八個可點區域；`#clue2` 等 hash 可直接開啟完整區塊，保留標題、圖與圖說。返回總覽保留本次瀏覽位置。
- 真正 HTML 文字預設顯示：正文 18px／1.6 行高，A+ 依序切換 20、22、18px。完整導覽是六段固定 narration；detail 另加一段有來源的深入說明。可展開選取原海報提取文字，PDF 為原文版面依據。
- 窄 sticky 控制列提供播放／暫停／繼續、停止、手動跳至目前文字、提問。沒有自動縮放或捲動。提問會暫停音訊，關閉後保持暫停，由使用者選 Resume。
- 原圖可開啟檢視器，再切換完整像素平移；Esc 關閉並還原焦點。沒有鎖定瀏覽器最大縮放。

## 建置素材

先將 `data/sources.json` 登錄且 SHA 相符的原海報 PDF 放在指定的專案相對位置，再於既有專案 Python 環境執行，不新增依賴：

```powershell
uv run --locked --offline python -B scripts/build_tour_assets.py
uv run --locked --offline python -B scripts/build_tour_assets.py --only discussion
```

直接由已登錄 PDF 的完整 `regions` clip 輸出 lossless WebP，不從整張低解析預覽裁切放大。總覽目標 800/1600px；各區目標 800/1600/2400px。render 邊界會多 1px，因此前端使用 manifest 的實際 801/1601/2401 等寬度建立 srcset。只載入目前畫面的圖片；其他區域在點選後載入。

`.orchid/assets/tour-preview/manifest.json` 記錄來源 PDF SHA、點尺寸、normalized bounds、圖片 URL、實際尺寸、bytes 與提取文字。Discussion bounds 下緣採 `.557`，包含結論末行，止於 References 之前；其他區沿用 `data/sources.json` 的 `regions`。不修改 `image_regions` 或來源 PDF。原始 PDF、衍生圖片、manifest 與音檔都在 Git 排除範圍；新 checkout 必須另行準備原 PDF 並執行建置，腳本不自動下載來源。Clue 2 原生內嵌點陣圖約 1264×1168px；高解析輸出能改善字型、向量與呈現密度，不能新增科學圖原本沒有的細節。

## 預製完整導覽音訊

僅在既有語音服務已運行且當次已授權語音生成時，序列執行：

```powershell
uv run --locked --offline python -B scripts/build_tour_audio.py --base-url http://127.0.0.1:8000
```

這會只向既有 loopback `/api/speech` 請求`tour_order` 原六段×兩語言固定 overview narration（八區探索 `order` 的新增兩區不加入整體錄音），驗證 24kHz／mono／16bit／非空 WAV，寫入 ignored 的 `audio/`。只有與 backend `guide_id` 實際完整文字精確相同才使用該 ID；其餘傳精確文字。腳本不啟動服務或模型，失敗即停止，不自動重試。

前端用 manifest 的 language/id/textSHA 對照目前 narration，精確匹配才由既有 speech controller 的 fetch adapter 讀取準備好的 WAV。static 音檔失敗不退回 API 重送。detail 的 narration＋深入說明仍由現有 API 按需產生，會明示準備狀態；沒有新增音訊 queue。訪客頁只顯示約 2 分鐘與 manifest 計算的實際錄音長度。

本輪預製錄音為英文 112.5866 秒（顯示 1:53）、中文 116.4474 秒（顯示 1:56）。兩者略短於最初 2–3 分鐘目標下限；這是開發驗收註記，不放在訪客頁。時長不包含段落之間的載入／停頓，也不代表人工聆聽接受。

## 問答與來源界線

問題前加固定、短的研究／海報區塊背景，包含背景後最多 600 Unicode 字元；超限不送出、不截斷問題。只送最近四則 history、每則最多 1000 字元。pending 防重，清除會 abort 本次 fetch 並撤銷 epoch，舊結果不會回到新對話；不表示已證實伺服器模型工作立刻終止。80 秒 client timeout 會顯示狀態，不自動重送。health 有 10 秒 timeout，可手動重查。

`/api/chat` 與 `/api/sources/{id}?language=...` 沿用原契約；回覆與節錄以 textContent 呈現，來源可開啟 paper/poster 原文。paper 是研究證據主體，poster 提供展場定位；論文方法與海報新增 FEM 不混稱，模型預測與實驗證明分開。

## 驗證與尚待人工接受

`node --check orchid/static/tour-preview/tour.js`、`node --test tests/tour-preview.test.cjs tests/speech.test.cjs`。Browser test 使用離線 route fixtures 和假 Audio，沒有呼叫真實 TTS／RAG。執行完整瀏覽器測試前，必須先準備已登錄原海報 PDF、執行 `scripts/build_tour_assets.py`，並能 resolve 已安裝的 Playwright、啟動 Chromium／Edge；fixture 仍會讀取 ignored 的圖片與 manifest。缺 Playwright 時 browser test 為 skip，已裝 Playwright 但缺素材時則會失敗，不能將 fresh clone 視為零素材可重現。純 `speech.test.cjs`／`locale.test.cjs` 不需這些圖片。

focused 檢查包括問題/history 上限、stop/ended 競態、精確音訊匹配與無暗中重試、Clue 2 hash/返回、關閉提問不自動出聲、清除忽略舊回覆、client timeout、320/360/390/430px、DPR 1/2/3 和桌面 body 不水平溢出。圖像檢視器內的平移是允許的。

2026-10-30 初次試作的 `tour-preview.test.cjs` 與既有 `speech.test.cjs` 合計 26/26 通過、沒有 skip；八區更新後為 27/27。2026-10-31 發布前完整四檔 Node suite 為 29/29 通過、0 skip。包含真實瀏覽器自然結束會先 pause 再 ended 的 regression：active run 的 playing/paused → idle 均可續播，explicit stop 在撤銷 run 後不會誤進下一段。這個檢查不修改 shared speech controller。

真實 HTTPS、RAG、來源、音訊播放與實際手機可達性由原目標對話核對；單元與 mock browser 通過不等於音訊聆聽接受或全套研究結論驗證。

### 本輪真實預覽證據（2026-10-30）

原目標對話已在既有 HTTPS 預覽實測：完整海報 → Clue 2 → 原解析度圖片 → 引用原文 → 中英文切換，以及英／中文各一題 RAG 問答成功；P08_1 原文節錄可開啟。英文完整導覽已由 intro 順序播放六段，到達「The guide has finished.」，確認自然 pause-before-ended 的續播修正有效。

Read along 以鍵盤 Enter 觸發後，閱讀內容頂緣約 149.8 CSS px、sticky 控制列底緣約 133.7 CSS px，文字位於控制列下方可讀區。這是使用者主動捲動，不會隨音訊自動捲動。首次指標操作的觀察未到達預期位置，原因尚未確定；後續鍵盤操作成功，沒有加入 CUA 特例。

中文音訊亦已在真實 HTTPS 網頁開始播放並續至後續段落；播放中開啟提問會暫停，關閉提問後維持暫停，按「繼續播放」可恢復。這是瀏覽器播放狀態驗證，尚未由真人確認發音與聆聽品質。

`output/tour-preview-mobile-overview.png` 與 `output/tour-preview-mobile-clue2.png` 是既有實際網站的 390×844 CSS px、DPR 3 畫面（PNG 為 1170×2532px），不是線框或重繪科學圖。實際頁面 body 寬 390px；總覽採 1600px variant、Clue 2 採實際 1601px variant，HTML 正文為 18px。使用者已於 2026-10-31 確認本輪 UI 並授權整合；音訊發音接受仍未確認。

## 八區與按鈕層級更新

本輪保留layout、18px/A+和原六段錄音，新增Reference與海報Supplementary兩區；`order`用於八區探索，`tour_order`固定原六段完整導覽。原海報補充、相關既有節錄及期刊獨立5頁補充PDF分別呈現；未變更evidence、索引或backend，不保證補充區所有問題都可回答。按鈕/框線、before/after量測與CPU fixture檢查詳見[視覺調整紀錄](poster-visual-polish.md)。八區視覺更新及發布前檢查未執行真實chat、生成、embedding、TTS評估及模型服務啟停。

## 發布前離線複核（2026-10-31）

完整四檔 Node suite：29 passed、0 failed、0 skipped；兩個 Edge browser tests 均實際執行，GPU disabled，API 由 fixture 攔截。四支網站 JS 和四支 CJS 語法檢查、兩支建置腳本 AST 語法及 Ruff 均通過。原目標對話另執行既有 Python fixtures：103 passed in 2.68s，`ruff check orchid tests` 通過，未載入模型權重。

design-taste app lint 為 0 FAIL、2 WARN，仍是 SHA bytes 與時長格式必要的 `padStart`；原 inspector 的四項 WARN 保留在視覺紀錄，未宣稱全部無警告。命令與精簡原始結果存本機 `output/release-poster-tour-check.txt`；不入 Git。這輪只更新交付文件，未更動使用者接受後的 runtime 程式，亦未重跑真實問答或語音。
