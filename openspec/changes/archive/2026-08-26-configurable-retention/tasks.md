## 1. 設定

- [x] 1.1 擴充 `api/config.py`：`AUTO_CLEANUP_ENABLED`（預設 false）、`CLEANUP_INTERVAL_SECONDS`（預設 60）
- [x] 1.2 調整 `FILE_TTL_HOURS`、`RESULT_TTL_HOURS` 預設為 `0`；新增 helper（如 `file_expiry_enabled`）
- [x] 1.3 更新 `.env.example`、`docker-compose.yml` 註解（含恢復舊行為範例）

## 2. 邏輯過期與 API response

- [x] 2.1 修改 `FileRecord.is_expired()`：`FILE_TTL_HOURS=0` 時永遠 false
- [x] 2.2 上傳 / import 時：`FILE_TTL_HOURS=0` 不設有效期限（DB sentinel 或 max datetime）
- [x] 2.3 `_file_response()` 與 job result：`expires_at` 在永不過期時回傳 JSON `null`
- [x] 2.4 更新 Swagger 範例（`api/main.py`、`api/routes/files.py`、`api/routes/jobs.py`）

## 3. 背景清理

- [x] 3.1 修改 `cleanup_expired()`：respect `AUTO_CLEANUP_ENABLED` 與 TTL=0 跳過對應分支
- [x] 3.2 修改 `runner.run_forever()`：cleanup disabled 時不呼叫；interval 讀 config

## 4. 測試

- [x] 4.1 單元/整合：預設配置下檔案不過期、不被 cleanup 刪除
- [x] 4.2 測試：`AUTO_CLEANUP_ENABLED=true` + TTL>0 時清理行為與舊版一致
- [x] 4.3 測試：done job 預設永久可查 `download_url`；enabled 後 result 被清

## 5. 文件

- [x] 5.1 更新 README / README.en（保留策略、breaking change、env 對照表）
- [x] 5.2 Swagger 頂層說明：TTL=0、cleanup 預設關閉
