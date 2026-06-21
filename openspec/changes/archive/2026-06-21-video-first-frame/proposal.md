## Why

MergeVideo 已有 `VideoLastFrame` 擷取最後一幀，但 ComfyUI 工作流有時也需要第一幀作為參考或預覽。缺少對應的對稱工具，使用者需手動用 FFmpeg 或剪輯軟體處理。

## What Changes

- 新增 `VideoFirstFrame` CLI，從單一影片檔擷取第一幀
- 輸出檔名為 `{stem}_FirstFrame.png`（如 `1.mp4` → `1_FirstFrame.png`）
- 輸出至影片所在目錄下的 `output/` 子資料夾（與 VideoLastFrame 相同）
- 預設 PNG 格式；輸入為單檔，不支援資料夾批次
- 擴充 `extract_frame.py` 加入 `extract_first_frame()`，複用既有驗證與路徑邏輯

## Capabilities

### New Capabilities

- `video-first-frame`: 從單支影片擷取第一幀並輸出 PNG 的 CLI 能力

### Modified Capabilities

（無既有 spec 變更）

## Impact

- 新增 `VideoFirstFrame` 可執行腳本
- 擴充 `extract_frame.py`
- 更新 `README.md`
- 依賴系統 FFmpeg / ffprobe（與現有工具相同）
