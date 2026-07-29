## ADDED Requirements

### Requirement: Upload video via HTTP multipart

The API SHALL accept a single video file via `POST /v1/files` with `Content-Type: multipart/form-data` and field name `file`. The API SHALL validate that the file is a supported video format (at least `.mp4`, `.mov`, `.webm`, `.mkv`, `.avi`, `.m4v`). The API SHALL reject files exceeding 200 MB with error code `FILE_TOO_LARGE`.

#### Scenario: Successful upload

- **WHEN** authenticated client uploads a valid 50 MB `.mp4` file
- **THEN** the API returns HTTP 201 with a unique `file_id`, original `filename`, `size_bytes`, and `expires_at`

#### Scenario: File too large

- **WHEN** authenticated client uploads a file larger than 200 MB
- **THEN** the API returns HTTP 413 with error code `FILE_TOO_LARGE`

#### Scenario: Unsupported format

- **WHEN** authenticated client uploads a file with unsupported extension (e.g. `.txt`)
- **THEN** the API returns HTTP 400 with an appropriate error code

### Requirement: Store uploaded file in object storage

Upon successful upload, the system SHALL persist the file to object storage at a path keyed by `file_id`. The system SHALL record the storage path in the file registry.

#### Scenario: File persisted after upload

- **WHEN** upload completes successfully
- **THEN** the file is accessible in object storage and retrievable by the registered storage path

### Requirement: Switchable storage backend

The storage backend SHALL be selected at service startup via the `STORAGE_BACKEND` environment variable. Supported backends SHALL include: `local` (local directory, dev), `s3` (AWS S3 and S3-compatible services such as MinIO / Cloudflare R2 / Alibaba OSS / Tencent COS), `gcs` (Google Cloud Storage), `azure` (Azure Blob Storage), and `rclone` (any rclone-configured remote, covering Google Drive / OneDrive / Dropbox and other consumer cloud drives). All backends SHALL implement the same interface (put, fetch, delete, delete_prefix, presigned_url) so that upload, worker, and cleanup logic are backend-agnostic.

#### Scenario: Start with S3 backend

- **WHEN** the service starts with `STORAGE_BACKEND=s3` and S3 credentials configured
- **THEN** uploads and results are stored in the configured S3 bucket, and download URLs are presigned S3 URLs

#### Scenario: Start with rclone backend for Google Drive or OneDrive

- **WHEN** the service starts with `STORAGE_BACKEND=rclone` and `RCLONE_REMOTE` pointing to a configured rclone remote (e.g. `gdrive:mergevideo`, `onedrive:mergevideo`)
- **THEN** files are stored on that remote and download URLs are share links produced by `rclone link`

#### Scenario: Unknown backend rejected

- **WHEN** the service starts with an unrecognized `STORAGE_BACKEND` value
- **THEN** the service fails to start with a clear error listing supported backends

#### Scenario: Missing backend configuration rejected

- **WHEN** the service starts with `STORAGE_BACKEND=rclone` without `RCLONE_REMOTE` (or `azure` without connection string)
- **THEN** the service fails to start with a clear configuration error

### Requirement: Return opaque file identifier

The API SHALL assign each uploaded file a non-guessable `file_id` (UUID or nanoid). The `file_id` SHALL be used by clients to reference the file in subsequent job requests.

#### Scenario: Unique file IDs

- **WHEN** two files are uploaded sequentially
- **THEN** each receives a distinct `file_id`

### Requirement: File ownership binding

Each file SHALL be bound to the authenticated API key (`owner_key`). Only the owning client SHALL be able to reference the file in job creation or query file metadata.

#### Scenario: Owner can reference file in job

- **WHEN** client A uploads a file and creates a job referencing its `file_id`
- **THEN** the job is accepted

#### Scenario: Non-owner cannot reference file

- **WHEN** client B attempts to create a job referencing client A's `file_id`
- **THEN** the API returns HTTP 403 with error code `UNAUTHORIZED_FILE`

### Requirement: File expiration

Uploaded files SHALL have a TTL (default 24 hours). When a file is referenced by an active job, the system SHALL extend or pin the file until the job completes. Expired files SHALL NOT be referenceable in new jobs.

#### Scenario: Expired file rejected

- **WHEN** client references a `file_id` whose `expires_at` has passed and no active job holds a pin
- **THEN** the API returns HTTP 404 with error code `FILE_NOT_FOUND`

#### Scenario: Active job pins file

- **WHEN** a job referencing the file is in `queued` or `processing` status
- **THEN** the file remains accessible until the job reaches `done` or `failed`

### Requirement: Query file metadata

The API SHALL provide `GET /v1/files/{file_id}` returning file metadata including `filename`, `size_bytes`, `expires_at`, and `created_at`. Optionally, the response MAY include ffprobe metadata (width, height, fps, codec, duration) if probed at upload time.

#### Scenario: Query own file

- **WHEN** owner requests `GET /v1/files/{file_id}` for a valid file
- **THEN** the API returns HTTP 200 with file metadata

#### Scenario: Query non-existent or expired file

- **WHEN** client requests a file that does not exist or has expired
- **THEN** the API returns HTTP 404 with error code `FILE_NOT_FOUND`

### Requirement: Delete uploaded file

The API SHALL provide `DELETE /v1/files/{file_id}` allowing the owner to delete the file from object storage and the registry, unless the file is pinned by an active job.

#### Scenario: Delete own unused file

- **WHEN** owner deletes a file not referenced by any active job
- **THEN** the file is removed from storage and registry, and subsequent references return `FILE_NOT_FOUND`

#### Scenario: Delete pinned file rejected

- **WHEN** owner attempts to delete a file pinned by an active job
- **THEN** the API returns HTTP 409 with an appropriate error code

### Requirement: API key authentication for file endpoints

All `/v1/files` endpoints SHALL require valid API key authentication via `Authorization: Bearer <api_key>`. Unauthenticated requests SHALL return HTTP 401.

#### Scenario: Missing API key

- **WHEN** client calls `POST /v1/files` without Authorization header
- **THEN** the API returns HTTP 401
