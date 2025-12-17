# Requirements Document: Agent Orchestration System for flexdub

## Introduction

This specification defines an AI agent system that orchestrates the flexdub dubbing pipeline. The agent will guide users through a structured workflow based on decision matrices, enforce text immutability principles, and manage multi-stage processing from semantic restructuring through final video output.

## Glossary

- **Agent**: The AI assistant that executes tasks according to the plan documents
- **LLM Stage**: Semantic operations (text cleaning, restructuring, terminology preservation)
- **Script Stage**: Timeline and media operations (rebalance, TTS, mux, audit)
- **CPM**: Characters Per Minute - metric for subtitle density
- **Dual-Track SRT**: Display SRT (for screen) and Audio SRT (for TTS)
- **Text Immutability**: Principle that text content cannot change after LLM stage
- **Decision Matrix**: Task routing table mapping operations to LLM or Script stage
- **Clustered Synthesis**: Macro-synthesis with micro-splitting to preserve timing anchors
- **Semantic Restructure**: Merging fragmented subtitles into complete sentences for TTS

## Requirements

### Requirement 1: Decision Matrix Management

**User Story:** As a developer, I want the agent to route tasks correctly between LLM and Script stages, so that semantic operations never happen in script stage and text remains immutable.

#### Acceptance Criteria

1. WHEN the agent receives a task request THEN the system SHALL classify it as either semantic (LLM) or media (Script) based on the decision matrix
2. WHEN a semantic task is identified THEN the system SHALL execute LLM operations before any script operations
3. WHEN a script stage operation is requested THEN the system SHALL verify text immutability by comparing original and processed text
4. WHEN text mutation is detected in script stage THEN the system SHALL raise a RuntimeError and halt execution
5. WHEN the decision matrix has ≥95% coverage of existing commands THEN the system SHALL be considered complete

### Requirement 2: Semantic-First Workflow Execution

**User Story:** As a user, I want the agent to automatically execute the semantic restructuring workflow, so that subtitles are optimized for TTS before timeline processing.

#### Acceptance Criteria

1. WHEN processing begins THEN the system SHALL execute stages in order: LLM → Rebalance → Synth → Mux → Audit
2. WHEN generating semantic output THEN the system SHALL enforce safety limits of ≤250 characters or ≤15 seconds per block
3. WHEN dual-track mode is enabled THEN the system SHALL generate both Display SRT and Audio SRT
4. WHEN LLM is unavailable THEN the system SHALL fallback to local `semantic_restructure` function
5. WHEN semantic restructure completes THEN the system SHALL validate output with `srt.parse` before proceeding

### Requirement 3: Multi-Speaker Protocol Support

**User Story:** As a user processing multi-speaker content, I want the agent to detect speaker boundaries and map voices correctly, so that each speaker has the appropriate voice.

#### Acceptance Criteria

1. WHEN parsing subtitles THEN the system SHALL recognize `[Speaker:Name]` tags with ≥99% accuracy
2. WHEN a speaker tag is detected THEN the system SHALL extract the speaker name and preserve it through processing
3. WHEN voice mapping is configured THEN the system SHALL apply the correct voice to each speaker's segments
4. WHEN no voice mapping exists for a speaker THEN the system SHALL use the DEFAULT voice from voice_map.json
5. WHEN speaker boundaries exist THEN the system SHALL prevent merging across speaker changes during clustering

### Requirement 4: Parameter Defaults and Configuration

**User Story:** As a user, I want sensible default parameters, so that I can run commands without specifying every option.

#### Acceptance Criteria

1. WHEN no sample rate is specified THEN the system SHALL default to 48000 Hz
2. WHEN no CPM targets are specified THEN the system SHALL use target_cpm=180, panic_cpm=300, max_shift=1000
3. WHEN backend is edge_tts THEN the system SHALL default to jobs=4 unless --no-fallback is set
4. WHEN backend is macos_say THEN the system SHALL force jobs=1
5. WHEN --no-fallback is enabled THEN the system SHALL force jobs=1 and disable backend fallback

### Requirement 5: Fallback and Error Handling

**User Story:** As a user, I want the agent to handle failures gracefully with automatic fallbacks, so that processing can complete even when services are unavailable.

#### Acceptance Criteria

1. WHEN Edge TTS fails and --no-fallback is not set THEN the system SHALL fallback to macos_say with jobs=1
2. WHEN LLM API is unavailable THEN the system SHALL fallback to local semantic_restructure
3. WHEN negative PTS is detected THEN the system SHALL automatically enable robust_ts mode
4. WHEN --no-fallback is enabled and synthesis fails THEN the system SHALL return exit code 1 without generating output
5. WHEN a fallback occurs THEN the system SHALL log the fallback action to process.log

### Requirement 6: Quality Assurance and Validation

**User Story:** As a user, I want automatic quality checks, so that I can verify the output meets synchronization and quality standards.

#### Acceptance Criteria

1. WHEN sync_audit runs THEN the system SHALL flag any segment with |delta_ms| > 180ms as out-of-sync
2. WHEN CPM audit runs THEN the system SHALL report all segments outside the min-cpm to max-cpm range
3. WHEN project validation runs THEN the system SHALL verify exactly one MP4 and one SRT file exist
4. WHEN validation detects negative PTS THEN the system SHALL set recommend_robust_ts=true in validation.json
5. WHEN --debug-sync is enabled THEN the system SHALL generate sync_debug.log with timing details

### Requirement 7: Plan Document Management

**User Story:** As a maintainer, I want the agent to follow structured plan documents, so that execution is consistent and traceable.

#### Acceptance Criteria

1. WHEN the agent starts a task THEN the system SHALL reference the appropriate plan document (01-09)
2. WHEN a plan document is updated THEN the system SHALL update version numbers in all referencing documents
3. WHEN executing a sub-task THEN the system SHALL verify all prerequisite dependencies are complete
4. WHEN a milestone is reached THEN the system SHALL update the progress report template
5. WHEN a quality checkpoint fails THEN the system SHALL halt and report the specific failure criteria

### Requirement 8: Text Immutability Enforcement

**User Story:** As a developer, I want strict text immutability in script stage, so that semantic changes never happen during timeline or media operations.

#### Acceptance Criteria

1. WHEN entering script stage THEN the system SHALL capture original text for all segments
2. WHEN rebalance completes THEN the system SHALL verify text matches original exactly
3. WHEN text mutation is detected THEN the system SHALL raise RuntimeError with message "text mutated in script stage"
4. WHEN --strip-meta or --strip-noise is used in non-rewrite commands THEN the system SHALL ignore these flags
5. WHEN text cleaning is needed THEN the system SHALL only allow it in the rewrite command

### Requirement 9: Clustered Synthesis with Micro-Splitting

**User Story:** As a user, I want clustered synthesis to preserve timing anchors, so that audio stays synchronized with original subtitle timing.

#### Acceptance Criteria

1. WHEN --clustered is enabled THEN the system SHALL merge text by terminal punctuation for macro-synthesis
2. WHEN macro-synthesis completes THEN the system SHALL split audio back to original segment durations
3. WHEN --clustered is enabled THEN the system SHALL automatically skip rebalance to avoid re-segmentation
4. WHEN --auto-dual-srt is enabled THEN the system SHALL automatically enable clustered mode
5. WHEN clustered mode is active THEN the system SHALL preserve micro-level timing anchors from original SRT

### Requirement 10: Strict Edge Mode

**User Story:** As a user requiring high-quality Edge TTS output, I want strict mode to fail immediately on errors, so that I never get fallback output when Edge TTS is required.

#### Acceptance Criteria

1. WHEN --no-fallback is enabled and Edge TTS fails THEN the system SHALL exit with code 1 without generating video
2. WHEN --no-fallback is enabled THEN the system SHALL force jobs=1 to reduce network instability
3. WHEN strict Edge mode is active THEN the system SHALL disable automatic backend fallback
4. WHEN synthesis fails in strict mode THEN the system SHALL not produce any output artifacts
5. WHEN preflight check fails THEN the system SHALL terminate before starting full synthesis

### Requirement 11: Project Structure Validation

**User Story:** As a user, I want automatic project structure validation, so that I know my input files are correctly organized before processing.

#### Acceptance Criteria

1. WHEN validate_project runs THEN the system SHALL verify exactly one MP4 file exists in project directory
2. WHEN validate_project runs THEN the system SHALL verify exactly one SRT file exists in project directory
3. WHEN multiple files of same type exist THEN the system SHALL warn and use the first file
4. WHEN validation succeeds THEN the system SHALL generate validation.json with language detection and voice recommendation
5. WHEN validation succeeds THEN the system SHALL create output directory structure under data/output/<ProjectName>/

### Requirement 12: Progress Reporting and Logging

**User Story:** As a user, I want detailed progress logs, so that I can track execution and debug issues.

#### Acceptance Criteria

1. WHEN project_merge runs THEN the system SHALL write all stages to process.log
2. WHEN CPM audit completes THEN the system SHALL generate cpm.csv with all segment metrics
3. WHEN processing completes THEN the system SHALL generate report.json with metadata
4. WHEN errors occur THEN the system SHALL write issue.md with root cause template
5. WHEN --debug-sync is enabled THEN the system SHALL log first 20 segments with text comparison

### Requirement 13: Plan Document Management and Version Control

**User Story:** As a maintainer, I want the agent to manage plan documents with version control, so that changes are traceable and references stay synchronized.

#### Acceptance Criteria

1. WHEN a plan document is created THEN the system SHALL follow naming convention `[序号]_[任务名称]_v[版本号].md`
2. WHEN a plan document is updated THEN the system SHALL create a new version file without overwriting the old version
3. WHEN a plan document version changes THEN the system SHALL update all referencing documents with the new version number
4. WHEN a plan document is referenced THEN the system SHALL maintain bidirectional reference links (引用来源 and 引用去向)
5. WHEN checking plan document integrity THEN the system SHALL verify no orphaned sections exist without references

### Requirement 14: Milestone and Task Dependency Management

**User Story:** As a project manager, I want the agent to track milestones and enforce task dependencies, so that work proceeds in the correct order.

#### Acceptance Criteria

1. WHEN starting a sub-task THEN the system SHALL verify all prerequisite dependencies are marked complete
2. WHEN a milestone is reached THEN the system SHALL update the milestone status (草拟→评审→冻结)
3. WHEN a task fails quality checkpoints THEN the system SHALL block progression to dependent tasks
4. WHEN all sub-tasks in a main task complete THEN the system SHALL automatically mark the main task as complete
5. WHEN task dependencies form a cycle THEN the system SHALL detect and report the circular dependency

### Requirement 15: Quality Checkpoint Enforcement

**User Story:** As a quality assurance lead, I want automatic quality checkpoints at each stage, so that issues are caught early.

#### Acceptance Criteria

1. WHEN LLM output is generated THEN the system SHALL verify SRT structure validity with `srt.parse()`
2. WHEN semantic restructure completes THEN the system SHALL verify terminology preservation rate is 100%
3. WHEN rebalance completes THEN the system SHALL verify text hash matches original exactly
4. WHEN synthesis completes THEN the system SHALL verify all WAV files exist and are non-zero size
5. WHEN any quality checkpoint fails THEN the system SHALL halt execution and report the specific failure

### Requirement 16: Risk Escalation and Emergency Response

**User Story:** As an operations manager, I want automatic risk escalation based on severity, so that critical issues get immediate attention.

#### Acceptance Criteria

1. WHEN a P1 (blocking) issue occurs THEN the system SHALL escalate to Agent Owner within 30 minutes
2. WHEN a P2 (major) issue occurs THEN the system SHALL escalate to responsible party within 4 hours
3. WHEN a P3 (general) issue occurs THEN the system SHALL log and notify within 24 hours
4. WHEN LLM is unavailable THEN the system SHALL trigger emergency fallback to semantic_restructure and log impact
5. WHEN FFmpeg robust-ts fails THEN the system SHALL provide manual mux command as emergency workaround

### Requirement 17: Change Log and Reference Network Maintenance

**User Story:** As a documentation maintainer, I want automatic change log updates, so that all modifications are tracked centrally.

#### Acceptance Criteria

1. WHEN any plan document changes THEN the system SHALL record the change in `09_Change_Log_and_References_v*.md`
2. WHEN recording a change THEN the system SHALL include: change reason, impact scope, and affected files
3. WHEN a document references another THEN the system SHALL maintain the reference network with section anchors
4. WHEN checking reference integrity THEN the system SHALL verify all referenced documents and sections exist
5. WHEN generating an update impact matrix THEN the system SHALL list all files requiring synchronization

### Requirement 18: Preflight Checks for Strict Edge Mode

**User Story:** As a user requiring Edge TTS quality, I want preflight checks before full processing, so that environment issues are caught early.

#### Acceptance Criteria

1. WHEN strict Edge mode is enabled THEN the system SHALL run Edge→MP3→FFmpeg→WAV preflight test
2. WHEN preflight generates test MP3 THEN the system SHALL verify the file is valid and non-empty
3. WHEN preflight converts MP3 to WAV THEN the system SHALL verify conversion succeeds with correct sample rate
4. WHEN preflight fails THEN the system SHALL terminate before starting full synthesis
5. WHEN preflight succeeds THEN the system SHALL log success and proceed to full processing

### Requirement 19: Configuration Template Management

**User Story:** As a user, I want configuration templates for common scenarios, so that I can quickly set up projects without manual parameter tuning.

#### Acceptance Criteria

1. WHEN requesting strict Edge configuration THEN the system SHALL provide template with --no-fallback, --jobs 1, --clustered
2. WHEN requesting regular configuration THEN the system SHALL provide template with standard defaults
3. WHEN voice_map.json is missing THEN the system SHALL generate template with DEFAULT voice entry
4. WHEN project.json is requested THEN the system SHALL include all standard fields (backend, ar, jobs, target_cpm, etc.)
5. WHEN configuration conflicts exist THEN the system SHALL detect and report the conflicting parameters

### Requirement 20: Execution Order and Stage Serialization

**User Story:** As a developer, I want strict execution order enforcement, so that stages never run out of sequence.

#### Acceptance Criteria

1. WHEN processing starts THEN the system SHALL enforce order: LLM → Rebalance → Synth → Mux → Audit
2. WHEN a stage fails THEN the system SHALL halt and not proceed to subsequent stages
3. WHEN --no-rebalance is set THEN the system SHALL skip rebalance stage but maintain other stage order
4. WHEN --clustered is enabled THEN the system SHALL automatically skip rebalance to avoid re-segmentation
5. WHEN stage order is violated THEN the system SHALL raise an error with the expected sequence

### Requirement 21: Terminology and Shortcut Preservation

**User Story:** As a localization specialist, I want automatic preservation of technical terms and shortcuts, so that specialized vocabulary remains accurate.

#### Acceptance Criteria

1. WHEN processing bilingual content THEN the system SHALL preserve English terms for software names (Maya, Blender, UV Editor)
2. WHEN processing CN-Only mode THEN the system SHALL translate all terms to Chinese and remove English remnants
3. WHEN encountering keyboard shortcuts THEN the system SHALL preserve symbols like `Ctrl + .` intact
4. WHEN validating terminology preservation THEN the system SHALL achieve 100% retention rate in random samples
5. WHEN terminology mapping is ambiguous THEN the system SHALL log the ambiguity for manual review

### Requirement 22: High-Density Subtitle Handling

**User Story:** As a user processing high-density content, I want special handling for extreme CPM segments, so that synthesis doesn't fail or sound rushed.

#### Acceptance Criteria

1. WHEN CPM exceeds 900 THEN the system SHALL flag the segment for mandatory splitting or window expansion
2. WHEN duration is <800ms and chars ≥30 THEN the system SHALL enforce minimum window of 1800ms
3. WHEN high-density is detected THEN the system SHALL recommend target_cpm=160, panic_cpm=300, max_shift=6000
4. WHEN splitting is required THEN the system SHALL split at comma/semicolon boundaries in LLM stage
5. WHEN window expansion fails THEN the system SHALL report the segment for manual review

## Quality Standards

- All SRT outputs must pass `srt.parse()` validation
- Text immutability: 100% match between original and script-stage text
- Speaker recognition: ≥99% accuracy
- Sync audit threshold: |delta_ms| ≤ 180ms for acceptable quality
- Decision matrix coverage: ≥95% of existing commands
- Fallback success rate: 100% when LLM unavailable
- Terminology preservation: 100% in random samples ≥20 segments
- Plan document reference integrity: 0 broken links
- Milestone tracking: All dependencies verified before task start
- Quality checkpoint pass rate: 100% before stage progression
