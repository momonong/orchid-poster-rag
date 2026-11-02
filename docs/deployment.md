# Ubuntu CPU 部署包

此包供 `https://cball.computing.ncku.edu.tw/orchid-poster/` 使用。這個階段只完成本機 Linux Docker 建置與隔離驗證；尚未登入或安裝 Ubuntu、修改 HTTPS 代理，也未驗收實體手機。

Orchid 與 Qwen 是兩個獨立服務。Orchid 的 CPU 映像包含程式與已鎖定的 Python 依賴；原始 PDF、E5、固定版本 tokenizer、Kokoro、圖片、預錄音訊和索引由唯讀 runtime 掛載。訪客 SQLite 目錄與導覽語音 cache 分開持久保存。映像、runtime 與 Git 都不包含 API key、既有訪客資料或 Qwen 權重。

## 網路與程序契約

- 正式 Compose 只支援原生 Linux Docker，以 host network 連同機 `127.0.0.1:18080` 的既有 selfhost-models API。Orchid 仍只監聽 `127.0.0.1:8000`，不 publish port、不要求 GPU、不掛 Docker socket。
- 既有 HTTPS 代理必須先移除 `/orchid-poster` 再轉送。`ORCHID_ROOT_PATH=/orchid-poster` 告知 ASGI server 外部前綴；不可把未移除前綴的請求再轉入。代理需將 Host／協定資訊依其可信任設定正確轉送。
- `/orchid-poster` 與 `/orchid-poster/` 入口需由既有代理導向 `/orchid-poster/tour-preview/`，呈現新完整海報與 Menu 版；實際代理種類與規則待 SSH 可用後核對。`/orchid-poster/tour-preview` 的應用端 redirect 會保留前綴。展覽入口驗收必須確認上述導向；原首頁程式保留供既有 root 客戶端使用。
- 單一應用程序沿用既有有界請求 queue；停止等待 120 秒，Uvicorn 的 graceful shutdown 上限 115 秒。取消網頁等待不代表 Qwen GPU 工作已終止，不自動重送。
- 模型服務由原本的 selfhost-models Compose 維運。本包不啟動、停止或修改它。先依該 repo 的 `docs/client-integration.md` 核對 ready、模型 id／revision／capabilities；目前規劃為 Qwen/Qwen3.5-4B、context 8192，不代表 Ubuntu 現況已驗證。

## 在已授權 Ubuntu 主機載入

以下 Bash 指令在**已傳送的部署包根目錄**執行。先核對 CPU 架構為 amd64、Docker/Compose 版本、8000/18080 使用者與既有代理；尚未核對時不要執行 start。`/srv/orchid` 是範例，應依主機既有路徑調整。

```bash
sha256sum --check SHA256SUMS
# 先核對 SHA256SUMS 本身來自可信任交付，再載入已核對的映像。
docker load --input orchid-image.tar
# 與 IMAGE-RECEIPT.json 的映像 id、architecture、設定比對。
docker image inspect orchid-poster:ubuntu-20261102

# 使用映像內的 Python 3.12 驗證／解包；主機不必另裝 Python。
# 目的地 runtime 必須尚不存在；完整 hash／路徑檢查成功後才開始解包。
runtime_parent="$PWD/runtime-data"
install -d -m 700 "$runtime_parent"
docker run --rm --network none --read-only --user "$(id -u):$(id -g)" \
  --mount "type=bind,source=$PWD,target=/bundle,readonly" \
  --mount "type=bind,source=$runtime_parent,target=/destination" \
  orchid-poster:ubuntu-20261102 python -m scripts.build_deployment_bundle \
  verify /bundle/runtime.tar --extract /destination/runtime
cp deploy/.env.example deploy/.env
# ORCHID_RUNTIME_DIR 應填成上面的 runtime_parent/runtime 實際絕對路徑。
```

修改 `deploy/.env` 的目標主機絕對路徑、UID/GID、port、key file 與 public URL。不要將 key 內容寫進 env；`SELFHOST_MODEL_KEY_FILE` 只填既有私密檔案路徑。Compose file secret 在本機 Compose 是唯讀 bind；不會自動修正檔案擁有權。容器 UID/GID 必須能讀取該檔案（例如同一位擁有者，600 權限），不以 chmod 644 放寬秘密。

```bash
# id -u / id -g 應由實際執行服務與持有 key 的帳號核對，填入 deploy/.env。
# 以下使用目前登入帳號示範；若需root建立父目錄，依主機既有維運程序處理。
install -d -m 700 /srv/orchid/records /srv/orchid/speech-cache
# runtime 檔案為644，目錄需可由容器帳號讀取/通行；模型、PDF等掛載唯讀。
# records 與 speech-cache 目錄需由 deploy/.env 指定的 UID/GID 持有。
docker compose --env-file deploy/.env config --quiet
docker compose --env-file deploy/.env up -d orchid
docker compose --env-file deploy/.env ps
curl --fail --silent --show-error http://127.0.0.1:8000/api/health
```

檢查 health 的 index、speech、recording **及 model** 都 ready 後，再驗證既有代理與外部 HTTPS。容器 healthcheck 只判斷應用 CPU 能力（index/speech/recording），Qwen 不可用時仍保留閱讀／預錄導覽能力；health 的 model.ready 另外明確回報，不能把容器 healthy 當成 GPU 或問答通過。CPU speech 的初次真正推論另依下方驗收。

若 port 改成 8001，代理 upstream 與 curl 也要使用相同 port；Qwen 的 loopback API 不跟著更動。不得為 Windows Docker Desktop 啟用 host network；本機建置驗證使用無網路、無公開 port 的隔離容器，不能推導為 Ubuntu host network 已驗收。

## 資料與停止／備份

新安裝的 records 目錄應為空。本包不遷移目前展場的 SQLite。SQLite 必須掛載整個目錄，涵蓋 WAL/SHM；不要只複製一個使用中的 `.sqlite3` 檔案。runtime 更新時保留 records 與 speech-cache，使用新 runtime 目錄驗證後才切換。

僅停止本應用（不停止 selfhost-models）：

```bash
docker compose --env-file deploy/.env stop -t 120 orchid
```

運作中可利用既有 SQLite backup API 匯出一致備份，以下內容是私密訪客資料，留在指定主機私密目錄：

```bash
stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup_dir="/srv/orchid/backups/$stamp"
install -d -m 700 "$backup_dir"
docker compose --env-file deploy/.env exec -T orchid \
  python -m orchid.cli export-records --output "/tmp/visitor-export-$stamp"
container_id=$(docker compose --env-file deploy/.env ps -q orchid)
docker cp "$container_id:/tmp/visitor-export-$stamp/." "$backup_dir/"
chmod -R go-rwx "$backup_dir"
```

輸出含 CSV 與完整 SQLite，CSV 已依原功能作試算表公式防護，備份保留原文。勿將備份併入 runtime、image、Git 或公開路徑。回復必須先完成本應用停止，保留原 records 目錄，再以新空目錄放置備份 `records.sqlite3` 並命名為 `visitor-records.sqlite3`，設定正確 UID/GID；不能把舊 WAL/SHM 混入新備份。

## 重建與驗證

原始碼 checkout 根目錄的 Windows PowerShell 範例；不要重新同步正在服務的 Windows `.venv`。映像只 COPY 明確允許的程式/data/部署腳本/鎖檔，`.dockerignore` 最後另排除 PDF、權重、key、DB與sidecars。

```powershell
uv lock --check
docker compose --env-file deploy/.env.example config --quiet
docker build --platform linux/amd64 -t orchid-poster:ubuntu-20261102 .
# 在獨立輸出目錄建立檔案；不覆寫既有archive。
python -m scripts.build_deployment_bundle build --output output/runtime.tar --source-commit <verified-commit> --image orchid-poster:ubuntu-20261102
python -m scripts.build_deployment_bundle verify output/runtime.tar
```

`runtime.tar` 的 `bundle-manifest.json` 保存逐檔 size/SHA-256、來源 baseline commit、映像 reference、E5/tokenizer revisions 與 PDF mapping。PDF 在 archive 內使用 `pdfs/poster.pdf`、`pdfs/paper.pdf`，只改生成的 sources registry 路徑，保留來源 SHA 與所有證據綁定。程式資料中的 API／圖片 URL 仍為應用相對資源，前端以實際載入的 `urls.js` 所在位置推導前綴。

映像內的 `python -m scripts.deployment_smoke` 只使用 CPU、無模型 API、短合成雙語文字與新合成 SQLite。需掛載 runtime 的 `.cache`、assets、index、PDF、sources registry，以及獨立可寫 records/speech-cache；使用 read-only rootfs 與 `/tmp` tmpfs。此驗證會測 E5 推論、固定 tokenizer、來源 SHA、雙語 Kokoro WAV 格式、靜態/API、合成回饋與一致匯出；不得對正式訪客 DB 執行它。

完整來源檢查沿用 Python pytest、Node test runner 與 Ruff。Node browser fixtures 支援 `ORCHID_TEST_PREFIX=/orchid-poster`，攔截所有網路請求，驗證資源／API未逃逸前綴；使用 fixture POST，沒有對真實服務送問答、回饋或 TTS。

## 本次交付證據與待驗收

本機輸出的 `VALIDATION.json`、`IMAGE-RECEIPT.json`、`SHA256SUMS` 與測試log記錄實際結果；`SOURCE-SNAPSHOT.json` 保存建置時程式檔案hash與baseline，明確區分未提交的部署變更與已提交來源。`runtime.tar` 包含451個允許檔案（不含自己的manifest），不包含訪客records、key、logs或Qwen權重。

Ubuntu 主機／UID/GID／Docker與模型堆疊、實際 HTTPS 代理的prefix stripping、外部HTTPS、手機音訊播放與語音品質、正式問答模型與訪客持久化，需要在SSH設定完成且獲授權後驗收。不能以本機Linux CPU smoke或工程測試代替上述現場與人工接受。

依賴參考：[uv PyTorch CPU來源](https://docs.astral.sh/uv/guides/integration/pytorch/)、[Docker Linux host networking](https://docs.docker.com/engine/network/drivers/host/)、[Compose file secrets](https://docs.docker.com/compose/how-tos/use-secrets/)、[sherpa-onnx CPU安裝](https://k2-fsa.github.io/sherpa/onnx/python/install.html)。Linux wheel在本次實測需額外鎖定同版 `sherpa-onnx-core==1.13.3`；映像build會直接驗證torch無CUDA及sherpa可import。
