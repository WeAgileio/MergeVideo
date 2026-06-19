## Context

專案目前為空，僅有 OpenSpec 設定。使用者透過 ComfyUI 產出多段數字人影片，需合併為一支成品。片段可能格式、解析度、幀率、音訊各異。系統已安裝 FFmpeg 8.0.1。

## Goals / Non-Goals

**Goals:**

- 提供 `mergevideo` CLI，一鍵合併指定資料夾內的數字序影片
- 自動分析片段相容性，互動式或旗標選擇 Copy / Encode 模式
- Encode 模式以最大像素面積片段為輸出解析度，統一音訊規格
- 嚴格輸入驗證與明確錯誤訊息
- 預設輸出至 input 同層 `output/mergedYYYYMMDDHHmmss.mp4`

**Non-Goals:**

- ComfyUI 輸出檔自動重新命名
- GUI、watch 資料夾、遠端處理
- 影片裁切、轉場特效、字幕

## Decisions

### 1. 語言與結構：Python 3 單一入口 + 模組拆分

**選擇**：`mergevideo` 為 CLI 入口（可執行腳本），邏輯拆分為 `scanner.py`、`probe.py`、`compat.py`、`merger.py`、`report.py`。

**理由**：ffprobe JSON 解析、argparse、互動 prompt 在 Python 中簡潔；模組拆分便於測試。

**替代方案**：Shell 腳本 —  rejected，複雜 filter_complex 字串難維護。

### 2. 核心引擎：FFmpeg / ffprobe

**選擇**：透過 `subprocess` 呼叫系統 ffmpeg/ffprobe，啟動時檢查是否存在。

**理由**：業界標準，使用者已安裝。

### 3. 排序：自然排序（natsort 或自實作）

**選擇**：優先使用標準庫實作自然排序（避免額外依賴）；若邏輯複雜則用 `natsort`。

**理由**：`1.mp4, 2.mp4, 10.mp4` 需正確排序。

### 4. 檔名驗證：純數字 stem

**選擇**：檔名 stem 必須符合 `^\d+$`（如 `1.mp4`、`02.mov`）。資料夾內若有任何非數字 stem 的影片副檔名檔案，整體報錯並列出。

**理由**：使用者明確要求 fail-fast，避免 silently 跳過造成順序混淆。

### 5. 輸出解析度：最大像素面積

**選擇**：計算每段 `width × height`，取最大者；若多段面積相同，取自然排序最前者。

**Encode 處理**：較小段 `scale` 等比縮放至能完整放入，`pad` 黑邊置中（不裁切、不拉伸）。

### 6. 音訊：每段保留，統一 48000Hz stereo AAC

**選擇**：有音訊段 resample + stereo；無音訊段以 `anullsrc` 產生等長靜音。

**Copy 條件**：全部有音訊且 codec、sample rate、channels 一致；或全部無音訊。

### 7. Copy 相容性判定

全部片段須一致：

- 寬、高
- video codec、pix_fmt
- fps（rational 值相同）
- 音訊狀態（全有或全無；有則 codec/sample rate/channels 一致）

任一不符 → Copy 不可用。

### 8. 合併實作

**Copy 模式**：產生 concat demuxer 列表檔，`ffmpeg -f concat -safe 0 -i list.txt -c copy`。

**Encode 模式**：單一 `filter_complex`：
- 每路 `[i:v] scale+pad [vi]`
- 每路 `[i:a]` 或 `anullsrc` → `aresample` → `[ai]`
- `[v0][a0][v1][a1]... concat=n=N:v=1:a=1`
- 輸出 `-c:v libx264 -crf 18 -c:a aac -b:a 192k`

### 9. CLI 介面

```
mergevideo <input_folder> [-o OUTPUT] [--mode auto|copy|encode] [--crf N] [--dry-run]
```

- 預設互動選擇模式
- `--mode auto`：相容則 copy，否則 encode
- `--mode copy`：不相容則 exit 1
- `--dry-run`：只分析報告，不合併
- `-o` 可覆寫輸出路徑；未指定則 `<input_parent>/output/merged{timestamp}.mp4`

### 10. 錯誤處理

| 情況 | 行為 |
|------|------|
| 輸入資料夾不存在 | exit 1 |
| 無影片檔 | exit 1 |
| 僅 1 段影片 | exit 1 |
| 非數字檔名 | exit 1，列出檔名 |
| ffmpeg/ffprobe 缺失 | exit 1 |
| Copy 不相容但選 copy | exit 1 |

## Risks / Trade-offs

- **[Risk] Encode 大量片段可能耗盡記憶體** → Mitigation：filter_complex 輸入路數過多（如 >20）時改為分段 concat 或警告；第一版先假設 <20 段
- **[Risk] 混合 fps 導致音畫不同步** → Mitigation：Encode 模式統一 `-r` 為最大段 fps 或第一段的 fps（取 probe 結果眾數）
- **[Risk] 非影片檔（如 .txt）在資料夾內** → Mitigation：只掃描已知影片副檔名；非影片檔忽略，但若為影片副檔名且非數字檔名則報錯
- **[Trade-off] Copy 條件嚴格** → 大多數 ComfyUI 混合格式場景會走 Encode，速度較慢但正確

## Migration Plan

新專案，無遷移。部署步驟：

1. 確保 ffmpeg/ffprobe 在 PATH
2. `mergevideo ./clips` 執行合併

## Open Questions

（無 — explore 階段已全部定案）
