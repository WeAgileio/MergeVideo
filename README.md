# MergeVideo

將資料夾內多段數字序影片（`1.mp4`、`2.mp4`…）合併為一支 MP4。適用於 ComfyUI 數字人工作流等場景，可自動處理不同解析度、格式與音訊，並在合併前分析是否可使用快速 Copy 模式。

## 功能

- 依檔名自然排序（`1 → 2 → 10`）
- 自動分析解析度、幀率、編碼、音訊
- 互動選擇 **Copy**（不重新編碼）或 **Encode**（統一規格後合併）
- Encode 模式以**最大像素面積**片段為輸出解析度，較小段等比縮放並加黑邊
- 每段保留音訊，無聲段自動補靜音
- 預設輸出至 input 同層的 `output/mergedYYYYMMDDHHmmss.mp4`

## 環境需求

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/) / ffprobe（需在 PATH 中）

```bash
# macOS (Homebrew)
brew install ffmpeg

# 確認安裝
ffmpeg -version
ffprobe -version
```

## 快速開始

```bash
# 克隆專案
git clone https://github.com/WeAgileio/MergeVideo.git
cd MergeVideo

# 互動模式（分析後選擇 Copy / Encode）
python3 mergevideo.py ./clips

# 自動判斷模式
python3 mergevideo.py ./clips --mode auto

# 只分析、不合併
python3 mergevideo.py ./clips --dry-run
```

也可加上執行權限後直接呼叫：

```bash
chmod +x mergevideo.py
./mergevideo.py ./clips
```

## 輸入規則

將待合併影片放入同一資料夾，檔名必須為**純數字**：

```
clips/
├── 1.mp4
├── 2.mp4
└── 10.mp4
```

| 規則 | 說明 |
|------|------|
| 檔名格式 | `1.mp4`、`02.mov` 等（stem 須為 `\d+`） |
| 非數字檔名 | 直接報錯（如 `intro.mp4`） |
| 最少數量 | 至少 2 段影片 |
| 支援格式 | `.mp4`、`.mov`、`.webm`、`.mkv`、`.avi`、`.m4v` |

## 輸出規則

未指定 `-o` 時，輸出至 input 資料夾**同層**的 `output/`：

```
project/
├── clips/          ← 輸入
│   ├── 1.mp4
│   └── 2.mp4
└── output/         ← 自動建立
    └── merged20260619120930.mp4
```

## 命令列參數

```
mergevideo.py <input_folder> [選項]

選項:
  -o, --output PATH     自訂輸出檔案路徑
  --mode {auto,copy,encode}
                        auto=相容則 copy，否則 encode
                        copy=串接不編碼（不相容則報錯）
                        encode=重新編碼
  --crf N               Encode 品質，預設 18（越小越好）
  --dry-run             只分析報告，不合併
```

### 範例

```bash
# 互動選擇
python3 mergevideo.py ./clips

# 強制重新編碼
python3 mergevideo.py ./clips --mode encode

# 片段規格一致時快速合併
python3 mergevideo.py ./clips --mode copy

# 自訂輸出路徑
python3 mergevideo.py ./clips -o ~/Desktop/final.mp4
```

## 合併模式

### Copy 模式

所有片段解析度、編碼、幀率、音訊格式完全一致時可用。直接串接，速度快、無畫質損失。

### Encode 模式

片段規格不一致時使用。統一輸出為 H.264 + AAC（48000 Hz stereo），解析度跟最大片段走，較小段加黑邊置中。

執行時會顯示分析報告：

```
掃描資料夾: ./clips
找到 3 個影片（自然排序）

 #  檔名      解析度      FPS  編碼    音訊
────────────────────────────────────────────
 1  1.mp4    1920×1080   30   h264    aac
 2  2.mp4    1280×720    30   h264    無

Copy 模式: 不可用
Encode 模式: 可用

請選擇 [E]ncode / [Q]uit:
```

## ComfyUI 工作流

1. ComfyUI 產出多段影片
2. 重新命名為 `1.mp4`、`2.mp4`、`3.mp4` …
3. 執行合併：

```bash
python3 mergevideo.py /path/to/comfyui/output --mode auto
```

## 專案結構

```
MergeVideo/
├── mergevideo.py      # CLI 入口
├── scanner.py         # 掃描與檔名驗證
├── probe.py           # ffprobe 解析
├── compat.py          # Copy 相容性判定
├── report.py          # 分析報告
├── merger.py          # 合併引擎
└── ffmpeg_utils.py    # FFmpeg 工具封裝
```

## 常見錯誤

| 訊息 | 原因 |
|------|------|
| 輸入資料夾不存在 | 路徑錯誤 |
| 發現非數字檔名的影片 | 資料夾內有 `intro.mp4` 等 |
| 至少需要 2 段影片 | 只有 1 個影片檔 |
| Copy 模式不可用 | 片段規格不一致，改用 `--mode encode` |
| 找不到 ffmpeg / ffprobe | 未安裝或未加入 PATH |

## License

MIT
