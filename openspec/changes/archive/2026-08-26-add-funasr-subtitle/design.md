## Context

MergeVideo API 已有上傳／URL import、非同步 job、Worker 以 FFmpeg 處理影片。數字人流程需要「成片 + 完整文字稿 → SRT」。FunASR 的 `fa-zh` 是強制對齊模型（音訊 + 文字 → 字級時間戳），只能透過 Python `AutoModel` 呼叫，**不是** `funasr-server` 的 HTTP 能力。

目前 API 與 Worker 共用同一 Dockerfile（`python:3.12-slim` + ffmpeg + 輕量 Python 依賴）。Worker 為單一 process，一次只跑一個 job。

## Goals / Non-Goals

**Goals:**

- `POST /v1/jobs/generate-subtitle`：`file_id` + 必填 `script` → 非同步產出 SRT
- `fa-zh` 跑在 **Worker process 內**（啟動或首次 job 載入一次）
- 標準 SRT、無 Speaker、字幕文字以稿子為準（不另做 ASR、不簡繁轉換）
- API 映像不安裝 PyTorch；Worker 映像另裝 FunASR 依賴
- CI 以 mock 覆蓋對齊與 SRT 組裝，不下載真實模型

**Non-Goals:**

- 無稿 ASR / `funasr-server` / 獨立 align HTTP 服務
- Speaker diarization
- 即時／串流字幕
- 把字幕燒進影片
- 多 Worker 並行與 GPU 排程

## Decisions

### 1. 對齊跑在 Worker，不另開服務

**決定：** Worker 內 `from funasr import AutoModel`，`model="fa-zh"`，`generate(input=(wav, text_path), data_type=("sound", "text"))`。

**理由：** 與 [FunASR 教程「時間戳預測」](https://github.com/modelscope/FunASR/blob/main/docs/tutorial/README_zh.md) 一致；少一個容器；38M 模型 CPU 可跑；使用者明確要求做在現有 Worker。

**替代方案：** 獨立 `funasr-align` HTTP — 多一層部署，目前規模不值得。`funasr-server` — 不支援 `(audio, text)` 對齊。

### 2. v1 `script` 必填

**決定：** API 拒絕缺漏或空白稿（`SCRIPT_REQUIRED` / `SCRIPT_EMPTY`）。無稿路徑不做。

**理由：** `fa-zh` 沒有稿就無法對齊；無稿需要另外部署 ASR。之後若要無稿，可再加 `funasr-server` 而不改有稿 API。

**上限：** `FUNASR_MAX_SCRIPT_CHARS`（預設 50000），超過回 HTTP 400 `SCRIPT_TOO_LONG`。

### 3. Worker 與 API 分開映像

**決定：**

- `requirements-api.txt`：維持現況（API / 測試不強制裝 torch）
- `requirements-worker.txt`：`-r requirements-api.txt` + `funasr`、`torch`、`torchaudio`、`soundfile`
- `Dockerfile.worker`：同 base，再裝 worker 依賴
- `docker-compose` 的 `worker` 改 `dockerfile: Dockerfile.worker`

**理由：** 共用映像會讓 API 容器多 1.5–3 GB 與常駐 torch。測試在 API 映像跑，對齊邏輯以 mock 注入。

**替代方案：** 同一映像、API 不 import funasr — 映像仍胖。拒絕。

### 4. 模型生命週期

**決定：** Worker 模組層 lazy singleton：第一次 `generate_subtitle` job（或 `run_forever` 啟動時可選預熱）載入 `AutoModel`。裝置由 `FUNASR_DEVICE` 決定（預設 `cpu`，可設 `cuda:0` / `mps`）。模型快取目錄掛 volume（`FUNASR_CACHE_DIR`，預設容器內 `/root/.cache`）。

**理由：** 避免每個 job 重載；首次下載需網路，之後走快取。

載入失敗 → job `FUNASR_UNAVAILABLE`。`GET /health` **不**檢查 fa-zh（health 在 API 容器，沒有模型）。

### 5. 音訊前處理

**決定：** Worker 用已有 ffmpeg：

```bash
ffmpeg -y -i input -vn -ac 1 -ar 16000 -f wav audio.wav
```

無音訊軌 → `NO_AUDIO_STREAM`。抽音完成前進度約 20。

**理由：** `fa-zh` 以 16k 訓練；Worker 已有 ffmpeg，不必在 FunASR 內解 mp4。

### 6. 字級時間戳 → SRT

**決定：** 純函式 `api/services/subtitle.py`（不依賴 FunASR），方便單測。

1. 將 `script` strip 後寫入 `text.txt`，原樣交給 `fa-zh`（不做簡繁轉換）
2. 解析 `res[0]["timestamp"]` 為 `list[[start_ms, end_ms], ...]`
3. 以 `[。！？!?；;，]` 分句（含中文逗號、分號），標點留在該句末；不斷開英文逗號 `,`（避免 `1,000`）。無標點則整段一句
4. 依「句內字元數（含標點、不含換行）」切 timestamp 切片；句 start = 切片首 start，句 end = 切片末 end
5. 輸出標準 SRT（序號、`HH:MM:SS,mmm --> HH:MM:SS,mmm`、正文、空行）；UTF-8 無 BOM；**禁止** Speaker 前綴
6. 過長單句（預設 > 42 字）不強制二次切分（v1 不做）

timestamp 數量與字元數對不上時：以 `zip` 對齊能對上的字；若整段沒有任何 timestamp → `ALIGN_FAILED`。稿與發音差太多導致明顯錯位，視為呼叫端責任，v1 不自動 ASR 校正。

### 7. Job 契約與進度

**決定：** 沿用 `_create_job`：pin `file_id`、`type=generate_subtitle`、`input_json` 含 `file_ids` 與 `script`。

進度（節流機制複用）：

| 階段 | progress |
|------|----------|
| queued | 0 |
| 下載輸入 | 10 |
| 抽 wav | 20 |
| 對齊中 | 50 |
| 寫 SRT + 上傳 | 90 |
| done | 100 |

`fa-zh` 無內建 callback，對齊階段無法細分。

`done` 的 `result`：`download_url`、`expires_at`、`filename`（來源 stem + `.srt`）、`content_type`（`application/x-subrip`）、`size_bytes`。存放 `results/{job_id}/{filename}`，TTL 與其他 result 相同。

### 8. 測試策略

**決定：** 不在 CI 下載 `fa-zh`。

- 單測：給假 timestamp + 稿 → 斷言 SRT 內容與時間碼
- Worker 測：patch `get_align_model().generate` 回固定結構
- API 測：缺 script、空白、過長、未授權 file、202 契約

本地可選手動：真實模型 smoke（不進預設 pytest）。

## Risks / Trade-offs

| 風險 | 緩解 |
|------|------|
| Worker 映像變大、RAM +1–2GB | 僅 Worker 裝 torch；文件標明記憶體需求 |
| 對齊 job 卡住 merge（單 Worker） | 接受排隊；文件說明；之後可加 replica |
| 稿與音訊不一致 → 時間軸偏 | 文件要求稿須對應發音；失敗才 `ALIGN_FAILED` |
| 首次啟動下載模型失敗 | volume 快取；錯誤碼 `FUNASR_UNAVAILABLE` |
| timestamp 長度與字數不符 | zip 對齊；全空則失敗 |
| API/Worker 共用程式碼但不同映像 | lazy import FunASR；API 路徑永不 import `funasr` |
| Docker 內 MPS 不可用 | 預設 `cpu`；有 NVIDIA 再設 `cuda:0` |

## Migration Plan

1. 新增 Worker 依賴與 `Dockerfile.worker`；compose 的 worker 改用該 Dockerfile
2. 部署時掛模型快取 volume；Worker 需能連 ModelScope／HuggingFace（首次）
3. 無 DB schema 變更
4. 回滾：還原映像即可；已產出的 SRT 與其他 result 相同保留策略
5. 未裝 FunASR 的舊 Worker 接到此 job type → `FUNASR_UNAVAILABLE`（勿當 `FFMPEG_ERROR`）

## Open Questions

（無。無稿 ASR、獨立 align 服務、Speaker 已列為 Non-Goals。）
