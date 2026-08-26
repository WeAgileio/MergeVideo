# MergeVideo

[English README](README.en.md)

將資料夾內多段數字序影片（`1.mp4`、`2.mp4`…）合併為一支 MP4，或從單支影片擷取第一幀 / 最後一幀 PNG。適用於 ComfyUI 數字人工作流等場景。

## 工具

| 指令 | 用途 |
|------|------|
| `mergevideo.py` | 合併多段數字序影片為一支 MP4 |
| `VideoFirstFrame` | 擷取單支影片第一幀為 PNG |
| `VideoLastFrame` | 擷取單支影片最後一幀為 PNG |

## mergevideo 功能

- 依檔名自然排序（`1 → 2 → 10`）
- 自動分析解析度、幀率、編碼、音訊
- 互動選擇 **Copy**（不重新編碼）或 **Encode**（統一規格後合併）
- Encode 模式以**最大像素面積**片段為輸出解析度，較小段等比縮放並加黑邊
- 每段保留音訊，無聲段自動補靜音
- 預設輸出至 input 資料夾內的 `output/mergedYYYYMMDDHHmmss.mp4`

## 環境需求

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/) / ffprobe（需在 PATH 中）

```bash
# macOS (Homebrew)
brew install ffmpeg

# 確認安裝
ffmpeg -version
ffprobe -version
```

## 快速開始

```bash
# 克隆專案
git clone https://github.com/WeAgileio/MergeVideo.git
cd MergeVideo

# 互動模式（分析後選擇 Copy / Encode）
python3 mergevideo.py ./clips

# 自動判斷模式
python3 mergevideo.py ./clips --mode auto

# 只分析、不合併
python3 mergevideo.py ./clips --dry-run
```

也可加上執行權限後直接呼叫：

```bash
chmod +x mergevideo.py
./mergevideo.py ./clips
```

## 輸入規則

將待合併影片放入同一資料夾，檔名必須為**純數字**：

```
clips/
├── 1.mp4
├── 2.mp4
└── 10.mp4
```

| 規則 | 說明 |
|------|------|
| 檔名格式 | `1.mp4`、`02.mov` 等（stem 須為 `\d+`） |
| 非數字檔名 | 直接報錯（如 `intro.mp4`） |
| 最少數量 | 至少 2 段影片 |
| 支援格式 | `.mp4`、`.mov`、`.webm`、`.mkv`、`.avi`、`.m4v` |

## 輸出規則

未指定 `-o` 時，輸出至 input 資料夾**裡面**的 `output/`：

```
clips/              ← 輸入
├── 1.mp4
├── 2.mp4
└── output/         ← 自動建立
    └── merged20260619120930.mp4
```

## 命令列參數

```
mergevideo.py <input_folder> [選項]

選項:
  -o, --output PATH     自訂輸出檔案路徑
  --mode {auto,copy,encode}
                        auto=相容則 copy，否則 encode
                        copy=串接不編碼（不相容則報錯）
                        encode=重新編碼
  --crf N               Encode 品質，預設 18（越小越好）
  --dry-run             只分析報告，不合併
```

### 範例

```bash
# 互動選擇
python3 mergevideo.py ./clips

# 強制重新編碼
python3 mergevideo.py ./clips --mode encode

# 片段規格一致時快速合併
python3 mergevideo.py ./clips --mode copy

# 自訂輸出路徑
python3 mergevideo.py ./clips -o ~/Desktop/final.mp4
```

## 合併模式

### Copy 模式

所有片段解析度、編碼、幀率、音訊格式完全一致時可用。直接串接，速度快、無畫質損失。

### Encode 模式

片段規格不一致時使用。統一輸出為 H.264 + AAC（48000 Hz stereo），解析度跟最大片段走，較小段加黑邊置中。

執行時會顯示分析報告：

```
掃描資料夾: ./clips
找到 3 個影片（自然排序）

 #  檔名      解析度      FPS  編碼    音訊
────────────────────────────────────────────
 1  1.mp4    1920×1080   30   h264    aac
 2  2.mp4    1280×720    30   h264    無

Copy 模式: 不可用
Encode 模式: 可用

請選擇 [E]ncode / [Q]uit:
```

## ComfyUI 工作流

1. ComfyUI 產出多段影片
2. （可選）擷取各段第一幀或最後一幀作為參考圖：

```bash
VideoFirstFrame ./clips/1.mp4
# → ./clips/output/1_FirstFrame.png

VideoLastFrame ./clips/1.mp4
# → ./clips/output/1_LastFrame.png
```

3. 重新命名為 `1.mp4`、`2.mp4`、`3.mp4` …
4. 執行合併：

```bash
python3 mergevideo.py /path/to/comfyui/output --mode auto
```

## VideoFirstFrame

擷取單支影片的第一幀，輸出 PNG。

```bash
VideoFirstFrame ./clips/1.mp4
# → ./clips/output/1_FirstFrame.png
```

| 項目 | 說明 |
|------|------|
| 輸入 | 單一影片檔（不支援資料夾） |
| 輸出檔名 | `{stem}_FirstFrame.png` |
| 輸出位置 | 影片所在目錄下的 `output/` |
| 格式 | PNG |

## VideoLastFrame

擷取單支影片的最後一幀，輸出 PNG。

```bash
VideoLastFrame ./clips/1.mp4
# → ./clips/output/1_LastFrame.png
```

| 項目 | 說明 |
|------|------|
| 輸入 | 單一影片檔（不支援資料夾） |
| 輸出檔名 | `{stem}_LastFrame.png` |
| 輸出位置 | 影片所在目錄下的 `output/` |
| 格式 | PNG |

也可加上執行權限後直接呼叫：

```bash
chmod +x VideoLastFrame
./VideoLastFrame ./clips/1.mp4
```

## HTTP API

除 CLI 外，另提供 REST API（FastAPI），供雲端 Web 服務呼叫。流程：**上傳檔案取得 `file_id` → 建立非同步 job → 輪詢 job 狀態 → 以 download URL 下載結果**。

### 啟動（本機開發）

```bash
pip install -r requirements-api.txt
# 若要跑字幕 job，Worker 需另裝 FunASR / PyTorch（映像約再增 1.5–3GB，RAM 預留 1–2GB）
pip install -r requirements-worker.txt
cp .env.example .env   # 修改 API_KEYS 等設定

# API server
uvicorn api.main:create_app --factory --reload

# Worker（另開終端）
python -m api.worker
```

或使用 Docker Compose（含 MinIO + Redis）。字幕 Worker 使用 `Dockerfile.worker`（含 PyTorch）；首次啟動會下載 `fa-zh` 模型（需網路），之後走 `funasr_models` volume 快取：

```bash
docker compose up --build
```

### 互動式 API 文檔（Swagger）

服務啟動後即可使用：

| 位址 | 說明 |
|------|------|
| `http://localhost:8000/docs` | Swagger UI — 可點右上角 **Authorize** 填入 API key，直接在頁面上傳檔案、建任務、輪詢結果 |
| `http://localhost:8000/redoc` | ReDoc — 適合閱讀的文檔版面 |
| `http://localhost:8000/openapi.json` | OpenAPI 3.1 spec — 可匯入 Postman / Insomnia 或產生 client SDK |

### Endpoints

| Method | Path | 用途 |
|--------|------|------|
| `POST` | `/v1/files` | 上傳影片、`.srt` 或圖片（multipart，欄位 `file`），回 `file_id` |
| `GET` | `/v1/files/{file_id}` | 查檔案 metadata |
| `DELETE` | `/v1/files/{file_id}` | 刪除檔案 |
| `POST` | `/v1/jobs/merge` | 合併，`file_ids` 依**陣列順序**，內部自動選 copy/encode |
| `POST` | `/v1/jobs/extract-first-frame` | 取第一幀 PNG |
| `POST` | `/v1/jobs/extract-last-frame` | 取最後一幀 PNG |
| `POST` | `/v1/jobs/import-url` | 從 URL 匯入影片（非同步），done 回 `file_id` |
| `POST` | `/v1/jobs/generate-subtitle` | 有稿產生 SRT（必填 `script`），done 回 `file_id` 與 `.srt` download URL |
| `POST` | `/v1/jobs/burn-subtitle` | 把 SRT 燒進影片；可選字級與離底邊距離 |
| `POST` | `/v1/jobs/replace-images` | 指定時段把畫面整框換成靜態圖（1–10 段），done 回 `file_id` 與 download URL |
| `GET` | `/v1/jobs/{job_id}` | 查 job 狀態；含 `progress`；merge/extract/burn `done` 回 `download_url`，generate-subtitle 與 replace-images 另回 `file_id`，import 回 `file_id` |
| `GET` | `/health` | 健康檢查（含 ffmpeg 可用性） |

所有 `/v1/*` 皆需 `Authorization: Bearer <api_key>`。

### 使用範例

```bash
KEY="change-me"
BASE="http://localhost:8000"

# 1. 上傳兩段影片
F1=$(curl -s -X POST "$BASE/v1/files" -H "Authorization: Bearer $KEY" \
  -F "file=@1.mp4" | python3 -c "import sys,json;print(json.load(sys.stdin)['file_id'])")
F2=$(curl -s -X POST "$BASE/v1/files" -H "Authorization: Bearer $KEY" \
  -F "file=@2.mp4" | python3 -c "import sys,json;print(json.load(sys.stdin)['file_id'])")

# 2. 建立合併 job（依陣列順序）
JOB=$(curl -s -X POST "$BASE/v1/jobs/merge" -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d "{\"file_ids\": [\"$F1\", \"$F2\"]}" | python3 -c "import sys,json;print(json.load(sys.stdin)['job_id'])")

# 3. 輪詢直到 done，取得 download_url（processing 時可用 progress 顯示進度條）
curl -s "$BASE/v1/jobs/$JOB" -H "Authorization: Bearer $KEY"
# {"job_id": "j_...", "status": "processing", "progress": 45, ...}
# {"job_id": "j_...", "status": "done", "progress": 100, "result": {"download_url": ...}}
```

### 從 URL 匯入（免自行上傳）

```bash
# 1. 建立 import job（server 代為下載，預設僅 https）
IMPORT=$(curl -s -X POST "$BASE/v1/jobs/import-url" -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://cdn.example.com/clip.mp4"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['job_id'])")

# 2. 輪詢直到 done，取得 file_id
curl -s "$BASE/v1/jobs/$IMPORT" -H "Authorization: Bearer $KEY"
# {"status": "done", "result": {"file_id": "f_...", ...}}

# 3. 用 file_id 接 merge / extract（同上）
```

### 有稿產生 SRT 字幕

Worker 內以 FunASR `fa-zh` 對齊時間軸（不是 funasr-server）。文字稿須與發音對應；字幕文字以稿為準。

```bash
# 1. 已有 file_id（上傳或 import-url）
SUB=$(curl -s -X POST "$BASE/v1/jobs/generate-subtitle" -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d "{\"file_id\": \"$F1\", \"script\": \"大家好。歡迎收看本期內容。\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['job_id'])")

# 2. 輪詢直到 done，取得 file_id 與 download_url
curl -s "$BASE/v1/jobs/$SUB" -H "Authorization: Bearer $KEY"
# {"status": "done", "result": {"file_id": "f_...", "filename": "1.srt", "download_url": "..."}}
```

### 燒字幕進影片

兩段式：先有 SRT（generate-subtitle 的 `result.file_id`，或自行上傳 `.srt`），再燒進畫面。必定重編碼。預設字型為台北黑體、字級 48、離底 6%、底部水平置中、白字黑描邊。

```bash
# 可用 generate-subtitle 回傳的 file_id，或另外上傳 .srt
SRT=$(curl -s -X POST "$BASE/v1/files" -H "Authorization: Bearer $KEY" \
  -F "file=@talk.srt" | python3 -c "import sys,json;print(json.load(sys.stdin)['file_id'])")

BURN=$(curl -s -X POST "$BASE/v1/jobs/burn-subtitle" -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d "{\"file_id\": \"$F1\", \"srt_file_id\": \"$SRT\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['job_id'])")

# 可選樣式：font_size、margin_bottom、margin_unit（px 或 percent）
# -d '{"file_id":"...","srt_file_id":"...","font_size":48,"margin_bottom":6,"margin_unit":"percent"}'

curl -s "$BASE/v1/jobs/$BURN" -H "Authorization: Bearer $KEY"
```

### 指定時段換成靜態圖

一次可換 1–10 段，每段整框只剩該圖。圖以 contain 縮放：等比縮到不超出畫面、置中，多餘處補黑邊，不裁切也不變形。音訊 stream copy、輸出時長與來源相同；畫面必定重編碼 H.264。

`done` 的 `result` 同時含 `file_id`（成片已註冊進檔案庫）與 `download_url`，因此可直接把 `file_id` 交給 burn-subtitle 等後續任務。換圖與燒字幕的先後由你決定：先換圖再燒字，字幕會蓋在圖上；先燒字再換圖，那幾秒連字一起被蓋掉。

```bash
# 1. 上傳圖片（png / jpg / jpeg / webp）
IMG=$(curl -s -X POST "$BASE/v1/files" -H "Authorization: Bearer $KEY" \
  -F "file=@slide.png" | python3 -c "import sys,json;print(json.load(sys.stdin)['file_id'])")

# 2. 建立換圖 job（時段不可重疊；end 等於下一段 start 可以）
REP=$(curl -s -X POST "$BASE/v1/jobs/replace-images" -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d "{\"file_id\": \"$F1\", \"replacements\": [{\"image_file_id\": \"$IMG\", \"start\": 3, \"end\": 5}]}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['job_id'])")

# 3. 輪詢直到 done，取得 file_id 與 download_url
curl -s "$BASE/v1/jobs/$REP" -H "Authorization: Bearer $KEY"
# {"status": "done", "result": {"file_id": "f_...", "filename": "1_replaced.mp4", "download_url": "..."}}
```

### 檔案儲存後端（啟動時切換）

以環境變數 `STORAGE_BACKEND` 切換，所有後端共用同一介面，上傳 / 處理 / 下載邏輯不變：

| backend | 適用 | 必要設定 | download URL |
|---------|------|----------|--------------|
| `local` | 本機開發 | `LOCAL_STORAGE_DIR` | API `/storage` 路由 |
| `s3` | AWS S3 及所有 S3 相容（MinIO / Cloudflare R2 / 阿里 OSS / 腾讯 COS / Wasabi / B2） | `S3_BUCKET`、`S3_ACCESS_KEY`、`S3_SECRET_KEY`，非 AWS 需 `S3_ENDPOINT_URL` | presigned URL |
| `gcs` | Google Cloud Storage | `GCS_BUCKET`、`GCS_CREDENTIALS_JSON`（service account） | v4 signed URL |
| `azure` | Azure Blob Storage | `AZURE_CONNECTION_STRING`、`AZURE_CONTAINER` | SAS URL |
| `rclone` | **Google Drive、OneDrive**、Dropbox、Box 等 rclone 支援的遠端 | 先 `rclone config` 建遠端，再設 `RCLONE_REMOTE`（如 `gdrive:mergevideo`） | `rclone link` 分享連結 |

```bash
# 例：切到 AWS S3
STORAGE_BACKEND=s3 S3_BUCKET=my-bucket S3_ACCESS_KEY=... S3_SECRET_KEY=... \
  uvicorn api.main:create_app --factory

# 例：切到 Google Drive（需先 rclone config 建立名為 gdrive 的遠端）
STORAGE_BACKEND=rclone RCLONE_REMOTE=gdrive:mergevideo \
  uvicorn api.main:create_app --factory
```

注意：`gcs` / `azure` 需另安裝對應套件（見 `requirements-api.txt` 註解）；rclone 分享連結無過期時間控制，適合內部流程、不適合需要嚴格權限的場景。

### 保留與清理

| 變數 | 預設 | 說明 |
|------|------|------|
| `FILE_TTL_HOURS` | `0` | `0` = 上傳檔永不過期；> 0 時邏輯過期 |
| `RESULT_TTL_HOURS` | `0` | `0` = job 結果永久保留 |
| `AUTO_CLEANUP_ENABLED` | `false` | Worker 是否背景物理刪除 |
| `CLEANUP_INTERVAL_SECONDS` | `60` | 清理間隔（僅 enabled 時） |
| `DOWNLOAD_URL_TTL_HOURS` | `24` | 單次 presigned URL 有效期 |

**Breaking change：** 未設 env 的部署，行為從「24h 過期 + 自動清」改為「永久保留」。恢復舊行為：

```bash
AUTO_CLEANUP_ENABLED=true
FILE_TTL_HOURS=24
RESULT_TTL_HOURS=72
```

手動刪除：`DELETE /v1/files/{file_id}`。

### 主要設定（環境變數）

詳見 `.env.example`：`API_KEYS`、`STORAGE_BACKEND`、`REDIS_URL`、`MAX_FILE_SIZE_MB`（預設 200）、`AUTO_CLEANUP_ENABLED`、`FILE_TTL_HOURS`、`DOWNLOAD_URL_TTL_HOURS`、`IMPORT_URL_ALLOW_HTTP` 等。

### 測試

```bash
pip install -r requirements-api.txt
python -m pytest tests/
```

## 專案結構

```
MergeVideo/
├── mergevideo.py      # 合併 CLI
├── VideoFirstFrame    # 擷取第一幀 CLI
├── VideoLastFrame     # 擷取最後一幀 CLI
├── extract_frame.py   # 取幀邏輯
├── scanner.py         # 掃描與檔名驗證
├── probe.py           # ffprobe 解析
├── compat.py          # Copy 相容性判定
├── report.py          # 分析報告
├── merger.py          # 合併引擎（含 merge_auto 供 API 使用）
├── ffmpeg_utils.py    # FFmpeg 工具封裝
├── api/               # HTTP API（FastAPI）
│   ├── main.py        #   app 入口（factory）
│   ├── routes/        #   files / jobs endpoints
│   ├── models/        #   file registry 與 job store
│   ├── services/      #   storage / queue / cleanup
│   └── worker/        #   背景處理 worker
└── tests/             # API 整合測試
```

## 常見錯誤

| 訊息 | 原因 |
|------|------|
| 輸入資料夾不存在 | 路徑錯誤 |
| 發現非數字檔名的影片 | 資料夾內有 `intro.mp4` 等 |
| 至少需要 2 段影片 | 只有 1 個影片檔 |
| Copy 模式不可用 | 片段規格不一致，改用 `--mode encode` |
| 找不到 ffmpeg / ffprobe | 未安裝或未加入 PATH |
| 請提供單一影片檔路徑 | VideoFirstFrame / VideoLastFrame 收到資料夾而非檔案 |
| 找不到影片串流 | 輸入檔不含 video stream |

## Release Notes

### v2.2.0

- **指定時段換圖**：`POST /v1/jobs/replace-images`，一次可換 1–10 段，每段把畫面整框換成已上傳的靜態圖。圖以 contain 縮放（等比、置中、補黑邊，不裁不變形）；音訊 stream copy，輸出時長與來源相同
- **換圖成片可直接接下一支任務**：`done` 的 `result` 同時含 `file_id` 與 `download_url`，可把 `file_id` 交給 burn-subtitle。換圖與燒字幕的先後由呼叫端決定
- **上傳圖片**：`POST /v1/files` 接受 `.png` / `.jpg` / `.jpeg` / `.webp`
- **字幕時間軸更準**：英文專名與數字（如 `Lookonchain`、`96191`）不再按字母數吃掉後面句子的時間戳；最後一句的結束時間會延伸到實際口播結束
- **新增 error code**：`EMPTY_REPLACEMENTS`、`TOO_MANY_REPLACEMENTS`、`INVALID_RANGE`、`OVERLAPPING_RANGES`、`INVALID_IMAGE`

### v2.1.0

- **有稿字幕**：`POST /v1/jobs/generate-subtitle`，必填文字稿 `script`；Worker 以 FunASR `fa-zh` 對齊並產出 SRT。完成後同時回 `file_id` 與 download URL
- **燒字幕**：`POST /v1/jobs/burn-subtitle`，把 SRT 燒進影片。可設 `font_size`、`margin_bottom`（`px` 或 `percent`）；預設台北黑體、字級 48、離底 6%、底部水平置中、白字黑邊
- **上傳 SRT**：`POST /v1/files` 接受 `.srt`，可供 burn 引用
- **部署**：Worker 使用 `Dockerfile.worker`（含 FunASR／PyTorch）；映像內建台北黑體。需重建映像

### v2.0.0

- **HTTP API**：上傳、合併、取幀非同步 job；Docker Compose 部署；可切換 storage 後端
- **URL 匯入**：`POST /v1/jobs/import-url`，server 代為下載並回 `file_id`
- **保留策略（Breaking）**：預設改為永久保留（`FILE_TTL_HOURS=0`、`RESULT_TTL_HOURS=0`、`AUTO_CLEANUP_ENABLED=false`）；恢復舊 24h/72h 自動清理需明確設定 env
- **手動刪除**：`DELETE /v1/files/{file_id}`

## License

MIT
