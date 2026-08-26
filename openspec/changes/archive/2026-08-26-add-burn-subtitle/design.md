## Context

MergeVideo 已有 `generate-subtitle`：Worker 以 FunASR `fa-zh` 對齊，job `done` 給 `.srt` 的 `download_url`。SRT 存在 `results/{job_id}/`，**不是** file registry 裡的 `file_id`。`POST /v1/files` 只接受影片副檔名。因此呼叫端無法把產出的字幕接到下一支 job，也無法上傳改過的 SRT。

燒字需要 ffmpeg `subtitles`（libass）、CJK 字型、以及一定重編碼。Worker 映像目前有 ffmpeg、無專案字型。使用者指定預設字型為台北黑體 Regular（`TaipeiSansTCBeta-Regular.ttf`，SIL OFL 1.1，內部家族名 `Taipei Sans TC Beta`）。

## Goals / Non-Goals

**Goals:**

- 兩段式：先 SRT（既有 generate-subtitle），再 `POST /v1/jobs/burn-subtitle` 燒進影片
- generate-subtitle 完成時註冊 SRT 為 `file_id`，並保留 `download_url`
- 上傳接受 `.srt`
- 可選 `font_size`（預設 48）、`margin_bottom`（預設 6）、`margin_unit`（`px` | `percent`，預設 `percent`）
- 底部水平置中、白字黑描邊、內建台北黑體；不開放呼叫端換字

**Non-Goals:**

- 一條龍「稿 → 燒字」單一 job
- 自訂字型上傳、左／右對齊、改字色、軟字幕軌道
- 自動折行策略以外的排版引擎
- 改變 merge copy/encode 邏輯

## Decisions

### 1. SRT 成為一等檔案，而不是只靠 download_url

**決定：** `generate_subtitle` 成功後，以 import-url 相同模式寫入 `FileRecord`：`uploads/{file_id}/original.srt`、`content_type: application/x-subrip`、`owner_key` 與 job 相同、TTL 走 `FILE_TTL_HOURS`。`result_json` 含 `file_id` 與 `storage_key`。`GET /v1/jobs/{id}` 對此類型同時回 `file_id` 與既有 `download_url`（presign 同一 `storage_key`）。

**理由：** burn 只認 `file_id`。若 SRT 留在 `results/{job_id}/`，會跟 `RESULT_TTL` 綁死，且與「輸入素材」語意不符。雙寫一份到 results、一份到 uploads 浪費儲存。

**替代方案：** burn 吃 `subtitle_job_id` — 與改過的 SRT 上傳對不上。拒絕。只給 download_url 再上傳 — 多一輪、現況上傳還不收 srt。拒絕作為唯一路徑。

### 2. 上傳放行 `.srt`，不污染 CLI 影片掃描

**決定：** `POST /v1/files` 在既有 `VIDEO_EXTENSIONS` 之外接受 `.srt`。SRT 不上 ffprobe、不要求影像軌。`scanner.VIDEO_EXTENSIONS` **不**加入 `.srt`，避免 CLI merge 把字幕當影片。

**驗證：** 副檔名 `.srt`、非空、大小仍受 `MAX_FILE_SIZE_MB` 約束。格式是否像 SRT 由 burn worker 再驗（上傳只做副檔名，與影片上傳「先收副檔名、probe 失敗不擋」一致）。

### 3. burn job 契約

**決定：** `POST /v1/jobs/burn-subtitle`

| 欄位 | 必填 | 預設 | 說明 |
|------|------|------|------|
| `file_id` | 是 | — | 影片 |
| `srt_file_id` | 是 | — | SRT |
| `font_size` | 否 | 48 | 正整數，範圍 1–512 |
| `margin_bottom` | 否 | 6 | 離底邊；單位見下一列 |
| `margin_unit` | 否 | `percent` | `px` 或 `percent` |

對齊、字型、顏色不進 body。可選 `crf` **不**開放（沿用 merge encode 的 CRF 18）。

建立時 pin **兩個** file。`type=burn_subtitle`。`input_json` 含 `file_ids: [video, srt]` 以及樣式欄位（已套預設後寫入，worker 不必再猜預設）。

API 400：

- 影片 `file_id` 不是影片副檔名 → `WRONG_FILE_TYPE`
- `srt_file_id` 不是 `.srt` → `WRONG_FILE_TYPE`
- `margin_unit` 非法，或 `percent` 時 `margin_bottom` 不在 0–100，或 `px` 時 `< 0` → `INVALID_MARGIN`
- `font_size` 超出 1–512 → `INVALID_FONT_SIZE`

所有權／過期沿用既有 403／404。

### 4. ffmpeg 燒字方式

**決定：** Worker 用 **Pillow** 依 cue 畫透明 PNG（台北黑體 TTF、白字黑邊、底部水平置中），再以 ffmpeg `overlay` 依時間疊上。不依賴 libass / `subtitles` / `drawtext`（Homebrew ffmpeg 8 常未編譯這些 filter）。

```
ffmpeg -y -i video.mp4 -i cue0.png \
  -filter_complex "[0:v][1:v]overlay=0:0:enable='between(t,start,end)'[vout]" \
  -map "[vout]" -c:v libx264 -crf 18 -c:a copy \
  burned.mp4
```

- 水平置中、垂直離底 `margin_v` 像素（percent 時 `round(height * margin_bottom / 100)`）
- 白字、`stroke_width=2` 黑邊
- 音訊 `-map 0:a -c:a copy`；無音訊軌則 `-an`
- 字型先複製到 job 暫存目錄再給 Pillow 載入

**理由：** 本機 Homebrew ffmpeg 8 無 `subtitles`、亦無 `drawtext`；`overlay` 為核心 filter。Pillow 畫 CJK 只需 TTF，與映像無關。

**替代方案：** `subtitles` / `drawtext` — 本機測試 Filter not found。拒絕作為唯一路徑。

無法解析 SRT（沒有任何 cue）→ job `INVALID_SRT`。ffmpeg 失敗且 stderr 不像缺字型 → `FFMPEG_ERROR`。字型檔不存在 → `FONT_UNAVAILABLE`（建立 job 不必檢查；worker 開跑時檢查）。

### 5. 字型進 repo 與映像

**決定：** 將使用者提供的 `TaipeiSansTCBeta-Regular.ttf` 複製到 `assets/fonts/TaipeiSansTCBeta-Regular.ttf`，並放 SIL OFL 1.1 授權全文於 `assets/fonts/OFL.txt`。Worker（及本機跑 worker）以相對專案根目錄的該路徑載入。`Dockerfile` / `Dockerfile.worker` 已 `COPY . .`，不必另 COPY；不需 `apt install fonts-noto-cjk`。

設定可選 `SUBTITLE_FONT_PATH`（預設 `assets/fonts/TaipeiSansTCBeta-Regular.ttf`），方便測試用小字型替換。`fontsdir` 為該檔所在目錄；`FontName` 固定 `Taipei Sans TC Beta`。

**理由：** OFL 允許捆綁與嵌入；家族名已用 `fc-query` 確認。約 20 MB，可接受進 git。

### 6. 進度

| 階段 | progress |
|------|----------|
| queued | 0 |
| 下載影片與 SRT | 10 |
| probe + 算 MarginV | 15 |
| ffmpeg 燒字 | 15–95（`run_ffmpeg_with_progress`，總時長 = 影片 duration） |
| 上傳 | 98 |
| done | 100 |

### 7. 測試

- API：預設值寫入 input_json、非法 margin／font、WRONG_FILE_TYPE、401、他人檔、202
- 上傳：`.srt` 201；`.txt` 仍 400
- generate-subtitle：mock 對齊後 result 含 `file_id`，且 registry 有該檔
- Worker burn：用極短色條影片 + 手寫 SRT，有 ffmpeg 才跑；斷言輸出有影像軌（像素級 OCR 不做）。缺字型 → `FONT_UNAVAILABLE`。壞 SRT → `INVALID_SRT`
- OpenAPI 含 `/v1/jobs/burn-subtitle`

## Risks / Trade-offs

| 風險 | 緩解 |
|------|------|
| 燒字必重編碼，比對齊慢、佔 CPU | 單 Worker 排隊；progress 跟 duration；文件說明 |
| 直式／橫式同一 `percent=6` 觀感不同 | 這正是選 percent 當預設的原因；要對齊固定版面改 `px` |
| libass FontSize 不是精確 CSS px | 接受 ASS 語意；文件寫「ASS FontSize」 |
| TTF 20 MB 讓 clone 變胖 | 可接受；不進 API 執行路徑 |
| SRT 過長單行超出畫面 | v1 交給 libass 預設換行；不另做智能斷行 |
| generate-subtitle 結果形狀多了 `file_id` | 加欄位、不刪 `download_url`，非 breaking |
| `results/` 改存 `uploads/` 後舊 job 不受影響 | 只影響新完成的 generate-subtitle |
| Debian ffmpeg 未編 libass | apt `ffmpeg` 依賴 `libass9`；CI／映像沿用該套件 |

## Migration Plan

1. 字型與 OFL 進 repo
2. 上傳與 generate-subtitle 結果先上線，既有客戶端可忽略新 `file_id`
3. 再啟用 burn-subtitle
4. 無 DB schema 變更
5. 回滾：停 burn endpoint／還原映像；已註冊的 SRT file 與其他 upload 相同保留策略

## Open Questions

（無。預設值、單位、字型、兩段式已在 explore 鎖定。）
