## Why

現有 MergeVideo 工具以 CLI 提供影片合併與取幀能力，適合本機操作，但無法供雲端 Web 服務以 HTTP 呼叫。Web 前端與自動化流程需要穩定 API：先上傳 10–200MB 影片取得 `file_id`，再以非同步 job 執行合併或取幀，並以 download URL 取得結果。

## What Changes

- 新增 FastAPI HTTP 服務，部署於雲端，供 Web 服務呼叫
- 新增檔案上傳 API（`POST /v1/files`），回傳 `file_id`；上傳檔案存至 object storage
- 新增非同步 job API，統一處理三種操作：
  - 合併多段影片（`file_ids` 依**陣列順序**排列，內部 `mode=auto`）
  - 擷取第一幀 PNG
  - 擷取最後一幀 PNG
- 新增 job 查詢 API（`GET /v1/jobs/{job_id}`），完成後回傳 presigned download URL
- 新增 API key 驗證與 file/job 所有權隔離
- 新增檔案與結果 TTL 自動清理
- **保留既有 CLI 不變**；核心 FFmpeg 模組（`merger.py`、`extract_frame.py` 等）由 API worker 複用

## Capabilities

### New Capabilities

- `api-file-upload`: HTTP 上傳影片、file registry、file_id 生命週期與所有權
- `api-video-jobs`: 非同步 job 佇列，涵蓋 merge / extract-first-frame / extract-last-frame 及結果 download URL

### Modified Capabilities

（無。既有 CLI spec `video-folder-merge`、`video-first-frame`、`video-last-frame` 行為不變，API 為新增能力層。）

## Impact

- 新增 `api/` 目錄（FastAPI routes、storage、job queue、worker）
- 新增依賴：FastAPI、uvicorn、boto3（或 S3 相容 SDK）、Redis（job queue）、PostgreSQL 或 SQLite（file/job registry）
- 雲端基礎設施：object storage（S3/OSS/MinIO）、反向代理 body size 設定
- 可能小幅調整 `merger.py` / `scanner.py` 以支援「有序 path list」輸入（API 不依數字檔名排序）
- 既有 CLI 與 `openspec/specs/` 下三份 spec 不受影響
