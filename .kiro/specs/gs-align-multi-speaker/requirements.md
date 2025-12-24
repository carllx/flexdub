# Requirements Document

## Introduction

This feature improves the `gs_align` functionality to generate complete, high-quality `audio.srt` files from `gs.md` reference documents. The current implementation produces incomplete output (240 entries vs 414 needed) and lacks multi-speaker support required for proper TTS voice mapping.

## Glossary

- **gs.md**: A human-edited reference document containing high-quality Chinese translations with time anchors and speaker information
- **audio.srt**: The TTS-optimized subtitle file used for speech synthesis
- **SRT**: SubRip subtitle format with index, timestamps, and text content
- **Time_Anchor**: A timestamp marker in gs.md format `### [MM:SS] Speaker_Name`
- **Speaker_Tag**: A marker indicating which speaker is talking, used for voice mapping
- **voice_map.json**: Configuration file mapping speaker names to TTS voice identifiers
- **Doubao_TTS**: The default TTS backend service with 75-character limit per segment
- **Alignment_System**: The component that maps gs.md translations to original SRT timeline

## Requirements

### Requirement 1: Complete Timeline Coverage

**User Story:** As a dubbing engineer, I want the generated audio.srt to cover the entire video duration, so that no content is missing from the dubbed output.

#### Acceptance Criteria

1. WHEN generating audio.srt from gs.md and original SRT, THE Alignment_System SHALL produce entries covering the full original SRT timeline
2. WHEN gs.md time anchors do not cover the entire video, THE Alignment_System SHALL fall back to original SRT translations for uncovered segments
3. THE Alignment_System SHALL preserve all original SRT entry count (414 entries for the test case)
4. WHEN a segment falls between gs.md anchors, THE Alignment_System SHALL use the translation from the preceding anchor's content

### Requirement 2: Multi-Speaker Detection and Tagging

**User Story:** As a dubbing engineer, I want speaker information extracted from gs.md, so that different voices can be assigned to different speakers.

#### Acceptance Criteria

1. WHEN parsing gs.md anchors, THE Alignment_System SHALL extract speaker names from anchor headers (e.g., `### [21:00] 观众提问 1`)
2. THE Alignment_System SHALL support at least 3 distinct speakers per video
3. WHEN a speaker change occurs, THE Alignment_System SHALL tag subsequent SRT entries with the new speaker until another change
4. THE Alignment_System SHALL output speaker tags in a format compatible with voice_map.json lookup

### Requirement 3: Speaker-to-Voice Mapping

**User Story:** As a dubbing engineer, I want automatic voice assignment based on speaker tags, so that each speaker has a consistent TTS voice.

#### Acceptance Criteria

1. WHEN voice_map.json exists, THE Alignment_System SHALL read speaker-to-voice mappings from it
2. WHEN a speaker is not found in voice_map.json, THE Alignment_System SHALL use the DEFAULT voice
3. THE Alignment_System SHALL validate that all speakers in gs.md have corresponding voice mappings
4. WHEN generating voice_map.json, THE Alignment_System SHALL extract all unique speakers from gs.md

### Requirement 4: Text Quality for TTS

**User Story:** As a dubbing engineer, I want the generated text to be optimized for TTS synthesis, so that the audio output sounds natural.

#### Acceptance Criteria

1. THE Alignment_System SHALL remove markdown formatting (bold, headers, lists) from output text
2. THE Alignment_System SHALL remove image descriptions (e.g., `**[05:07]** 画面内容：...`)
3. THE Alignment_System SHALL split segments exceeding 75 characters at natural sentence boundaries
4. WHEN splitting long segments, THE Alignment_System SHALL preserve the original timestamp proportionally
5. THE Alignment_System SHALL remove oral fillers and hesitation markers from the text

### Requirement 5: Glossary Consistency

**User Story:** As a dubbing engineer, I want terminology to be consistent throughout the translation, so that proper nouns and technical terms are translated uniformly.

#### Acceptance Criteria

1. WHEN glossary.yaml exists, THE Alignment_System SHALL load term mappings
2. THE Alignment_System SHALL verify that gs.md translations use glossary terms consistently
3. IF inconsistent terminology is detected, THE Alignment_System SHALL log a warning with the specific term and location

### Requirement 6: Fallback Handling

**User Story:** As a dubbing engineer, I want graceful handling when gs.md coverage is incomplete, so that the pipeline doesn't fail.

#### Acceptance Criteria

1. WHEN gs.md ends before the video ends, THE Alignment_System SHALL use original SRT text for remaining segments
2. WHEN original SRT text is used as fallback, THE Alignment_System SHALL log which segments used fallback
3. THE Alignment_System SHALL report coverage statistics (percentage of video covered by gs.md)
4. IF gs.md coverage is below 80%, THE Alignment_System SHALL emit a warning

### Requirement 7: Output Format Compatibility

**User Story:** As a dubbing engineer, I want the output to be compatible with the existing FlexDub pipeline, so that no downstream changes are needed.

#### Acceptance Criteria

1. THE Alignment_System SHALL output valid SRT format parseable by the `srt` library
2. THE Alignment_System SHALL preserve original SRT index numbers
3. THE Alignment_System SHALL preserve original SRT timestamps exactly
4. WHEN speaker tags are included, THE Alignment_System SHALL use format `[Speaker: Name] Text` at the start of content
