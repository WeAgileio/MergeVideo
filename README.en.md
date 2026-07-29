# MergeVideo

[中文 README](README.md)

Merge numerically named videos in a folder (`1.mp4`, `2.mp4`, …) into a single MP4, or extract the first / last frame from a video as PNG. Useful for ComfyUI digital-human workflows and similar pipelines.

## Tools

| Command | Purpose |
|---------|---------|
| `mergevideo.py` | Merge multiple numerically named videos into one MP4 |
| `VideoFirstFrame` | Extract the first frame of a video as PNG |
| `VideoLastFrame` | Extract the last frame of a video as PNG |

## mergevideo Features

- Natural sort by filename (`1 → 2 → 10`)
- Auto-analyze resolution, frame rate, codec, and audio
- Interactive choice between **Copy** (no re-encode) and **Encode** (normalize specs then merge)
- Encode mode uses the clip with the **largest pixel area** as output resolution; smaller clips are scaled with letterboxing
- Keeps audio on every clip; silent clips get a silent audio track
- Default output: `output/mergedYYYYMMDDHHmmss.mp4` inside the input folder

## Requirements

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/) / ffprobe (must be on `PATH`)

```bash
# macOS (Homebrew)
brew install ffmpeg

# Verify installation
ffmpeg -version
ffprobe -version
```

## Quick Start

```bash
# Clone the repo
git clone https://github.com/WeAgileio/MergeVideo.git
cd MergeVideo

# Interactive mode (analyze, then choose Copy / Encode)
python3 mergevideo.py ./clips

# Auto mode
python3 mergevideo.py ./clips --mode auto

# Analyze only, no merge
python3 mergevideo.py ./clips --dry-run
```

Or make it executable and run directly:

```bash
chmod +x mergevideo.py
./mergevideo.py ./clips
```

## Input Rules

Put all videos to merge in the same folder. Filenames must be **numeric only**:

```
clips/
├── 1.mp4
├── 2.mp4
└── 10.mp4
```

| Rule | Description |
|------|-------------|
| Filename format | `1.mp4`, `02.mov`, etc. (stem must match `\d+`) |
| Non-numeric names | Error (e.g. `intro.mp4`) |
| Minimum count | At least 2 videos |
| Supported formats | `.mp4`, `.mov`, `.webm`, `.mkv`, `.avi`, `.m4v` |

## Output Rules

When `-o` is not set, output goes to `output/` **inside** the input folder:

```
clips/              ← input
├── 1.mp4
├── 2.mp4
└── output/         ← created automatically
    └── merged20260619120930.mp4
```

## CLI Options

```
mergevideo.py <input_folder> [options]

Options:
  -o, --output PATH     Custom output file path
  --mode {auto,copy,encode}
                        auto = copy if compatible, else encode
                        copy = concat without re-encoding (errors if incompatible)
                        encode = re-encode
  --crf N               Encode quality, default 18 (lower = better)
  --dry-run             Analyze and report only, no merge
```

### Examples

```bash
# Interactive
python3 mergevideo.py ./clips

# Force re-encode
python3 mergevideo.py ./clips --mode encode

# Fast merge when clips are compatible
python3 mergevideo.py ./clips --mode copy

# Custom output path
python3 mergevideo.py ./clips -o ~/Desktop/final.mp4
```

## Merge Modes

### Copy Mode

Use when all clips share the same resolution, codec, frame rate, and audio format. Concatenates directly—fast, no quality loss.

### Encode Mode

Use when clip specs differ. Output is normalized to H.264 + AAC (48000 Hz stereo). Resolution follows the largest clip; smaller clips are letterboxed and centered.

A sample analysis report:

```
Scanning folder: ./clips
Found 3 videos (natural sort)

 #  File      Resolution  FPS  Codec  Audio
────────────────────────────────────────────
 1  1.mp4    1920×1080   30   h264   aac
 2  2.mp4    1280×720    30   h264   none

Copy mode: unavailable
Encode mode: available

Choose [E]ncode / [Q]uit:
```

## ComfyUI Workflow

1. ComfyUI produces multiple video clips
2. (Optional) Extract first or last frame from each clip as reference images:

```bash
VideoFirstFrame ./clips/1.mp4
# → ./clips/output/1_FirstFrame.png

VideoLastFrame ./clips/1.mp4
# → ./clips/output/1_LastFrame.png
```

3. Rename clips to `1.mp4`, `2.mp4`, `3.mp4`, …
4. Merge:

```bash
python3 mergevideo.py /path/to/comfyui/output --mode auto
```

## VideoFirstFrame

Extract the first frame of a single video as PNG.

```bash
VideoFirstFrame ./clips/1.mp4
# → ./clips/output/1_FirstFrame.png
```

| Item | Description |
|------|-------------|
| Input | Single video file (folders not supported) |
| Output filename | `{stem}_FirstFrame.png` |
| Output location | `output/` under the video's directory |
| Format | PNG |

## VideoLastFrame

Extract the last frame of a single video as PNG.

```bash
VideoLastFrame ./clips/1.mp4
# → ./clips/output/1_LastFrame.png
```

| Item | Description |
|------|-------------|
| Input | Single video file (folders not supported) |
| Output filename | `{stem}_LastFrame.png` |
| Output location | `output/` under the video's directory |
| Format | PNG |

Or make it executable:

```bash
chmod +x VideoLastFrame
./VideoLastFrame ./clips/1.mp4
```

## HTTP API

In addition to the CLI, a REST API (FastAPI) is available for cloud web services. Flow: **upload file → get `file_id` → create async job → poll job status → download result via URL**.

### Local Development

```bash
pip install -r requirements-api.txt
cp .env.example .env   # set API_KEYS and other config

# API server
uvicorn api.main:create_app --factory --reload

# Worker (separate terminal)
python -m api.worker
```

Or use Docker Compose (includes MinIO + Redis):

```bash
docker compose up --build
```

### Interactive API Docs (Swagger)

Once the service is running:

| URL | Description |
|-----|-------------|
| `http://localhost:8000/docs` | Swagger UI — click **Authorize**, enter your API key, upload files, create jobs, and poll results in the browser |
| `http://localhost:8000/redoc` | ReDoc — documentation-focused layout |
| `http://localhost:8000/openapi.json` | OpenAPI 3.1 spec — import into Postman / Insomnia or generate client SDKs |

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/v1/files` | Upload a video (multipart, field `file`), returns `file_id` |
| `GET` | `/v1/files/{file_id}` | Get file metadata |
| `DELETE` | `/v1/files/{file_id}` | Delete a file |
| `POST` | `/v1/jobs/merge` | Merge videos; order follows **`file_ids` array order**; auto copy/encode internally |
| `POST` | `/v1/jobs/extract-first-frame` | Extract first frame as PNG |
| `POST` | `/v1/jobs/extract-last-frame` | Extract last frame as PNG |
| `GET` | `/v1/jobs/{job_id}` | Get job status; includes `progress` (0–100); returns `result.download_url` when `done` |
| `GET` | `/health` | Health check (includes ffmpeg availability) |

All `/v1/*` endpoints require `Authorization: Bearer <api_key>`.

### Usage Example

```bash
KEY="change-me"
BASE="http://localhost:8000"

# 1. Upload two videos
F1=$(curl -s -X POST "$BASE/v1/files" -H "Authorization: Bearer $KEY" \
  -F "file=@1.mp4" | python3 -c "import sys,json;print(json.load(sys.stdin)['file_id'])")
F2=$(curl -s -X POST "$BASE/v1/files" -H "Authorization: Bearer $KEY" \
  -F "file=@2.mp4" | python3 -c "import sys,json;print(json.load(sys.stdin)['file_id'])")

# 2. Create merge job (array order = merge order)
JOB=$(curl -s -X POST "$BASE/v1/jobs/merge" -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d "{\"file_ids\": [\"$F1\", \"$F2\"]}" | python3 -c "import sys,json;print(json.load(sys.stdin)['job_id'])")

# 3. Poll until done; use progress for a progress bar while processing
curl -s "$BASE/v1/jobs/$JOB" -H "Authorization: Bearer $KEY"
# {"job_id": "j_...", "status": "processing", "progress": 45, ...}
# {"job_id": "j_...", "status": "done", "progress": 100, "result": {"download_url": ...}}
```

### Storage Backends (switch at startup)

Set `STORAGE_BACKEND` to switch backends. Upload / processing / download logic stays the same:

| backend | Use case | Required config | Download URL |
|---------|----------|-----------------|--------------|
| `local` | Local dev | `LOCAL_STORAGE_DIR` | API `/storage` route |
| `s3` | AWS S3 and S3-compatible (MinIO / Cloudflare R2 / Alibaba OSS / Tencent COS / Wasabi / B2) | `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`; set `S3_ENDPOINT_URL` for non-AWS | presigned URL |
| `gcs` | Google Cloud Storage | `GCS_BUCKET`, `GCS_CREDENTIALS_JSON` (service account) | v4 signed URL |
| `azure` | Azure Blob Storage | `AZURE_CONNECTION_STRING`, `AZURE_CONTAINER` | SAS URL |
| `rclone` | **Google Drive, OneDrive**, Dropbox, Box, and other rclone remotes | Run `rclone config` first, then set `RCLONE_REMOTE` (e.g. `gdrive:mergevideo`) | `rclone link` share URL |

```bash
# Example: AWS S3
STORAGE_BACKEND=s3 S3_BUCKET=my-bucket S3_ACCESS_KEY=... S3_SECRET_KEY=... \
  uvicorn api.main:create_app --factory

# Example: Google Drive (requires a gdrive remote from rclone config)
STORAGE_BACKEND=rclone RCLONE_REMOTE=gdrive:mergevideo \
  uvicorn api.main:create_app --factory
```

Note: `gcs` / `azure` need extra packages (see comments in `requirements-api.txt`). rclone share links have no expiry control—fine for internal workflows, not for strict access control.

### Key Settings (Environment Variables)

See `.env.example`: `API_KEYS`, `STORAGE_BACKEND`, `REDIS_URL`, `MAX_FILE_SIZE_MB` (default 200), `FILE_TTL_HOURS`, `DOWNLOAD_URL_TTL_HOURS`, etc.

### Tests

```bash
pip install -r requirements-api.txt
python -m pytest tests/
```

## Project Structure

```
MergeVideo/
├── mergevideo.py      # Merge CLI
├── VideoFirstFrame    # First-frame CLI
├── VideoLastFrame     # Last-frame CLI
├── extract_frame.py   # Frame extraction logic
├── scanner.py         # Folder scan and filename validation
├── probe.py           # ffprobe parsing
├── compat.py          # Copy compatibility checks
├── report.py          # Analysis report
├── merger.py          # Merge engine (includes merge_auto for API)
├── ffmpeg_utils.py    # FFmpeg helpers
├── api/               # HTTP API (FastAPI)
│   ├── main.py        #   app entry (factory)
│   ├── routes/        #   files / jobs endpoints
│   ├── models/        #   file registry and job store
│   ├── services/      #   storage / queue / cleanup
│   └── worker/        #   background worker
└── tests/             # API integration tests
```

## Common Errors

| Message | Cause |
|---------|-------|
| Input folder does not exist | Wrong path |
| Non-numeric video filename found | Folder contains `intro.mp4`, etc. |
| At least 2 videos required | Only one video file |
| Copy mode unavailable | Clip specs differ; use `--mode encode` |
| ffmpeg / ffprobe not found | Not installed or not on PATH |
| Please provide a single video file path | VideoFirstFrame / VideoLastFrame received a folder |
| No video stream found | Input file has no video stream |

## License

MIT
