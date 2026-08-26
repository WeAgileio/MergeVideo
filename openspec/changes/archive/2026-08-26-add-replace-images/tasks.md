## 1. 上傳圖片

- [x] 1.1 `POST /v1/files` 接受 `.png` `.jpg` `.jpeg` `.webp`：對應 `image/png` / `image/jpeg` / `image/webp`、不上 ffprobe、空檔仍 `EMPTY_FILE`；`scanner.VIDEO_EXTENSIONS` 不加圖副檔名
- [x] 1.2 更新 files 的 Swagger `summary` / `description` / 上傳成功 examples

## 2. Replace-images API

- [x] 2.1 實作 `POST /v1/jobs/replace-images`：驗證檔案類型、1–10 段、start/end、重疊，pin 影片與引用到的圖，202
- [x] 2.2 新增錯誤碼 `EMPTY_REPLACEMENTS`、`TOO_MANY_REPLACEMENTS`、`INVALID_RANGE`、`OVERLAPPING_RANGES`、`INVALID_IMAGE`（`api/errors.py` 與 `_API_DESCRIPTION`）；`WRONG_FILE_TYPE` 沿用
- [x] 2.3 更新 job 查詢 Swagger：`replace_images` done / failed 範例；總覽說明含換圖流程

## 3. Worker 換圖

- [x] 3.1 新增模組：Pillow contain 到影片寬高黑底、透明墊黑；ffmpeg overlay `between(t,start,end)`、libx264 CRF 18、音訊 copy
- [x] 3.2 `runner.py` 新增 `_run_replace_images`：下載影片與圖 → 壞圖 `INVALID_IMAGE` → 超出片長 `INVALID_RANGE` → 上傳 `uploads/{file_id}/original.mp4` 並寫 `FileRecord`；`result_json` 含 `file_id` 與 `storage_key`
- [x] 3.3 `GET /v1/jobs/{id}` 對 `replace_images` 的 `done` 同時回 `file_id` 與 `download_url`；接上 `run_ffmpeg_with_progress`（15–95）

## 4. 測試與文件

- [x] 4.1 上傳測試：png/jpeg 201；`.txt` 仍 400
- [x] 4.2 API 測試：202、EMPTY_REPLACEMENTS、TOO_MANY_REPLACEMENTS、WRONG_FILE_TYPE、INVALID_RANGE、OVERLAPPING_RANGES、401、他人檔
- [x] 4.3 Worker 測試（需 ffmpeg）：短影片 + 圖產出 mp4，duration 不變；壞圖 → `INVALID_IMAGE`；end 超過片長 → `INVALID_RANGE`；done 可 GET 該 `file_id`
- [x] 4.4 更新 `README.md` 與 `README.en.md`（endpoint 表、curl、contain／file_id）
- [x] 4.5 以 `create_app().openapi()` 確認 path 含 `/v1/jobs/replace-images`
