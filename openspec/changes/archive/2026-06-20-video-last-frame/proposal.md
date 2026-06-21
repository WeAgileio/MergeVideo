## Why

ComfyUI 數字人工作流在產出各段影片後，常需要該段的最後一幀作為下一段的參考圖或銜接用。目前缺乏一個簡單指令能從單支影片擷取最後一幀並以固定命名規則輸出 PNG。

## What Changes

- 新增 `VideoLastFrame` CLI，從單一影片檔擷取最後一幀
- 輸出檔名為 `{stem}_LastFrame.png`（如 `1.mp4` → `1_LastFrame.png`）
- 輸出至影片所在目錄下的 `output/` 子資料夾（自動建立）
- 預設 PNG 格式；輸入為單檔，不支援資料夾批次
- 複用既有 `ffmpeg_utils.py` 與 `probe.py`

## Capabilities

### New Capabilities

- `video-last-frame`: 從單支影片擷取最後一幀並輸出 PNG 的 CLI 能力

### Modified Capabilities

（無既有 spec 變更）

## Impact

- 新增 `VideoLastFrame` 可執行腳本及 `extract_frame.py`（或等價模組）
- 更新 `README.md` 說明新指令
- 依賴系統 FFmpeg / ffprobe（與 mergevideo 相同）
