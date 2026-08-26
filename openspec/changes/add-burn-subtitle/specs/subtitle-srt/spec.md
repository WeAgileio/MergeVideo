## ADDED Requirements

### Requirement: Aligned SRT is registered as a file

After successful alignment, the system SHALL persist the generated SRT in the file registry as a new object owned by the same API key as the job. The registered file SHALL have `content_type` `application/x-subrip` and a filename ending in `.srt`. The SRT SHALL remain addressable by `file_id` after the job completes so a later burn-in job can use it as input. File TTL SHALL follow the same `FILE_TTL_HOURS` rules as uploaded files.

#### Scenario: Alignment produces a registry file

- **WHEN** generate-subtitle alignment succeeds for a video whose stem is `talk`
- **THEN** a new file record exists with filename `talk.srt` and can be fetched by the returned `file_id`
