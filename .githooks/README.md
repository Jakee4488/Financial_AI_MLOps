# Setup Git Hooks

This directory contains Git hooks that enforce branch protection rules **locally**,
preventing direct commits or pushes to `main` before they reach GitHub.

## Hooks

| Hook | Triggers on | What it blocks |
|---|---|---|
| `pre-commit` | Every `git commit` | Blocks the commit if you are on `main` |
| `pre-push` | Every `git push` | Blocks the push if the target remote branch is `main` |

## One-Time Setup (Required per developer)

### Windows (PowerShell)

```powershell
git config core.hooksPath .githooks
```

### macOS / Linux

```bash
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit
chmod +x .githooks/pre-push
```

> Run this once after cloning the repo. Git will then use these hooks automatically.

## Verify it works

```bash
# Should be blocked immediately:
git checkout main
git commit --allow-empty -m "test"
# Expected: 🚫 COMMIT BLOCKED — You are on 'main'

git push origin main
# Expected: 🚫 PUSH BLOCKED — Target branch is 'main'
```

## Emergency bypass (use with extreme caution)

```bash
# Skip hooks for a single commit (admin hotfix only):
git commit --no-verify -m "emergency hotfix"

# Skip hooks for a single push (admin hotfix only):
git push --no-verify origin main
```

> ⚠️ Only use `--no-verify` for genuine production emergencies.
> Document the bypass in the commit message and open a follow-up PR immediately.

## Notes

- These hooks are stored in `.githooks/` (tracked by git) not `.git/hooks/` (untracked).
- Every developer must run `git config core.hooksPath .githooks` once after cloning.
- These hooks work alongside GitHub Branch Protection Rules — together they provide
  two layers of protection: local (hooks) and remote (GitHub).
