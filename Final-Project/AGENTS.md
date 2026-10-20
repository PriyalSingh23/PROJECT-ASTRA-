# AGENTS.md — Agent System & gstack Workflow Configuration

## Agent Tooling: gstack Software Factory

This workspace uses [gstack](https://github.com/garrytan/gstack) to structure AI collaboration into specialized roles.

### Quick Command Dispatch

- **Product Scoping & Strategy:** Use `/office-hours` or `/plan-ceo-review`.
- **Engineering Architecture & Review:** Use `/plan-eng-review`.
- **Code Review & Diff Inspection:** Use `/review` before landing any code modifications.
- **Automated QA & Verification:** Use `/qa` to test endpoints, UI flows, and regression suites.
- **Security Audit:** Use `/cso` to check cryptographic boundaries, nonces, and input validation.
- **Pre-Landing / Release:** Use `/ship` to verify test matrices and prepare release logs.

### Execution Environment
- Bun runtime: `/Users/sabhay/.gemini/antigravity/bin/bun`
- gstack root: `~/.claude/skills/gstack`
- Global skills: `~/.gemini/antigravity-cli/skills/` and `~/.gemini/config/skills/`

### Core Guardrails
- Maintain 100% test pass rate across `pytest tests/ -v` (57 tests).
- Preserve OpenBLAS dynamic linker safety (`import torch` before `numpy`/`scipy`).
- Keep backend on canonical port 5050.
- Do not commit or push to git without explicit user authorization.
