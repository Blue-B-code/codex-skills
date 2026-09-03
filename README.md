# Codex Skills

Personal collection of [Codex](https://github.com/openai/codex) skills used to automate day-to-day software development workflows with an AI coding agent.

Each folder is a self-contained skill: it ships a `SKILL.md` (the skill's instructions) plus any scripts or config templates it needs. Skills are loaded by Codex from a skills directory and applied automatically when a task matches their description.

## Skills

| Skill | Purpose |
| --- | --- |
| **ticket-driver** | End-to-end ticket handling: pull review feedback (GitLab MR / GitHub PR / Redmine journal) or implement a feature, run each project's validation gate, then report back (status, assignee, screenshot, PR links) and hand off to QA. Three modes per project: `auto` / `propose` (human approval via Telegram) / `signal`. |
| **openimis** | Standard git + PR workflow for [OpenIMIS](https://openimis.org) modules: feature branch from `develop`, single commit, push, PR with the official openIMIS template; Comoros and CSU fan-out workflows. |
| **mi** | Validation workflow for a Docker-based mobile-invoice stack (React + PHP): all tests and static analysis run inside the project's dev container. |
| **flownote** | Validation and conventions for an async FastAPI backend + React/Vite admin frontend (TDD, i18n, ruff/mypy, vitest). |
| **upwork-job-filter** | Evaluate Upwork/freelance job postings against the owner's real profile and return an explicit APPLY / SKIP / CONDITIONAL verdict with a fit table and reasons (optionally a draft proposal). Encodes the 2-minute filter, a ~$15/hr rate floor, red flags and keywords to seek/exclude. |

## Usage

Skills are consumed by Codex, not installed as libraries. To use them locally, point your Codex config at this directory (or a copy of it) and describe the task — the matching skill is picked up automatically.

### Example

```
~/.codex/config.toml
skills = ["/path/to/codex-skills"]
```

## Structure of a skill

```
my-skill/
├── SKILL.md            # Skill instructions (required)
├── config.example.json # Config template — copy to config.json, never commit real secrets
└── scripts/            # Helper scripts used by the skill
```

## Notes

- **Security**: this repo only ever contains *templates and placeholders*. Real credentials (Redmine API keys, Telegram bot tokens) are loaded at runtime from a local, git-ignored `config.json` and must never be committed.
- The project names, hosts and commands shown in the skills are personal defaults — replace them with your own.
- These skills are opinionated personal workflows; they are published as a demonstration of AI-assisted software development, not as a general-purpose product.

## License

MIT
