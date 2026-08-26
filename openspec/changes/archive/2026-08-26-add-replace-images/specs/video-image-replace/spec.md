## ADDED Requirements

### Requirement: Replace full frames with images for time ranges

The pipeline SHALL overlay each replacement image onto the video as opaque full-frame pixels for `[start, end]` seconds (inclusive of both ends in ffmpeg `between`). Outside those ranges the original video SHALL remain. Audio SHALL be stream-copied when an audio track exists. Output duration SHALL equal the source duration. The pipeline SHALL NOT change pitch, volume, or audio codec.

Each image SHALL be fit with contain: scale uniformly to fit inside the video frame, centered, with black bars in the unused region. The pipeline SHALL NOT crop or stretch. Transparent pixels SHALL be composited onto black before overlay.

The pipeline SHALL always re-encode video (H.264). It SHALL NOT use stream copy for the video track.

#### Scenario: Single range covers the frame

- **WHEN** replace-images runs with one range 3.0–5.0 on a 10 second video
- **THEN** frames from 3.0s through 5.0s show only the contained image (plus black bars if needed), and audio matches the source

#### Scenario: Duration unchanged

- **WHEN** the source video is 30.75 seconds
- **THEN** the output duration is 30.75 seconds

#### Scenario: Contain letterboxes a mismatched image

- **WHEN** the video is 1080×1920 and the image is 1920×1080
- **THEN** the image is fully visible, centered, with black bars above and below (not cropped, not stretched)

### Requirement: Multiple non-overlapping ranges in one run

The pipeline SHALL apply every range in `replacements` on the same encode. Adjacent ranges that share an endpoint (`end` of A equals `start` of B) SHALL be allowed. Intersecting ranges SHALL fail before encode.

#### Scenario: Two adjacent ranges

- **WHEN** ranges are 1.0–2.0 and 2.0–3.0
- **THEN** both images are applied and processing succeeds

#### Scenario: Overlapping ranges rejected

- **WHEN** ranges are 1.0–3.0 and 2.0–4.0
- **THEN** processing is not started with error code `OVERLAPPING_RANGES`

### Requirement: Replace-images output is a registered video file

The pipeline SHALL write an MP4 (H.264). The output filename stem SHALL derive from the source video stem with a `_replaced` suffix (for example `talk_replaced.mp4`). After success the system SHALL persist the file in the file registry as a new object owned by the same API key as the job, with `content_type` `video/mp4`. File TTL SHALL follow `FILE_TTL_HOURS` like uploaded files. The file SHALL remain addressable by `file_id` so a later job (for example burn-subtitle) can use it as `file_id`.

#### Scenario: Output naming

- **WHEN** the source video filename is `talk.mp4`
- **THEN** the result filename is `talk_replaced.mp4`

#### Scenario: Result can be used by a later job

- **WHEN** replace-images completes and the client passes `result.file_id` as `file_id` to burn-subtitle
- **THEN** the burn job is accepted (assuming the SRT `srt_file_id` is also valid)

### Requirement: Unreadable image fails

The pipeline SHALL fail with error code `INVALID_IMAGE` when an image file cannot be decoded. FFmpeg encode failures SHALL use `FFMPEG_ERROR` and SHALL NOT be labelled `INVALID_IMAGE`. Ranges past the probed video duration SHALL fail with `INVALID_RANGE`.

#### Scenario: Corrupt image

- **WHEN** an `image_file_id` is a non-empty file that is not a decodable image
- **THEN** processing fails with error code `INVALID_IMAGE`

#### Scenario: End after duration

- **WHEN** `end` is greater than the source video duration
- **THEN** processing fails with error code `INVALID_RANGE`
