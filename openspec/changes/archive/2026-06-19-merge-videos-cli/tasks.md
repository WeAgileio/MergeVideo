## 1. 專案骨架

- [x] 1.1 建立專案目錄結構（`mergevideo`、`scanner.py`、`probe.py`、`compat.py`、`merger.py`、`report.py`）
- [x] 1.2 實作 ffmpeg/ffprobe 存在性檢查與 subprocess 封裝
- [x] 1.3 實作 CLI argparse（input_folder、-o、--mode、--crf、--dry-run）
- [x] 1.4 設定 `mergevideo` 為可執行腳本（shebang + chmod +x），可直接在命令列呼叫

## 2. 掃描與驗證

- [x] 2.1 實作 `scanner.py`：掃描影片副檔名、驗證純數字 stem（`^\d+$`）
- [x] 2.2 實作自然排序（1, 2, 10）
- [x] 2.3 實作錯誤處理：非數字檔名、僅 1 段、無影片、資料夾不存在

## 3. 分析與報告

- [x] 3.1 實作 `probe.py`：ffprobe JSON 解析（解析度、fps、codec、pix_fmt、音訊）
- [x] 3.2 實作最大像素面積輸出解析度選取（同面積取排序前者）
- [x] 3.3 實作 `compat.py`：Copy 相容性判定
- [x] 3.4 實作 `report.py`：表格化分析報告與相容性摘要

## 4. 合併引擎

- [x] 4.1 實作 Copy 模式：concat demuxer 列表檔 + `-c copy`
- [x] 4.2 實作 Encode 模式：filter_complex（scale+pad、anullsrc 補靜音、concat）
- [x] 4.3 實作預設輸出路徑：`<input_parent>/output/merged{timestamp}.mp4`，自動建立 output 目錄

## 5. 互動與模式選擇

- [x] 5.1 實作互動 prompt（C/E/Q），Copy 不可用時禁用 C
- [x] 5.2 實作 `--mode auto|copy|encode` 非互動邏輯
- [x] 5.3 實作 `--dry-run`：只分析不合併

## 6. 整合與驗證

- [x] 6.1 整合 `mergevideo` 主流程（掃描 → 分析 → 選模式 → 合併）
- [x] 6.2 手動測試：同規格片段 Copy 合併
- [x] 6.3 手動測試：不同解析度/音訊 Encode 合併
- [x] 6.4 手動測試：錯誤情境（非數字檔名、單段、--mode copy 不相容）
