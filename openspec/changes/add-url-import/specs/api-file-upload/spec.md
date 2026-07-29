## ADDED Requirements

### Requirement: Acquire file via URL import job

In addition to multipart upload, clients SHALL obtain a `file_id` by completing an `import_url` job. Upon success, the system SHALL create a `FileRecord` with the same lifecycle rules (TTL, owner binding, metadata) as an uploaded file.

#### Scenario: Import creates registry entry

- **WHEN** an `import_url` job completes successfully
- **THEN** a new `file_id` exists in the file registry, bound to the caller's API key, with the downloaded file stored in object storage

#### Scenario: Imported file usable in merge job

- **WHEN** client creates a merge job referencing the `file_id` from a completed import
- **THEN** the merge job is accepted and processes the imported file

### Requirement: URL scheme policy for import

The system SHALL accept only `https://` URLs by default. When `IMPORT_URL_ALLOW_HTTP=true`, the system MAY also accept `http://` URLs. All other schemes (e.g. `file://`, `ftp://`) SHALL be rejected with error code `INVALID_URL`.

#### Scenario: HTTPS URL accepted

- **WHEN** client submits `https://cdn.example.com/video.mp4`
- **THEN** the import job is enqueued

#### Scenario: HTTP rejected by default

- **WHEN** `IMPORT_URL_ALLOW_HTTP` is false and client submits `http://example.com/video.mp4`
- **THEN** the API returns HTTP 400 with error code `INVALID_URL`

#### Scenario: HTTP allowed when configured

- **WHEN** `IMPORT_URL_ALLOW_HTTP=true` and client submits a valid `http://` URL to a public host
- **THEN** the import job is enqueued
