## Why

目前 Worker 每 60 秒自動清理過期上傳檔與 job 結果，且 `FILE_TTL_HOURS=24`、`RESULT_TTL_HOURS=72` 為硬編碼預設。對自架或長期保留素材的場景，檔案會在 API 層邏輯過期（404）並被背景刪除，與「留著直到手動刪」的需求不符。需將保留策略改為可配置，並以**永不過期、不自動清理**為新預設。

## What Changes

- 新增 `AUTO_CLEANUP_ENABLED`（預設 `false`）：控制 Worker 是否執行背景物理清理
- 新增 `CLEANUP_INTERVAL_SECONDS`（預設 `60`）：背景清理間隔（僅在 enabled 時有效）
- **`FILE_TTL_HOURS` 預設改為 `0`**（0 = 永不邏輯過期）；> 0 時維持現有 expires_at 行為
- **`RESULT_TTL_HOURS` 預設改為 `0`**（0 = 永不清理 job 結果）；> 0 且 cleanup enabled 時清理 result
- `expires_at` 在永不過期時回傳 `null`（Swagger / API response 更新）
- `is_expired()` 在 `FILE_TTL_HOURS=0` 時永遠 false
- 手動 `DELETE /v1/files/{file_id}` 行為不變
- **`BREAKING`**：未明確設定 env 的既有部署，行為從「24h 過期 + 自動清」變為「永久保留」

## Capabilities

### New Capabilities

（無。保留與清理屬於既有 file / job 生命週期能力擴充。）

### Modified Capabilities

- `api-file-upload`：檔案 TTL 預設改為永不過期；`expires_at` 可為 null；新增背景清理配置需求
- `api-video-jobs`：job 結果預設永久保留；清理行為可配置

## Impact

- `api/config.py`：新增/調整 env 預設值
- `api/models/records.py`：`is_expired()` 邏輯
- `api/routes/files.py`：上傳/import 時 `expires_at` 計算；response 允許 null
- `api/services/cleanup.py`：依配置跳過清理
- `api/worker/runner.py`：cleanup 開關與 interval 可配置
- `.env.example`、`docker-compose.yml`、README 雙語、Swagger（`api/main.py`）
- 測試：過期/清理/永久保留案例
