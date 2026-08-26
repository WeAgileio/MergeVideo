## MODIFIED Requirements

### Requirement: File expiration

Uploaded files SHALL support an optional TTL controlled by `FILE_TTL_HOURS`. When `FILE_TTL_HOURS` is `0` (default), files SHALL NOT expire and SHALL remain referenceable indefinitely until manually deleted. When `FILE_TTL_HOURS` is greater than `0`, files SHALL expire after that many hours; expired files SHALL NOT be referenceable in new jobs unless pinned by an active job. When a file is referenced by an active job, the system SHALL pin the file until the job completes.

#### Scenario: No expiration by default

- **WHEN** a file is uploaded with default configuration (`FILE_TTL_HOURS=0`)
- **THEN** the file remains accessible via API indefinitely and `expires_at` in responses is `null`

#### Scenario: Expired file rejected when TTL configured

- **WHEN** `FILE_TTL_HOURS` is greater than `0` and client references a `file_id` whose `expires_at` has passed and no active job holds a pin
- **THEN** the API returns HTTP 404 with error code `FILE_NOT_FOUND`

#### Scenario: Active job pins file

- **WHEN** a job referencing the file is in `queued` or `processing` status
- **THEN** the file remains accessible until the job reaches `done` or `failed`

### Requirement: Query file metadata

The API SHALL provide `GET /v1/files/{file_id}` returning file metadata including `filename`, `size_bytes`, `expires_at`, and `created_at`. When the file has no expiration (`FILE_TTL_HOURS=0`), `expires_at` SHALL be `null`. Optionally, the response MAY include ffprobe metadata (width, height, fps, codec, duration) if probed at upload time.

#### Scenario: Query own file without expiration

- **WHEN** owner requests `GET /v1/files/{file_id}` for a file with no TTL
- **THEN** the API returns HTTP 200 with `expires_at: null`

#### Scenario: Query own file with expiration

- **WHEN** owner requests `GET /v1/files/{file_id}` for a valid non-expired file with TTL configured
- **THEN** the API returns HTTP 200 with file metadata including a non-null `expires_at`

#### Scenario: Query non-existent or expired file

- **WHEN** client requests a file that does not exist, or has expired when TTL is enabled
- **THEN** the API returns HTTP 404 with error code `FILE_NOT_FOUND`

## ADDED Requirements

### Requirement: Configurable background cleanup for uploads

When `AUTO_CLEANUP_ENABLED=true` and `FILE_TTL_HOURS` is greater than `0`, the worker SHALL periodically delete uploaded files from object storage and the file registry when `expires_at` has passed and `active_jobs` is zero. When `AUTO_CLEANUP_ENABLED=false` (default), the worker SHALL NOT delete uploaded files automatically.

#### Scenario: Cleanup disabled by default

- **WHEN** default configuration is used and a file's `expires_at` is in the past
- **THEN** the file record and storage object remain until manually deleted

#### Scenario: Cleanup removes expired uploads when enabled

- **WHEN** `AUTO_CLEANUP_ENABLED=true`, `FILE_TTL_HOURS=24`, and an unpinned file is past expiration
- **THEN** the worker removes the file from storage and registry

#### Scenario: Cleanup interval configurable

- **WHEN** `AUTO_CLEANUP_ENABLED=true` and `CLEANUP_INTERVAL_SECONDS` is set
- **THEN** the worker runs cleanup at most once per configured interval
