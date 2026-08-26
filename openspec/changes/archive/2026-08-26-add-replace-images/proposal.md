## Why

數字人口播常要在某幾秒換成靜態圖（資訊圖、截圖），同時保留原聲、片長不變。現有 job 只能合併、取幀、燒字幕，無法只替換畫面。圖也還不能上傳進 file registry，無法用 `file_id` 接到下一支任務。

## What Changes

- 新增 `POST /v1/jobs/replace-images`：影片 `file_id` + 多段 `replacements`（每段 `image_file_id`、`start`、`end`），非同步整框換成該圖
- 圖須先 `POST /v1/files` 上傳；本 job 只引用 `file_id`
- 每段為 contain（等比縮進片幅、黑邊、不裁不變形）；該時段整框只剩圖
- 音訊 stream copy；輸出時長與輸入相同
- `done` 同時回 `file_id`（成片進 file registry）與 `download_url`，以便呼叫端自行串 burn-subtitle 或其他 job
- `POST /v1/files` 接受 `.png` / `.jpg` / `.jpeg` / `.webp`
- **不包含**：畫中畫、cover／stretch、呼叫端選 fit 模式、與燒字幕綁定順序、軟字幕、改音訊

## Capabilities

### New Capabilities

- `video-image-replace`：在指定時段把影片畫面整框換成已上傳的靜態圖（contain、音訊不變、片長不變）

### Modified Capabilities

- `api-video-jobs`：新增 `replace_images` job；完成結果含 `file_id` 與 download URL
- `api-file-upload`：上傳與檔案庫支援靜態圖（png / jpeg / webp）

## Impact

- 新增 `POST /v1/jobs/replace-images`；沿用既有 job 生命週期、pin、API key
- 修改 `api/routes/files.py`、`api/routes/jobs.py`、`api/worker/runner.py`、`api/errors.py`、`api/main.py`
- 畫面時段 overlay 必定重編碼 H.264；音訊 copy
- 新增錯誤碼（錯誤檔案類型、無效時段、時段重疊）
- merge / extract / import-url / 字幕行為不變
