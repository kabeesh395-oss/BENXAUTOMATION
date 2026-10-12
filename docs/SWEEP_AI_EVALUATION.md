# Sweep AI Evaluation & Architectural Decision

## 1. Executive Summary & Status Verification

| Evaluation Criteria | Findings |
| :--- | :--- |
| **Service Status** | **Discontinued / Deprecated** |
| **GitHub App Availability** | The original Sweep GitHub App (automated issue-to-PR bot) was formally wound down and discontinued. |
| **Product Pivot** | The Sweep team pivoted away from the GitHub App model to an IDE-based autocomplete plugin for JetBrains before discontinuing active cloud service. |
| **Architectural Decision** | **Do NOT install or invent abandoned Sweep integrations.** Installing deprecated GitHub apps or abandoned packages introduces unmaintained attack surfaces and broken CI webhooks. |

---

## 2. In-Depth Technical Assessment

### A. Original Sweep Model vs Current Industry State
Sweep originally ran as an autonomous webhook listener that parsed GitHub issues and submitted auto-generated Pull Requests. In practice, autonomous unchecked code generators generated high noise, frequently broke test suites, and failed on complex domain models like FFmpeg rendering and audio synchronization pipelines.

### B. Security & Safety Risks of Unrestricted AI Coding Bots
Granting autonomous AI agents write or merge permissions introduces critical supply chain risks:
- Risk of committing unverified dependencies or hallucinated package names.
- Accidental bypass of branch protection rules.
- Potential leakage of API tokens or credential stores.

**Strict Security Rule:**
> **No AI agent (CodeRabbit, coding assistants, or CLI bots) is ever granted unrestricted permissions to merge code, publish releases, or deploy production workloads. All merges into `main` require green CI checks and human engineer approval.**

---

## 3. Recommended Maintained Alternatives

For developers seeking AI assistance within the **BENXAUTOMATION** workflow without compromising repository stability:

1. **Aider (Open-Source CLI):**
   - Operates locally in terminal (`python -m aider`).
   - Edits code locally with Git integration, allowing interactive developer review before any commit is pushed.
   - Fully optional, zero GitHub App overhead.
2. **Claude Code / Cursor / Copilot (Local Developer Assistants):**
   - Operates inside the developer's local environment.
   - Developer reviews diffs, runs `pytest`, formats with `ruff`, and creates the PR.
3. **CodeRabbit AI (PR Review Layer):**
   - Configured in [`.coderabbit.yaml`](../.coderabbit.yaml) to review human-opened PRs.
   - Provides non-destructive, read-only analysis focusing on security, edge cases, and regressions.

---

## 4. Operational AI Development Workflow

Our maintainable workflow enforces strict quality gates:

```
[Developer / Local Agent]
         │
         ▼
[Local Testing & Ruff Lint] (pytest -q, ruff check)
         │
         ▼
[Push to feature branch & Open PR]
         │
         ├───► [GitHub Actions CI: Pytest + Ruff + Matrix 3.11/3.12]
         ├───► [CodeRabbit AI: High-level review & security scan]
         │
         ▼
[Human Developer Review & Approval Required]
         │
         ▼
[Squash & Merge to protected `main` branch]
```
