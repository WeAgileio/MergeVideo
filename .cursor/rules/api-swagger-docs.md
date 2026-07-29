---
description: API 變更時須同步更新 Swagger（OpenAPI）文檔
globs:
  - "api/**/*.py"
  - "README.md"
  - "README.en.md"
alwaysApply: false
---

# API Swagger 文檔同步規則

本專案 Swagger UI 為 `/docs`，OpenAPI schema 由 FastAPI 從程式碼與 decorator **即時產生**。新增、修改或刪除 API 行為時，**同一 PR／同一批次變更內**須一併更新文檔，不可只改 handler 邏輯。

## 必改檔案對照

| 變更類型 | 須更新 |
|---------|--------|
| 新增／刪除 endpoint | 對應 `api/routes/*.py` 的 `@router.*`（`summary`、`description`、`responses`、request/response 範例） |
| 新增 error code | `api/main.py` → `_API_DESCRIPTION` 錯誤碼表 |
| 新增 tag 或調整分類 | `api/main.py` → `_TAGS_METADATA` |
| 使用流程、認證、全域說明 | `api/main.py` → `_API_DESCRIPTION` |
| endpoint 表、curl 範例 | `README.md`、`README.en.md` 的 HTTP API 章節 |

## Endpoint 文檔最低要求

每個 `@router.post/get/delete` 須具備：

- `summary`：一句話說明
- `description`：參數、行為、狀態流轉、與其他 endpoint 的關係
- `responses`：至少含成功與常見錯誤的 `example`（參考 `api/routes/jobs.py` 的 `_JOB_ACCEPTED_RESPONSE`、`_IMPORT_URL_ACCEPTED_RESPONSE`）
- Pydantic model 的 `Field(description=..., examples=[...])`

## 完成前自檢

1. 本地確認 OpenAPI 含預期 path：

```bash
python -c "from api.main import create_app; s=create_app().openapi(); print([p for p in s['paths'] if '你的路徑' in p])"
```

2. 若用 Docker，映像內程式碼在 **build 時 COPY**，改完須重建後才會在 `/docs` 看到：

```bash
docker compose up -d --build api
```

3. 瀏覽器開 `http://localhost:8000/docs`，必要時 Cmd+Shift+R 強制重新整理。

## 禁止

- 只改 route handler、不補 `summary` / `description` / `responses`
- 新增 error code 卻未寫入 `_API_DESCRIPTION` 錯誤碼表
- 對外可見的 endpoint 變更卻未更新 README 雙語 endpoint 表
