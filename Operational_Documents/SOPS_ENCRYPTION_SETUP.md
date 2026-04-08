# SOPS Encryption Setup for Operational Documents

Use this guide to encrypt Markdown files in `Operational_Documents/` while keeping them in git.

## 1) Prerequisites

- Install `sops` (latest).
- Choose a key backend:
  - AGE (simple/team-friendly), or
  - Cloud KMS (AWS/Azure/GCP).

## 2) Configure keys

The repository includes `.sops.yaml` with placeholder values.

Before encrypting, replace placeholders in `.sops.yaml`:
- `age1replace_with_real_recipient_key`
- or uncomment one KMS rule and provide real key IDs/URIs.

## 3) Encrypt documents

Encrypt one file:

```bash
sops -e -i Operational_Documents/RUNBOOK.md
```

Encrypt all operational docs (PowerShell):

```powershell
Get-ChildItem Operational_Documents -Filter *.md | ForEach-Object { sops -e -i $_.FullName }
```

## 4) Decrypt for reading/editing

Temporary decrypt to stdout:

```bash
sops -d Operational_Documents/RUNBOOK.md
```

Decrypt in place (for editing):

```bash
sops -d -i Operational_Documents/RUNBOOK.md
```

Re-encrypt after edits:

```bash
sops -e -i Operational_Documents/RUNBOOK.md
```

## 5) Validate before commit

- Confirm files are encrypted (contain `sops:` metadata block).
- Ensure no plaintext secrets exist in git diff.
- Commit encrypted files only.

## 6) Recommended team policy

- Restrict decrypt key access to operators/admins only.
- Rotate keys periodically.
- Keep CI runners using short-lived identity to decrypt (OIDC + KMS preferred).
- Keep non-sensitive docs in plaintext if broad collaboration is needed.
