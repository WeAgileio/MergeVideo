## 1. 專案骨架與依賴

- [x] 1.1 建立 `api/` 目錄結構（`main.py`、`routes/`、`models/`、`services/`、`worker/`）
- [x] 1.2 新增 `requirements-api.txt`（FastAPI、uvicorn、boto3、redis、sqlalchemy 等）
- [x] 1.3 新增環境設定（`.env.example`：S3、Redis、DB、API key、TTL 等）
- [x] 1.4 新增 `docker-compose.yml`（本地 MinIO + Redis + API + Worker）

## 2. 基礎設施層

- [x] 2.1 實作 S3 相容 storage 服務（upload、download、delete、presigned URL）
- [x] 2.2 實作 file registry 資料模型與 CRUD（SQLite 開發 / PostgreSQL 生產）
- [x] 2.3 實作 job store 資料模型與狀態轉換（queued → processing → done/failed）
- [x] 2.4 實作 Redis job queue（enqueue、dequeue）
- [x] 2.5 實作 API key 驗證 middleware 與 owner_key 綁定

## 3. 核心模組調整

- [x] 3.1 新增有序 path list 合併入口（不依數字檔名排序，接受 `list[Path]`）
- [x] 3.2 封裝 `mode=auto` 合併邏輯供 worker 呼叫（probe → compat → copy/encode）
- [x] 3.3 確認 `extract_frame.py` 可被 worker 以 temp 路徑呼叫（必要時小幅調整）

## 4. File Upload API

- [x] 4.1 實作 `POST /v1/files`（multipart 上傳、大小/格式驗證、存 storage、回 file_id）
- [x] 4.2 實作上傳時可選 ffprobe metadata 寫入 registry
- [x] 4.3 實作 `GET /v1/files/{file_id}`（metadata 查詢、所有權驗證）
- [x] 4.4 實作 `DELETE /v1/files/{file_id}`（刪除 storage + registry、active job pin 檢查）
- [x] 4.5 實作 file TTL 與 job pin 延長邏輯

## 5. Job API

- [x] 5.1 實作 `POST /v1/jobs/merge`（file_ids 陣列順序、≥2 驗證、enqueue）
- [x] 5.2 實作 `POST /v1/jobs/extract-first-frame` 與 `extract-last-frame`
- [x] 5.3 實作 `GET /v1/jobs/{job_id}`（統一 response 格式、done 含 download_url）
- [x] 5.4 實作結構化錯誤回應（FILE_NOT_FOUND、INSUFFICIENT_FILES 等）

## 6. Worker

- [x] 6.1 實作 merge worker（下載 inputs → temp dir → mode=auto merge → 上傳結果 → 更新 job）
- [x] 6.2 實作 extract-first-frame worker
- [x] 6.3 實作 extract-last-frame worker
- [x] 6.4 實作 worker 錯誤處理與 job failed 狀態寫入
- [x] 6.5 實作 worker temp 目錄清理

## 7. 運維與清理

- [x] 7.1 實作 `GET /health`（ffmpeg/ffprobe 可用性）
- [x] 7.2 實作過期 file 與 result 定時清理 task
- [x] 7.3 設定 CORS（Web 前端 origin）

## 8. 可切換 Storage 後端

- [x] 8.1 擴充 Settings 支援 gcs / azure / rclone 設定
- [x] 8.2 實作 GCSStorage（signed URL）與 AzureBlobStorage（SAS URL）
- [x] 8.3 實作 RcloneStorage（Google Drive / OneDrive / Dropbox 等 rclone 遠端）
- [x] 8.4 storage factory 依 STORAGE_BACKEND 分派，未知/缺設定時啟動報錯
- [x] 8.5 撰寫 backend 切換測試

## 9. Job 進度回報

- [x] 9.1 ffmpeg_utils 新增 `-progress` 串流執行函式
- [x] 9.2 merger 三個合併函式支援 progress_callback
- [x] 9.3 JobRecord 新增 progress 欄位與輕量 migration
- [x] 9.4 worker 節流更新進度、GET /v1/jobs 回傳 progress

## 10. 測試與文件

- [x] 10.1 撰寫 API 整合測試（upload → merge job → poll → download URL）
- [x] 10.2 撰寫 extract job 整合測試
- [x] 10.3 撰寫錯誤情境測試（過大檔案、非 owner file_id、過期 file）
- [x] 10.4 更新 README 新增 API 使用說明與部署指南
