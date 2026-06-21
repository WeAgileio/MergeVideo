# video-last-frame Specification

## Purpose
TBD - created by archiving change video-last-frame. Update Purpose after archive.
## Requirements
### Requirement: Accept single video file input

The CLI SHALL accept exactly one video file path as input. If the path is a directory, the system SHALL exit with an error. If the path does not exist, the system SHALL exit with an error.

#### Scenario: Valid video file

- **WHEN** user runs `VideoLastFrame ./clips/1.mp4` and the file exists with a video stream
- **THEN** the system proceeds to extract the last frame

#### Scenario: Input is a directory

- **WHEN** user provides a folder path instead of a file
- **THEN** the system exits with an error indicating a single video file is required

#### Scenario: File not found

- **WHEN** the input path does not exist
- **THEN** the system exits with an error

### Requirement: Extract last video frame

The system SHALL use FFmpeg to extract the last frame of the video. The system SHALL verify via ffprobe that a video stream exists before extraction.

#### Scenario: Successful extraction

- **WHEN** the input is a valid video file
- **THEN** the system writes a PNG image containing the last frame

#### Scenario: No video stream

- **WHEN** the input file has no video stream
- **THEN** the system exits with an error before extraction

#### Scenario: ffmpeg unavailable

- **WHEN** ffmpeg or ffprobe is not found on PATH
- **THEN** the system exits with an error

### Requirement: Output path and naming

The system SHALL write output to `{video_directory}/output/{stem}_LastFrame.png`, creating the `output` directory if it does not exist. The image format SHALL be PNG.

#### Scenario: Default output for 1.mp4

- **WHEN** user runs `VideoLastFrame ./clips/1.mp4`
- **THEN** output is written to `./clips/output/1_LastFrame.png`

#### Scenario: Output directory creation

- **WHEN** `{video_directory}/output/` does not exist
- **THEN** the system creates it before writing the file

### Requirement: Overwrite existing output

When the output file already exists, the system SHALL overwrite it without error.

#### Scenario: Output file exists

- **WHEN** `./clips/output/1_LastFrame.png` already exists
- **THEN** the system overwrites it with the newly extracted frame

### Requirement: Report completion

After successful extraction, the system SHALL print the output file path to stdout.

#### Scenario: Success message

- **WHEN** extraction completes successfully
- **THEN** the system prints the full output path

