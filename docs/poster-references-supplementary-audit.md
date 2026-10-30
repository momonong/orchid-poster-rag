# 海報 References 與 Supplementary 核對

日期：2026-10-30。範圍：CPU、本地 PDF、既有 corpus；初次只新增本文件與 `.orchid/tour-extra-sections.json` 內容提案。後續獲授權從官方論文頁查核期刊補充PDF與程式入口，只更新本audit，沒有改正在整合的proposal。沒有改 frontend、data/evidence、索引、服務、模型或 GPU，沒有送出 `/api/chat`、生成或 embedding 請求。本文件不是問答能力驗收。

## 來源與定位

- 海報 `理學院研究日.pdf`：1頁，2383 × 3368pt，SHA-256 `69cc0c2c61fb2afd78b7468735bd43b52b73348aebc23d42c1d15f75d51bd3d3`。
- 論文 `s12870-024-05305-z.pdf`：12頁，本地PDF首頁標示 corrected publication 2024，SHA-256 `4e4e4ca4f3b4423f4928e92fed5d5dd6056014f943862aba7bab9979e45bcab9`。
- 官方勘誤：初次使用 `data/evidence.json` 的 C01 原始摘錄；後續直接讀取[官方更正HTML頁](https://link.springer.com/article/10.1186/s12870-024-05475-w)確認相同圖號更正，沒有下載更正PDF。
- 下列 normalized rect 使用左上原點，順序 `[x0,y0,x1,y1]`，均指海報第1頁。

| 區域 | 建議normalized bounds | 關鍵完整性證據 |
|---|---|---|
| Reference | `[0.703,0.559,0.977,0.640]` | 標題文字框y1889.519–1951.511pt；文獻最後一行到y2137.403pt，裁區下緣2155.520pt；下一標題起於2178.140pt。 |
| Supplementary | `[0.703,0.644,0.977,1.000]` | 包含標題、兩段圖說、xref27與xref36兩張圖。xref36超出頁框5.158pt的區域只是底部留白；目視確認末行與外框均保留在原頁內。 |

海報Reference與Supplementary沒有既有專用證據ID。提案中的 `source_locators` / `role=direct_source` 才是兩個新區塊的直接來源。P01/C01及P02/P03/P04/P05/S02只是相關論文或海報Methods脈絡；不得把既有S02或S04的locator冒充Supplementary直接引用。根據這份提案新增證據ID或索引，仍須由原目標整合並核對；本次未執行。

## Reference：海報只有一筆，不等於已讀完上游文獻

海報逐行內容已核對：Lu, T. W., Chen, W. H., Chen, P. Y., Shu, Y. C., & Chen, H. H. (2024). *Perturbation of periodic spot-generation balance leads to diversified pigmentation patterning of harlequin Phalaenopsis orchids: in silico prediction*. *BMC Plant Biology*, 24(1), 681。

本地論文第1頁核對全名為Ti-Wen Lu、Wen-Huei Chen、Pao-Yang Chen、Yu-Chen Shu、Hong-Hwa Chen；DOI為`10.1186/s12870-024-05305-z`，681是文章編號。海報作者僅Ti-Wen Lu與Yu-Chen Shu，不能與完整論文作者名單混用。

C01記載的圖號更正：舊Fig.2 → Fig.10；舊Fig.3 → Fig.11；舊Figs.4–11 → Figs.2–9。這適用於期刊論文；海報Figs.1–4為獨立編號。本地論文Fig.10在第10頁、Fig.11在第11頁，與此更正一致。

論文第12頁另有20筆References。本次只核對其書目，沒有讀取這20篇的原始全文。可作為延伸閱讀入口的三筆，提案保留原論文書目轉錄並標示未讀全文：

- Ref.2 Hsu et al. (2019)，HORT1插入PeMYB11 promoter與harlequin/black花色，*Plant Physiol.* 180:1535–48。
- Ref.8 Gierer & Meinhardt (1972)，*A theory of biological pattern formation*，*Kybernetik* 12:30–9。
- Ref.9 Ding et al. (2020)，*Two MYB proteins in a self-organizing activator-inhibitor system produce spotted pigmentation patterns*，*Curr Biol.*；本地書目格式為30(802–814):e808，僅按原樣轉錄，未另行查核書目格式或原文。

## Supplementary：兩張內嵌圖片已逐項人工目視

這些圖中文字不在PDF的可抽取文字層；僅靠`get_text()`會漏掉。使用既有PyMuPDF將xref27與xref36抽至記憶體，再以Pillow縮圖人工目視，未啟用OCR、外部模型或GPU。

海報可抽取的兩個圖說是：

1. `An illustration of the spatial heterogeneity of HORT1 distribution:`，文字框約y2271.544–2290.363pt。
2. `Additional Mathematical Information of the Gierer-Meinhardt Model:`，文字框約y2794.896–2813.716pt。

### 圖一：HORT1遺傳背景與調控示意

- xref27：1426 × 1325px，放置框`[1725.703,2296.290,2248.597,2782.148]`pt。
- Genetic background：HORT1 retrotransposon、solo-LTR（single LTR remnant）及full-length HORT1（coding sequence）兩種示意。
- Regulatory pathway：solo-LTR insertion acts as enhancer → PeMYB11 promoter → PeMYB11 gene/activator → anthocyanin biosynthesis → pigmentation。
- Phenotype comparison：solo-LTR present可見deep red-purple spots or patches/classic harlequin pattern；solo-LTR absent仍有large purple patches，圖中舉P. ‘Plum’，並註full-length HORT1 present。
- 這是遺傳／調控關係示意，不是每個細胞HORT1插入位置的直接量測地圖。不能將圖中「pattern depends on solo-LTR status」讀成solo-LTR單一因素充分決定所有花紋；圖本身已列Plum反例。
- 相關論文事實：第2頁Introduction明確提P. Ever-spring Prince ‘Plum’沒有solo-LTR但仍有大紫斑，與既有P02一致。該段描述所引用的上游實驗文獻未在本次另讀原始全文。

### 圖二：量綱表與細胞間耦合示意

- xref36：1426 × 1481px，放置框`[1725.703,2822.079,2256.317,3373.158]`pt。
- 表列A、H為PeMYB11/PeMYBx層級的活化者／抑制者濃度，分別以C_A、C_H表示濃度量綱；T為時間、L為長度。

| 參數 | 圖中單位 | 核對含義 |
|---|---|---|
| A | C_A | activator concentration |
| H | C_H | repressor concentration |
| ρ_A | C_A / T | A基本產生率 |
| D_A | L² / T | 圖中註apparent, via H的A擴散尺度 |
| D_H | L² / T | H細胞間擴散尺度 |
| μ_A, μ_H | 1 / T | A/H降解率；圖上寫lifetime=1/μ，應限於單獨一階降解時間尺度 |
| G_A | C_H / (C_A · T) | 受H抑制的A自我活化強度 |
| G_H | C_H / (C_A² · T) | A²驅動H生成的強度 |
| k | C_H | 固定A時，相對H=0使活化項減半的H濃度尺度 |

以上量綱與論文第10頁方程式一致；這是代數上的單位檢核，不是模型已經校準到實際細胞長度／時間的證據。A與H在論文第9頁表示包含轉錄、轉錄後及翻譯的整體過程，不宜把表格讀成單一純蛋白濃度的直接實測。

下方cell-to-cell coupling畫三個細胞；A以不同深淺表示高低，A通路以no A flux及叉號標示，H以D_H的雙向箭頭跨細胞。兩行文字為：

> A is not transported between cells, but H diffuses, so H_i and A_i differ from cell to cell.
>
> A therefore appears to diffuse: an apparent (effective) D_A

必須把以上保留為海報圖的詮釋。論文第10頁把D_A、D_H均列為模型擴散率，方程式含非零D_A∇²A，沒有在本次查閱的本地論文段落中建立「H移動所以數學上等效為固定D_A擴散」的推導或運輸實驗。不可把海報圖的no A flux當作該PDE的額外已證明條件。

### 可用數值：清楚標為Methods背景

論文第10頁與海報Methods（P05、S02）共同給出標準設定：D_A=0.01、D_H=0.5、μ_A=μ_H=0.03、G_A=0.08、G_H=0.12、ρ_A=0.01、k=0.001。論文使用100 × 100格點、L=100、週期邊界，A初值隨機0到1、H初值0。這些參數是先前研究沿用的模擬設定，不是Supplementary表上實際印出的數字，也不是每個細胞的新量測或所有蘭花通用常數。海報花瓣形FEM／Neumann延伸仍屬海報Methods，不改歸期刊Supplementary。

## 海報Supplementary與期刊補充檔分開

本地完整論文第12頁`Supplementary Information`明列`Supplementary Material 1`，指向論文DOI。主文引用Supplementary Figs.1–5，獨立補充檔並不內嵌於目前12頁主文PDF（嵌入附件數為0）。初次核對未下載該檔；後續授權下已從官方頁取得5頁PDF並逐頁閱讀，詳見末節。海報新示意圖仍不能說成該期刊補充檔的圖片。

同頁`Availability of data and materials`列出[Figshare程式入口](https://figshare.com/s/0bc3fd0532a1bb336edb)。初次只核對主文連結；後續已用web工具讀取其頁面metadata，單次即時HTTP GET則得到202與空body，詳見末節。仍未下載程式、審查程式、重跑模擬或驗證可重現性。

## 論文內容覆蓋與邊界

| 範圍 | 目前可用證據 | 本輪新增／尚待補足 |
|---|---|---|
| 研究問題與模型角色 | P01–P04，論文pp1–2、9–10 | 已有六段導覽，本輪不重寫或重驗問答。 |
| 標準參數、數值法 | P05–P06，論文p10；海報S02 | 補充區可連結既有參數；物理校準／cell-to-cell詮釋仍未驗證。 |
| 三條主要模擬結果 | P07–P14，論文pp3–8、11 | 已有六段導覽；不能因此保證每個研究細節都已有可答證據。 |
| 摘要措辭衝突與官方圖號更正 | P15、C01 | 區分PeMYB11降解與miR858表達；更正不處理此措辭衝突。 |
| 海報Reference | 原PDF新rect | 已核對唯一文獻及本地完整論文身份；paper另20筆參考文獻僅讀書目。 |
| 海報Supplementary | 原PDF新rect、xref27/xref36人工目視 | 新增雙語導覽提案、量綱與確定的Methods參數；尚未寫入evidence/index。 |
| 期刊Supplementary Material 1 | 官方DOI頁附件；5頁PDF與主文pp2/5/7/9補圖引用 | 後續已下載並逐頁核對S1–S5、S2參數；未新增evidence/index或做問答驗收。 |
| 研究程式與實驗外細節 | 主文p12列Figshare入口；web可讀頁面metadata但即時直連202空body | 程式檔未下載／審查／執行，未重現模擬；沒有未發表或研究外資料。 |

本輪沒有對問答、檢索、生成或embedding作任何評估；也沒有使用GPU。加入這兩段提升海報內容覆蓋，不能保證回答所有研究外問題或未記載的細節。前端整合、手機閱讀／播放與人工接受仍由原目標另行核對；本提案生成不代表已部署或問答驗收通過。


## 後續有界核對：官方期刊附件與程式入口

本節是同日追加授權，僅CPU、官方頁面與5頁期刊PDF閱讀。不修改 `.orchid/tour-extra-sections.json`、frontend、evidence或索引，不送生成／embedding／問答請求，也不下載或執行程式。

### 實際期刊附件：已取得並讀完5頁

從[論文官方頁的Supplementary Information](https://link.springer.com/article/10.1186/s12870-024-05305-z)實際附件連結取得：

[Supplementary Material 1：5頁PDF](https://media.springernature.com/original/springer-static/esm/art%3A10.1186%2Fs12870-024-05305-z/MediaObjects/12870_2024_5305_MOESM1_ESM.pdf)

- 官方檔名：`12870_2024_5305_MOESM1_ESM.pdf`。
- 2026-10-30單次即時下載：HTTP200，`application/pdf`，612,367 bytes，5頁，PDF1.5；沒有密碼或嵌入附件。
- SHA-256：`a1612a32a5d464160787143bff68a655590c0262863a26bc45643d6564efd4b5`。
- 附件曾下載至本機暫存區供核對，未納入repository。讀者可由上方官方HTTPS連結取得同名PDF，依檔案大小與SHA-256重做身分核對；不依賴特定機器的暫存路徑。
- PDF由PowerPoint2016輸出，generic title/author並非正式書目；附件身分由官方論文的實際連結、檔名及各頁Lu et al.補圖圖說共同確認。metadata建立／修改日為2024-06-04，但不能僅憑metadata斷言後續版本歷史。
- 既有PyMuPDF抽取五頁可讀文字，並將五頁在記憶體渲染後逐頁目視核對。沒有OCR、模型、GPU或新套件。

| PDF頁／補圖 | 已核對內容 | 解讀邊界 |
|---|---|---|
| p1／S1 | P. Ever-spring Prince ‘Plum’花朵照片與紫色分布的說明。 | 屬文獻補圖；本次沒有重新量測花青素。 |
| p2／S2 | 固定G_A=2.712，比較A: μ_A=0.03與B: μ_A=0.01的花紋模擬。 | 用以呈現活化／降解組合條件的效果，不是新育種實驗。 |
| p3／S3 | 玉山小珍珠與Golden Peoker ‘Black’的紫斑外形比較。 | 圖中的輪廓與花朵示例，不能作為所有品種的統計結論。 |
| p4／S4 | HORT1結構圖，圖說指出兩端LTR與缺少reverse transcriptase的非自主性。 | 原圖結構／圖說核對，不代表本次重做序列分析。 |
| p5／S5 | 同一Golden Peoker ‘Black’植株上不同花朵的花紋差異。 | 是同株花朵差異的例圖，不是本次新增採樣。 |

五頁附件均使用Supplementary Figure1–5。官方更正只指定主文圖2–11重編，沒有列出補圖S1–S5需要重編。因此導覽可稱S1–S5，不能把主文舊／新圖號對應套到這五張補圖。這不等於已證明附件從未被修改；未取得完整版本歷史。

海報Supplementary的HORT1調控示意、量綱表及cell-to-cell coupling圖不在這份5頁期刊附件內；兩者必須保留不同名稱與來源。

### 程式入口：metadata可讀，即時直連未取得內容

官方論文在Availability of data and materials列出的入口為：

[Pattern_simulation (package) and Pattern_simulation_piecewise (package)](https://figshare.com/s/0bc3fd0532a1bb336edb)

web工具可讀到Figshare頁面metadata（工具標示快取約6天前）：類型software、MIT授權、修改日期2024-03-09，頁面宣稱Download all約6.71kB。兩個package分別描述均勻與分段自我活化參數的Gierer–Meinhardt求解及花紋繪圖。頁面亦標示`This item is shared privately`，所以宜稱「論文列出的Figshare分享入口」，不能自行稱為持久公開archive或已有可用版本保證。

另做一次即時標準HTTP GET：回202、`text/html; charset=UTF-8`、body0 bytes、未redirect；沒有嘗試繞過或反覆重試。故不能將metadata讀取成功當成當下程式檔可下載或使用者瀏覽器可達的證據。程式檔未下載、未審查、未執行；沒有驗證依賴或模擬可重現性。

### 可直接採用的使用者短文案

繁中：**期刊補充資料（5頁PDF）**：補圖S1–S5涵蓋Plum花色、活化與降解的組合模擬、不同紫斑輪廓、HORT1結構，以及同株花朵的花紋差異；這與海報Supplementary的說明圖不同。本次已核對附件，尚未納入問答索引。另有論文列出的程式分享入口，程式未執行。

English: **Journal supplementary material (5-page PDF)**: Figures S1–S5 cover Plum pigmentation, combined activation/degradation simulations, patch outlines, HORT1 structure, and variation among flowers on the same plant. These are separate from the poster’s supplementary illustrations. The PDF was reviewed in this update and has not been added to the question-answering index. The paper also links a code-sharing page; the code has not been run.

本節核對的是官方附件內容與入口，不是問答能力、程式可重現性或所有研究細節的完整性驗收。此前proposal若仍寫「期刊附件未讀」，那是初次提案狀態；應由原目標整合者依本節更新對外文案，避免與目前已讀狀態混淆。
