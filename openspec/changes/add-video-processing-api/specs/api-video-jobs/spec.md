## ADDED Requirements

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

The API SHALL provide `GET /v1/jobs/{job_id}` returning job metadata. For `queued` and `processing`, the response SHALL include `status`, `type`, and timestamps. For `done`, the response SHALL include a `result` object. For `failed`, the response SHALL include an `error` object.

#### Scenario: Poll processing job

- **WHEN** client polls a job in `processing` status
- **THEN** the API returns HTTP 200 with `status: "processing"`

#### Scenario: Poll completed merge job

- **WHEN** client polls a merge job in `done` status
- **THEN** the response includes `result.download_url`, `result.expires_at`, `result.filename`, `result.content_type` (`video/mp4`), and `result.size_bytes`

#### Scenario: Poll completed extract job

- **WHEN** client polls an extract job in `done` status
- **THEN** the response includes `result.download_url`, `result.filename` ending in `_FirstFrame.png` or `_LastFrame.png`, and `result.content_type` (`image/png`)

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
