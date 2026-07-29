## Context

MergeVideo 目前提供三個 CLI 工具（合併、取第一幀、取最後一幀），核心邏輯已模組化（`merger.py`、`extract_frame.py`、`probe.py` 等）。需求是為雲端 Web 服務提供 HTTP API：客戶端先上傳 10–200MB 影片取得 `file_id`，再以非同步 job 觸發處理，完成後以 presigned download URL 取得結果。

## Goals / Non-Goals

**Goals:**

- 提供 REST API：`/v1/files` 上傳與查詢、`/v1/jobs/*` 建立任務、`/v1/jobs/{id}` 輪詢狀態
- 所有處理（merge、extract-first-frame、extract-last-frame）統一為非同步 job
- merge 的片段順序由 `file_ids` 陣列順序決定；合併模式固定 `mode=auto`
- 結果以 object storage presigned URL 交付，具過期時間
- API key 驗證與 file/job 所有權隔離
- 複用現有 FFmpeg 模組，保留 CLI 不變

**Non-Goals:**

- presigned 直傳 upload（v2 再考慮）
- WebSocket 進度推送（v1 以 poll 為主）
- analyze endpoint（`mode=auto` 內建）
- 使用者帳號系統（v1 僅 API key）
- 修改既有 CLI 行為或 spec

## Decisions

### 1. FastAPI + 獨立 Worker

**決定：** API server（FastAPI）與 job worker 分離；job 佇列使用 Redis（RQ 或 Celery）。

**理由：** merge encode 可能耗時數分鐘，API 需保持 stateless 以水平擴展。Worker 可獨立調整 CPU 並發。

**替代方案：** FastAPI BackgroundTasks — 僅適合單機 MVP，不利雲端擴展。

### 2. 兩步流程：Upload → Job

**決定：** 客戶端先 `POST /v1/files` 取得 `file_id`，再 `POST /v1/jobs/*` 引用 file_id。

**理由：** 大檔上傳與處理解耦；同一 file_id 可多次建立 job；失敗只需重跑 job。

**替代方案：** 單 request multipart 上傳+處理 — 易 timeout，不適合 200MB × N。

### 3. Object Storage（啟動時可切換多後端）

**決定：** 儲存層抽象為統一介面（put / fetch / delete / delete_prefix / presigned_url），啟動時以 `STORAGE_BACKEND` 切換：

| backend | 覆蓋範圍 | download URL |
|---------|----------|--------------|
| `local` | 本機目錄（開發） | API `/storage` 靜態路由 |
| `s3` | AWS S3 + 所有 S3 相容（MinIO/R2/OSS/COS/Wasabi/B2） | presigned URL |
| `gcs` | Google Cloud Storage | v4 signed URL |
| `azure` | Azure Blob Storage | SAS URL |
| `rclone` | Google Drive / OneDrive / Dropbox 等 rclone 遠端 | `rclone link` 分享連結 |

**理由：** 雲端部署不能依賴本地磁碟；presigned URL 讓 client 直接下載，減輕 API 流量。消費型雲端硬碟（Google Drive / OneDrive）無原生 presigned URL 概念，透過 rclone 統一支援最務實，也一併涵蓋其他常見雲端。

**限制：** rclone 分享連結無法控制過期時間；gcs signed URL 需 service account 認證。

**路徑慣例：**
- 上傳：`uploads/{file_id}/original`
- 結果：`results/{job_id}/{filename}`

### 4. File Registry 與 Job Store

**決定：** SQLite（開發）/ PostgreSQL（生產）儲存 file 與 job metadata；Redis 作 job queue。

**File 欄位：** `file_id`, `owner_key`, `storage_path`, `filename`, `size_bytes`, `expires_at`, `created_at`, 可選 `metadata`（ffprobe）

**Job 欄位：** `job_id`, `type`, `owner_key`, `status`, `input`（JSON）, `result`（JSON）, `error`, timestamps

**file_id / job_id：** 使用 nanoid 或 UUID，不可猜測。

### 5. Merge 排序與核心模組整合

**決定：** API merge 依 `file_ids` 陣列順序；worker 將檔案依序放入 temp dir，新增 `merge_videos(paths: list[Path], ...)` 或讓 scanner 接受有序 path list，**不**依賴數字檔名排序。

**理由：** Web 前端可控順序；與 CLI 的數字檔名規則解耦。

**mode=auto：** worker 內呼叫 `check_copy_compat` + 自動選 copy/encode，不暴露給 client。

### 6. 認證與授權

**決定：** `Authorization: Bearer <api_key>`；file 與 job 綁定 `owner_key`（api_key hash）；引用 file_id 時驗證所有權。

### 7. 限制與 TTL

| 項目 | 值 |
|------|-----|
| 單檔大小上限 | 200 MB |
| merge 最少片段 | 2 |
| merge 最多片段 | 10（可配置） |
| 上傳檔 TTL | 24h（job 進行中 pin 延長） |
| download URL 有效期 | 24h |
| 結果檔 TTL | 72h 後清理 |

### 8. 錯誤回應格式

```json
{
  "error": {
    "code": "FILE_NOT_FOUND",
    "message": "human readable"
  }
}
```

## Risks / Trade-offs

| 風險 | 緩解 |
|------|------|
| 大檔上傳 timeout | 反向代理 `client_max_body_size` ≥ 200MB；超時調大；v2 presigned 直傳 |
| encode 耗 CPU | worker 限制並發 merge 數；API 與 worker 分離部署 |
| 磁碟/tmp 不足 | worker 用 temp dir，處理完即刪；輸入輸出以 object storage 為主 |
| file 過期但 job 仍需要 | job 開始時 pin file，延長 TTL 至 job 完成 |
| 惡意上傳 | API key + rate limit + 大小檢查 |
| S3 成本 | TTL 自動清理 uploads/results |

## Migration Plan

1. 新增 `api/` 與依賴，不修改 CLI 入口
2. 本地開發：MinIO + Redis + SQLite
3. 部署：API container + Worker container + 託管 Redis/Postgres/S3
4. 健康檢查：`GET /health` 驗證 ffmpeg 可用
5. 回滾：API/worker 可獨立下線，CLI 不受影響

## Open Questions

- 生產環境 object storage 供應商（AWS / 阿里 / 騰訊 / MinIO）待部署時確定
- worker 並發上限需依實例 CPU 調整
- 是否在 v1 提供 `DELETE /v1/files/{id}`（spec 已列為可選，建議 v1 實作）
