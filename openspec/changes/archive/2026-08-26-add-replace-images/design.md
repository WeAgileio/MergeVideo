## Context

MergeVideo 已能合併、取幀、有稿字幕、燒字幕。數字人口播需要在某幾秒把畫面整框換成靜態圖（資訊圖、截圖），音訊與片長不變。`POST /v1/files` 目前只收影片與 `.srt`。burn / merge 的 `done` 只有 `download_url`，不能直接當下一支 job 的輸入；generate-subtitle 才會把結果註冊為 `file_id`。

燒字幕已用 Pillow + ffmpeg `overlay` + `enable='between(t,start,end)'`、音訊 copy。換圖可走同一條路。

## Goals / Non-Goals

**Goals:**

- `POST /v1/jobs/replace-images`：一支片一次換多段，每段整框只剩該圖
- 圖先上傳再以 `file_id` 引用
- contain（等比縮進片幅、黑邊）
- 音訊 copy、輸出時長等於輸入
- `done` 給 `file_id` + `download_url`，呼叫端自行串 burn-subtitle 或其他 job
- 上傳接受 png / jpeg / webp

**Non-Goals:**

- 畫中畫、cover、stretch、呼叫端選 fit
- 系統綁定與燒字幕的先後
- 改音訊、改片長、軟字幕
- GIF／動畫圖

## Decisions

### 1. 獨立 job，不與燒字幕耦合

**決定：** `POST /v1/jobs/replace-images`，`type=replace_images`。與 `burn-subtitle` 誰先誰後由呼叫端排。

**理由：** 先換圖再燒字＝圖上也有字幕；先燒再換圖＝那幾秒連字一起蓋掉。兩種都合理。

**替代方案：** 單一 job 同時燒字＋換圖 — 範圍膨脹。拒絕。

### 2. 輸入契約

**決定：**

| 欄位 | 必填 | 說明 |
|------|------|------|
| `file_id` | 是 | 影片 |
| `replacements` | 是 | 1–10 段，陣列 |
| `replacements[].image_file_id` | 是 | 已上傳的圖 |
| `replacements[].start` | 是 | 秒，`>= 0` |
| `replacements[].end` | 是 | 秒，`> start` |

`start` 含、`end` 含（ffmpeg `between`）。兩段相交（`startA < endB && startB < endA`）拒絕；`end` 剛好等於下一段 `start` 允許。同一 `image_file_id` 可用在多段。

API 400：

- `replacements` 空或缺 → `EMPTY_REPLACEMENTS`
- 超過 10 段 → `TOO_MANY_REPLACEMENTS`
- `file_id` 非影片或 `image_file_id` 非圖 → `WRONG_FILE_TYPE`
- `start < 0` 或 `end <= start` → `INVALID_RANGE`
- 時段重疊 → `OVERLAPPING_RANGES`

若上傳時 ffprobe 有 `duration_sec`，且 `end` 超過片長 → `INVALID_RANGE`。Worker 一律再 probe；超出片長同樣 `INVALID_RANGE`。

建立時 pin 影片與所有引用到的圖。`input_json` 含 `file_ids: [video, ...unique images]` 與 `replacements`。

### 3. 上傳靜態圖，不污染 CLI 掃描

**決定：** `POST /v1/files` 在現有副檔名外接受 `.png` `.jpg` `.jpeg` `.webp`。不上 ffprobe。`content_type`：`image/png`、`image/jpeg`、`image/webp`。空檔 `EMPTY_FILE`；大小仍走 `MAX_FILE_SIZE_MB`。`scanner.VIDEO_EXTENSIONS` **不加** 圖副檔名。

**理由：** 與 SRT 上傳同一模式。CLI merge 不該把圖當影片。

### 4. contain 用 Pillow 畫滿框，再 overlay

**決定：** 對每段用 Pillow 把圖 contain 到影片寬高的不透明黑底 RGB 畫布（透明 PNG 先墊黑），存成 PNG，再 ffmpeg overlay：

```
ffmpeg -y -i video.mp4 -i seg0.png -i seg1.png ...
  -filter_complex "
    [0:v][1:v]overlay=0:0:enable='between(t,s0,e0)'[v1];
    [v1][2:v]overlay=0:0:enable='between(t,s1,e1)'[vout]
  "
  -map "[vout]" -c:v libx264 -crf 18 -pix_fmt yuv420p
  -map 0:a -c:a copy
  out.mp4
```

無音訊軌則 `-an`。輸出檔名 `{stem}_replaced.mp4`。

**理由：** 與 burn-subtitle 同一條已驗證的 overlay 路徑；contain 在 Pillow 算，不依賴 `scale+pad` filter。黑底符合「整框只剩那張圖」。

**替代方案：** ffmpeg `scale=force_original_aspect_ratio=decrease,pad` — 可行，但本機／映像 filter 組合較碎。拒絕作為 v1 唯一路徑。

無法解圖 → job `INVALID_IMAGE`。ffmpeg 失敗 → `FFMPEG_ERROR`。

### 5. 成片註冊為 file_id

**決定：** 成功後寫 `FileRecord`：`uploads/{file_id}/original.mp4`、`content_type: video/mp4`、owner 與 job 相同、TTL 走 `FILE_TTL_HOURS`。`result_json` 含 `file_id`、`storage_key`、`filename`、`size_bytes`。`GET /v1/jobs/{id}` 同時回 `file_id` 與 `download_url`（presign 同一物件）。**不**另寫 `results/{job_id}/`。

**理由：** 與 generate-subtitle 相同，才能直接當 burn-subtitle 的 `file_id`。成片語意是下一支 job 的輸入素材。

**替代方案：** 只給 download_url（跟 burn 一樣）— 串接下一步要再上傳。與「呼叫端自己排」衝突。拒絕。

### 6. 進度

| 階段 | progress |
|------|----------|
| queued | 0 |
| 下載影片與圖 | 10 |
| Pillow contain | 15 |
| ffmpeg overlay | 15–95（跟影片 duration） |
| 上傳 registry | 98 |
| done | 100 |

## Risks / Trade-offs

| 風險 | 緩解 |
|------|------|
| 必重編碼畫面，CPU 與 burn 同級 | 單 Worker 排隊；progress 跟 duration |
| 黑邊在直式片＋橫圖很明顯 | 這是 contain 的預期；不提供 cover |
| 10 段上限 | 與 merge 檔數同級；不夠再加 env |
| 成片走 `FILE_TTL` 而非 `RESULT_TTL` | 與 generate-subtitle 一致；文件寫明 |
| overlay 未 loop 靜圖 | 與 burn 相同：Pillow 單幀 PNG + overlay 預設 repeat |

## Migration Plan

1. 上傳開放圖副檔名（既有客戶端可忽略）
2. 上線 `replace-images`；burn / merge 不變
3. 呼叫端若要「換圖→燒字」，用本 job 的 `result.file_id` 當 burn 的 `file_id`

無 breaking change。

## Open Questions

無。fit、多段、file_id 輸出、與燒字幕解耦已在探索中鎖定。
