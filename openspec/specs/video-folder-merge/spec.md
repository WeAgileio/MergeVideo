# video-folder-merge Specification

## Purpose
TBD - created by archiving change merge-videos-cli. Update Purpose after archive.
## Requirements
### Requirement: Scan folder for numeric-named videos

The CLI SHALL scan the given input folder for video files with numeric-only stems (matching `^\d+$`, e.g. `1.mp4`, `02.mov`). Supported extensions SHALL include at least `.mp4`, `.mov`, `.webm`, `.mkv`. Files SHALL be sorted in natural numeric order (1, 2, 10 — not 1, 10, 2).

#### Scenario: Valid folder with multiple videos

- **WHEN** the input folder contains `1.mp4`, `2.mp4`, `10.mp4`
- **THEN** the system discovers 3 videos in order [1, 2, 10]

#### Scenario: Non-numeric filename present

- **WHEN** the input folder contains `1.mp4` and `intro.mp4`
- **THEN** the system exits with an error listing the invalid filename(s)

#### Scenario: Only one video found

- **WHEN** the input folder contains only `1.mp4`
- **THEN** the system exits with an error indicating at least 2 videos are required

#### Scenario: No videos found

- **WHEN** the input folder contains no video files
- **THEN** the system exits with an error indicating no videos were found

### Requirement: Probe video metadata

The system SHALL use ffprobe to extract each video's width, height, fps, video codec, pixel format, and audio presence (codec, sample rate, channels if present).

#### Scenario: Successful probe

- **WHEN** all discovered videos are valid media files
- **THEN** the system collects metadata for each and displays it in an analysis report

#### Scenario: ffprobe unavailable

- **WHEN** ffprobe is not found on the system PATH
- **THEN** the system exits with an error before attempting merge

### Requirement: Determine output resolution from largest segment

The system SHALL set output resolution to the width and height of the segment with the largest pixel area (width × height). If multiple segments tie, the system SHALL use the segment that appears first in the sorted order.

#### Scenario: Mixed resolutions

- **WHEN** segments are 1920×1080 and 1280×720
- **THEN** output resolution is 1920×1080

### Requirement: Analyze copy compatibility

The system SHALL determine whether copy mode is viable. Copy mode is viable only when ALL segments share identical width, height, video codec, pixel format, fps, and consistent audio (all have audio with matching codec/sample rate/channels, OR all have no audio).

#### Scenario: All segments identical

- **WHEN** all segments have the same resolution, codec, fps, and audio format
- **THEN** copy mode is reported as available

#### Scenario: Resolution mismatch

- **WHEN** any segment differs in width or height
- **THEN** copy mode is reported as unavailable with reason

#### Scenario: Mixed audio presence

- **WHEN** some segments have audio and others do not
- **THEN** copy mode is reported as unavailable with reason

### Requirement: Interactive mode selection

When no `--mode` flag is provided and `--dry-run` is not set, the system SHALL display an analysis report and prompt the user to choose Copy, Encode, or Quit. Copy option SHALL be disabled when copy is not viable.

#### Scenario: User selects encode interactively

- **WHEN** the user enters E at the prompt
- **THEN** the system proceeds with encode merge

#### Scenario: User selects copy when available

- **WHEN** copy is viable and the user enters C at the prompt
- **THEN** the system proceeds with copy merge without re-encoding

#### Scenario: User quits

- **WHEN** the user enters Q at the prompt
- **THEN** the system exits without merging

### Requirement: Non-interactive mode flags

The system SHALL support `--mode auto`, `--mode copy`, and `--mode encode`. Auto mode SHALL use copy when viable, otherwise encode. Copy mode SHALL exit with error if copy is not viable.

#### Scenario: Auto mode with compatible segments

- **WHEN** `--mode auto` is used and segments are copy-compatible
- **THEN** the system merges using copy without prompting

#### Scenario: Auto mode with incompatible segments

- **WHEN** `--mode auto` is used and segments are not copy-compatible
- **THEN** the system merges using encode without prompting

#### Scenario: Copy mode when incompatible

- **WHEN** `--mode copy` is used but segments are not copy-compatible
- **THEN** the system exits with an error

### Requirement: Encode merge with normalization

In encode mode, the system SHALL re-encode all segments to a unified output: H.264 video at the determined output resolution (scale to fit + black padding, no crop/stretch), AAC audio at 48000 Hz stereo. Segments without audio SHALL receive a silent audio track of matching duration.

#### Scenario: Segment smaller than output

- **WHEN** a 1280×720 segment is merged into 1920×1080 output
- **THEN** the segment is scaled proportionally and padded with black bars

#### Scenario: Segment without audio

- **WHEN** a segment has no audio track
- **THEN** a silent audio track is inserted for that segment's duration

### Requirement: Copy merge without re-encoding

In copy mode, the system SHALL concatenate segments using FFmpeg concat demuxer with stream copy (`-c copy`).

#### Scenario: Successful copy merge

- **WHEN** copy mode is selected and segments are compatible
- **THEN** the output file contains all segments concatenated without re-encoding

### Requirement: Default output path and naming

When `-o` is not specified, the system SHALL create an `output` directory inside the input folder (i.e. `<input_folder>/output/`) if it does not exist, and write the merged file as `mergedYYYYMMDDHHmmss.mp4` using the current local timestamp.

#### Scenario: Default output

- **WHEN** user runs `mergevideo ./clips` without `-o` at 2026-06-19 12:09:30
- **THEN** output is written to `./clips/output/merged20260619120930.mp4`

#### Scenario: Custom output path

- **WHEN** user specifies `-o /path/to/final.mp4`
- **THEN** output is written to the specified path

### Requirement: Dry run analysis only

When `--dry-run` is specified, the system SHALL perform scanning, validation, probing, and compatibility analysis, display the report, and exit without merging.

#### Scenario: Dry run

- **WHEN** user runs with `--dry-run`
- **THEN** no output video file is created

