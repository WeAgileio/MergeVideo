## Context

MergeVideo API 有兩層「過期」機制：

1. **邏輯過期（API）**：`FileRecord.is_expired()` → `get_owned_file()` 回 404
2. **物理清理（Worker）**：`cleanup_expired()` 每 60 秒刪 storage + DB / 清 `result_json`

目前預設兩層皆啟用（24h / 72h）。使用者希望預設改為：**檔案與 job 結果永久可用**，僅在明確配置時才啟用 TTL 與背景清理。

## Goals / Non-Goals

**Goals:**

- `AUTO_CLEANUP_ENABLED=false`（預設）→ Worker 不物理刪除
- `FILE_TTL_HOURS=0`（預設）→ 檔案永不邏輯過期，API 永久可引用
- `RESULT_TTL_HOURS=0`（預設）→ job 結果永久保留，`GET /v1/jobs/{id}` 可持續取得 download_url
- TTL=0 時 API 回傳 `expires_at: null`
- 舊行為可透過 env 一行恢復（cleanup=true, TTL=24/72）
- `CLEANUP_INTERVAL_SECONDS` 可配置（預設 60）

**Non-Goals:**

- 新增「延長 TTL」或「刷新 download_url」專用 endpoint
- 改變 `DOWNLOAD_URL_TTL_HOURS`（單次 presigned URL 有效期，預設仍 24h）
- 批次刪除、storage quota、archive 策略
- DB schema migration（`expires_at` 欄位保留，永不過期時設 sentinel 或 far-future；API 層轉 null）

## Decisions

### 1. TTL=0 表示「永不」

**決定：** `FILE_TTL_HOURS=0` 與 `RESULT_TTL_HOURS=0` 表示關閉對應的過期/清理邏輯。

**理由：** 與常見「0=disabled」慣例一致；單一變數控制，無需額外 `FILE_EXPIRY_ENABLED`。

**替代方案：** 獨立 boolean — 變數增多，與 TTL 可能不一致。

### 2. 物理清理與邏輯過期分離配置

**決定：**

- `AUTO_CLEANUP_ENABLED` 控制 Worker 是否呼叫 `cleanup_expired()`
- 邏輯過期僅由 `FILE_TTL_HOURS` 控制（0 = 不過期）
- 結果清理僅在 `AUTO_CLEANUP_ENABLED=true` 且 `RESULT_TTL_HOURS>0` 時執行
- 上傳檔清理僅在 `AUTO_CLEANUP_ENABLED=true` 且 `FILE_TTL_HOURS>0` 時執行

**理由：** 使用者可組合：例如邏輯過期但暂不刪 storage（cleanup=false, TTL=24），或永久可用（預設）。

### 3. expires_at 對外呈現 null

**決定：** `FILE_TTL_HOURS=0` 時，API response 的 `expires_at` 為 JSON `null`。

**理由：** 語意清楚；避免誤導客戶端以為有截止日。

**實作：** DB 可存 `datetime.max` 或固定 sentinel；`_file_response()` 轉換為 null。

### 4. is_expired() 短路

**決定：** `FileRecord.is_expired()` 在 settings 的 `file_ttl_hours == 0` 時直接回 false（或 expires_at 為 sentinel 時回 false）。

**理由：** 所有引用 `get_owned_file()` 的路徑自動生效。

### 5. cleanup 間隔可配置

**決定：** `CLEANUP_INTERVAL_SECONDS` 預設 60，從 `api/config.py` 讀取；`AUTO_CLEANUP_ENABLED=false` 時不排程。

**理由：** 順便解決 hardcode 60 秒問題；disabled 時 interval 無意義。

## Risks / Trade-offs

| 風險 | 緩解 |
|------|------|
| Storage / DB 無限增長 | README 說明；需成本控管時設 cleanup + TTL；手動 DELETE |
| **BREAKING** 既有部署預設行為改變 | `.env.example` 註明恢復舊行為的 env；Release Notes |
| expires_at null 破壞嚴格型別客戶端 | Swagger 標 optional/nullable；README 說明 |
| 舊 DB 中已有 expires_at 過去的 record | 升級後若 FILE_TTL=0，is_expired 仍 false → 舊「已過期」檔案恢復可用（可能符合預期） |
| presigned URL 仍 24h 過期 | 文件說明：永久保留的是 result 存在，非單一 URL 永久有效 |

## Migration Plan

1. 更新 `api/config.py` 預設值與 helper（如 `file_expiry_enabled`）
2. 調整 upload / import / cleanup / worker / response 序列化
3. 更新 `.env.example`、README、Swagger
4. 部署：現有生產若需舊行為，部署前在 env 設：
   ```yaml
   AUTO_CLEANUP_ENABLED=true
   FILE_TTL_HOURS=24
   RESULT_TTL_HOURS=72
   ```
5. 回滾：還原舊版或調回 env

## Open Questions

- （無。使用者已確認：關清理後檔案永久可用；job 結果預設永久保留。）
