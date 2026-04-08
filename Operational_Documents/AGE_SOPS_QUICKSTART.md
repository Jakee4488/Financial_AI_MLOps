# AGE + SOPS Quickstart

Use this guide to encrypt files under `Operational_Documents/` using AGE keys with SOPS.

## 1) Install dependencies

- Install `age`
- Install `sops`

## 2) Generate AGE keypair (per user)

```bash
age-keygen -o ~/.config/sops/age/keys.txt
```

This creates:
- private key at `~/.config/sops/age/keys.txt`
- public recipient key (printed in terminal, starts with `age1...`)

## 3) Configure `.sops.yaml`

Edit `.sops.yaml` and replace placeholder recipient with real keys:

```yaml
creation_rules:
  - path_regex: ^Operational_Documents/.*\.md$
    age: >-
      age1alicepublickey,age1bobpublickey
    encrypted_regex: '^(.*)$'
```

## 4) Configure local environment

SOPS usually auto-detects the key file. If needed:

PowerShell:

```powershell
$env:SOPS_AGE_KEY_FILE="$HOME\.config\sops\age\keys.txt"
```

Bash:

```bash
export SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"
```

## 5) Encrypt documents

Single file:

```bash
sops -e -i Operational_Documents/RUNBOOK.md
```

All Markdown files (PowerShell):

```powershell
Get-ChildItem Operational_Documents -Filter *.md | ForEach-Object { sops -e -i $_.FullName }
```

## 6) Decrypt for view/edit

View plaintext (stdout):

```bash
sops -d Operational_Documents/RUNBOOK.md
```

Decrypt in-place for editing:

```bash
sops -d -i Operational_Documents/RUNBOOK.md
```

Re-encrypt after editing:

```bash
sops -e -i Operational_Documents/RUNBOOK.md
```

## 7) Add new teammate access

1. Teammate generates AGE keypair.
2. Add their public recipient (`age1...`) to `.sops.yaml`.
3. Update recipients on encrypted docs:

```bash
sops updatekeys -y Operational_Documents/RUNBOOK.md
```

## 8) Commit policy

- Commit only encrypted files.
- Never commit private keys.
- Verify encrypted files contain a `sops` metadata block.
