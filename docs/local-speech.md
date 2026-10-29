# 本機雙語音訊

2026-10-30；功能分支 `feat/bilingual-voice-guide`。沿用同一 FastAPI，CPU 兩執行緒，不呼叫外部 TTS、模型服務或 GPU。保留生成 prompt 與研究選段；整合時發現抑制者 H 自我活化錯述，另加最小拒絕保護，詳見雙語驗證紀錄。

## 版本、模型與安裝

Python 3.12，`sherpa-onnx==1.13.3`、`opencc-python-reimplemented==0.1.7` 固定在 `pyproject.toml`／`uv.lock`。首次在專案根目錄執行（Windows PowerShell 與 Linux shell 的 uv 命令相同）：

```text
uv sync --locked
uv run --locked python scripts/provision_speech.py --download --smoke
```

模型為官方 [kokoro-multi-lang-v1_1](https://k2-fsa.github.io/sherpa/onnx/tts/all/Chinese-English/kokoro-multi-lang-v1_1.html)，來源是 [Kokoro-82M-v1.1-zh](https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh)。[固定下載](https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-multi-lang-v1_1.tar.bz2) 共 364,855,331 bytes，SHA-256：

```text
b78e1ac42b852e839cceaafbe88f66806bf5860992d1d7b9a3f2ad1198427aed
```

佈建腳本先核對 archive hash，再核對其 377 個檔案，寫入 `.cache/tts/kokoro-multi-lang-v1_1/provision.json`；首次載入再核對檔案 hash。模型 archive 內含 Apache-2.0 `LICENSE`；保留模型及 runtime 的原授權檔，模型授權不代替所有內含軟體的授權。模型、archive、快取及測試 WAV 均排除 Git。沒有更新原本 embedding／Qwen／torch 配置。

`model.onnx` SHA-256 為 `99db0bc8fd0c5033d249fe922db16768b71b4a6b26cfd93d206fbf66c76efb5f`；`voices.bin` 為 `e64a5a581d8c2a350d848f51c3121657cd83aa07ed6109172177345874a7244c`。英文用官方 sid 0 `af_maple`，中文 sid 3 `zf_001`，輸出 24 kHz、mono、PCM16 WAV；不宣稱中文聲線是台灣口音。

選擇 1.13.3 的實測理由：2.0.1 移除內建 espeak 詞外讀音後，Phalaenopsis／研究識別字曾被略讀。1.13.3 支援詞外讀音，配合科學識別字逐字旁讀。一次 `lang=en-gb`／sid 2 的受限診斷因 `Failed to set eSpeak-ng voice` 停止，沒有變更產品配置。Windows x64、Python 3.12 已實測；程式與安裝命令保留 Windows／Linux 可攜方式，尚未在 Linux 或未來實驗室桌機執行。

## 音訊及播放契約

`POST /api/speech` 接受 `language: en|zh-TW`，省略為 en。`guide_id` 只查詢 `intro` 或三個現有 clue ID，由伺服器讀取對應導覽原文，不接受任意路徑。回答傳 `text`，最多 4000 字且禁止空白／額外欄位，沒有靜默截斷。成功是 `audio/wav`、`Cache-Control: no-store`；422 無效、429 等候滿／等候逾時、503 未佈建／合成失敗、504 準備逾時。`/api/health` 的 `speech` 提供 ready／支援語言／sample_rate／active／pending／容量，沒有路徑或文字。

容量獨立於 Qwen：一筆 CPU 合成、最多兩筆等候；等候最多 20 秒，HTTP 準備最多 100 秒。生成以句子 callback 檢查 80 秒期限及取消信號；C++ 單句不能強制中斷，因此取消／逾時後保留 active 名額，直到真實 worker 結束，不讓第二筆合成並跑。WAV 上限五分鐘／14,400,044 bytes。超限或失敗不回傳部分音訊，不自動重試。

斷線監聽在 FastAPI 已消耗完整 JSON body 後直接等待 ASGI `http.disconnect`。整合發現 `Request.is_disconnected()` 的立即取消探測在現行 BaseHTTPMiddleware receive checkpoint 前就被取消，導致 CPU 收不到斷線信號；已修復並用原路由／中介層及可控 worker 回歸確認取消可達、完成後釋放名額及不留回答快取。這不代表原生 C++ 可以立即中止，仍以真實 callback／worker 結束為準。

靜態導覽由已核對原文合成，按模型／runtime／語言／旁讀文字 hash 保存 `.cache/speech/*.wav`。回答只保存記憶體音訊，最多六筆及 24 MB，120 秒自行到期清除；不保存問題、對話、回答文字或回答音檔至磁碟。忽略目錄中的驗證 WAV 僅使用明確指定的公開研究文本。

播放器準備中可 Stop、不可 Pause。非同步 fetch 完成後若 `audio.play()` 被瀏覽器阻擋，顯示再次點 Play；同一段使用已備妥 blob，不重新合成。停止／新播放／切語言／清除對話會中止 fetch、使舊回覆與媒體事件失效並釋放 blob URL。播放中的緊湊控制列保持頂部可見；歷史回答用其原語言播放，不切換整頁語言或寫入偏好。

## 旁讀與內容邊界

只修改送給 TTS 的副本：移除來源 ID／呈現標記，PeMYB11、PeMYBx、HORT1、miR858 逐字拼讀，參數保留各下標字母。英文小數逐位讀出，例如 `0.0296` → `zero point zero two nine six`，避免共用模型的中文數字 FST 改用中文讀數；比較符號與 µM 單位明確旁讀。畫面文字、引用、生成 prompt 與英文選段不因 TTS 改動。

繁中以 OpenCC t2s 僅轉換送入模型的字元，配合原模型中文詞典；畫面與來源仍為繁體中文。完整導覽四段及 21 份繁中研究摘要，轉換後 425 個不同 CJK 字元在詞典中缺字為零；這是字元覆蓋檢查，不是發音或語意驗收。

## CPU 實測與限制

本機 Windows、CPU 兩執行緒的首次完整合成：

| 文本 | 合成等待 | WAV 長度 |
| --- | ---: | ---: |
| 英文 introduction（428 原文字元） | 11.80 秒 | 26.78 秒 |
| 英文 Clue 1–3 | 5.64–6.53 秒 | 14.51–16.97 秒 |
| 繁中 introduction（138 原文字元） | 12.56 秒 | 29.22 秒 |
| 繁中 Clue 1–3 | 6.23–6.91 秒 | 15.27–16.30 秒 |
| 英文精確參數 P12（520 原文字元） | 17.97 秒 | 41.65 秒 |
| 既有真實回答最長 G16（1198 原文字元） | 30.09 秒 | 77.21 秒 |

靜態八段已預錄；同機 API introduction 快取回應英文 0.015 秒、繁中 0.016 秒。這些不是手機下載時間或多人負載保證。4000 字是拒絕上限，不保證每段能在期限內完成。

完整旁讀文字、WAV 與效能／字元覆蓋收據位於 `.orchid/speech-smoke/`（`report.json`、`boundary-report.json`）。最初 2.0.1 小樣：模型載入 1.49 秒、英文 108 字 2.53 秒產生 5.93 秒音訊、繁中 100 字 6.70 秒產生 17.02 秒音訊；因專名漏讀不採用，後續以完整 1.13.3 文本和 WAV 驗收。

1.13.3 在部分英文詞的 fallback 仍會回報 `ɚ`（U+025A）不在模型 token 的警告；已沒有觀察到 2.0.1 的整個 Phalaenopsis／研究名稱略讀，但這個單音的聽感影響尚未人工確認。另有載入詞典的 `❓` token 警告。不可把檔案成功、時長、瀏覽器媒體事件或字元覆蓋當成人耳聽感通過；專名、數值、聲線、實體手機／iOS 聲音仍需使用者試聽。
