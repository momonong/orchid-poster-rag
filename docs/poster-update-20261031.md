# 新版海報與 Supplementary 同步更新

來源接收：2026-10-31；最終驗證：2026-11-01（Asia/Taipei）。本次範圍為學姊提供的新版海報，以及目前導覽網站的圖材、雙語解說、語音、RAG 來源與資料更新流程。沒有修改生成策略或模型部署。

## 已核對的版本差異

- 新原檔：`盧提文_理學院研究日.pdf`，11,443,368 bytes，1 頁，2383 × 3368 pt。SHA-256：`b1a8378e6a317fa4b3cd1ed2fe6f690038e60a580ac481376a53244be50a9107`。原始檔另存於部署 worktree，`data/sources.json` 已指向新版；舊 `理學院研究日.pdf` 保留，未覆寫。
- 新舊 PDF 的可抽取文字相同；差異在內嵌圖片與圖像位置。逐項對照新 PDF、舊 PDF 與使用者附圖，確認新版量綱表。只做文字擷取不能發現這次更新。
- 舊圖以 C_A、C_H 分別書寫濃度量綱；新版明示 A 與 H 使用共同濃度單位 C，T 為時間、L 為長度。這是單位慣例的明確化，不是宣稱模型方程或實驗結果改變。

| 量／參數 | 新版表列單位 |
|---|---|
| A、H、k | C |
| ρ_A | C/T |
| D_A、D_H | L²/T |
| µ_A、µ_H、G_A | 1/T |
| G_H | 1/(C·T) |

細胞間耦合圖保留 no A flux、H 的跨細胞 D_H 箭頭與 apparent (effective) D_A。說明明確標成海報的模型詮釋，未宣稱運輸實驗或固定擴散係數的等效推導；原論文方程仍有 D_A∇²A。獨立期刊補充 PDF S1–S5 與海報補充圖保持不同來源。

## 同步內容

- 從新版 PDF 重建舊首頁圖片、完整海報與八個區塊，共 26 張 tour-preview WebP；總覽 800／1600，其餘 800／1600／2400 像素級版本。圖片 manifest 與所有活躍海報 source locator 均綁定新 SHA。
- 更新 Supplementary 英文／繁中 narration、detail、來源按鈕名稱與直接圖像定位；預設英文及原版英文海報不變。
- 新增 S05（新版量綱表）與 S06（細胞間耦合詮釋）。圖片文字經目視轉錄，記錄 `original_excerpt_method=manual_transcription_of_embedded_image`，不是宣稱 PDF 有可抽取文字層。兩者都指向完整數學補圖 `[0.710323,0.837909,0.929176,0.998729]`，避免切掉表尾或圖說。
- 全部 23 筆摘要與 23 筆英文譯文對齊 canonical ID，更新 corpus SHA 綁定；CPU 索引為 35 chunks，上限 480 embedding tokens。復用 `.cache/e5-model` 的固定 multilingual-e5-small，未下載權重。
- 補充導覽使用更新後的 narration + detail 即時合成本機 CPU WAV。既有六段完整導覽的十二份預製音訊沒有改文案；仍須逐項核對文字 SHA 與 WAV SHA，避免誤用舊音訊。
- 固定題組增加 G22／G23，中文與英文問題各 23 題；19 題可回答、4 題預期拒答。`prepare` 省略 PDF 參數時沿用已登錄版本，避免選回舊海報；既有指紋不符仍須校對後使用 `--accept-reviewed`。

## 驗證結果與界線

- 最後乾淨環境：104 Python tests passed（1.33s）；Ruff passed；29 Node tests passed、0 skipped（含既有 Edge 手機版面／播放器 fixtures）。`prepare` 新回歸測試先見到舊檔名失敗，再通過已登錄來源版本。
- CPU 檢索：23 題完成，19/19 可回答題取得預期來源；G22 首項 S05，G23 首項 S06。這不是 23 題全部生成品質驗收。
- 實際 Qwen 產品 API：新版量綱／耦合各以英文與繁中提問，共 4/4 answered，引用均為 S05／S06；逐項人工對照單位與模型／實驗界線。等待分別為英文 1.219／0.922s、繁中 4.156／3.359s。完整歷史題組本輪未重跑 live。
- 英文補充 WAV：69.160s、3,319,712 bytes、合成 30.406s；繁中：80.615s、3,869,544 bytes、合成 33.094s。均為 24kHz／mono／PCM16、文字 SHA 相符。這些是準備與檔案幾何驗證，尚未經學姊逐句確認發音。
- 已於既有外部 HTTPS 頁面核對新版雙語解說、S05 量綱來源視窗，以及手機尺寸的圖片放大與約 2400 像素 variant；英文補充導覽在真實瀏覽器到達播放結束，公開 PDF 的 bytes SHA 與新版原檔一致；實體手機行動網路本輪未重測。
- 首次並行 CPU 建置時，既有 10ms 音訊快取測試 `test_answer_audio_is_evicted_without_another_request` 曾因排程延遲失敗；建置結束後完整測試通過，未修改其斷言。另一次測試 shell 繼承啟動用 context 環境變數，使 `test_undeclared_context_is_not_assumed` 失敗；清除僅供啟動使用的環境設定後，上述最終完整測試通過。應用程序保留原 8192 context 設定。

公開試用入口仍為既有 ngrok HTTPS：`/tour-preview/#supplementary`。只重載導覽應用以載入新索引；Qwen、ngrok 及其他服務沒有被本輪啟停。原始 PDF、圖片、WAV、向量與驗證輸出均由既有 ignore 排除 Git；本次尚未提交、合併或推送。

部署機主專案的 `output/poster-update-20261031/verification.json` 保存四題產品回覆與兩語音訊的驗證資料；同目錄保存 WAV 與瀏覽器截圖。新語料與精確定位的最終一致性檢查亦存於該目錄。這些產物不作永久訪客對話紀錄。
