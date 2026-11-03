# 研究團隊審閱頁

入口：`https://cball.computing.ncku.edu.tw/orchid-poster/review`。

此頁僅供研究團隊查看已保存的問題、最終回答、回答狀態、引用ID及回饋。搜尋、語言／回答狀態篩選、每頁25筆與重新載入均不呼叫模型。手機將篩選收合，先顯示紀錄；原導覽、語言選項與訪客流程不變。

## 存取

- 使用獨立43字元以上的隨機審閱密碼，與模型API key分開。
- 正式密碼檔：`/home/cball/orchid-poster-deploy/private/review.key`，cball擁有、mode600。勿加入Git、runtime壓縮檔或公開資料夾。
- 瀏覽器只在記憶體暫存密碼，透過Authorization header送出，不放URL、cookie、localStorage或sessionStorage。重新整理或登出後重新輸入。頁面本身可公開開啟，但沒有密碼讀不到任何紀錄。
- 所有回應沿用no-store；沒有公開匯出、編輯、刪除或帳號管理功能。請勿公開分享密碼。可直接在主機替換秘密檔案內容來撤換密碼，不需重新部署；檔案權限與擁有者須保留。
- 外部入口HTTPS，中央代理至工作站沿用既有LAN HTTP；本次沒有變更此網路架構。

## 啟用與更新

base Compose相容舊部署；審閱功能透過額外的 `deploy/compose.review.yaml` 啟用。

在既有 `deploy/.env` 新增 `ORCHID_REVIEW_KEY_FILE=/home/cball/orchid-poster-deploy/private/review.key`，並將ORCHID_IMAGE改為新映像。不要把密碼本身放進env。

```bash
cd /home/cball/orchid-poster-deploy
docker compose --env-file deploy/.env -f compose.yaml -f deploy/compose.ingress.yaml -f deploy/compose.review.yaml up -d --no-deps --pull never orchid
```

這只更新網站容器；保留模型、入口代理及全部資料掛載。日後管理網站請保留review override，否則重建容器會停用審閱入口（資料仍保留）。停止網站前確認queue與pending紀錄歸零；不使用 `down -v`、刪資料目錄或還原舊DB覆蓋新訪客紀錄。

## 資料保護與回復

審閱讀取使用SQLite `mode=ro`、`PRAGMA query_only=ON`、短交易、參數化搜尋與最多50筆限制，不使用RecordStore初始化或復原函式。沒有資料庫遷移、重建、複製取代或寫入路由。訪客提交仍沿用原WAL寫入與儲存流程；使用者內容只以純文字呈現。

部署前使用SQLite online backup保存正式資料庫快照與每一舊有列的SHA256，原始備份只留部署機私人目錄。更新後核對所有舊有列與schema、資料庫inode及掛載來源；允許新增正常訪客資料。驗證不往正式資料庫插入測試問答或回饋。

回復程式時將ORCHID_IMAGE改回 `orchid-poster:ubuntu-20261102`，用同一Compose指令只重建orchid。保留現用records目錄、speech-cache及runtime；不回復舊DB，避免遺失更新後的提交。舊映像不認識review設定，將停用審閱頁但仍保留原有訪客功能。

本功能不識別真人身分，匿名conversation ID不等於獨立參觀者。`unknown`只代表沒有可確認的回答，不能單憑狀態認定是模型故障或證據不足。

## 2026-11-03 部署驗證

- 映像 `orchid-poster:review-20261103`，ID `sha256:287ffb6f503be4e09e9d152021e15be25555f9fc3288bbd5082f86a341b3400a`。
- Python 148項、Node 36項（含1440px及390px合成資料瀏覽器測試）、Ruff及Linux CPU容器煙霧測試通過。獨立程式審查沒有阻擋交付的P1/P2問題。
- 備份在工作站 `backups/review-20261103/visitor-records.before.sqlite3`。更新後逐列雜湊核對：原1筆提問完整保留、schema版本1與內容不變、同一DB inode與records掛載、其餘23個容器身分不變。當時回饋為0筆，正式紀錄未混入本次測試資料。
- 正式HTTPS審閱shell/CSS/JS皆200，匿名與錯誤密碼401、正確密碼的提問及回饋API皆200。導覽雙語文字、海報manifest/圖片、原中英文intro音檔與來源S05皆200；index/model/speech/recording皆ready。
- 真實瀏覽器核對正式登入頁；登入後互動、惡意HTML純文字顯示、篩選/分頁/登出與手機版面使用合成資料測試。沒有把正式訪客內容放進截圖或測試報告；實體手機人工驗收仍待使用者確認。
- 不含訪客內容的驗證收據保存在本機ignored `output/review-20261103/` 與工作站 `backups/review-20261103/verification.json`。
