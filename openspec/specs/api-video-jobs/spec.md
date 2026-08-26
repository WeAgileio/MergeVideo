# api-video-jobs Specification

## Purpose
TBD - created by archiving change add-video-processing-api. Update Purpose after archive.
## Requirements
### Requirement: Create merge job

The API SHALL provide `POST /v1/jobs/merge` accepting JSON body with `file_ids` (array of strings, minimum 2, maximum 10) and optional `crf` (integer, default 18). Merge order SHALL follow the array order of `file_ids` (index 0 first, index 1 second, etc.). The system SHALL use internal `mode=auto` (copy if compatible, otherwise encode). The API SHALL return HTTP 202 with `job_id`, `type: "merge"`, `status: "queued"`, and `status_url`.

#### Scenario: Successful merge job creation

- **WHEN** authenticated client submits `file_ids` with 3 valid owned files in desired order
- **THEN** the API returns HTTP 202 with a unique `job_id` and status `queued`

#### Scenario: Insufficient files for merge

- **WHEN** client submits fewer than 2 `file_ids`
- **THEN** the API returns HTTP 400 with error code `INSUFFICIENT_FILES`

#### Scenario: Referenced file not found

- **WHEN** any `file_id` in the array does not exist, has expired, or is not owned by the caller
- **THEN** the API returns HTTP 404 or 403 with appropriate error code

### Requirement: Create extract first frame job

The API SHALL provide `POST /v1/jobs/extract-first-frame` accepting JSON body with `file_id`. The API SHALL return HTTP 202 with `job_id`, `type: "extract_first_frame"`, `status: "queued"`, and `status_url`.

#### Scenario: Successful extract first frame job

- **WHEN** authenticated client submits a valid owned `file_id`
- **THEN** the API returns HTTP 202 with `job_id` and status `queued`

### Requirement: Create extract last frame job

The API SHALL provide `POST /v1/jobs/extract-last-frame` accepting JSON body with `file_id`. The API SHALL return HTTP 202 with `job_id`, `type: "extract_last_frame"`, `status: "queued"`, and `status_url`.

#### Scenario: Successful extract last frame job

- **WHEN** authenticated client submits a valid owned `file_id`
- **THEN** the API returns HTTP 202 with `job_id` and status `queued`

### Requirement: Job lifecycle states

Each job SHALL progress through states: `queued` → `processing` → `done` | `failed`. Status transitions SHALL be monotonic (no regression from `processing` to `queued`).

#### Scenario: Job progresses to done

- **WHEN** worker completes processing successfully
- **THEN** job status becomes `done` and result metadata is populated

#### Scenario: Job fails

- **WHEN** processing fails (e.g. ffmpeg error, missing video stream)
- **THEN** job status becomes `failed` with structured error containing `code` and `message`

### Requirement: Job progress reporting

Each job SHALL expose a `progress` field (integer 0–100) in the job status response. Progress SHALL be 0 when queued, estimated from FFmpeg processed duration versus total input duration while processing (capped at 99), and 100 when done. Progress updates SHALL be throttled (at least 1 percentage point change and 1 second interval) to limit database writes.

#### Scenario: Progress during merge processing

- **WHEN** a merge job is processing and FFmpeg has handled half of the total input duration
- **THEN** polling the job returns `progress` approximately 50

#### Scenario: Progress on completion

- **WHEN** a job reaches `done`
- **THEN** `progress` is 100

### Requirement: Query job status

The API SHALL provide `GET /v1/jobs/{job_id}` returning job metadata. For `queued` and `processing`, the response SHALL include `status`, `type`, and timestamps. For `done`, the response SHALL include a `result` object. For `failed`, the response SHALL include an `error` object. When `RESULT_TTL_HOURS=0` (default), completed job results SHALL remain available indefinitely unless manually removed by other means.

#### Scenario: Poll processing job

- **WHEN** client polls a job in `processing` status
- **THEN** the API returns HTTP 200 with `status: "processing"`

#### Scenario: Poll completed merge job

- **WHEN** client polls a merge job in `done` status
- **THEN** the response includes `result.download_url`, `result.expires_at`, `result.filename`, `result.content_type` (`video/mp4`), and `result.size_bytes`

#### Scenario: Poll completed extract job

- **WHEN** client polls an extract job in `done` status
- **THEN** the response includes `result.download_url`, `result.filename` ending in `_FirstFrame.png` or `_LastFrame.png`, and `result.content_type` (`image/png`)

#### Scenario: Completed job result retained by default

- **WHEN** default configuration is used (`RESULT_TTL_HOURS=0`) and client polls a completed merge job days later
- **THEN** the response still includes `result.download_url` and result metadata

#### Scenario: Query non-existent job

- **WHEN** client requests an unknown `job_id`
- **THEN** the API returns HTTP 404 with error code `JOB_NOT_FOUND`

#### Scenario: Non-owner cannot query job

- **WHEN** client B requests client A's `job_id`
- **THEN** the API returns HTTP 404 with error code `JOB_NOT_FOUND`

### Requirement: Result delivery via presigned download URL

When a job reaches `done`, the system SHALL upload the result to object storage and provide a presigned download URL in `result.download_url`. The URL SHALL have a configurable expiration (default 24 hours). Result files SHALL be stored at `results/{job_id}/{filename}`.

#### Scenario: Download URL accessible

- **WHEN** job completes successfully
- **THEN** client can download the result file via `result.download_url` before expiration

#### Scenario: Download URL expired

- **WHEN** client accesses `download_url` after expiration
- **THEN** object storage returns access denied; client must request a new job or URL refresh (v2)

### Requirement: Configurable background cleanup for job results

When `AUTO_CLEANUP_ENABLED=true` and `RESULT_TTL_HOURS` is greater than `0`, the worker SHALL periodically delete result objects under `results/{job_id}/` and clear `result_json` for completed jobs older than the configured TTL. When `AUTO_CLEANUP_ENABLED=false` (default) or `RESULT_TTL_HOURS=0`, the worker SHALL NOT delete job results automatically.

#### Scenario: Result cleanup disabled by default

- **WHEN** default configuration is used and a merge job completed days ago
- **THEN** polling the job still returns a `result` with `download_url`

#### Scenario: Result cleanup when enabled

- **WHEN** `AUTO_CLEANUP_ENABLED=true`, `RESULT_TTL_HOURS=72`, and a completed job is older than 72 hours
- **THEN** the worker removes result storage and subsequent polls no longer include downloadable result metadata

#### Scenario: Presigned URL TTL unchanged

- **WHEN** client polls a completed job and receives `result.download_url`
- **THEN** each presigned URL expires according to `DOWNLOAD_URL_TTL_HOURS` independently of result retention

### Requirement: Merge processing behavior

The merge worker SHALL download input files from object storage in `file_ids` array order, probe metadata, apply `mode=auto` (copy if all segments compatible, otherwise encode with max-pixel-area output resolution and letterboxing). Encode mode SHALL output H.264 + AAC consistent with existing CLI encode behavior.

#### Scenario: Auto selects copy mode

- **WHEN** all segments have identical resolution, codec, fps, and audio format
- **THEN** worker uses copy merge without re-encoding

#### Scenario: Auto selects encode mode

- **WHEN** segments differ in resolution, fps, or audio
- **THEN** worker re-encodes with unified output specification

### Requirement: Extract processing behavior

The extract worker SHALL download the input file, verify a video stream exists via ffprobe, and extract the first or last frame as PNG using FFmpeg, consistent with existing `extract_frame.py` behavior.

#### Scenario: Extract first frame output

- **WHEN** extract-first-frame job completes
- **THEN** result is a PNG of the first video frame

#### Scenario: Extract last frame output

- **WHEN** extract-last-frame job completes
- **THEN** result is a PNG of the last video frame

#### Scenario: No video stream

- **WHEN** input file has no video stream
- **THEN** job fails with error code `FFMPEG_ERROR`

### Requirement: API key authentication for job endpoints

All `/v1/jobs` endpoints SHALL require valid API key authentication. Unauthenticated requests SHALL return HTTP 401.

#### Scenario: Missing API key on job creation

- **WHEN** client calls `POST /v1/jobs/merge` without Authorization header
- **THEN** the API returns HTTP 401

### Requirement: Health check endpoint

The API SHALL provide `GET /health` returning service status. The response SHALL indicate whether ffmpeg and ffprobe are available on the worker path.

#### Scenario: Healthy service

- **WHEN** ffmpeg and ffprobe are available
- **THEN** `GET /health` returns HTTP 200 with status indicating healthy

### Requirement: Create import URL job

The API SHALL provide `POST /v1/jobs/import-url` accepting JSON body with `url` (required, string) and optional `filename` (string). The API SHALL return HTTP 202 with `job_id`, `type: "import_url"`, `status: "queued"`, and `status_url`. The API SHALL perform basic URL format and scheme validation before enqueueing; SSRF checks SHALL occur in the worker before download.

#### Scenario: Successful import job creation

- **WHEN** authenticated client submits a valid HTTPS URL
- **THEN** the API returns HTTP 202 with a unique `job_id` and status `queued`

#### Scenario: Invalid URL rejected at API

- **WHEN** client submits a malformed URL or disallowed scheme
- **THEN** the API returns HTTP 400 with error code `INVALID_URL`

### Requirement: Import URL job completion result

When an `import_url` job reaches `done`, the response SHALL include a `result` object with `file_id`, `filename`, `size_bytes`, and `expires_at`. The result SHALL NOT include `download_url` (the imported file is input material, not a deliverable).

#### Scenario: Poll completed import job

- **WHEN** client polls an import job in `done` status
- **THEN** the response includes `result.file_id` and `result.filename`

### Requirement: Import URL download progress

While an `import_url` job is `processing`, progress SHALL reflect download status when `Content-Length` is available: bytes downloaded divided by content length, scaled to 0–90 during download, then 100 when the file registry entry is created. When `Content-Length` is unavailable, progress MAY remain at 0 until completion.

#### Scenario: Progress during download with Content-Length

- **WHEN** import job is downloading and half of the declared content length has been received
- **THEN** polling returns `progress` approximately 45

#### Scenario: Progress on import completion

- **WHEN** import job reaches `done`
- **THEN** `progress` is 100

### Requirement: Import URL SSRF protection

Before downloading, the worker SHALL resolve the URL hostname to IP addresses and reject the request if any resolved IP is private, loopback, link-local, or a known cloud metadata address. The worker SHALL follow at most `IMPORT_URL_MAX_REDIRECTS` redirects (default 3) and re-apply IP checks after each redirect. Blocked requests SHALL fail the job with error code `URL_NOT_ALLOWED`.

#### Scenario: Private IP blocked

- **WHEN** worker resolves URL hostname to `127.0.0.1` or `10.0.0.1`
- **THEN** job fails with error code `URL_NOT_ALLOWED`

#### Scenario: Redirect to private IP blocked

- **WHEN** URL redirects to a host resolving to a private IP
- **THEN** job fails with error code `URL_NOT_ALLOWED`

### Requirement: Import URL download limits

The worker SHALL enforce the same maximum file size as upload (`MAX_FILE_SIZE_MB`, default 200). The worker SHALL enforce connect timeout (default 10 seconds) and total download timeout (default 10 minutes), configurable via environment variables. Exceeding size SHALL fail with `FILE_TOO_LARGE`; timeout or connection failure SHALL fail with `DOWNLOAD_FAILED`.

#### Scenario: File too large during download

- **WHEN** downloaded bytes exceed the configured maximum
- **THEN** job fails with error code `FILE_TOO_LARGE`

#### Scenario: Download timeout

- **WHEN** download does not complete within total timeout
- **THEN** job fails with error code `DOWNLOAD_FAILED`

### Requirement: Import URL format validation

After download, the worker SHALL validate the file extension against supported video formats and verify a video stream exists via ffprobe, consistent with upload validation. Invalid files SHALL fail with `UNSUPPORTED_FORMAT`.

#### Scenario: Non-video file rejected

- **WHEN** downloaded content is not a supported video format
- **THEN** job fails with error code `UNSUPPORTED_FORMAT`

### Requirement: API key authentication for import URL endpoint

`POST /v1/jobs/import-url` SHALL require valid API key authentication. Unauthenticated requests SHALL return HTTP 401.

#### Scenario: Missing API key

- **WHEN** client calls `POST /v1/jobs/import-url` without Authorization header
- **THEN** the API returns HTTP 401

### Requirement: Create generate subtitle job

The API SHALL provide `POST /v1/jobs/generate-subtitle` accepting JSON body with `file_id` (required string) and `script` (required string). The API SHALL return HTTP 202 with `job_id`, `type: "generate_subtitle"`, `status: "queued"`, and `status_url`. The endpoint SHALL require valid API key authentication.

#### Scenario: Successful subtitle job creation

- **WHEN** an authenticated client submits a valid owned `file_id` and a non-empty `script`
- **THEN** the API returns HTTP 202 with a unique `job_id` and status `queued`

#### Scenario: Missing or blank script rejected at API

- **WHEN** `script` is omitted, empty, or only whitespace
- **THEN** the API returns HTTP 400 with error code `SCRIPT_REQUIRED` or `SCRIPT_EMPTY`

#### Scenario: Script exceeds maximum length

- **WHEN** `script` length exceeds `FUNASR_MAX_SCRIPT_CHARS` (default 50000)
- **THEN** the API returns HTTP 400 with error code `SCRIPT_TOO_LONG`

#### Scenario: Referenced file not found

- **WHEN** `file_id` does not exist, has expired, or is not owned by the caller
- **THEN** the API returns HTTP 404 or 403 with the existing file error codes

#### Scenario: Missing API key

- **WHEN** the client calls `POST /v1/jobs/generate-subtitle` without Authorization
- **THEN** the API returns HTTP 401

### Requirement: Generate subtitle job completion result

When a `generate_subtitle` job reaches `done`, the status response SHALL include `result.download_url`, `result.expires_at`, `result.filename` ending in `.srt`, `result.content_type` of `application/x-subrip`, and `result.size_bytes`. Result files SHALL be stored at `results/{job_id}/{filename}`.

#### Scenario: Poll completed subtitle job

- **WHEN** the client polls a `generate_subtitle` job in `done` status
- **THEN** the response includes a downloadable SRT URL and `content_type` `application/x-subrip`

### Requirement: Generate subtitle job failure codes

When subtitle processing fails, the job SHALL be `failed` with a structured error. The worker SHALL use `NO_AUDIO_STREAM` when the input has no audio, `ALIGN_FAILED` when alignment produces no usable timestamps, and `FUNASR_UNAVAILABLE` when the FunASR model cannot be loaded. These SHALL NOT be reported as `FFMPEG_ERROR` unless FFmpeg itself failed (for example wav extraction errors other than missing audio).

#### Scenario: Alignment model missing

- **WHEN** the worker cannot import or load `fa-zh`
- **THEN** the job fails with error code `FUNASR_UNAVAILABLE`

#### Scenario: No audio stream

- **WHEN** the input video has no audio stream
- **THEN** the job fails with error code `NO_AUDIO_STREAM`

### Requirement: Generate subtitle progress

While a `generate_subtitle` job is `processing`, `progress` SHALL advance through coarse stages (download, wav extract, align, upload) and SHALL be 100 when `done`. Updates SHALL reuse the existing throttle (at least 1 percentage point and 1 second).

#### Scenario: Progress on subtitle completion

- **WHEN** a generate-subtitle job reaches `done`
- **THEN** `progress` is 100

