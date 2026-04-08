# Deployment and Environment Validation Guide

This document provides a step-by-step playbook for validating your GitHub Actions CI/CD pipelines and confirming that the deployments propagate correctly into your Databricks environments (Dev, Acceptance, Production). 

---

## Prerequisites: Unity Catalog Infrastructure

**One-time setup required before first CD run.**

Your Databricks workspace needs three Unity Catalogs (dev, acc, prd) with schemas and volumes for artifact storage.

### Quick Setup

1. In Databricks SQL editor, open [setup_uc_infrastructure.sql](setup_uc_infrastructure.sql).
2. Run the entire script.
3. Verify output shows:
   - Three catalogs: mlops_dev, mlops_acc, mlops_prd
   - Three schemas: mlops_dev.financial_transactions, mlops_acc.financial_transactions, mlops_prd.financial_transactions
   - Three volumes: mlops_dev.financial_transactions.packages, mlops_acc.financial_transactions.packages, mlops_prd.financial_transactions.packages

This is required because CD uploads Python wheels to these volumes, and notebook jobs discover wheels from them at runtime.

---

## Step 1: Pre-requisites & GitHub Secrets Validation

Before running the pipelines, ensure your GitHub repository has the required Environments and Secrets configured.

1. Go to **Settings > Environments** in your GitHub repository and ensure `dev`, `acc`, and `prd` are created.
2. Go to **Settings > Secrets and variables > Actions**.
3. Verify the following **Repository Secrets** exist:
   - `DATABRICKS_HOST`
   - `DATABRICKS_TOKEN` (Or OAuth alternatives: `DATABRICKS_CLIENT_ID` and `DATABRICKS_CLIENT_SECRET`)
   - `FINNHUB_API_KEY`
   - `ALPHAVANTAGE_API_KEY`

---

## Step 2: Validate Continuous Integration (CI) Pipeline
**Workflow Source:** `.github/workflows/ci.yml`

The CI pipeline runs on Push (to `main` or `develop`) and Pull Request logic. To test it:

1. **Trigger:** Create a feature branch off of `develop` or `main`. Make a non-breaking code change (e.g., adding a comment), commit, and push. Open a Pull Request targeting `main`.
2. **Monitor Actions:** Navigate to the **Actions** tab in GitHub and click on the "CI Pipeline" run.
3. **Verify Jobs:**
   - **Lint & Test:** Ensure `ruff` format checks pass and unit tests execute successfully (`pytest`). Verify `test-results.xml` and `coverage.xml` artifacts upload successfully.
   - **Security Scan:** Ensure `bandit` and `safety` scans succeed without errors. Verify that the hardcoded API key safeguard is working.
   - **Validate Databricks Bundle:** Ensure the action successfully authenticates to Databricks and runs `databricks bundle validate -t dev` without throwing syntax or topological errors.
   - **Build Package:** Verify the Python wheel builds and uploads successfully as `dist/*.whl`.

---

## Step 3: Validate Continuous Deployment (CD) Pipeline
**Workflow Source:** `.github/workflows/cd.yml`

The CD pipeline triggers on pushes to the `main` branch or manually via `workflow_dispatch`. To thoroughly validate it:

1. **Trigger:** Navigate to the Actions tab, select "CD Pipeline," click **Run workflow**, choose a target environment (e.g., `dev`), and run it. Alternatively, merge your PR into `main` to trigger end-to-end.
2. **Monitor the Progression:**
   - **Deploy to Dev:** The pipeline should install dependencies, run `bundle validate`, and then execute `bundle deploy -t dev` seamlessly injecting the API keys and Git SHA context. It will immediately trigger a smoke test using `databricks bundle run financial_retraining_workflow -t dev --no-wait`.
   - **Deploy to Acceptance (Acc):** If triggered off the `main` branch, verify the environment automatically progresses to the `acc` deployment step.
   - **Deploy to Production (Prd):** Check that the workflow reaches the production deployment phase natively pointing to the production URL.
3. **Validate the Rollback Process:** 
   - Temporarily introduce a failing step into the `Deploy to Production` job.
   - Run the CD pipeline and allow it to fail on the `deploy-prd` step.
   - Confirm that the `Emergency Rollback` step automatically triggers (`if: failure() && needs.deploy-prd.result == 'failure'`) and successfully re-deploys the *previous* commit SHA.

---

## Step 4: Validate Manual Model Validation Gate
**Workflow Source:** `.github/workflows/model_validation.yml`

1. **Trigger:** Go to Actions, select "Model Validation Gate", and run it via `workflow_dispatch`.
2. Provide a dummy `model_version` (e.g., `v1.2.0`).
3. Ensure the workflow checks out successfully, runs the `ModelValidator` logic verifying PR-AUC and F1 scores, and connects seamlessly to the Unity Catalog MLflow registry. 

---

## Step 5: Databricks Environment Post-Deployment Verification

Once the GitHub Actions succeed, head over to the Databricks Workspace (`dev`, `acc`, or `prd`) to ensure the artifacts landed as expected:

1. **Workflows Execution:**
   - Navigate to **Workflows**.
   - Ensure the newly deployed definitions exist inside your target directory.
   - Check the **Job Runs** overview. Ensure the `financial_retraining_workflow` triggered by the GitHub CD Pipeline kicked off successfully.
2. **Variables and Injection:**
   - Review an executed job’s parameter arguments and tags. Ensure the Git SHA and branch names passed in from `${{ github.sha }}` and `${{ github.ref_name }}` populated correctly.
3. **Pipeline (Delta Live Tables) Verification:**
   - Navigate to **Delta Live Tables**.
   - Check if your DLT pipeline executes without issue, picking up the right `dev`/`prd` configurations respectively.
   - Look for the physical Databricks SQL tables in the Unity Catalog `mlops_dev` (or production equivalent) catalog. 
4. **Endpoint/Compute Check:**
   - Finally, verify that any model serving endpoints attached expected the correct new registry version.

---

## Step 6: Normal Deployment Flow (How It Is Usually Deployed)

This repository is normally deployed through GitHub Actions CD.

1. CD triggers on push to `main` or manual `workflow_dispatch`.
2. The workflow builds the wheel package (`uv build`).
3. Databricks Bundle is validated and deployed:
    - `databricks bundle validate -t <target>`
    - `databricks bundle deploy -t <target>`
4. Wheel artifact is uploaded for runtime installation.
5. Smoke workflow runs:
    - `databricks bundle run financial_retraining_workflow -t <target> --no-wait`

Manual equivalent (local terminal):

```bash
uv build
databricks bundle validate -t dev
databricks bundle deploy -t dev \
   --var="git_sha=<sha>" \
   --var="branch=<branch>" \
   --var="finnhub_api_key=<key>" \
   --var="alphavantage_api_key=<key>"

databricks fs cp --overwrite dist/<wheel-name>.whl dbfs:/FileStore/financial_ai_mlops_<sha>.whl
databricks bundle run financial_retraining_workflow -t dev
```

---

## Step 7: Alternatives to Uploading Wheel to DBFS FileStore

Yes, there are better alternatives depending on your environment controls.

### Option A: Unity Catalog Volumes (Recommended for governed environments)
- Upload wheel to a UC Volume path such as:
   - `dbfs:/Volumes/<catalog>/<schema>/packages/<wheel>.whl`
- Pros: governance, permissions, lineage-friendly storage.
- Cons: requires Volume to exist and correct grants.

### Option B: Private Python package index (Recommended for mature CI/CD)
- Publish wheel to Artifactory, Nexus, AWS CodeArtifact, or Azure Artifacts.
- Install in jobs/notebooks with pinned version:
   - `pip install financial-ai-mlops==<version>`
- Pros: proper versioning and dependency lifecycle.
- Cons: requires index credentials and network setup.

### Option C: Databricks Job libraries / Python wheel task
- Attach wheel as a job library or migrate notebook jobs to `python_wheel_task`.
- Pros: avoids runtime `%pip install` bootstrapping overhead.
- Cons: requires job definition changes and entrypoint refactor.

### Option D: Workspace Files path
- Store wheel under Workspace Files and install from absolute workspace path.
- Pros: easy for smaller teams.
- Cons: less robust for strict release governance.

### Recommendation

For your current setup, use this order of preference:
1. Unity Catalog Volume (if Volume resources and grants are managed in IaC).
2. Private package index (best long-term software supply-chain posture).
3. DBFS FileStore (good fallback, easiest to bootstrap).
