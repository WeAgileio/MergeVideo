## Context

MergeVideo 專案已有 `mergevideo.py` 合併多段影片。使用者需要在 ComfyUI 產出各段後，擷取每段最後一幀作為參考圖。現有 `ffmpeg_utils.py`、`probe.py` 可複用。

## Goals / Non-Goals

**Goals:**

- 提供 `VideoLastFrame` CLI，一鍵擷取單支影片最後一幀
- 輸出 `{video_dir}/output/{stem}_LastFrame.png`
- 使用 FFmpeg 從尾部 seek 取幀，穩定可靠
- 明確錯誤處理（檔案不存在、無 video stream、輸入為資料夾）

**Non-Goals:**

- 資料夾批次處理
- 自訂輸出格式（JPG/WebP）— 第一版固定 PNG
- 擷取任意時間點的幀
- `-o` 自訂輸出路徑（可後續擴充）

## Decisions

### 1. CLI 入口：`VideoLastFrame`

**選擇**：獨立可執行腳本 `VideoLastFrame`，與 `mergevideo.py` 平行。

**理由**：使用者指定指令名；單一職責、用法清晰。

### 2. 取幀方式：`-sseof` 從尾部 seek

**選擇**：

```bash
ffmpeg -sseof -0.1 -i input.mp4 -frames:v 1 -y output.png
```

**理由**：簡單可靠，不需計算總幀數；對大多數編碼格式有效。

**Fallback**：若失敗，以 ffprobe duration 計算 `-ss {duration - epsilon}` 重試。

### 3. 輸出路徑

**選擇**：`{video.parent}/output/{stem}_LastFrame.png`

範例：`clips/1.mp4` → `clips/output/1_LastFrame.png`

**理由**：使用者指定「影片同級下的 output 資料夾」；與 mergevideo 的全域 output 不同，每段影片目錄各自有 output。

### 4. 輸入驗證

| 情況 | 行為 |
|------|------|
| 路徑不存在 | exit 1 |
| 路徑為資料夾 | exit 1（本次只做單檔） |
| 無 video stream | exit 1 |
| ffmpeg/ffprobe 缺失 | exit 1 |

### 5. 模組結構

```
VideoLastFrame          # CLI 入口
extract_frame.py        # extract_last_frame(video_path) -> Path
ffmpeg_utils.py         # 共用
probe.py                # 共用（確認 video stream）
```

### 6. 覆寫行為

輸出檔已存在時使用 ffmpeg `-y` 覆寫。

## Risks / Trade-offs

- **[Risk] VFR 或特殊編碼 `-sseof` 不準** → Mitigation：duration fallback
- **[Risk] 極短影片（<0.1s）** → Mitigation：調整 seek 為 `-sseof -0.04` 或 `-ss 0`
- **[Trade-off] 固定 PNG** → 檔案較大但無損，適合 ComfyUI 參考圖

## Migration Plan

新功能，無遷移。使用方式：

```bash
VideoLastFrame ./clips/1.mp4
```

## Open Questions

（無 — explore 階段已全部定案）
