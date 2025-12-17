# Changelog

All notable changes to this project will be documented in this file.

## [2.0.0] - 2025-11-20
- Added `data/` workspace with `input/` and `output/` directories.
- Introduced media-focused `.gitignore` to avoid committing large binaries.
- Renamed and rewrote `agents/指令代理.md` to `agents/agent_manual.md` (English, bilingual terms).
- Renamed `next-plan.md` to `roadmap.md` with structured sections and release history.
- Updated `README.md` with architecture diagram, quick start, folder structure, environment requirements, and contribution guide.
- Confirmed SemVer adoption and documented current version.

[2.0.0]: https://example.com/releases/2.0.0
[2.1.0] - 2025-11-20
- Added `validate_project` and `project_merge` CLI commands for standardized folder processing and end-to-end dubbing with logging and report.
- Introduced JSON adapters and IO helpers for WhisperX/Gemini segment lists.
- Updated agent manual to reference new package paths and standardized project structure.