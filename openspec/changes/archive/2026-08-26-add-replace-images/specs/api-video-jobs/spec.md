## ADDED Requirements

### Requirement: Create replace-images job

The API SHALL provide `POST /v1/jobs/replace-images` accepting JSON with `file_id` (required, video) and `replacements` (required array, length 1–10). Each replacement SHALL have `image_file_id` (required, image), `start` (number, seconds, `>= 0`), and `end` (number, seconds, `> start`). The API SHALL return HTTP 202 with `job_id`, `type: "replace_images"`, `status: "queued"`, and `status_url`. The endpoint SHALL require valid API key authentication. The video and every referenced image SHALL be pinned for the job lifetime.

#### Scenario: Successful job with two ranges

- **WHEN** an authenticated client submits an owned video `file_id` and two non-overlapping replacements
- **THEN** the API returns HTTP 202 with `type` `replace_images`

#### Scenario: Empty replacements rejected

- **WHEN** `replacements` is omitted or empty
- **THEN** the API returns HTTP 400 with error code `EMPTY_REPLACEMENTS`

#### Scenario: Too many replacements rejected

- **WHEN** `replacements` has more than 10 items
- **THEN** the API returns HTTP 400 with error code `TOO_MANY_REPLACEMENTS`

#### Scenario: Wrong file kinds rejected

- **WHEN** `file_id` refers to an image or SRT, or `image_file_id` refers to a video or SRT
- **THEN** the API returns HTTP 400 with error code `WRONG_FILE_TYPE`

#### Scenario: Invalid range rejected

- **WHEN** `start` is negative, or `end` is less than or equal to `start`
- **THEN** the API returns HTTP 400 with error code `INVALID_RANGE`

#### Scenario: Overlapping ranges rejected

- **WHEN** two replacements satisfy `startA < endB` and `startB < endA`
- **THEN** the API returns HTTP 400 with error code `OVERLAPPING_RANGES`

#### Scenario: Missing API key

- **WHEN** the client calls `POST /v1/jobs/replace-images` without Authorization
- **THEN** the API returns HTTP 401

### Requirement: Replace-images job completion result

When a `replace_images` job reaches `done`, the status response SHALL include `result.file_id` (a newly registered MP4 owned by the job caller), `result.download_url`, `result.expires_at`, `result.filename` ending in `_replaced.mp4`, `result.content_type` of `video/mp4`, and `result.size_bytes`. The bytes SHALL be stored as a file-registry object (`uploads/{file_id}/...`) so a subsequent job can reference `result.file_id`. `download_url` SHALL be a presigned URL for that same object.

#### Scenario: Poll completed replace-images job

- **WHEN** the client polls a `replace_images` job in `done` status
- **THEN** the response includes both a `file_id` and a downloadable MP4 URL with `content_type` `video/mp4`

### Requirement: Replace-images job failure codes

When replacement fails, the job SHALL be `failed` with a structured error. The worker SHALL use `INVALID_IMAGE` when an image cannot be decoded, `INVALID_RANGE` when a range exceeds the probed duration, and `FFMPEG_ERROR` when FFmpeg encode fails for other reasons.

#### Scenario: Unreadable image

- **WHEN** a referenced image cannot be decoded
- **THEN** the job fails with error code `INVALID_IMAGE`

### Requirement: Replace-images progress

While a `replace_images` job is `processing`, `progress` SHALL advance through download, encode, and upload, tracking FFmpeg output time against source duration during encode, and SHALL be 100 when `done`. Updates SHALL reuse the existing throttle (at least 1 percentage point and 1 second).

#### Scenario: Progress on replace-images completion

- **WHEN** a replace-images job reaches `done`
- **THEN** `progress` is 100
