## ADDED Requirements

### Requirement: Create import URL job

The API SHALL provide `POST /v1/jobs/import-url` accepting JSON body with `url` (required, string) and optional `filename` (string). The API SHALL return HTTP 202 with `job_id`, `type: "import_url"`, `status: "queued"`, and `status_url`. The API SHALL perform basic URL format and scheme validation before enqueueing; SSRF checks SHALL occur in the worker before download.

#### Scenario: Successful import job creation

- **WHEN** authenticated client submits a valid HTTPS URL
- **THEN** the API returns HTTP 202 with a unique `job_id` and status `queued`

#### Scenario: Invalid URL rejected at API

- **WHEN** client submits a malformed URL or disallowed scheme
- **THEN** the API returns HTTP 400 with error code `INVALID_URL`

### Requirement: Import URL job completion result

When an `import_url` job reaches `done`, the response SHALL include a `result` object with `file_id`, `filename`, `size_bytes`, and `expires_at`. The result SHALL NOT include `download_url` (the imported file is input material, not a deliverable).

#### Scenario: Poll completed import job

- **WHEN** client polls an import job in `done` status
- **THEN** the response includes `result.file_id` and `result.filename`

### Requirement: Import URL download progress

While an `import_url` job is `processing`, progress SHALL reflect download status when `Content-Length` is available: bytes downloaded divided by content length, scaled to 0–90 during download, then 100 when the file registry entry is created. When `Content-Length` is unavailable, progress MAY remain at 0 until completion.

#### Scenario: Progress during download with Content-Length

- **WHEN** import job is downloading and half of the declared content length has been received
- **THEN** polling returns `progress` approximately 45

#### Scenario: Progress on import completion

- **WHEN** import job reaches `done`
- **THEN** `progress` is 100

### Requirement: Import URL SSRF protection

Before downloading, the worker SHALL resolve the URL hostname to IP addresses and reject the request if any resolved IP is private, loopback, link-local, or a known cloud metadata address. The worker SHALL follow at most `IMPORT_URL_MAX_REDIRECTS` redirects (default 3) and re-apply IP checks after each redirect. Blocked requests SHALL fail the job with error code `URL_NOT_ALLOWED`.

#### Scenario: Private IP blocked

- **WHEN** worker resolves URL hostname to `127.0.0.1` or `10.0.0.1`
- **THEN** job fails with error code `URL_NOT_ALLOWED`

#### Scenario: Redirect to private IP blocked

- **WHEN** URL redirects to a host resolving to a private IP
- **THEN** job fails with error code `URL_NOT_ALLOWED`

### Requirement: Import URL download limits

The worker SHALL enforce the same maximum file size as upload (`MAX_FILE_SIZE_MB`, default 200). The worker SHALL enforce connect timeout (default 10 seconds) and total download timeout (default 10 minutes), configurable via environment variables. Exceeding size SHALL fail with `FILE_TOO_LARGE`; timeout or connection failure SHALL fail with `DOWNLOAD_FAILED`.

#### Scenario: File too large during download

- **WHEN** downloaded bytes exceed the configured maximum
- **THEN** job fails with error code `FILE_TOO_LARGE`

#### Scenario: Download timeout

- **WHEN** download does not complete within total timeout
- **THEN** job fails with error code `DOWNLOAD_FAILED`

### Requirement: Import URL format validation

After download, the worker SHALL validate the file extension against supported video formats and verify a video stream exists via ffprobe, consistent with upload validation. Invalid files SHALL fail with `UNSUPPORTED_FORMAT`.

#### Scenario: Non-video file rejected

- **WHEN** downloaded content is not a supported video format
- **THEN** job fails with error code `UNSUPPORTED_FORMAT`

### Requirement: API key authentication for import URL endpoint

`POST /v1/jobs/import-url` SHALL require valid API key authentication. Unauthenticated requests SHALL return HTTP 401.

#### Scenario: Missing API key

- **WHEN** client calls `POST /v1/jobs/import-url` without Authorization header
- **THEN** the API returns HTTP 401
