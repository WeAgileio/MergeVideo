## Why

ComfyUI 數字人工作流會產出多段獨立影片（如 `1.mp4`、`2.mp4`），目前缺乏一個簡單可靠的方式將它們合併成一支成品。片段可能格式、解析度、幀率、音訊各異，手動用剪輯軟體處理耗時且容易出錯。

## What Changes

- 新增 Python CLI 工具，從指定資料夾讀取純數字檔名的影片並依自然排序合併
- 自動分析各片段的解析度、編碼、幀率、音訊，判定是否可使用快速 copy 模式
- 互動式選擇合併模式（Copy / Encode），並支援 `--mode auto|copy|encode` 非互動旗標
- Encode 模式：以像素面積最大的片段為輸出解析度，較小段等比縮放並加黑邊置中；每段保留音訊，無聲段補靜音
- 預設輸出至 input 同層的 `output/` 資料夾，檔名為 `mergedYYYYMMDDHHmmss.mp4`
- 嚴格輸入驗證：非數字檔名、僅一段影片、無影片時直接報錯

## Capabilities

### New Capabilities

- `video-folder-merge`: 從資料夾掃描、驗證、分析並合併多段影片為單一 MP4 的 CLI 能力

### Modified Capabilities

（無既有 spec）

## Impact

- 新增 `mergevideo` CLI 指令及相關模組
- 依賴系統已安裝的 FFmpeg / ffprobe（不納入 Python 套件）
- 可選 Python 依賴：`natsort`（自然排序）或標準庫實作
- 與 ComfyUI 工作流銜接：ComfyUI 輸出重新命名為數字序後，執行本工具合併（rename 自動化留待後續 change）
