## Context

MergeVideo 已有 `VideoLastFrame` 與 `extract_frame.py`（`extract_last_frame`）。使用者需要對稱的第一幀擷取能力，行為與命名規則一致，僅改為取第一幀。

## Goals / Non-Goals

**Goals:**

- 提供 `VideoFirstFrame` CLI，一鍵擷取單支影片第一幀
- 輸出 `{video_dir}/output/{stem}_FirstFrame.png`
- 複用 `extract_frame.py` 的驗證、輸出路徑邏輯
- 錯誤處理與 VideoLastFrame 一致

**Non-Goals:**

- 資料夾批次處理
- 自訂輸出格式或 `-o` 路徑
- 合併 VideoLastFrame / VideoFirstFrame 為單一指令

## Decisions

### 1. CLI 入口：`VideoFirstFrame`

**選擇**：獨立可執行腳本，與 `VideoLastFrame` 平行。

**理由**：命名對稱、用法一致、職責單一。

### 2. 取幀方式：從開頭擷取 1 幀

**選擇**：

```bash
ffmpeg -y -ss 0 -i input.mp4 -frames:v 1 output.png
```

**理由**：第一幀無需 seek 計算，比 last frame 更簡單可靠。

### 3. 輸出路徑與命名

**選擇**：`{video.parent}/output/{stem}_FirstFrame.png`

範例：`clips/1.mp4` → `clips/output/1_FirstFrame.png`

### 4. 模組結構

**選擇**：擴充 `extract_frame.py`：

- 抽出共用的 `resolve_first_frame_output_path()` 或參數化 `resolve_output_path(suffix)`
- 新增 `extract_first_frame(video_path) -> Path`
- `VideoFirstFrame` CLI 呼叫 `extract_first_frame`

**替代方案**：複製整份 extract_frame.py — rejected，維護成本高。

### 5. 輸入驗證

與 VideoLastFrame 相同：單檔、存在、有 video stream、ffmpeg/ffprobe 可用。

### 6. 覆寫行為

輸出檔已存在時使用 ffmpeg `-y` 覆寫。

## Risks / Trade-offs

- **[Risk] 部分影片第一幀為黑場** → 屬影片本身特性，不在 scope 內處理
- **[Trade-off] 兩個獨立 CLI** → 與 LastFrame 對稱，使用者認知成本低

## Migration Plan

新功能，無遷移：

```bash
VideoFirstFrame ./clips/1.mp4
```

## Open Questions

（無）
