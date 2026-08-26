## 1. 字型與設定

- [x] 1.1 將 `TaipeiSansTCBeta-Regular.ttf` 複製到 `assets/fonts/`，並放入 SIL OFL 1.1 授權檔 `assets/fonts/OFL.txt`
- [x] 1.2 擴充 `api/config.py`：`SUBTITLE_FONT_PATH`（預設 `assets/fonts/TaipeiSansTCBeta-Regular.ttf`）
- [x] 1.3 更新 `.env.example`（字型路徑註解；說明 burn 必重編碼）

## 2. 上傳 SRT 與 generate-subtitle 註冊檔案

- [x] 2.1 `POST /v1/files` 接受 `.srt`：`content_type=application/x-subrip`、不上 ffprobe、空檔仍 `EMPTY_FILE`；`scanner.VIDEO_EXTENSIONS` 不加 `.srt`
- [x] 2.2 `_run_generate_subtitle` 成功後寫入 `FileRecord`（`uploads/{file_id}/original.srt`），`result_json` 含 `file_id` 與 `storage_key`
- [x] 2.3 `GET /v1/jobs/{id}` 對 `generate_subtitle` 的 `done` 同時回 `file_id` 與 `download_url`（presign 同一物件）
- [x] 2.4 更新 files 與 generate-subtitle 的 Swagger `summary` / `description` / examples

## 3. Burn API

- [x] 3.1 實作 `POST /v1/jobs/burn-subtitle`：驗證檔案類型、margin、font_size，套預設後寫入 `input_json`，pin 兩個 file，202
- [x] 3.2 新增錯誤碼 `WRONG_FILE_TYPE`、`INVALID_MARGIN`、`INVALID_FONT_SIZE`、`INVALID_SRT`、`FONT_UNAVAILABLE`（`api/errors.py` 與 `_API_DESCRIPTION`）
- [x] 3.3 更新 job 查詢 Swagger：`burn_subtitle` done / failed 範例

## 4. Worker 燒字

- [x] 4.1 新增燒字模組（SRT 至少一條 cue、計算離底像素、Pillow 繪透明 PNG + ffmpeg overlay：台北黑體、底部置中、白字黑邊）
- [x] 4.2 `runner.py` 新增 `_run_burn_subtitle`：下載兩檔 → 缺字型 `FONT_UNAVAILABLE` → 壞 SRT `INVALID_SRT` → ffmpeg libx264 CRF 18、音訊 copy → 上傳 `*_burned.mp4`
- [x] 4.3 接上 `run_ffmpeg_with_progress`（15–95）與既有節流

## 5. 測試與文件

- [x] 5.1 上傳測試：`.srt` 201；`.txt` 仍 400
- [x] 5.2 generate-subtitle 測試：mock 對齊後 result 含 `file_id`，且可 GET 該 file
- [x] 5.3 burn API 測試：預設寫入 input、WRONG_FILE_TYPE、INVALID_MARGIN、INVALID_FONT_SIZE、401、他人檔、202
- [x] 5.4 Worker 測試（需 ffmpeg）：短影片 + 合法 SRT 產出 mp4；空 SRT → `INVALID_SRT`；缺字型 → `FONT_UNAVAILABLE`
- [x] 5.5 更新 `README.md` 與 `README.en.md`（endpoint 表、兩段式 curl、預設樣式）
- [x] 5.6 以 `create_app().openapi()` 確認 path 含 `/v1/jobs/burn-subtitle`
