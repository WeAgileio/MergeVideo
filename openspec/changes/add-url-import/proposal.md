## Why

Web 服務常已有影片 URL（CDN、ComfyUI 輸出、第三方托管），但現有 API 僅支援 multipart 上傳。客戶端需先自行下載再上傳，增加延遲與頻寬浪費。提供 server-side URL import 可讓流程變成：提供 URL → 取得 `file_id` → 沿用既有 merge / extract job。

## What Changes

- 新增 `POST /v1/jobs/import-url`，接受公開可 GET 的影片 URL，以非同步 job 下載並註冊為 `file_id`
- job 完成後 `result` 含 `file_id`（非 download URL），後續 merge / extract 流程不變
- 下載進度納入既有 `progress` 欄位（有 Content-Length 時依 bytes 估算）
- SSRF 防護：DNS/IP 檢查、redirect 限制、大小與 timeout 限制
- 預設只允許 `https://`；`IMPORT_URL_ALLOW_HTTP=true` 可開放 `http://`
- **不包含**：自訂 download header、rate limit、domain allowlist（v1）

## Capabilities

### New Capabilities

（無。URL import 擴展既有 API 能力，不新增獨立 capability 名稱。）

### Modified Capabilities

- `api-file-upload`: 除 multipart 上傳外，亦可透過 URL import job 取得 `file_id` 並寫入 file registry
- `api-video-jobs`: 新增 `import_url` job type、下載 progress、完成後回傳 `file_id`

## Impact

- 新增 `api/services/url_import.py`（URL 驗證、SSRF 檢查、streaming 下載）
- 修改 `api/routes/jobs.py`、`api/worker/runner.py`、`api/config.py`、`.env.example`
- 新增環境變數：`IMPORT_URL_ALLOW_HTTP`、`IMPORT_URL_CONNECT_TIMEOUT_SEC`、`IMPORT_URL_TOTAL_TIMEOUT_SEC`、`IMPORT_URL_MAX_REDIRECTS`
- 新增依賴：`httpx`（或沿用現有 HTTP client）
- 新增整合測試（mock HTTP server、SSRF 案例）
- merge / extract / storage 核心邏輯不變
