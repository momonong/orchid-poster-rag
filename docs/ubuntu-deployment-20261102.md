# 實驗室工作站部署紀錄 — 2026-11-02

正式入口：https://cball.computing.ncku.edu.tw/orchid-poster/ ，會導向完整海報導覽。SSH既有id_ed25519金鑰可登入cball帳號，不必再執行ssh-copy-id。

## 實際部署

- Ubuntu24.04.3、RTX5090 32GB、Docker29.2／Compose5.0.2，UID/GID1000。
- 應用目錄 `/home/cball/orchid-poster-deploy`，CPU映像與程式版本沿用683a13b部署包；runtime451檔及映像轉送後全部核對SHA。
- 外部HTTPS代理位於另一台電腦，使用者提供 `proxy_pass http://192.168.51.175:8000/;`；沒有更動該代理。
- 本專案獨立Nginx入口監聽192.168.51.175:8000，轉送loopback127.0.0.1:8000。`deploy/compose.ingress.yaml` 固定官方映像digest，`deploy/nginx-lab.conf` 為這台主機專用設定。保留唯讀rootfs、非root帳號、暫存tmpfs；關閉存取日誌與upstream重試。
- 應用與Qwen API分別只監聽127.0.0.1:8000與127.0.0.1:18080。瀏覽器只接網站。外部為HTTPS；另一台代理到工作站沿用使用者指定的LAN HTTP。
- SQLite在 `records/visitor-records.sqlite3`，整目錄持久掛載；未移入筆電訪客資料。靜態語音cache在 `speech-cache/`。
- model key在 `/home/cball/.local/state/selfhost-models/api-key`，mode600，透過唯讀file secret接入；文件與Git都不含值。

Qwen服務使用selfhost-models已發布0.2.0映像，執行來源29bec681f6577f88067edf8cca9952e66b58232c；接入契約另核對45ebfd57db5313292ae8f38e733f3e2894a99e5f。模型Qwen/Qwen3.5-4B固定revision851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a、context8192、max-inflight1、GPU fraction0.45。權重與映像由筆電既有已核對資產轉送，沒有重新下載權重或修改主機uv。

模型權重在 `/home/cball/.local/share/selfhost-models/models`，私密state在 `/home/cball/.local/state/selfhost-models`。原四個AD GPU程序及全部既有AD容器保留；模型驗收時新vLLM約14846MiB，GPU尚餘8533MiB。這是當時量測，不是硬性顯存隔離或未來負載保證。

## 啟停

2026-11-03網站已更新為 `orchid-poster:review-20261103`，新增[研究團隊唯讀審閱入口](review.md)。以下網站指令包含必須保留的review override。原始2026-11-02的模型與資產驗收紀錄仍保留於本文件。

在工作站執行，僅管理本專案網站：

```bash
cd /home/cball/orchid-poster-deploy
docker compose --env-file deploy/.env -f compose.yaml -f deploy/compose.ingress.yaml -f deploy/compose.review.yaml up -d orchid ingress
docker compose --env-file deploy/.env -f compose.yaml -f deploy/compose.ingress.yaml -f deploy/compose.review.yaml ps
# 關閉網站入口與應用，保留資料與Qwen服務
docker compose --env-file deploy/.env -f compose.yaml -f deploy/compose.ingress.yaml -f deploy/compose.review.yaml stop orchid ingress
```

模型沿用已發布Compose的生命週期，沒有新增開機自啟政策；主機重開後需手動啟動並核對ready。模型服務的完整Compose前綴：

```bash
docker compose --project-directory /home/cball/orchid-poster-deploy/selfhost-models \
  --env-file /home/cball/.local/state/selfhost-models/compose.env \
  -f /home/cball/orchid-poster-deploy/selfhost-models/compose.yaml \
  -f /home/cball/.local/state/selfhost-models/images.json \
  up -d --no-build --pull never
```

以同一完整前綴加ps可查詢；停止前確認active/detached/uncertain leases都為0。不要對整台Docker或其他GPU工作執行清理／重啟。SQLite備份與回復沿用[部署包說明](deployment.md#資料與停止備份)。

## 驗證與界線

- 外部HTTPS入口、導覽、JS、圖片manifest、來源S05及預錄WAV均200；入口redirect維持HTTPS與/orchid-poster/前綴。
- 正式health的model/index/speech/recording全部ready；公開/api/records為404。
- 真實瀏覽器390px：預設英文、雙語切換、英文／繁中預錄導覽均到playing並停止，圖片載入且無橫向溢出。沒有以程式HTTP成功冒充實機掃碼或人工聽感。
- 獨立暫存SQLite的staging容器執行同一產品RAG：只提高G_A的英文／繁中問題皆answered並引用P08_1，逐項核對斑點放大與模擬條件。兩次等待0.525／0.960秒，僅代表這兩題，不是完整題組或並行效能驗收。
- 正式HTTPS的空問答／回饋POST皆422，不寫訪客紀錄；中英文短句CPU語音皆200且24kHz、mono、PCM16。staging中英語音亦成功。
- API錯誤key401、模型revision/context與英文及繁中SSE均核對，最後leases歸零。暫存RAG容器已停止移除，正式訪客DB沒有混入本次合成問答。
- 現有筆電ngrok與模型服務保留供對照；沒有停止其他工作。實體手機行動網路、QR實際掃描、人工音質、主機重開機流程與完整23題生成本輪未重測。

本機收據位於ignored的 `output/deployment-20261102/remote/`：gpu-validation.json、rag-speech-smoke.json、public-ready-final.json、public-post-validation.json、實際手機尺寸截圖、guide-qr.png與OPERATIONS.md。原始PDF、權重、Docker archives、私密state與訪客紀錄不進Git。
