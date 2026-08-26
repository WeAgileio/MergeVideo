## 1. 設定與映像

- [x] 1.1 新增 `requirements-worker.txt`（含 `-r requirements-api.txt` 與 `funasr`、`torch`、`torchaudio`、`soundfile`）
- [x] 1.2 新增 `Dockerfile.worker`；`docker-compose.yml` 的 worker 改用該 Dockerfile，並掛模型快取 volume
- [x] 1.3 擴充 `api/config.py`：`FUNASR_DEVICE`、`FUNASR_CACHE_DIR`、`FUNASR_MAX_SCRIPT_CHARS`
- [x] 1.4 更新 `.env.example`（含註解：Worker 需另建映像、首次下載模型需網路）

## 2. SRT 組裝（不依賴 FunASR）

- [x] 2.1 新增 `api/services/subtitle.py`：標點分句、timestamp → cue、毫秒轉 SRT 時間碼
- [x] 2.2 實作 UTF-8 無 BOM 標準 SRT 輸出（無 Speaker 前綴）
- [x] 2.3 單元測試：兩句、無標點單句、時間碼、空 timestamp → ALIGN 語意（函式層）

## 3. API endpoint

- [x] 3.1 實作 `POST /v1/jobs/generate-subtitle`（驗證 script、pin file、enqueue、202）
- [x] 3.2 新增錯誤碼：`SCRIPT_REQUIRED`、`SCRIPT_EMPTY`、`SCRIPT_TOO_LONG`、`NO_AUDIO_STREAM`、`ALIGN_FAILED`、`FUNASR_UNAVAILABLE`（寫入 `api/errors.py` 與 `_API_DESCRIPTION`）
- [x] 3.3 更新 Swagger：`summary` / `description` / `responses`，以及 `GET /v1/jobs/{id}` 的 generate_subtitle done 範例

## 4. Worker 對齊

- [x] 4.1 新增 lazy singleton 載入 `AutoModel("fa-zh")`；失敗拋出可對應 `FUNASR_UNAVAILABLE` 的錯誤（API 模組不 import funasr）
- [x] 4.2 在 `runner.py` 新增 `_run_generate_subtitle`：下載 → ffmpeg 16k mono wav → 寫 text.txt → generate → 組 SRT → 上傳
- [x] 4.3 無音訊軌 → `NO_AUDIO_STREAM`；空 timestamp → `ALIGN_FAILED`；勿把上述誤標為 `FFMPEG_ERROR`
- [x] 4.4 接上既有 progress 節流（10 / 20 / 50 / 90 / 100）

## 5. 測試與文件

- [x] 5.1 API 測試：缺稿、空白、過長、401、他人 file、202 契約
- [x] 5.2 Worker 測試：mock `generate` 成功產出 SRT；mock 無音訊／空 timestamp 錯誤碼
- [x] 5.3 更新 `README.md` 與 `README.en.md`（endpoint 表、curl、Worker 映像與記憶體說明）
- [x] 5.4 以 `create_app().openapi()` 確認 path 含 `/v1/jobs/generate-subtitle`
