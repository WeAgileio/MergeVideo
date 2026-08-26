## ADDED Requirements

### Requirement: Upload SRT via HTTP multipart

The API SHALL accept a `.srt` file via `POST /v1/files` with `Content-Type: multipart/form-data` and field name `file`. Successful upload SHALL return HTTP 201 with a `file_id`, original `filename`, `size_bytes`, `content_type` of `application/x-subrip`, and `expires_at`. The file SHALL be bound to the caller `owner_key` like video uploads. The API SHALL NOT require a video stream or ffprobe metadata for `.srt`. Empty files SHALL be rejected with `EMPTY_FILE`. Size SHALL obey `MAX_FILE_SIZE_MB`. Unsupported extensions (for example `.txt`) SHALL continue to be rejected with `UNSUPPORTED_FORMAT`.

#### Scenario: Successful SRT upload

- **WHEN** an authenticated client uploads a non-empty `talk.srt`
- **THEN** the API returns HTTP 201 with a `file_id` and `content_type` `application/x-subrip`

#### Scenario: SRT can be referenced in a burn job

- **WHEN** the owner creates `POST /v1/jobs/burn-subtitle` with that `file_id` as `srt_file_id`
- **THEN** the job is accepted (assuming the video `file_id` is valid)
