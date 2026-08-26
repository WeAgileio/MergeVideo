## Why

數字人短片已有成片與完整文字稿，但 MergeVideo 只能合併／抽幀，無法產出對齊時間軸的 SRT。客戶端若自行對齊，需另建 FunASR 服務。在既有 Worker 內用 `fa-zh` 強制對齊，可把「影片 + 稿子 → 字幕」納入同一套非同步 job。

## What Changes

- 新增 `POST /v1/jobs/generate-subtitle`，接受 `file_id` 與必填 `script`（一整段文字稿）
- 新增 job type `generate_subtitle`；Worker 抽 16k mono wav，以 FunASR `AutoModel("fa-zh")` 對齊時間戳，再依標點組成標準 SRT
- job `done` 後 `result.download_url` 指向 `.srt`（`content_type: application/x-subrip`）
- Worker 映像另裝 `funasr` / PyTorch；API 映像維持輕量，不載入模型
- **不包含**：無稿 ASR、`funasr-server`、獨立 align HTTP 服務、Speaker 標籤、簡繁轉換

## Capabilities

### New Capabilities

- `subtitle-srt`：有稿強制對齊、標點分句、標準 SRT 輸出（無 Speaker）

### Modified Capabilities

- `api-video-jobs`: 新增 `generate_subtitle` job type、建立／輪詢／下載行為

## Impact

- 新增 `POST /v1/jobs/generate-subtitle`；沿用既有 job 生命週期與 API key
- 修改 `api/routes/jobs.py`、`api/worker/runner.py`、`api/config.py`、`.env.example`、`docker-compose.yml`
- 新增 Worker 依賴與（可選）`Dockerfile.worker` / `requirements-worker.txt`，避免 API 映像帶入 torch
- 新增錯誤碼：`SCRIPT_REQUIRED`、`SCRIPT_EMPTY`、`NO_AUDIO_STREAM`、`ALIGN_FAILED`、`FUNASR_UNAVAILABLE`
- 單元測試 mock `AutoModel`（CI 不下載真實模型）
- merge / extract / import-url 行為不變
