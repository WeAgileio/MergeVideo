## ADDED Requirements

### Requirement: Create burn subtitle job

The API SHALL provide `POST /v1/jobs/burn-subtitle` accepting JSON with `file_id` (required, video) and `srt_file_id` (required, SRT). Optional fields: `font_size` (integer, default 48, allowed 1–512), `margin_bottom` (number, default 6), `margin_unit` (`px` or `percent`, default `percent`). The API SHALL return HTTP 202 with `job_id`, `type: "burn_subtitle"`, `status: "queued"`, and `status_url`. The endpoint SHALL require valid API key authentication. Both files SHALL be pinned for the job lifetime.

#### Scenario: Successful burn job creation with defaults

- **WHEN** an authenticated client submits owned video `file_id` and SRT `srt_file_id` with no style fields
- **THEN** the API returns HTTP 202 with `type` `burn_subtitle` and the stored job input uses `font_size` 48, `margin_bottom` 6, and `margin_unit` `percent`

#### Scenario: Wrong file kinds rejected

- **WHEN** `file_id` refers to an SRT or `srt_file_id` refers to a video
- **THEN** the API returns HTTP 400 with error code `WRONG_FILE_TYPE`

#### Scenario: Invalid margin rejected

- **WHEN** `margin_unit` is not `px` or `percent`, or `percent` is used with a value outside 0–100, or `px` is used with a negative value
- **THEN** the API returns HTTP 400 with error code `INVALID_MARGIN`

#### Scenario: Invalid font size rejected

- **WHEN** `font_size` is 0 or greater than 512
- **THEN** the API returns HTTP 400 with error code `INVALID_FONT_SIZE`

#### Scenario: Missing API key

- **WHEN** the client calls `POST /v1/jobs/burn-subtitle` without Authorization
- **THEN** the API returns HTTP 401

### Requirement: Burn subtitle job completion result

When a `burn_subtitle` job reaches `done`, the status response SHALL include `result.download_url`, `result.expires_at`, `result.filename` ending in `_burned.mp4`, `result.content_type` of `video/mp4`, and `result.size_bytes`. Result files SHALL be stored at `results/{job_id}/{filename}`. The result SHALL NOT include a new `file_id`.

#### Scenario: Poll completed burn job

- **WHEN** the client polls a `burn_subtitle` job in `done` status
- **THEN** the response includes a downloadable MP4 URL and `content_type` `video/mp4`

### Requirement: Burn subtitle job failure codes

When burn-in fails, the job SHALL be `failed` with a structured error. The worker SHALL use `INVALID_SRT` when the SRT has no parseable cues, `FONT_UNAVAILABLE` when the bundled font cannot be read, and `FFMPEG_ERROR` when FFmpeg encode fails for other reasons.

#### Scenario: Unparseable SRT

- **WHEN** the referenced SRT contains no cues
- **THEN** the job fails with error code `INVALID_SRT`

### Requirement: Burn subtitle progress

While a `burn_subtitle` job is `processing`, `progress` SHALL advance through download, encode, and upload, tracking FFmpeg output time against source duration during encode, and SHALL be 100 when `done`. Updates SHALL reuse the existing throttle (at least 1 percentage point and 1 second).

#### Scenario: Progress on burn completion

- **WHEN** a burn-subtitle job reaches `done`
- **THEN** `progress` is 100

## MODIFIED Requirements

### Requirement: Generate subtitle job completion result

When a `generate_subtitle` job reaches `done`, the status response SHALL include `result.file_id` (a newly registered SRT file owned by the job caller), `result.download_url`, `result.expires_at`, `result.filename` ending in `.srt`, `result.content_type` of `application/x-subrip`, and `result.size_bytes`. The SRT bytes SHALL be stored as a file-registry object (`uploads/{file_id}/...`) so a subsequent burn job can reference `result.file_id`. `download_url` SHALL be a presigned URL for that same object.

#### Scenario: Poll completed subtitle job

- **WHEN** the client polls a `generate_subtitle` job in `done` status
- **THEN** the response includes both a `file_id` and a downloadable SRT URL with `content_type` `application/x-subrip`

#### Scenario: SRT file can be referenced by a later job

- **WHEN** generate-subtitle completes and the client passes the returned `file_id` as `srt_file_id` to burn-subtitle
- **THEN** the burn job is accepted (assuming the video `file_id` is also valid)
