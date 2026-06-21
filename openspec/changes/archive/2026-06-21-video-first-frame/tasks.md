## 1. 核心模組

- [x] 1.1 重構 `extract_frame.py`：參數化輸出路徑 suffix（LastFrame / FirstFrame）
- [x] 1.2 實作 `extract_first_frame()`：ffmpeg `-ss 0 -frames:v 1`
- [x] 1.3 輸出至 `{video_dir}/output/{stem}_FirstFrame.png`

## 2. CLI 入口

- [x] 2.1 建立 `VideoFirstFrame` 可執行腳本（shebang + argparse）
- [x] 2.2 整合錯誤處理（與 VideoLastFrame 一致）
- [x] 2.3 設定 chmod +x

## 3. 文件與驗證

- [x] 3.1 更新 `README.md` 加入 VideoFirstFrame 用法
- [x] 3.2 手動測試：正常影片擷取第一幀
- [x] 3.3 手動測試：錯誤情境（資料夾輸入、不存在檔案）
