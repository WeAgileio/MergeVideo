## ADDED Requirements

### Requirement: Burn subtitles with configurable size and bottom margin

The burn-in pipeline SHALL overlay a standard SRT onto a video as hard-burned pixels (not a soft subtitle track). Cue text SHALL be horizontally centered at the bottom of the frame. The pipeline SHALL use the bundled Taipei Sans TC Beta Regular typeface. Glyphs SHALL be white with a black outline. The pipeline SHALL NOT accept a caller-supplied font file, alignment, or colour.

Font size SHALL default to 48 when omitted. Bottom margin SHALL default to 6 percent of the video frame height when omitted. The caller MAY set `font_size` (integer 1–512), `margin_bottom`, and `margin_unit` of `px` or `percent`. When `margin_unit` is `percent`, the pixel offset from the bottom SHALL be `round(frame_height * margin_bottom / 100)`. When `margin_unit` is `px`, the offset SHALL equal `margin_bottom`.

Burn-in SHALL always re-encode video (H.264). It SHALL NOT use stream copy for the video track.

#### Scenario: Defaults applied

- **WHEN** burn-in runs without font or margin overrides
- **THEN** FontSize is 48 and the subtitle baseline sits 6 percent of the frame height above the bottom edge, centered horizontally

#### Scenario: Pixel margin

- **WHEN** burn-in runs with `margin_bottom` 80 and `margin_unit` `px` on a 1920×1080 video
- **THEN** the pixel offset from the bottom is 80

#### Scenario: Percent margin on a vertical video

- **WHEN** burn-in runs with `margin_bottom` 6 and `margin_unit` `percent` on a 1080×1920 video
- **THEN** the pixel offset from the bottom is 115

#### Scenario: Bundled font is used

- **WHEN** burn-in renders Chinese cue text
- **THEN** glyphs come from Taipei Sans TC Beta Regular, not a system fallback sans

### Requirement: Burn-in output is a video file

The pipeline SHALL write an MP4 (H.264). Audio SHALL be stream-copied when an audio track exists. The output filename stem SHALL derive from the source video stem with a `_burned` suffix (for example `talk_burned.mp4`).

#### Scenario: Output naming

- **WHEN** the source video filename is `talk.mp4`
- **THEN** the result filename is `talk_burned.mp4`

### Requirement: Invalid SRT fails before or during burn

The pipeline SHALL fail with error code `INVALID_SRT` when the subtitle file cannot be parsed as SRT containing at least one cue. The pipeline SHALL fail with `FONT_UNAVAILABLE` when the bundled font file is missing. FFmpeg encode failures SHALL use `FFMPEG_ERROR` and SHALL NOT be labelled `INVALID_SRT`.

#### Scenario: Empty subtitle file

- **WHEN** the SRT file has no cues
- **THEN** processing fails with error code `INVALID_SRT`

#### Scenario: Font file missing

- **WHEN** the configured font path does not exist
- **THEN** processing fails with error code `FONT_UNAVAILABLE`
