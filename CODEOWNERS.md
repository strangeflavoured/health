# CODEOWNERS

#

# Each line is a file pattern followed by one or more owners.

# The last matching pattern takes precedence.

# https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners

# Global default — Jonathan owns everything unless overridden below

- @strangeflavoured

# CI/CD and security-sensitive configuration

# Changes here carry the highest risk and require careful review

/.github/ @strangeflavoured
/.github/workflows/ @strangeflavoured
/.pre-commit-config.yaml @strangeflavoured
/renovate.json @strangeflavoured
/.github/dependabot.yml @strangeflavoured

# Security and compliance documents

/SECURITY.md @strangeflavoured
/SECURITY-INSIGHTS.yml @strangeflavoured
/security-insights.yml @strangeflavoured
/docs/security-assessment.md @strangeflavoured

# Docker and infrastructure

/docker/ @strangeflavoured
/scripts/ @strangeflavoured

# Backend (Django + Redis ETL)

/backend/ @strangeflavoured
/src/ @strangeflavoured

# Frontend (React/Vite)

/frontend/ @strangeflavoured

# Documentation

/docs/ @strangeflavoured

# Dependency manifests

# deps-bot opens automated PRs against these but is not a code owner —

# human review is still required before merge.

/requirements\*.txt @strangeflavoured
/pip-requirements.txt @strangeflavoured
/requirements-dev.txt @strangeflavoured
/backend/requirements/ @strangeflavoured
/docs/requirements.txt @strangeflavoured
/frontend/package.json @strangeflavoured
/frontend/package-lock.json @strangeflavoured

# Governance and legal

/LICENSE @strangeflavoured
/MAINTAINERS.md @strangeflavoured
/CHANGELOG.md @strangeflavoured
