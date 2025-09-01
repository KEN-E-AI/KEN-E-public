# Company News Chatbot - Deployment Commands

# Install dependencies
install:
	@command -v uv >/dev/null 2>&1 || { echo "uv is not installed. Installing uv..."; curl -LsSf https://astral.sh/uv/install.sh | sh; }
	uv sync

# Test the agent locally
test-local:
	uv run python test_agent.py

# Deploy to Vertex AI Agent Engine  
deploy:
	uv run python deploy_supervisor.py

# Deploy with specific project
deploy-staging:
	GOOGLE_CLOUD_PROJECT_ID=ken-e-staging VERTEX_AI_PROJECT_ID=ken-e-staging VERTEX_AI_LOCATION=us-central1 uv run python deploy_supervisor.py

# Setup dev environment resources
setup-dev:
	uv run python setup_dev_resources.py --project ken-e-dev

# Deploy to dev environment
deploy-dev:
	GOOGLE_CLOUD_PROJECT_ID=ken-e-dev VERTEX_AI_PROJECT_ID=ken-e-dev VERTEX_AI_LOCATION=us-central1 uv run python deploy_supervisor.py

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

.PHONY: install test-local deploy deploy-staging test-deployed clean