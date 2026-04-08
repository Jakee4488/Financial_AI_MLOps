# Secure Access and Encryption Guide

This guide recommends practical controls for securing operational documents, secrets, and pipeline access.

## 1) Encrypt Data at Rest

- **Databricks managed data**: use Unity Catalog managed storage with cloud-provider encryption by default.
- **Customer-managed keys (recommended for regulated workloads)**:
  - AWS: KMS CMK
  - Azure: Key Vault CMK
  - GCP: Cloud KMS CMEK
- **Volumes and tables**: keep all sensitive artifacts in UC-governed locations (`Volumes`, managed tables), not public DBFS paths.

## 2) Encrypt Data in Transit

- Enforce TLS 1.2+ for all service-to-service traffic.
- Use private networking patterns where possible (Private Link / VPC peering / private endpoints).
- Disable public ingress to sensitive endpoints unless explicitly required.

## 3) Secrets Encryption and Access

- Never store API keys or tokens in Markdown, code, or `project_config.yml`.
- Store secrets in:
  - Databricks Secret Scopes (or cloud secret manager integration),
  - GitHub Actions encrypted secrets for CI/CD.
- Rotate credentials on a schedule (for example every 60-90 days).
- Use short-lived tokens and service principals instead of personal tokens.

## 4) Document Access Hardening

- Restrict repo/document access by role (least privilege):
  - `Readers`: read-only docs
  - `Operators`: runbooks + deployment docs
  - `Admins`: infra and key management
- Protect `main` with branch protection and PR reviews.
- Require SSO + MFA on GitHub and Databricks.
- Add audit logging for document and repo access.

## 5) Recommended Encryption Pattern for This Project

1. Keep operational docs in `Operational_Documents/`.
2. Classify docs by sensitivity:
   - Public/Internal/Restricted.
3. For Restricted docs:
   - keep sanitized version in repo,
   - store sensitive appendices in encrypted storage (cloud KMS-backed bucket or secure wiki with SSO).
4. Reference restricted assets by URL, not embedded secrets.

## 6) Optional: File-Level Encryption for Highly Sensitive Markdown

For rare cases where specific Markdown files must be encrypted in git:
- Use `SOPS` with cloud KMS backend and commit encrypted files only.
- Decrypt only in CI or controlled admin workstations.

Example tooling:
- Mozilla SOPS + AWS KMS / Azure Key Vault / GCP KMS
- age keys (for non-cloud KMS scenarios)

## 7) Minimum Baseline Checklist

- [ ] No secrets in repository history or Markdown docs.
- [ ] Databricks and GitHub protected by SSO + MFA.
- [ ] Secrets in vault/scope, rotated periodically.
- [ ] UC permissions follow least privilege.
- [ ] Audit logs enabled and reviewed.
- [ ] Restricted docs stored in encrypted backend.
