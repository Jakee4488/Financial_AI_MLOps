# Operational Documents

Centralised operational documentation for Financial AI MLOps.

## Contents

### Reference (Start Here)

| Document | Purpose |
|---|---|
| [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md) | Complete directory map — every file, every table, every resource |
| [`FUNCTION_AND_CONFIG_REFERENCE.md`](FUNCTION_AND_CONFIG_REFERENCE.md) | Every class, function, and config field with full parameter tables |

### Setup & Deployment

| Document | Purpose |
|---|---|
| [`COMPREHENSIVE_MLOPS_SETUP_GUIDE.md`](COMPREHENSIVE_MLOPS_SETUP_GUIDE.md) | Full environment setup from scratch |
| [`DEPLOYMENT_VALIDATION_GUIDE.md`](DEPLOYMENT_VALIDATION_GUIDE.md) | Step-by-step deployment checklist |
| [`GETTING_STARTED_PIPELINE_TESTING.md`](GETTING_STARTED_PIPELINE_TESTING.md) | How to run and test all pipelines |

### Operations

| Document | Purpose |
|---|---|
| [`RUNBOOK.md`](RUNBOOK.md) | On-call incident response procedures |
| [`CICD_EXECUTION_GRAPH.md`](CICD_EXECUTION_GRAPH.md) | Full CI/CD + Databricks execution flow diagram with timing |

### Security

| Document | Purpose |
|---|---|
| [`SECURE_ACCESS_ENCRYPTION_GUIDE.md`](SECURE_ACCESS_ENCRYPTION_GUIDE.md) | SOPS/Age secret management |
| [`SOPS_ENCRYPTION_SETUP.md`](SOPS_ENCRYPTION_SETUP.md) | SOPS tooling setup |
| [`AGE_SOPS_QUICKSTART.md`](AGE_SOPS_QUICKSTART.md) | Quick Age key generation guide |

## Notes

- The files in this folder are operational entry points for team usage.
- Source canonical docs currently remain at repository root to avoid breaking existing references.
- Use `.sops.yaml` + `SOPS_ENCRYPTION_SETUP.md` to encrypt documents in git when needed.
