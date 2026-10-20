# GEMINI.md — AI Agent Guidelines & gstack Integration

## gstack Integration

This project is integrated with [gstack](https://github.com/garrytan/gstack), an opinionated software factory and workflow system by Garry Tan (President & CEO of Y Combinator).

### Installed Locations
- **Core Repository & Binaries:** `~/.claude/skills/gstack` (with CLI tools in `~/.claude/skills/gstack/bin/`)
- **Global Antigravity Skills:** `~/.gemini/antigravity-cli/skills/` and `~/.gemini/config/skills/`
- **JavaScript Runtime:** Bun v1.4.3 (`/Users/sabhay/.gemini/antigravity/bin/bun`)

### Available Specialized Roles & Skills
When assisting with coding, reviews, testing, or architecture in this repository, leverage the corresponding gstack skills:

| Role / Skill | Slash Command | Purpose |
|---|---|---|
| **Office Hours** | `/office-hours` | Product interrogation and scoping with 6 forcing questions |
| **CEO Review** | `/plan-ceo-review` | Challenge product assumptions, cut scope, and focus on core value |
| **Eng Review** | `/plan-eng-review` | Architecture, data model integrity, failure modes, and concurrency |
| **Paranoid Review** | `/review` | Deep multi-angle diff analysis, SQL safety, and logic bug detection |
| **Automated QA** | `/qa` / `/qa-only` | System verification, edge case testing, and regression analysis |
| **Chief Security Officer** | `/cso` | Security audit (OWASP, STRIDE, cryptographic framing, secrets scan) |
| **Release Manager** | `/ship` | Pre-landing verification, changelog generation, and PR readiness |
| **Web Browser** | `/browse` | Web browsing and visual verification via gstack browser tools |

---

## SHADOWCOMM Project Constraints & Operational Rules

1. **Brownfield Stack Integrity:**
   - Backend: Flask 3.x WSGI on canonical port `5050` with SQLite WAL mode (5000ms busy timeout).
   - Frontend: React 19 + TypeScript + Tailwind CSS v4 in `frontend/`, built to `frontend/dist/`.
   - Physical/DSP: PyTorch with Apple Silicon MPS detection and deterministic CPU fallback.
2. **OpenBLAS Linker Safety (macOS Apple Silicon):**
   - Always ensure `import torch` strictly precedes `numpy` and `scipy` across all Python entry points to prevent `SIGSEGV 139`.
3. **Hardware Safety Interlocks:**
   - STAR-V tactical radio must remain strictly locked out (`STARV_SAFETY_LOCKOUT`).
   - Motorola MOTOTRBO TMS adapter enforces the strict 280-byte DMR ceiling.
4. **Git Safety:**
   - **Zero automated git commits, pushes, merges, or resets.** All git changes must be explicitly reviewed and authorized by the user.
