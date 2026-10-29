# 雙語音訊整合驗證（2026-10-30）

本次以 Windows RTX 5090 Laptop 為試用機；語音使用 CPU 兩執行緒。既有 Qwen 與 ngrok 未重啟，僅更新本專案的 loopback 8000 應用。尚未搬到其他主機。

## 已核對

- 最終工程收據：103 pytest、21 Node、Ruff、三份 JavaScript 語法及 `git diff --check` 通過。收據的程式檔案指紋已與工作樹核對。
- 公開 HTTPS 瀏覽器：英文／繁中介紹、線索導覽、英文與中文實際回答都進入播放；暫停、續播、停止、切語言、切線索、清除對話與來源開啟已操作確認。
- 390 × 844 CSS viewport：介紹播放鍵位於首屏；播放控制列捲動後仍可見，未出現水平溢出。播放舊英文回答不改變中文介面。
- 實際中文回答：產生 27.899 秒、24 kHz 單聲道 PCM16 WAV，合成等待 13.25 秒。
- 三筆獨立音訊請求：均為 200、不同 WAV，總等待分別 5.922／13.047／19.625 秒；同時第四筆為 429。當時 active=1、pending=2。
- 真實 HTTP 斷線回歸：修正前，取消後 10 秒仍未釋放名額；查明中介層阻斷 `is_disconnected()` 的立即取消探測。改為讀完 body 後等待 ASGI disconnect，修正後同一情境在 3.703 秒釋放名額。原生合成仍需到 callback 才能停止；不能宣稱即時中斷。
- 新發現的中文錯述「PeMYBx 透過 G_H 活化自身」已依 P03 原文加入聚焦拒絕規則；實際重問會回傳 unknown，不顯示該錯誤。這不是完整語意驗證器。

## 收據與限制

本機忽略目錄中的 `output/portable-audio-validation.json`、`output/portable-audio-live-final.json` 保存工程與實際 API 證據；後者保留斷線修正前失敗及修正後結果。`output/portable-audio-observed-zh-error.json` 保留研究錯述樣本。語音模型、WAV 與原始 PDF 不進 Git。

瀏覽器媒體事件、音訊格式與效能測試不等於人耳驗收。英文部分 fallback 有 `ɚ` 音素警告；專有名詞、聲線自然度、實體手機／iOS／行動網路仍待試聽。Linux 尚未實測，部署與模型佈建步驟見 [本機語音說明](local-speech.md)。

目前入口仍為既有 ngrok 試用網址。建議先在筆電完成人工試用，再評估可長期保留 GPU 資源的實驗室 5090 桌機；固定網域與主機遷移另行準備，家中 4090 不列為目標。本文件記錄 baseline 合併前的驗收；提交與合併版本以 Git 歷史為準，部署狀態另行核對。
