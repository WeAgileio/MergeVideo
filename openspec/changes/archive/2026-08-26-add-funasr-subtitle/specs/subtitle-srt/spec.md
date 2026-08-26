## ADDED Requirements

### Requirement: Forced alignment input

The subtitle pipeline SHALL accept a video file and a non-empty script string. The script SHALL be used as the subtitle text source. The system SHALL NOT run speech-to-text to invent wording, and SHALL NOT convert between Simplified and Traditional Chinese.

#### Scenario: Script text appears in cues

- **WHEN** alignment succeeds for script `你好。世界。`
- **THEN** the SRT cue texts contain `你好。` and `世界。` (or the same characters grouped by the sentence splitter), not ASR-recognized substitutes

#### Scenario: Empty script rejected before alignment

- **WHEN** the script is missing or contains only whitespace
- **THEN** the pipeline SHALL NOT invoke the alignment model

### Requirement: Sixteen kilohertz mono wav extraction

The pipeline SHALL extract audio from the input video as 16 kHz mono WAV before calling `fa-zh`. If the input has no audio stream, alignment SHALL NOT run.

#### Scenario: Video with audio is converted

- **WHEN** the input is an MP4 with an audio track
- **THEN** the aligner receives a 16 kHz mono WAV derived from that track

#### Scenario: Video without audio fails

- **WHEN** the input has no audio stream
- **THEN** processing fails with error code `NO_AUDIO_STREAM`

### Requirement: Sentence split by punctuation

The pipeline SHALL split the script into cues on `。` `！` `？` `!` `?` `；` `;` `，`. The splitting punctuation SHALL remain at the end of its cue. The pipeline SHALL NOT split on ASCII comma `,` (to avoid breaking numeric thousands separators). If the script contains none of those marks, the entire script SHALL be a single cue.

#### Scenario: Two sentences become two cues

- **WHEN** the script is `第一句。第二句。` and timestamps exist for each character
- **THEN** the SRT contains two cues whose texts are `第一句。` and `第二句。`

#### Scenario: Chinese comma splits extra cues

- **WHEN** the script is `甲，乙，丙。` and timestamps exist
- **THEN** the SRT contains three cues: `甲，` `乙，` `丙。`

#### Scenario: No punctuation is one cue

- **WHEN** the script is `沒有句號的稿` and timestamps exist
- **THEN** the SRT contains exactly one cue with that text

### Requirement: Cue timestamps from character alignment

Each cue's start time SHALL be the start of the first aligned timestamp in that cue's character slice. Each cue's end time SHALL be the end of the last aligned timestamp in that slice. Times SHALL be expressed in milliseconds internally and formatted as SRT `HH:MM:SS,mmm`.

#### Scenario: Cue uses first and last character times

- **WHEN** a sentence's characters have timestamps `[[100, 200], [200, 350], [350, 400]]`
- **THEN** that cue's time range is `00:00:00,100 --> 00:00:00,400`

#### Scenario: No timestamps fail alignment

- **WHEN** the aligner returns an empty timestamp list
- **THEN** processing fails with error code `ALIGN_FAILED`

### Requirement: Standard SRT without speaker labels

The output SHALL be UTF-8 (no BOM) standard SRT: sequential integer index starting at 1, a time line `start --> end`, cue text, then a blank line. Cue text SHALL NOT be prefixed with speaker tags such as `Speaker 1:` or `[spk]`.

#### Scenario: Valid two-cue file shape

- **WHEN** two sentences are aligned successfully
- **THEN** the file matches SRT structure with indexes `1` and `2` and contains no speaker prefix

#### Scenario: Filename uses srt extension

- **WHEN** the source filename stem is `talk`
- **THEN** the result filename is `talk.srt`
