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
# Subtitle jobs need FunASR / PyTorch on the worker (~1.5–3GB extra image size, reserve 1–2GB RAM)
pip install -r requirements-worker.txt
cp .env.example .env   # set API_KEYS and other config

# API server
uvicorn api.main:create_app --factory --reload

# Worker (separate terminal)
python -m api.worker
```

Or use Docker Compose (includes MinIO + Redis). The subtitle worker uses `Dockerfile.worker` (PyTorch). The first start downloads the `fa-zh` model (needs network); later runs use the `funasr_models` volume cache:

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
| `POST` | `/v1/files` | Upload a video, `.srt`, or image (multipart, field `file`), returns `file_id` |
| `GET` | `/v1/files/{file_id}` | Get file metadata |
| `DELETE` | `/v1/files/{file_id}` | Delete a file |
| `POST` | `/v1/jobs/merge` | Merge videos; order follows **`file_ids` array order**; auto copy/encode internally |
| `POST` | `/v1/jobs/extract-first-frame` | Extract first frame as PNG |
| `POST` | `/v1/jobs/extract-last-frame` | Extract last frame as PNG |
| `POST` | `/v1/jobs/import-url` | Import video from URL (async); returns `file_id` when done |
| `POST` | `/v1/jobs/generate-subtitle` | Forced-align SRT from a required `script`; `done` returns `file_id` and a `.srt` download URL |
| `POST` | `/v1/jobs/burn-subtitle` | Burn an SRT into the video; optional font size and bottom margin |
| `POST` | `/v1/jobs/replace-images` | Replace full frames with static images for 1–10 time ranges; `done` returns `file_id` and a download URL |
| `GET` | `/v1/jobs/{job_id}` | Get job status; includes `progress`; merge/extract/burn `done` returns `download_url`; generate-subtitle and replace-images also return `file_id`; import `done` returns `file_id` |
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

### Import from URL (skip manual upload)

```bash
# 1. Create import job (server downloads; HTTPS only by default)
IMPORT=$(curl -s -X POST "$BASE/v1/jobs/import-url" -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://cdn.example.com/clip.mp4"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['job_id'])")

# 2. Poll until done; get file_id
curl -s "$BASE/v1/jobs/$IMPORT" -H "Authorization: Bearer $KEY"

# 3. Use file_id in merge / extract jobs (same as above)
```

### Generate SRT from a script

The worker runs FunASR `fa-zh` in-process (not funasr-server). The script must match the spoken audio; cue text comes from the script.

```bash
SUB=$(curl -s -X POST "$BASE/v1/jobs/generate-subtitle" -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d "{\"file_id\": \"$F1\", \"script\": \"Hello everyone. Welcome to this episode.\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['job_id'])")

curl -s "$BASE/v1/jobs/$SUB" -H "Authorization: Bearer $KEY"
```

### Burn subtitles into a video

Two-step: get an SRT (`generate-subtitle` `result.file_id`, or upload a `.srt`), then burn it in. Always re-encodes. Defaults: Taipei Sans TC Beta, font size 48, bottom margin 6 percent, bottom-center, white text with black outline.

```bash
SRT=$(curl -s -X POST "$BASE/v1/files" -H "Authorization: Bearer $KEY" \
  -F "file=@talk.srt" | python3 -c "import sys,json;print(json.load(sys.stdin)['file_id'])")

BURN=$(curl -s -X POST "$BASE/v1/jobs/burn-subtitle" -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d "{\"file_id\": \"$F1\", \"srt_file_id\": \"$SRT\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['job_id'])")

curl -s "$BASE/v1/jobs/$BURN" -H "Authorization: Bearer $KEY"
```

### Replace frames with static images

Up to 10 ranges per job; each range shows only that image. Images are fit with contain: scaled uniformly to fit inside the frame, centered, with black bars filling the rest — never cropped, never stretched. Audio is stream-copied and the output duration matches the source; video is always re-encoded to H.264.

The `done` result carries both a `file_id` (the output is registered in the file registry) and a `download_url`, so you can pass `file_id` straight into a later job such as burn-subtitle. You choose the order: replacing first puts subtitles on top of the images, burning first means those seconds are covered along with their subtitles.

```bash
# 1. Upload an image (png / jpg / jpeg / webp)
IMG=$(curl -s -X POST "$BASE/v1/files" -H "Authorization: Bearer $KEY" \
  -F "file=@slide.png" | python3 -c "import sys,json;print(json.load(sys.stdin)['file_id'])")

# 2. Create the replace job (ranges must not overlap; end may equal the next start)
REP=$(curl -s -X POST "$BASE/v1/jobs/replace-images" -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d "{\"file_id\": \"$F1\", \"replacements\": [{\"image_file_id\": \"$IMG\", \"start\": 3, \"end\": 5}]}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['job_id'])")

# 3. Poll until done; get file_id and download_url
curl -s "$BASE/v1/jobs/$REP" -H "Authorization: Bearer $KEY"
# {"status": "done", "result": {"file_id": "f_...", "filename": "1_replaced.mp4", "download_url": "..."}}
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

### Retention and cleanup

| Variable | Default | Description |
|----------|---------|-------------|
| `FILE_TTL_HOURS` | `0` | `0` = uploads never expire; > 0 enables logical expiry |
| `RESULT_TTL_HOURS` | `0` | `0` = job results kept indefinitely |
| `AUTO_CLEANUP_ENABLED` | `false` | Whether the worker physically deletes expired resources |
| `CLEANUP_INTERVAL_SECONDS` | `60` | Cleanup interval (when enabled) |
| `DOWNLOAD_URL_TTL_HOURS` | `24` | Single presigned URL lifetime |

**Breaking change:** Deployments without explicit env now retain files/results indefinitely instead of auto-expiring after 24h/72h. To restore previous behavior:

```bash
AUTO_CLEANUP_ENABLED=true
FILE_TTL_HOURS=24
RESULT_TTL_HOURS=72
```

Manual delete: `DELETE /v1/files/{file_id}`.

### Key Settings (Environment Variables)

See `.env.example`: `API_KEYS`, `STORAGE_BACKEND`, `REDIS_URL`, `MAX_FILE_SIZE_MB` (default 200), `AUTO_CLEANUP_ENABLED`, `FILE_TTL_HOURS`, `DOWNLOAD_URL_TTL_HOURS`, `IMPORT_URL_ALLOW_HTTP`, etc.

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

## Release Notes

### v2.2.0

- **Replace frames with images**: `POST /v1/jobs/replace-images` replaces the full frame with an uploaded static image for 1–10 time ranges. Images are fit with contain (uniform scale, centered, black bars, never cropped or stretched); audio is stream-copied and output duration matches the source
- **Output chains into the next job**: the `done` result carries both `file_id` and `download_url`, so you can pass `file_id` straight to burn-subtitle. You choose the order of replacing and burning
- **Image upload**: `POST /v1/files` accepts `.png` / `.jpg` / `.jpeg` / `.webp`
- **More accurate subtitle timing**: Latin names and numbers (e.g. `Lookonchain`, `96191`) no longer consume later cues' timestamps by letter count, and the last cue now extends to the end of the trailing speech
- **New error codes**: `EMPTY_REPLACEMENTS`, `TOO_MANY_REPLACEMENTS`, `INVALID_RANGE`, `OVERLAPPING_RANGES`, `INVALID_IMAGE`

### v2.1.0

- **Scripted subtitles**: `POST /v1/jobs/generate-subtitle` takes a required `script`; the worker aligns with FunASR `fa-zh` and returns SRT. `done` includes both `file_id` and a download URL
- **Burn-in subtitles**: `POST /v1/jobs/burn-subtitle` burns an SRT into the video. Optional `font_size` and `margin_bottom` (`px` or `percent`). Defaults: Taipei Sans TC Beta, size 48, 6% from the bottom, bottom-center, white text with black outline
- **SRT upload**: `POST /v1/files` accepts `.srt` for burn-in
- **Deploy**: Worker uses `Dockerfile.worker` (FunASR / PyTorch); the image bundles Taipei Sans TC Beta. Rebuild images to pick this up

### v2.0.0

- **HTTP API**: upload, merge, and frame-extraction async jobs; Docker Compose deployment; switchable storage backends
- **URL import**: `POST /v1/jobs/import-url` downloads on the server and returns `file_id`
- **Retention (Breaking)**: default is indefinite retention (`FILE_TTL_HOURS=0`, `RESULT_TTL_HOURS=0`, `AUTO_CLEANUP_ENABLED=false`); restore previous 24h/72h auto-cleanup via env
- **Manual delete**: `DELETE /v1/files/{file_id}`

## License

MIT
