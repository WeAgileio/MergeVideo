## 1. 核心模組

- [x] 1.1 建立 `extract_frame.py`：驗證輸入、計算輸出路徑、ffmpeg 取最後一幀
- [x] 1.2 實作 `-sseof` 取幀與 duration fallback
- [x] 1.3 實作 `{video_dir}/output/{stem}_LastFrame.png` 路徑邏輯與自動建立 output 目錄

## 2. CLI 入口

- [x] 2.1 建立 `VideoLastFrame` 可執行腳本（shebang + argparse）
- [x] 2.2 整合錯誤處理（檔案不存在、資料夾輸入、無 video stream）
- [x] 2.3 設定 chmod +x

## 3. 文件與驗證

- [x] 3.1 更新 `README.md` 加入 VideoLastFrame 用法
- [x] 3.2 手動測試：正常影片擷取最後一幀
- [x] 3.3 手動測試：錯誤情境（資料夾輸入、不存在檔案）
