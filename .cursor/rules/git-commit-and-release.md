---
description: Git commit/push/tag 前須確認；Conventional Commits 與發版流程
globs:
  - "**/*"
alwaysApply: true
---


## Git 提交流程規則

在這個專案中，**只要需要你協助執行任何會影響遠端狀態的 git 操作（包含 `commit`、`tag`、以及 `push`/`push --tags` 推送）時**，操作順序為：

1. `git commit`：使用符合本檔案 Commits 規範建立提交（僅在使用者明確要求，或變更已就緒且使用者同意提交時）。
2. **推送前同步**：以 `git status` / `git fetch` 確認與遠端分支狀態；若本地落後遠端，先 `git pull --rebase`（或 merge）並處理衝突。
3. `git push` / `git push --tags`：確認已與遠端同步後，才把本地提交推送到遠端。

- 若 `git status` 已顯示與遠端同步（例如 `Your branch is up to date with 'origin/main'`），**不必在每次 commit 前先 pull**。
- 若使用者已手動完成部分步驟（例如已自行 pull 或 commit），可跳過已完成步驟；但 **push 前仍須確認遠端狀態**。
- **確認時機**：
  - 使用者**已明確要求**（例如「幫我提交並 push」）→ 可直接執行；執行前可簡短說明將做的步驟。
  - **僅在你主動建議**提交/推送，或範圍不清（要 commit 哪些檔、訊息怎麼寫、是否 force push 等）→ 先說明計畫並等待使用者確認後再執行。

---

## Commits 規範

### 1. Commit 訊息格式

請使用以下格式：

```text
<type>[可選 scope]: <description>

[可選 body]

[可選 footer(s)]
```

---

### 2. 類型（type）

優先使用以下類型：

- **feat**: 新功能
- **fix**: 錯誤修復
- **docs**: 文件相關修改
- **style**: 格式調整（不影響程式邏輯，如空白、分號等）
- **refactor**: 重構（非修 bug、非加功能）
- **perf**: 效能優化
- **test**: 測試新增或修正
- **build**: 建置系統或相依套件變更
- **ci**: CI/CD 流程變更
- **chore**: 雜項或維護性工作（不影響產品功能）

---

### 3. Scope（範圍）

- scope 為 **可選**
- 若有幫助，請使用 **簡短名詞** 描述影響範圍

範例：

```text
feat(auth): 新增 SSO 登入
fix(api): 處理空 payload
docs(readme): 更新安裝步驟
```

---

### 4. Description（描述）

- 使用 **中文** 撰寫 description
- 描述需 **簡潔且具體**
- **不要加句號結尾**
- 使用 **祈使句**（如「新增…」「修正…」「更新…」），避免過去式（如「新增了…」）

建議寫法：

```text
新增使用者頭像上傳
修正 webhook 逾時的重試邏輯
```

---

### 5. Breaking Changes（破壞性變更）

若為破壞性修改，請在 type 後加上 `!`：

```text
feat(api)!: 移除 v1 session 端點
refactor(core)!: 調整 plugin 生命週期鉤子
```

必要時在 footer 加上：

```text
BREAKING CHANGE: 說明變更內容、影響對象、遷移方式
```

---

### 6. Body（內文）

僅在「有價值」時補充，內容可以包含：

- 為什麼需要這個變更
- 重要實作細節
- 取捨或副作用

---

### 7. Footer（附註）

常見用途：

```text
BREAKING CHANGE: 說明破壞性變更內容
Refs: #123
Closes: #456
```

---

### 8. 選擇規則（Selection Rules）

- 若同時包含功能與修復 → **優先拆成多個 commit**
- 若只能寫一個 → **選主要意圖**
- 不要捏造 diff 中不存在的變更
- 若使用者只要 commit message → **不要多餘說明**

---

### 9. 輸出規則（Output Rules）

當被要求產生 commit message 時：

1. 第一行必須符合 Conventional Commit 格式
2. 僅在必要時補 body / footer
3. 預設輸出為純文字（除非另有要求）

---

### 10. 良好範例

```text
feat(auth): 新增 Google OAuth 登入
fix(upload): 避免重複提交檔案
docs(readme): 釐清本地開發環境設定
refactor(api): 簡化錯誤對應邏輯
perf(search): 快取標籤彙總結果
test(payment): 新增 webhook 重試測試覆蓋
chore(deps): 升級 vite 至 6
ci(github): 新增 release 流程
feat(api)!: 移除舊版 token 端點

BREAKING CHANGE: 客戶端須從 /v1/token 遷移至 /v2/token
```

---

### 11. 不良範例

```text
新增了登入功能（用了過去式，且無 type）
修 bug（描述過於籠統）
更新一些東西（語意不清）
feat: 新增了新功能（描述空泛，且用了過去式）
```

---

## Release 規則

當你要協助建立新版本（例如：打 tag、建立 GitHub Release、或在討論中明確提到「release / 發版 / 上線」）時，須確保：

- `README.md` 中有對應這次版本的 **Release Notes** 區塊或條目，內容至少包含：
  - 本次版本的簡短說明（例如：新增了哪些主要功能或修正了哪些問題）
  - 若有破壞性修改，需在這裡特別標註
  - 以**使用者可感知**的功能變更為主；不必寫內部重構或程式碼調整
  - **API、部署、設定**等對使用者或整合方有影響的變更也要寫（例如新增 endpoint、環境變數變更）
- 若 `README.md` 尚未有 Release 區塊，先幫使用者在 README 底部加上一個簡單的「Release Notes」章節，然後再加入這次版本的說明。
- 在建立/推送 tag 及建立 GitHub Release 前，先確認（或補齊）上述 `README.md` 的 Release Notes
- 在幫忙產生 release 描述或 changelog 時，**優先復用或同步到 `README.md` 的 Release Notes**，避免兩邊內容不一致。
- 使用者明確說「發版」（即使沒特別拆開講），**預設**同時完成 **Git 發版 + GitHub Release**。
- 若使用者明確表示**只要打 tag、不要 GitHub Release**（或類似表述），可略過 `gh release create`，其餘步驟仍須完成。
- 預設執行順序：
  1. 整理版本內容（必要時更新 `README.md` 版本紀錄／`package.json` 版本號）。
  2. Git 發版：`commit`（含 README 等版本內容）→ 推送前以 `git status` / `git fetch` 確認遠端狀態，必要時 `git pull --rebase`（或 merge）→ 建立 **annotated tag**（`git tag -a vX.Y.Z -m "vX.Y.Z"`，例如 `v1.2.0`，與 `package.json` 一致；**勿用 lightweight tag**）→ `push` / `push --tags`。
  3. **GitHub Release**（預設執行）：在標籤已於遠端存在後，使用 **`gh release create <tag>`** 建立 Release（標題可用版本號；內文優先自 `README.md` 該版條目整理，與 README 一致）。若本機無 `gh` 或未登入，須向使用者說明並改請其於網頁建立，或協助安裝／登入後再執行。
- 若任一步驟缺少必要資訊（例如版本號、tag 命名規則），先向使用者確認；若資訊齊全則直接完整執行（預設含 GitHub Release；使用者只要 tag 時則至 tag 推送完成即可）。

