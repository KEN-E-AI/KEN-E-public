install:
	@command -v uv >/dev/null 2>&1 || { echo "uv is not installed. Installing uv..."; curl -LsSf https://astral.sh/uv/install.sh | sh; source ~/.bashrc; }
	uv sync --dev --extra streamlit --extra jupyter --frozen

# Environment switching targets
env-dev:
	@./set-environment.sh development

env-staging:
	@./set-environment.sh staging

env-prod:
	@./set-environment.sh production

test:
	uv run pytest tests/unit && uv run pytest tests/integration

ken-e:
	PYTHONPATH=. uv run streamlit run frontend/streamlit_app.py --browser.serverAddress=localhost --server.enableCORS=false --server.enableXsrfProtection=false

# backend target removed - ADK Agent Engine is accessed directly via API



lint:
	uv run codespell
	uv run ruff check . --diff
	uv run ruff format . --check --diff
	uv run mypy .
	uv run python api/scripts/lint/check_context_window_registry_coverage.py
