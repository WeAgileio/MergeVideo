## Why

數字人流程已能從成片 + 文字稿產出 SRT，但成品仍是外掛字幕檔。發布與客戶端播放需要把字幕燒進畫面，並可調字級與離底邊距離。現有 SRT 只是 job 下載結果、上傳又不收 `.srt`，無法接到下一步。

## What Changes

- 新增 `POST /v1/jobs/burn-subtitle`：以影片 `file_id` + SRT `srt_file_id` 非同步燒字幕，產出 `.mp4`
- 可選 `font_size`（預設 48）、`margin_bottom`（預設 6）、`margin_unit`（`px` 或 `percent`，預設 `percent`）；對齊固定底部水平置中
- 預設字型為專案內建的台北黑體 Regular（`TaipeiSansTCBeta-Regular.ttf`）；白字黑描邊；不開放換字型／對齊／顏色
- `generate-subtitle` `done` 時除既有 `download_url` 外，**另註冊 SRT 為 `file_id`**，供 burn 直接引用
- `POST /v1/files` 接受 `.srt`，以便下載修改後再上傳
- **不包含**：自訂字型檔、左／右／垂直置中對齊、改字色、一條龍「稿→燒字」、軟字幕軌道（mov_text）

## Capabilities

### New Capabilities

- `subtitle-burn-in`：將標準 SRT 燒進影片畫面（字級、離底邊距離、內建台北黑體、底部置中）

### Modified Capabilities

- `api-video-jobs`：新增 `burn_subtitle` job；`generate_subtitle` 完成結果新增 `file_id`
- `api-file-upload`：上傳與檔案庫支援 `.srt`（`application/x-subrip`）
- `subtitle-srt`：對齊產出的 SRT 須進入 file registry，而不只存在 job result

## Impact

- 新增 `POST /v1/jobs/burn-subtitle`；沿用既有 job 生命週期、pin、API key
- 修改 `api/routes/files.py`、`api/routes/jobs.py`、`api/worker/runner.py`、`api/errors.py`、`api/main.py`
- 將 `TaipeiSansTCBeta-Regular.ttf`（SIL OFL 1.1）納入 repo（約 20 MB）並寫入 Worker 映像
- 燒字必定重編碼（H.264），無法 copy；進度跟 ffmpeg 時長
- 新增錯誤碼（例如無效 SRT、錯誤的檔案類型、字型缺失）
- merge / extract / import-url 行為不變
