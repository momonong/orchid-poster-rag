# 海報導覽按鈕與八區入口調整

2026-10-30。沿用使用者已在手機確認的大框架：總覽 → 完整區塊 → 閱讀／聆聽／提問，英文預設、繁中切換與英文原海報不變。這是 component restyle，依 design-taste-frontend 的 app-screen 規則檢查，不重新抽設計方向或重建 layout。

## 本輪設計

畫面核心問題是「我能點哪裡、目前能做什麼？」。主要物件是原海報和導覽文字，不是來源ID。播放維持唯一深藍主操作；閱讀和提問是清楚可辨的次要按鈕；PDF、文件、章節導覽與來源使用有邊框、開啟語意的控制，保留真正 a/href。

八區入口為 Introduction、Methods、Clue 1–3、Discussion & conclusions、References、Supplementary。海報保留完整透明框，短標籤與加號表示可放大，不在圖內加整片遮色。Reference在320px手機上原區域只有約33px高，地圖入口保持貼合原bounds，不硬擴張以免點到鄰區；外部另提供44px高的References按鈕作等效操作。其餘一般控制與八區按鈕導覽均至少44px。

來源改以可讀題名呈現，ID為次要資訊；一組來源預設收於單一清楚控制，避免長Pxx chips擠滿正文。新補充圖的直接來源是原海報區塊，相關P/S節錄另標「相關來源」。期刊獨立5頁補充PDF另列，不與海報補充示意混稱。

18px／1.6正文、A+20／22、44px觸控與瀏覽器縮放保留。新增 `tour_order` 固定原六段完整導覽，`order`負責八區導覽；不重製音訊、不呼叫模型／TTS／embedding、不改首頁/backend/shared speech.js。

## Before 證據與 critique

原稿保存在 `output/poster-polish-before/source/`。HEAD為`3140682219ed1832d50d329a10e4b0ca815e722d`。技能inspector以既有網站靜態GET執行，health由fixture回應，其他API與外部網路阻擋，使用CPU headless Edge；沒有另開專案server。初次CDP launcher的Edge code0退出，以同機已驗證的Edge旗標修正，沒有安裝依賴或改技能。

- 1440／768／390：0 FAIL、4 WARN。before六張fold/page截圖均已目視。
- lint：0 FAIL、2 WARN，兩處補零分別是SHA byte與時長格式，屬必要資料格式。
- 最有影響的三點：閱讀／提問看似普通超連結；海報框沒有開啟語意；大量相同Pxx來源chip打斷閱讀。文字18px與原圖清晰度良好，保留。
- 規則警告的界線：深色框是海報互動區，框內留白是透明圖片hit area；海報自身顏色不是裝飾chrome。品牌紫紅由使用者指定，inspector只明確allow palette-purple，其他規則照常檢查。

## After 證據

- `output/poster-polish-after/report.json`：1440／768／390三寬度，0 FAIL、4 WARN。before/after各6張fold/page截圖，實作者與原目標對話均已全部目視。沒有更換layout。
- before/after皆為18px正文、1.6行高；總覽標題在三寬度均1行。可見來源由大量Pxx chips改為6組可展開控制；完整文字與依據仍保留。inspector量到desktop約3 → 2.8屏，可見文字541 → 489詞，差異來自來源呈現，並非刪去六段腳本。
- 技能lint：0 FAIL、2 WARN。只涉及SHA byte與時長的必要padStart，不是裝飾流水號。
- `node --check orchid/static/tour-preview/tour.js`通過。`node --test tests/tour-preview.test.cjs tests/speech.test.cjs`為27/27通過、0 skip。全部瀏覽器API由fixture攔截，假Audio不做TTS；沒有真實chat/生成/embedding或音訊評估。
- focused browser核對320／360／390／430 CSS px、DPR1／2／3及1280px桌面無body水平溢出；八區觸控矩形沒有重疊，正常八區外部入口至少44px。Reference縮圖維持原bounds，在320px約33px高，使用外部44px按鈕作等效操作，沒有硬擴張導致點錯。
- 320px實測修正：英文標題縮為`Poster supplement`（不超過2行），閱讀按鈕縮為`Read guide`，快捷列stretch，使閱讀／提問均44px高；繁中與A+仍可讀。
- CPU來源保護：原目標對話比對before原稿，原6區各語言title/summary/narration/detail逐字不變；12個既有WAV的audioSHA與目前narration textSHA全數匹配。`tour_order`維持原6段，沒有重製錄音。

### App-screen critique（以實際截圖為準）

1. **核心問題**：完整海報與導覽文字仍是最大內容；Play保留唯一深色主操作，Read guide／Ask可立即辨識為次要操作，入口不再像普通文內連結。
2. **邊界與空間**：桌面圖文兩欄與手機堆疊未變。PDF、章節、來源和原文展開控制共享可辨的形狀與間距，沒有新增浮動大按鈕或無內容卡片。
3. **色彩與身份**：海報深藍用於主操作和框，紫紅只在次要提問、開啟glyph／焦點呼應原海報；沒有重繪、改色或整片遮住科學圖。
4. **一致資料**：8區探索與6段完整錄音分開；References／海報補充／期刊獨立5頁PDF具不同標籤。相關P/S節錄不冒充新補圖的直接證據。
5. **狀態**：既有準備、暫停、明確Resume、timeout、不自動重試與清除忽略舊結果均由fixture回歸保留，沒有假音訊進度或新成功宣稱。
6. **標記與來源**：完整區域框、短標籤與加號提供開啟語意；透明hit area不填色。來源展開後顯示題名、ID為次資訊，直接PDF仍保留a/href。
7. **手機**：320px標題與等高按鈕已修正。地圖References尺寸例外有可見44px替代入口；各區無重疊、主正文18px、A+20／22未變。

### 四個 inspector WARN 的具體解釋

`heavy-borders`與`panel-void`指向海報完整區域框／透明hit area，它們是使用者要求辨識的圖片控制，不是待填滿的卡片。`colour-sprawl`約19%主要來自保留的原海報深藍標頭與科學圖色彩，不以改色滿足一般dashboard配色比例。`edge-text`對「Perturbation…」海報原文提取文字回報右距12px，主要layout實際左右為16px；這個before已存在的文字量測警告尚待查明，不宣稱已消除，也不為它擴大本輪修改。沒有改動原PDF字距。除使用者指定的品牌紫紅`palette-purple`外，沒有新增規則allow或修改inspector判定。

## 原目標對話的 HTTPS 唯讀複核

新版按鈕可辨；Read guide pointer操作後，閱讀頂緣178.8px、sticky底緣162.7px，保留約16px間距。問答dialog開關成功，沒有送題。References框能進、C01題名與原文出處能開。Supplementary切繁中、放大原圖及完整解析度成功，currentSrc為`supplementary-2400.webp`，海報仍英文。

320px再次確認：標題60px＝2行，Read guide與Ask均44px，無body水平溢出。原目標對話也逐張查看after的1440／768／390全部fold/page截圖，沒有看到新阻塞。

官方期刊補充PDF已由內容agent以CPU讀取並目視5頁，SHA為`a1612a32a5d464160787143bff68a655590c0262863a26bc45643d6564efd4b5`；S1–S5與海報補充兩圖分開，主文圖號勘誤不套用到S1–S5。本輪沒有改evidence/index/backend，也不將新增閱讀內容等同所有細節已有問答覆蓋。

使用者已於 2026-10-31 確認這版 UI 並授權合併與推送；實際 Git 完成狀態由整合結果另行核對。音訊發音接受仍未確認；這次視覺更新沒有播放／重製／評估真實語音，沒有啟停任何模型或服務。

## 發布前複核（2026-10-31）

使用者接受後未再改 runtime 程式。完整四檔 Node suite 為 29/29 通過、0 skip，包含兩個實際 CPU headless Edge fixture tests；兩支建置腳本語法／Ruff、四支網站 JS 與四支 CJS 語法均通過。原目標對話的 Python fixtures 為 103 passed in 2.68s、`ruff check orchid tests` 通過。這輪未呼叫真實 chat／TTS／embedding，未重跑版面檢查；沿用上述同版本 before／after 證據。app lint 再確認為 0 FAIL、2 WARN，原因同前，不宣稱無警告。

完整 browser tests 需要已安裝 Playwright／Chromium 或 Edge，以及由已登錄原海報 PDF 建置的 ignored 圖片與 manifest；缺素材而具備 Playwright 的 checkout 會失敗。重建入口和限制見[海報網頁試作](poster-web-preview.md)；發布檢查命令與原始結果保留於本機 `output/release-poster-tour-check.txt`。新增兩區僅供閱讀與原文定位，沒有擴充 RAG evidence／索引。音訊人工發音接受與長時間展場穩定性仍是獨立驗收。
