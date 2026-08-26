## ADDED Requirements

### Requirement: Upload image via HTTP multipart

The API SHALL accept `.png`, `.jpg`, `.jpeg`, and `.webp` via `POST /v1/files` with `Content-Type: multipart/form-data` and field name `file`. Successful upload SHALL return HTTP 201 with a `file_id`, original `filename`, `size_bytes`, `content_type` of `image/png`, `image/jpeg`, or `image/webp` as appropriate, and `expires_at`. The file SHALL be bound to the caller `owner_key` like video uploads. The API SHALL NOT require a video stream or ffprobe metadata for images. Empty files SHALL be rejected with `EMPTY_FILE`. Size SHALL obey `MAX_FILE_SIZE_MB`. Unsupported extensions SHALL continue to be rejected with `UNSUPPORTED_FORMAT`. CLI video scanning SHALL NOT treat image extensions as mergeable videos.

#### Scenario: Successful PNG upload

- **WHEN** an authenticated client uploads a non-empty `slide.png`
- **THEN** the API returns HTTP 201 with a `file_id` and `content_type` `image/png`

#### Scenario: Image can be referenced in a replace-images job

- **WHEN** the owner creates `POST /v1/jobs/replace-images` with that `file_id` as a replacement `image_file_id`
- **THEN** the job is accepted (assuming the video `file_id` and times are valid)
