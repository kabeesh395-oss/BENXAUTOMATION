# CodeRabbit AI Setup and Integration Guide

This document outlines the setup, repository permissions, pull request review configuration, and troubleshooting procedures for **CodeRabbit AI** in the **BENXAUTOMATION** repository.

---

## 1. Overview
CodeRabbit is integrated via the root configuration file [`.coderabbit.yaml`](../.coderabbit.yaml) (conforming to official Schema v2). It provides automated, context-aware code reviews on Pull Requests targeting the `main` branch, prioritizing:
- Real logic bugs, edge cases, and runtime exceptions.
- Regression risks in video rendering and subtitle synchronization pipelines.
- Security and credential leakage prevention.
- Test coverage and idempotency validation.
- Native integration with **Ruff** for static analysis without noisy style nitpicks.

---

## 2. GitHub App Installation & Permissions

### Step 1: Install the GitHub App
1. Navigate to the GitHub Marketplace or official portal: [https://coderabbit.ai](https://coderabbit.ai) (or GitHub Marketplace -> CodeRabbit).
2. Click **Install / Configure**.
3. Select your GitHub account or organization (`kabeesh395-oss`).
4. Choose **Only select repositories** and pick `BENXAUTOMATION`.

### Step 2: Required Repository Permissions
CodeRabbit requests the minimum necessary permissions:
- **Pull Requests (Read and Write):** Required to post inline review comments, summaries, and walkthroughs.
- **Issues (Read and Write):** Required if issue-linking or issue comments are activated.
- **Repository Contents & Metadata (Read):** Required to analyze diffs and project files (`pyproject.toml`, `.coderabbit.yaml`).
- **Checks & Commit Statuses (Read):** Required to coordinate with GitHub Actions CI checks.

---

## 3. Pull Request Review Workflow

Once authorized, CodeRabbit operates automatically:
1. **Developer opens a Pull Request** targeting `main`.
2. **Automated Review:** CodeRabbit triggers on PR opening or new commits pushed to the branch.
   - Generates a **High-Level Summary** and change walkthrough.
   - Runs static checks via **Ruff** based on rules in `pyproject.toml`.
   - Posts targeted comments focusing on bugs and security.
3. **Interactive Chat:** Developers can interact with CodeRabbit directly on the PR by replying to any review comment or typing `@coderabbitai` in comments (e.g., `@coderabbitai explain this regex` or `@coderabbitai suggest a unit test for this function`).
4. **Human Review Gate:** CodeRabbit does **not** merge pull requests. Human developer review and approval remain mandatory before merging into `main`.

---

## 4. Configuration Reference (`.coderabbit.yaml`)

Our repository configuration:
```yaml
# yaml-language-server: $schema=https://coderabbit.ai/integrations/schema.v2.json
language: "en-US"
early_access: false

reviews:
  profile: "assertive"
  request_changes_workflow: false
  high_level_summary: true
  poem: false
  review_status: true
  collapse_walkthrough: false
  auto_review:
    enabled: true
    drafts: false
    base_branches:
      - "main"
  path_instructions:
    - path: "**/*.py"
      instructions: "Focus on genuine bugs, regressions, exception handling, data integrity, FFmpeg argument escaping, and test coverage. Suppress purely stylistic nitpicks."
    - path: ".github/workflows/**/*.yml"
      instructions: "Review for workflow security, credential leakage, correct cron expression syntax, and secret handling."
  tools:
    ruff:
      enabled: true
      config_file: "pyproject.toml"
    github-checks:
      enabled: true

chat:
  auto_reply: true
```

---

## 5. Troubleshooting & FAQ

- **Q: CodeRabbit is not reviewing my PR.**
  - Check if the PR is marked as a **Draft**. By default, `drafts: false` skips draft PRs. Convert the PR to "Ready for review".
  - Ensure the PR target base branch is `main`.
  - Verify that the CodeRabbit GitHub App is installed for the repository at: `https://github.com/kabeesh395-oss/BENXAUTOMATION/settings/installations`.
- **Q: Too many stylistic comments.**
  - We have set `profile: "assertive"` and targeted instructions to ignore stylistic trivia. Formatting is automatically handled by `ruff format` in CI.
- **Q: Does CodeRabbit expose secret tokens or private keys?**
  - No. CodeRabbit runs remotely against the PR diff; repository secrets stored in GitHub Actions Secrets are never accessible to CodeRabbit.
