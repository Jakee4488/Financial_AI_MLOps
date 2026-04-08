-- Unity Catalog Infrastructure Setup
-- Run this ONCE in your Databricks workspace to provision catalogs, schemas, and volumes for dev/acc/prd
-- Execute as a user/service principal with CREATE CATALOG privilege
-- NOTE: If needed, replace `jacobbinu4488code@gmail.com` below with your group or service principal.
-- Example alternatives:
--   `account users`
--   `my-deploy-sp`

-- ============================================================================
-- DEV Environment
-- ============================================================================

-- Create dev catalog
CREATE CATALOG IF NOT EXISTS mlops_dev
COMMENT 'Development environment for Financial AI MLOps';

-- Grant permissions on dev catalog
GRANT USE CATALOG, CREATE SCHEMA ON CATALOG mlops_dev TO `jacobbinu4488code@gmail.com`;

-- Create schema
CREATE SCHEMA IF NOT EXISTS mlops_dev.financial_transactions
COMMENT 'Financial transactions schema for dev environment';

-- Grant permissions on schema
GRANT USE SCHEMA, CREATE TABLE ON SCHEMA mlops_dev.financial_transactions TO `jacobbinu4488code@gmail.com`;

-- Create volume for artifact storage
CREATE VOLUME IF NOT EXISTS mlops_dev.financial_transactions.packages
COMMENT 'Packages volume for storing Python wheels';

-- Grant permissions on volume
GRANT READ_VOLUME, WRITE_VOLUME ON VOLUME mlops_dev.financial_transactions.packages TO `jacobbinu4488code@gmail.com`;

-- ============================================================================
-- ACC (ACCEPTANCE) Environment
-- ============================================================================

-- Create acc catalog
CREATE CATALOG IF NOT EXISTS mlops_acc
COMMENT 'Acceptance environment for Financial AI MLOps';

-- Grant permissions on acc catalog
GRANT USE CATALOG, CREATE SCHEMA ON CATALOG mlops_acc TO `jacobbinu4488code@gmail.com`;

-- Create schema
CREATE SCHEMA IF NOT EXISTS mlops_acc.financial_transactions
COMMENT 'Financial transactions schema for acceptance environment';

-- Grant permissions on schema
GRANT USE SCHEMA, CREATE TABLE ON SCHEMA mlops_acc.financial_transactions TO `jacobbinu4488code@gmail.com`;

-- Create volume for artifact storage
CREATE VOLUME IF NOT EXISTS mlops_acc.financial_transactions.packages
COMMENT 'Packages volume for storing Python wheels';

-- Grant permissions on volume
GRANT READ_VOLUME, WRITE_VOLUME ON VOLUME mlops_acc.financial_transactions.packages TO `jacobbinu4488code@gmail.com`;

-- ============================================================================
-- PRD (PRODUCTION) Environment
-- ============================================================================

-- Create prd catalog
CREATE CATALOG IF NOT EXISTS mlops_prd
COMMENT 'Production environment for Financial AI MLOps';

-- Grant permissions on prd catalog
GRANT USE CATALOG, CREATE SCHEMA ON CATALOG mlops_prd TO `jacobbinu4488code@gmail.com`;

-- Create schema
CREATE SCHEMA IF NOT EXISTS mlops_prd.financial_transactions
COMMENT 'Financial transactions schema for production environment';

-- Grant permissions on schema
GRANT USE SCHEMA, CREATE TABLE ON SCHEMA mlops_prd.financial_transactions TO `jacobbinu4488code@gmail.com`;

-- Create volume for artifact storage
CREATE VOLUME IF NOT EXISTS mlops_prd.financial_transactions.packages
COMMENT 'Packages volume for storing Python wheels';

-- Grant permissions on volume
GRANT READ_VOLUME, WRITE_VOLUME ON VOLUME mlops_prd.financial_transactions.packages TO `jacobbinu4488code@gmail.com`;

-- ============================================================================
-- Verification
-- ============================================================================

-- Verify all catalogs exist
SHOW CATALOGS;

-- Verify all schemas exist
SHOW SCHEMAS IN mlops_dev;
SHOW SCHEMAS IN mlops_acc;
SHOW SCHEMAS IN mlops_prd;

-- Verify all volumes exist
SHOW VOLUMES IN mlops_dev.financial_transactions;
SHOW VOLUMES IN mlops_acc.financial_transactions;
SHOW VOLUMES IN mlops_prd.financial_transactions;
