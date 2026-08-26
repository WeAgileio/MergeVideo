## Context

MergeVideo API 已支援 multipart 上傳取得 `file_id`，以及 merge / extract 非同步 job。ComfyUI 等工作流常產出可公開 GET 的影片 URL，客戶端若需使用本 API 處理，目前必須中轉上傳。本 change 在既有 job 基礎設施上新增 `import_url` 類型，由 worker 代為下載並註冊 file。

## Goals / Non-Goals

**Goals:**

- `POST /v1/jobs/import-url` 建立非同步 job，done 時回 `file_id`
- 支援任意公網 HTTPS URL 及自家 CDN / presigned URL
- SSRF 防護（DNS 解析後 IP 檢查、redirect 重檢、內網/metadata IP 拒絕）
- 大小上限與 upload 一致（200 MB）、connect/total timeout 可配置
- 副檔名 + ffprobe 驗證為支援的影片格式
- 下載 progress（有 Content-Length 時）寫入 job.progress

**Non-Goals:**

- 自訂 HTTP header（Authorization、Cookie 等）— v2
- Rate limit — 獨立 change
- Domain allowlist — v2
- 同步下載 endpoint
- 修改 merge / extract 行為

## Decisions

### 1. Job type 而非 Files endpoint

**決定：** `POST /v1/jobs/import-url`，非 `POST /v1/files/from-url`。

**理由：** 大檔下載可能耗時數分鐘，與 merge 相同需非同步 + progress；語意上 import 是「取得 file 的過程」，結果是 `file_id` 而非 presigned URL。

### 2. HTTPS-only，HTTP 可選開放

**決定：** 預設只允許 `https://`；`IMPORT_URL_ALLOW_HTTP=true` 時允許 `http://`。

**理由：** 降低中間人與誤用風險；開發/內網測試可透過 env 開放。

### 3. SSRF 防護在 worker 執行

**決定：** API 僅做 URL 格式與 scheme 驗證；DNS 解析、IP 檢查、實際下載在 worker 進行（下載前 + 每次 redirect 後）。

**理由：** 避免 API 被用作 SSRF 探測；worker 與下載邏輯同處，redirect re-check 較自然。

**檢查規則：**

- 拒絕 private、loopback、link-local、reserved、cloud metadata（如 169.254.169.254）
- 最多 3 次 redirect（`IMPORT_URL_MAX_REDIRECTS`），每次跟隨前 re-resolve 並 re-check IP
- 僅允許 `http`/`https` scheme（http 受 `IMPORT_URL_ALLOW_HTTP` 控制）

### 4. Streaming 下載 + 大小截斷

**決定：** 使用 streaming GET；若 `Content-Length` 已知且超過上限，立即失敗；下載過程累計 bytes，超過 `MAX_FILE_SIZE_MB` 中止。

**理由：** 避免將超大檔完整寫入磁碟；與 upload 200MB 上限一致。

### 5. HTTP client：httpx

**決定：** 使用 `httpx` 做 async-capable streaming（worker 可同步包裝）。

**理由：** 支援 timeout、redirect 控制、streaming；比 raw urllib 易測試。

**替代方案：** `requests` + stream — 已足夠但 httpx 與 FastAPI 生態一致。

### 6. Progress 算法

**決定：**

- 有 `Content-Length`：`progress = min(bytes_downloaded / content_length * 90, 90)`（留 10% 給 storage + registry）
- 無 `Content-Length`：下載階段不更新 progress（維持 0 或最後已知值），完成後跳 100

**理由：** 與 merge progress 節流機制複用；無 Content-Length 時無法準確估算。

### 7. 完成結果型態

**決定：** `done` 時 `result` 含 `file_id`, `filename`, `size_bytes`, `expires_at`（不含 `download_url`）。

**理由：** import 目的是取得可引用於後續 job 的 file，不是交付成品。

## Risks / Trade-offs

| 風險 | 緩解 |
|------|------|
| SSRF 繞過（DNS rebinding、redirect） | 每次 redirect 前 re-resolve + IP check；拒絕 IP 字面量 URL（可選） |
| 惡意大檔 / 慢速下載 | 200MB 上限 + total timeout；streaming 截斷 |
| URL 短 TTL 過期 | 文件建議客戶端在 URL 有效時盡快建立 job；失敗回 `DOWNLOAD_FAILED` |
| 無 Content-Length 無 progress | 文件說明；v2 可改 indeterminate 狀態 |
| worker 對外網路依賴 | 部署需允許 worker egress；health 不檢查外網 |

## Migration Plan

1. 新增 `httpx` 至 `requirements-api.txt`
2. 部署 API + worker 新版本；無 DB schema 變更（沿用 JobRecord / FileRecord）
3. 新增 env 至 `.env.example`；預設 `IMPORT_URL_ALLOW_HTTP=false`
4. 回滾：下線新版本即可；已 import 的 file 與一般 upload 相同 TTL 清理

## Open Questions

- （無。Rate limit、header、allowlist 已明確列為 Non-Goals。）
