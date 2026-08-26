## 1. 設定與依賴

- [x] 1.1 新增 `httpx` 至 `requirements-api.txt`
- [x] 1.2 擴充 `api/config.py`：`IMPORT_URL_ALLOW_HTTP`、`IMPORT_URL_CONNECT_TIMEOUT_SEC`、`IMPORT_URL_TOTAL_TIMEOUT_SEC`、`IMPORT_URL_MAX_REDIRECTS`
- [x] 1.3 更新 `.env.example` 與 docker-compose 註解

## 2. URL import 服務

- [x] 2.1 新增 `api/services/url_import.py`：URL scheme 驗證、DNS 解析、IP blocklist 檢查
- [x] 2.2 實作 streaming 下載（redirect 限制、每次 redirect re-check IP、大小截斷）
- [x] 2.3 實作 progress callback（有 Content-Length 時回報 bytes 比例）
- [x] 2.4 單元測試：SSRF 案例（127.0.0.1、10.x、169.254.169.254、redirect 至內網）

## 3. API endpoint

- [x] 3.1 實作 `POST /v1/jobs/import-url`（驗證 url/filename、enqueue、202 回應）
- [x] 3.2 新增錯誤碼：`INVALID_URL`、`URL_NOT_ALLOWED`、`DOWNLOAD_FAILED`
- [x] 3.3 更新 Swagger 範例與 `/v1/jobs/{id}` import_url done 範例

## 4. Worker

- [x] 4.1 在 `runner.py` 新增 `_run_import_url`：下載 → ffprobe → 存 storage → 建 FileRecord
- [x] 4.2 job done 時 `result` 回傳 `file_id`、`filename`、`size_bytes`、`expires_at`
- [x] 4.3 整合 progress updater（下載階段 0–90，完成 100）

## 5. 測試與文件

- [x] 5.1 整合測試：mock HTTP server 成功 import → 取得 file_id → 用於 merge
- [x] 5.2 整合測試：過大檔、非影片、HTTP 預設拒絕
- [x] 5.3 更新 README / README.en（import-url 流程與 env 說明）
