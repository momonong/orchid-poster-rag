# 雙語語音版驗證紀錄

日期：2026-10-29（Asia/Taipei）。基線 `3900ee1`；功能分支 `feat/bilingual-voice-guide`。此文件分開記錄工程、模型語意、瀏覽器控制與人工聽感，不把其中一項替代其他項目。

## 工程與靜態內容

初次實作後 56 項 pytest、7 項 Node 測試及 Ruff／3 份 JS syntax／diff check 通過。英文檢索修正後為 **61 項 pytest、7 項 Node 測試通過**；最後僅修改英文 prompt，重跑 61 項 pytest、Ruff、diff check 通過，未變的 Node 證據沿用。獨立工程審查與後續英文檢索修正審查未發現重大問題。語音回歸包括取消後全域 paused 保留、舊 utterance 回呼、缺少相符的本機語音與取消失敗。英文介紹、Clue 1–3 及來源標題經獨立代理對照既有資料，沒有發現科學主張擴張。

## 初次真實模型測試（待修正的歷史結果）

`output/bilingual-live-20261029T130236Z.json`：21 題英文與 5 題繁中，序列呼叫隔離 app 8002 的 `/api/chat`，無自動重送。

- 英文可答題經來源核對為 10/17 通過；4 題不可答正確拒答。
- 5 個 answered 的問題是漏掉 miR858 表達降低條件、海報／論文圖號混淆、圖號映射錯誤，以及 2 題額外敘述的引用支持不足。
- G07、G14 保守拒答；單次診斷分別確認過度必要性措辭與檢索缺少閾值來源。
- 繁中 4 個 answered 通過、1 題未知正確拒答。
- 詳細審查與診斷保存於 `output/bilingual-science-review.md`、`output/bilingual-diagnosis.json`；未覆寫原始結果。

第二次 `output/bilingual-live-20261029T132413Z.json`：英文 15/17 可答題通過，4 題不可答正確拒答。G07 拒答；G16 把研究範圍校註提升為「作者明確聲明」，引用歸屬不受原文支持。繁中抽查 3/4 可答題通過、G17 拒答，G18 正確拒答。這批未達門檻，沒有更新公開入口。報告為 `output/bilingual-science-review-final.md`（檔名為當時的審查，不是本次功能最終驗收）。

依一次受限診斷 `output/bilingual-abstentions-20261029T132912Z.json`，G07 的多餘第二句把空間異質設定說成必要條件，原 scope guard 正確拒絕；繁中 G17 同設定的診斷回覆通過，顯示生成仍會波動。後續只收斂英文 prompt 為單段最多兩句、僅答所問、區分校註與作者明示。繁中 prompt、scope guard、語料、索引與數值檢查均保留；沒有用題號或固定答案規避驗收。診斷原文不是訪客收到的產品答案。

## 初版 SpeechSynthesis 瀏覽器觀察（歷史）

在 Codex in-app browser 操作 `http://127.0.0.1:8002`：

- 無既有偏好的 origin 首次使用 English。English／繁體中文切換連動頁面標題、導覽、建議問題與控制；展開介紹保留對應內容。
- 目前此瀏覽器提供相符的繁中本機 voice，沒有可用的本機英文 voice。英文播放明確停用並顯示說明，不改用遠端語音。
- 實際點選繁中介紹播放、暫停、繼續、停止，再播放線索；已觀察 `starting` → `playing`、`paused`、`idle` 的 UI 狀態。暫停後停止再播新段能開始；播放中切 English 會停止舊段。
- 上一條／下一條可切換對應線索與來源。P11 來源視窗呈現原始英文、paper Figure 7/page 7，繁中校註獨立標示；重新整理保留所選語言。
- 英文問題送出後切成繁中，收到的答案仍保留英文；接著繁中問題以繁中回答並可點播放。清除對話會清除訊息並停止播放。這些是前端語言與控制行為證據，不取代逐題科學審查。
- 以上是瀏覽器控制與事件證據，未由研究作者或使用者確認耳朵聽到的聲音、音色與專有名詞發音。不能宣稱人工聽感通過。
- 以 390×844 viewport override 檢視英文長頁，DOM 回報可用寬度 375px／scrollWidth 375px；語言、語音、線索與提問控制可呈現。真正手機、行動網路與實體相機掃碼仍待驗收。

初版英文語音受訪客已安裝 voice 限制，使用 `localService=true` 且語言匹配的聲音。此方案已由下述本機 CPU 音訊取代；沒有安裝 Windows 語言套件、開啟麥克風或新增雲端 TTS。

## 最終模式與驗收

英文自由轉述未達標，因此沒有直接發布。`133339Z` 的 42 題為英文 13/17、繁中 14/17；加入英文摘要並恢復繁中原版輸入後，`134933Z` 為英文 13/17、繁中 16/17。各語言不可答題皆 4/4 正確拒答。原始結果及獨立審查保留，不用單題重跑取代失敗紀錄。

最終英文採抽取式 RAG：Qwen 根據問題與追問，從前四筆來源的已核對英文摘要選一至兩個完整段落；後端原字組合並附當輪來源 ID。模型不能重寫數值／機制或插入額外 answer。譯文綁定原 corpus hash；缺失、過期或不完整時 unavailable。非法選取、重複 canonical 段落或超過 512-token 答案時 unknown，不截斷條件。頁面明示 **Reviewed source summary**。選段仍可能不切題，因此驗收另核對直接答題性。

- 工程：**92 pytest、7 Node** 通過；Ruff、3 份 JS syntax、diff check 通過。獨立工程審查無具體阻擋。
- 英文：`output/bilingual-live-20261029T140448Z-1e6b0a8b.json`，**17/17 可答題通過、4/4 正確拒答**。逐題核對數值、條件、來源與直接答題性，未見中重大科學錯誤。報告：`output/bilingual-science-review-extractive.md`。
- 繁中：沿用 `output/bilingual-live-20261029T134933Z.json` 中完整 21 題，**16/17（94.1%）可答題通過、4/4 正確拒答**。G07 保守拒答仍計未通過。最終版繁中完整 request payload 與原版相同，英文抽取式沒有更動該路徑或 guards；收據為 `output/bilingual-extractive-zh-baseline-check.json`。
- 完整 API 等待時間（含各語言 21 題 answered／unknown）：英文 **0.55–1.75 秒，中位數 1.02 秒**；繁中 **3.203–8.737 秒，中位數 4.867 秒**。僅代表暖機後單人序列測試，不保證其他問題、多人或行動網路相同。

上述是固定題組及獨立代理審查，不等於研究作者／使用者人工接受。英文完整段落可能較長；G11 的「above」指完整來源前段，G16 含額外但有據的背景，列為可讀性限制。

## 公開試用與啟停

功能工作樹 app 已接到原 `127.0.0.1:8000`，測試 8002 已停止；既有 ngrok、HTTPS 網址與 QR 不變。沒有重啟 Qwen、NeuroAI 或變更網路設定。原 main 程式保持原樣，本次功能尚未 commit／merge／push。

科學版公開 HTTPS 瀏覽器已確認預設 English、研究與模型 ready、一題英文問答呈現 Reviewed source summary、P10_1 可開啟原文／Fig. 6／頁碼；繁中切換與線索播放控制可操作，切回 English 停止播放。初版瀏覽器沒有英文 local voice 的問題，已由下述本機 CPU 音訊取代。人工聽感、實體手機行動網路與相機掃碼仍待驗收。

serving checkout 的本機路徑、PID 與網址記於忽略的 `output/bilingual-preview.json`。啟停應在該工作樹執行 `.venv/Scripts/python.exe -m orchid.cli status|stop|start`，先核對 `.orchid/app.json` 與閒置狀態；不要在原 checkout 另啟一個 8000 副本。

## 重現英文問題驗收

`data/questions.en.json` 保存已核對的 21 題英文問題與追問；answerable／來源預期對應 `data/golden.json`。服務就緒、閒置且當次允許推論時執行：

```powershell
.venv/Scripts/python.exe scripts/evaluate_bilingual.py --language en --base http://127.0.0.1:8000
# --language zh-TW 或 both：繁中或兩語，每題只送一次。
```

腳本只接受 loopback HTTP，保存唯一命名 checkpoint，不自動重送。state=complete 僅代表收齊回覆，仍須另外審查語意與來源。

## 本機雙語音訊實作（2026-10-30）

以同一 FastAPI 的 CPU Kokoro／sherpa-onnx 及 HTMLAudio 取代初版 SpeechSynthesis，不再依賴 OS voice。固定模型、archive／檔案 SHA、授權、Windows／Linux 可攜邊界及完整效能收據見[本機雙語音訊](local-speech.md)。保留科學生成 prompt 與已審核英文選段，也沒有重跑或覆寫上述 Qwen 題組。

- 工程：103 項 pytest；20 項 Node 控制器／語言測試，加 1 項已安裝 Edge 的真實頁面回歸。涵蓋 WAV API、語言／字數／欄位邊界、忙碌與逾時、CPU worker 真正結束前不釋放名額、ASGI 斷線事件穿過原中介層後確實傳給 CPU 取消信號、回答音訊自行到期、不落地私密回答、舊 fetch／媒體事件隔離、播放封鎖後沿用 blob，以及中文介面播放舊英文回答不切換偏好。
- 整合時新增實際失敗：中文回答將 PeMYBx 說成「作為抑制者 H 透過 G_H 活化自身」。P03／P04 明確是 A 以 G_H 活化 H，H 不自我活化；既有引用／數字檢查不能防止這個機制錯誤。因此只在 `validate_claim_scope` 新增具主體範圍的錯述拒絕，失敗回傳 unknown，不顯示可播放答案。回歸確認已觀察錯誤被拒、正確 A 自我活化＋A 促進 H、明確否定 H 自我活化及 H 抑制 A 的描述仍通過。這不是通用科學語意驗證，舊模型通過率不能替代所有新問題的人工驗收。
- 真實 CPU：八段完整英中 introduction／Clue 1–3 均產生 24 kHz mono PCM16 WAV，首次合成約 5.64–12.56 秒；導覽快取已預錄。精確數值 P12 17.97 秒；既有最長英文回答 G16（1198 原文字元）30.09 秒產生 77.21 秒 WAV。完整旁讀文字保存在 `.orchid/speech-smoke/`，不截斷原文。
- 中文字元：四段繁中導覽及 21 份既有摘要在僅旁讀的 t2s 轉換後，425 個不同 CJK 字元在模型詞典缺字為零；不是人工發音驗收。
- 根對話在公開頁實測英中 introduction 的播放／暫停／續播／停止／切語言、英文真實回答播放及清除取消；API 英中 introduction 均為 200 WAV，快取約 0.015／0.016 秒。手機首屏入口及最後版本的其餘現場檢查由根對話接續核對。
- 保留限制：部分英文 fallback 有 U+025A `ɚ` token 警告，未宣稱人耳聽感、台灣口音、iOS 實體機聲音、行動網路或 Linux 執行已通過。音訊生成、瀏覽器事件及人工接受分開記錄。
