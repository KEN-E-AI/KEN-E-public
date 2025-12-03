# KEN-E Agent Deployment - Makefile

# Install dependencies
install:
	@command -v uv >/dev/null 2>&1 || { echo "uv is not installed. Installing uv..."; curl -LsSf https://astral.sh/uv/install.sh | sh; }
	uv sync

# Test the agent locally
test-local:
	uv run python test_agent.py

# ============================================================================
# Strategy Supervisor Agent Deployment
# ============================================================================

# Deploy Strategy Supervisor to development
deploy:
	uv run python deploy_with_sys_version.py --env dev

deploy-dev:
	uv run python deploy_with_sys_version.py --env dev

# Deploy Strategy Supervisor to staging
deploy-staging:
	uv run python deploy_with_sys_version.py --env staging

# Deploy Strategy Supervisor to production
deploy-production:
	uv run python deploy_with_sys_version.py --env prod

# ============================================================================
# KEN-E Chat Agent Deployment
# ============================================================================

# Deploy KEN-E Chat Agent to development
deploy-ken-e:
	uv run python deploy_ken_e.py --env dev

# Deploy KEN-E Chat Agent to staging
deploy-ken-e-staging:
	uv run python deploy_ken_e.py --env staging

# Deploy KEN-E Chat Agent to production
deploy-ken-e-production:
	uv run python deploy_ken_e.py --env prod

# ============================================================================
# Utilities
# ============================================================================

# Setup dev environment resources
setup-dev:
	uv run python setup_dev_resources.py --project ken-e-dev

# Test the deployed agent
test-deployed:
	uv run python test_deployed_agent.py

# Test the dev deployed agent
test-dev:
	uv run python test_dev_deployment.py

# Clean up
clean:
	rm -rf .venv/
	rm -f deployment_metadata.json

.PHONY: install test-local deploy deploy-dev deploy-staging deploy-production deploy-ken-e deploy-ken-e-staging deploy-ken-e-production setup-dev test-deployed test-dev clean