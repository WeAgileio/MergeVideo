## MODIFIED Requirements

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

## ADDED Requirements

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
