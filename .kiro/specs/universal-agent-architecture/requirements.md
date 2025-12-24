# Requirements Document

## Introduction

This document specifies the requirements for refactoring FlexDub from the current "Markdown-Driven" architecture (v2) to a "Universal Agent Architecture" (v3). The core philosophy is "Thick Code, Thin Prompts" - moving business logic from Markdown documentation into executable Python code, exposing functionality through Model Context Protocol (MCP) tools, and organizing agent capabilities into discrete skill modules.

The refactoring aims to:
1. Eliminate pseudo-code and decision trees from Markdown files
2. Create a structured MCP interface for agent-code interaction
3. Organize domain knowledge into discoverable skill modules
4. Maintain backward compatibility with existing CLI functionality

## Glossary

- **MCP (Model Context Protocol)**: A standardized protocol for AI agents to interact with external tools and services through structured function calls
- **Agent**: An AI assistant (like Kiro) that orchestrates FlexDub operations
- **Cognition Layer**: The `.agent/config.md` file containing project overview and core directives for the agent
- **Interface Layer**: The MCP server (`flexdub/mcp/`) exposing Python functions as callable tools
- **Skill Layer**: Modular knowledge packages (`.agent/skills/`) containing domain-specific logic and context
- **CPM (Characters Per Minute)**: Metric for measuring subtitle reading/speaking speed
- **Mode A (Elastic Audio)**: Processing mode where video duration is fixed and audio is stretched/compressed
- **Mode B (Elastic Video)**: Processing mode where audio is natural and video is stretched/compressed
- **Decision Matrix**: Logic for determining processing parameters based on input characteristics
- **Semantic Refinement**: LLM-based text optimization for TTS quality
- **QA (Quality Assurance)**: Automated validation of generated artifacts

## Requirements

### Requirement 1: Cognition Layer Setup

**User Story:** As an AI agent, I want a concise configuration file that provides project context and core directives, so that I can understand the project structure without parsing verbose documentation.

#### Acceptance Criteria

1. WHEN the agent starts a session THEN the system SHALL provide a `.agent/config.md` file containing project architecture overview
2. WHEN the config file is read THEN the system SHALL include directory structure definitions and their purposes
3. WHEN the config file is read THEN the system SHALL include core development directives (e.g., "use tools instead of direct file manipulation")
4. WHEN the config file is read THEN the system SHALL NOT include specific business logic or decision trees

### Requirement 2: MCP Server Infrastructure

**User Story:** As an AI agent, I want to interact with FlexDub through structured tool calls, so that I can execute operations without constructing CLI commands.

#### Acceptance Criteria

1. WHEN the MCP server initializes THEN the system SHALL create a `flexdub/mcp/server.py` module with a functional MCP server class
2. WHEN the MCP server runs THEN the system SHALL support stdio communication mode for agent interaction
3. WHEN tools are registered THEN the system SHALL expose them with typed input schemas using Pydantic models
4. WHEN a tool is called THEN the system SHALL return structured JSON responses with success/error status
5. WHEN a tool encounters an error THEN the system SHALL return a descriptive error message without crashing the server

### Requirement 3: Project Analyzer Tool

**User Story:** As an AI agent, I want to analyze a project directory and receive processing recommendations, so that I can make informed decisions about which mode and parameters to use.

#### Acceptance Criteria

1. WHEN the `analyze_project` tool is called with a project path THEN the system SHALL return video duration in milliseconds
2. WHEN the `analyze_project` tool is called THEN the system SHALL return average CPM from the SRT file
3. WHEN the `analyze_project` tool is called THEN the system SHALL return a recommended processing mode (A or B) based on CPM thresholds
4. WHEN CPM exceeds 300 THEN the system SHALL recommend Mode B (elastic-video)
5. WHEN CPM is at or below 300 THEN the system SHALL recommend Mode A (elastic-audio)
6. WHEN the project directory is invalid THEN the system SHALL return an error with specific validation failures

### Requirement 4: Semantic Refinement Skill

**User Story:** As an AI agent, I want access to semantic refinement rules and implementation, so that I can improve subtitle quality for TTS synthesis.

#### Acceptance Criteria

1. WHEN the semantic refinement skill is loaded THEN the system SHALL provide a `SKILL.md` file describing when to use the skill
2. WHEN the skill is activated THEN the system SHALL provide terminology preservation rules (software names, shortcuts, technical terms)
3. WHEN the skill is activated THEN the system SHALL provide speaker identification patterns
4. WHEN text refinement is requested THEN the system SHALL apply rules from a structured configuration file
5. WHEN refinement completes THEN the system SHALL validate output against character and duration limits per mode

### Requirement 5: Auto-Dub Workflow Skill

**User Story:** As an AI agent, I want a robust dubbing workflow with automatic retry and QA validation, so that I can complete dubbing tasks reliably without manual intervention.

#### Acceptance Criteria

1. WHEN the auto-dub workflow is invoked THEN the system SHALL execute the complete pipeline (semantic refinement → rebalance → TTS → merge)
2. WHEN a pipeline step fails THEN the system SHALL retry with fallback parameters before reporting failure
3. WHEN the pipeline completes THEN the system SHALL automatically execute QA validation
4. WHEN QA validation fails THEN the system SHALL attempt automatic remediation up to a configured retry limit
5. WHEN the workflow succeeds THEN the system SHALL return a structured report with processing statistics
6. WHEN the `run_auto_dub` MCP tool is called THEN the system SHALL execute the workflow and return results

### Requirement 6: Diagnosis Skill

**User Story:** As an AI agent, I want to diagnose processing failures and receive actionable fix suggestions, so that I can resolve issues without searching through documentation.

#### Acceptance Criteria

1. WHEN the diagnosis skill is loaded THEN the system SHALL provide error code mappings from the v2 manual
2. WHEN an error report is analyzed THEN the system SHALL return human-readable fix suggestions
3. WHEN a common error pattern is detected THEN the system SHALL provide specific remediation steps
4. WHEN diagnosis completes THEN the system SHALL categorize the issue (configuration, input quality, resource, or unknown)

### Requirement 7: Legacy Manual Migration

**User Story:** As a developer, I want the v2 agent manual preserved as a reference while the new v3 manual provides streamlined guidance, so that I can transition gradually without losing institutional knowledge.

#### Acceptance Criteria

1. WHEN migration completes THEN the system SHALL rename `agent_manual.md` to `agent_manual_legacy.md`
2. WHEN migration completes THEN the system SHALL create a new `agent_manual.md` with minimal content
3. WHEN the v3 manual is read THEN the system SHALL contain only role definition, config reference, and tool usage guidance
4. WHEN the v3 manual is read THEN the system SHALL NOT contain decision trees, pseudo-code, or detailed business logic

### Requirement 8: MCP Tool Validation

**User Story:** As a developer, I want automated tests for MCP tools, so that I can verify the agent interface works correctly.

#### Acceptance Criteria

1. WHEN validation tests run THEN the system SHALL verify `analyze_project` returns valid JSON with required fields
2. WHEN validation tests run THEN the system SHALL verify `run_auto_dub` executes without crashing on valid input
3. WHEN validation tests run THEN the system SHALL verify error handling returns structured error responses
4. WHEN all validation tests pass THEN the system SHALL output a success summary

### Requirement 9: Backward Compatibility

**User Story:** As a user, I want existing CLI commands to continue working after the refactoring, so that my current workflows are not disrupted.

#### Acceptance Criteria

1. WHEN the refactoring completes THEN the system SHALL preserve all existing CLI commands (merge, rebalance, audit, etc.)
2. WHEN existing CLI commands are invoked THEN the system SHALL produce identical outputs for identical inputs
3. WHEN new MCP tools are added THEN the system SHALL NOT modify existing CLI behavior
4. WHEN running the existing test suite THEN the system SHALL pass all tests without modification
