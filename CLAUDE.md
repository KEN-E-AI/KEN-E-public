# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

KEN-E is a multi-agent system implemented with CrewAI for coding activities, built on Google Cloud Platform infrastructure. The system consists of multiple components working together to provide a comprehensive marketing analysis platform.

## Common Development Commands

### Root Level (Main Application)
- `make install` - Install all dependencies using uv
- `make test` - Run unit and integration tests
- `make lint` - Run code quality checks (codespell, ruff, mypy)
- `make ken-e` - Launch Streamlit interface for local testing
- `make backend` - Deploy agent to Agent Engine service
- `uv run jupyter lab` - Launch Jupyter notebooks for prototyping

### API Service (api/)
- `cd api && uvicorn src.kene_api.main:app --reload` - Run FastAPI development server
- `cd api && pytest tests/` - Run API tests
- `cd api && python -m pytest tests/test_*.py` - Run specific test file

### Frontend (frontend/)
- `cd frontend && npm run dev` - Start development server
- `cd frontend && npm run build` - Build for production
- `cd frontend && npm test` - Run tests
- `cd frontend && npm run typecheck` - Type checking

### Data Ingestion (data_ingestion/)
- `cd data_ingestion && python data_ingestion_pipeline/submit_pipeline.py` - Submit data pipeline to Vertex AI

## Architecture Overview

### Core Components

1. **Agent System** (`app/`):
   - **Main Agent** (`app/agent.py`): LangGraph-based orchestration using ChatVertexAI (Gemini 2.0 Flash)
   - **CrewAI Multi-Agent** (`app/crew/`): Three specialized agents (KEN-E, BET-E, VIK-E) for execution, web scraping, and reporting
   - **Agent Engine App** (`app/agent_engine_app.py`): Deployment wrapper for Google Cloud Agent Engine

2. **API Service** (`api/`):
   - **FastAPI Application** (`api/src/kene_api/main.py`): RESTful API with Neo4j and Firestore integration
   - **Database Layer**: Neo4j for graph data, Firestore for document storage
   - **Routers**: Modular endpoints for metrics, activities, insights, intuitions, items, and funnel reports

3. **Frontend** (`frontend/`):
   - **React + TypeScript**: Modern SPA built with Vite
   - **UI Components**: Comprehensive component library with Radix UI and TailwindCSS
   - **Routing**: React Router 6 for client-side navigation
   - **State Management**: Context API for authentication and dashboard state

4. **Data Ingestion** (`data_ingestion/`):
   - **Vertex AI Pipeline**: Kubeflow pipeline for data processing and embedding generation
   - **Components**: Modular data ingestion and processing components

### Key Libraries and Frameworks

- **Python**: LangGraph, CrewAI, FastAPI, Neo4j, Firebase Admin SDK
- **JavaScript**: React, TypeScript, Vite, TailwindCSS, Radix UI
- **Infrastructure**: Google Cloud Platform (Vertex AI, Firestore, Neo4j)
- **AI/ML**: ChatVertexAI (Gemini 2.0 Flash), OpenTelemetry tracing

## Development Workflow

### Agent Development
1. Prototype in Jupyter notebooks (`notebooks/`)
2. Implement agent logic in `app/agent.py`
3. Configure crew agents in `app/crew/config/`
4. Test locally with `make ken-e`
5. Deploy with `make backend`

### API Development
1. Define models in `api/src/kene_api/models/`
2. Create routers in `api/src/kene_api/routers/`
3. Add tests in `api/tests/`
4. Test endpoints with `/docs` (Swagger UI)

### Frontend Development
1. Create components in `frontend/src/components/`
2. Define types in `frontend/src/types/`
3. Add pages in `frontend/src/pages/`
4. Test with `npm run dev`

## Testing Strategy

- **Unit Tests**: Python pytest for API and agent components
- **Integration Tests**: End-to-end testing with databases
- **Frontend Tests**: Vitest for React components
- **Load Testing**: Dedicated load test suite in `tests/load_test/`

## Infrastructure & Deployment

- **Terraform**: Infrastructure as code in `deployment/terraform/`
- **CI/CD**: GitHub Actions workflows in `deployment/ci/` and `deployment/cd/`
- **Docker**: Containerization for API and frontend services
- **Environment**: Dev and prod environments with separate GCP projects

## Data Architecture

- **Neo4j**: Graph database for relationships between entities
- **Firestore**: Document storage for user data and configurations
- **BigQuery**: Data warehousing and analytics
- **Vertex AI Search**: RAG-enabled search and retrieval

## Monitoring & Observability

- **OpenTelemetry**: Distributed tracing throughout the system
- **Google Cloud Logging**: Centralized logging
- **BigQuery**: Event storage for analytics
- **Health Checks**: Built-in health endpoints for all services