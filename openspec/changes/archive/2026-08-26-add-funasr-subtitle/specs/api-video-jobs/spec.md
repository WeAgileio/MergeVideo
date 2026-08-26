## ADDED Requirements

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
