# KEN-E

A multi-agent AI system for marketing analysis built on Google Cloud Platform. KEN-E combines LangGraph orchestration, CrewAI multi-agent collaboration, and a modern React frontend to provide comprehensive marketing insights and analytics.

## Overview

KEN-E is a sophisticated marketing analysis platform that leverages:
- **AI-Powered Agents**: Three specialized CrewAI agents (KEN-E, BET-E, VIK-E) for execution, data collection, and reporting
- **Modern Tech Stack**: FastAPI backend, React frontend, Neo4j graph database
- **Cloud-Native**: Fully deployed on Google Cloud Platform with Vertex AI integration
- **Real-time Analytics**: Performance metrics, big bets tracking, and exploration tools
- **Claude Code Shortcuts**: A series of shortcuts have been created for Claude Code, and an example for using them properly can be found [here](https://www.youtube.com/watch?v=SDiDkK0r-9c)

## Project Structure

```
ken-e/
├── app/                    # Main agent system (LangGraph & CrewAI)
│   ├── agent.py           # Core LangGraph orchestration
│   ├── agent_engine_app.py # Google Cloud Agent Engine deployment
│   ├── crew/              # CrewAI multi-agent configuration
│   └── utils/             # Utilities for GCS, tracing, typing
├── api/                   # FastAPI REST service
│   ├── src/kene_api/      # API source code
│   ├── tests/             # API test suite
│   └── docker files       # Containerization configs
├── frontend/              # React TypeScript application
│   ├── src/               # Frontend source code
│   └── public/            # Static assets
├── data_ingestion/        # Vertex AI data pipeline
│   └── data_ingestion_pipeline/
├── deployment/            # Infrastructure & CI/CD
│   ├── terraform/         # IaC for GCP resources
│   ├── ci/               # CI pipeline (PR checks)
│   └── cd/               # CD pipelines (staging/prod)
├── notebooks/             # Jupyter notebooks for prototyping
└── tests/                 # Testing suite
    ├── unit/             # Unit tests
    ├── integration/      # Integration tests
    └── load_test/        # Load testing with Locust
```

## Requirements

Before you begin, ensure you have:
- **Python 3.10-3.11**: Required Python version
- **Node.js 18+**: For frontend development
- **uv**: Modern Python package manager - [Install](https://docs.astral.sh/uv/getting-started/installation/)
- **Google Cloud SDK**: For GCP services - [Install](https://cloud.google.com/sdk/docs/install)
- **Terraform**: For infrastructure deployment - [Install](https://developer.hashicorp.com/terraform/downloads)
- **Docker**: For containerized development - [Install](https://docs.docker.com/get-docker/)
- **make**: Build automation tool (pre-installed on most Unix-based systems)

## Quick Start

### 1. Clone and Install

```bash
# Clone the repository
git clone https://github.com/KEN-E-AI/ken-e.git
cd ken-e

# Install Python dependencies
make install

# Install frontend dependencies
cd frontend && npm install
cd ..
```

### 2. Configure Environment

```bash
# Set up Google Cloud
export PROJECT_ID="YOUR_PROJECT_ID"
export LOCATION="us-central1"
gcloud config set project $PROJECT_ID
gcloud auth application-default login
gcloud auth application-default set-quota-project $PROJECT_ID

# Copy environment files
cp api/.env.example api/.env
# Edit api/.env with your configuration

# Create frontend environment
cat > frontend/.env.local << EOF
VITE_API_BASE_URL=http://localhost:8000
VITE_FIREBASE_API_KEY=your-firebase-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-auth-domain
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-storage-bucket
VITE_FIREBASE_MESSAGING_SENDER_ID=your-sender-id
VITE_FIREBASE_APP_ID=your-app-id
EOF
```

### 3. Start Development Servers

```bash
# Terminal 1: Start API server
cd api && uvicorn src.kene_api.main:app --reload

# Terminal 2: Start frontend
cd frontend && npm run dev

# Access applications:
# - Frontend: http://localhost:8080
# - API Docs: http://localhost:8000/docs
```

## Development Commands

### Root Level Commands
| Command              | Description                                                    |
| -------------------- | -------------------------------------------------------------- |
| `make install`       | Install all Python dependencies using uv                       |
| `make test`          | Run unit and integration tests                                 |
| `make lint`          | Run code quality checks (codespell, ruff, mypy)              |
| `make backend`       | Deploy agent to Google Cloud Agent Engine                      |
| `uv run jupyter lab` | Launch Jupyter notebooks for prototyping                       |

### API Development
```bash
cd api
uvicorn src.kene_api.main:app --reload  # Start dev server
pytest tests/                            # Run tests
./docker.sh dev                          # Run in Docker
./docker.sh test                         # Run tests in Docker
```

### Frontend Development
```bash
cd frontend
npm run dev          # Start dev server (port 8080)
npm run build        # Build for production
npm test            # Run tests
npm run typecheck   # Type checking
npm run format.fix  # Format code
```

### Data Pipeline
```bash
cd data_ingestion
python data_ingestion_pipeline/submit_pipeline.py  # Submit to Vertex AI
```

## Architecture

### Core Components

1. **Agent System** (`app/`): LangGraph orchestration with CrewAI agents
   - KEN-E: Main execution agent
   - BET-E: Web scraping and data collection
   - VIK-E: Reporting and analysis

2. **API Service** (`api/`): FastAPI with Neo4j and Firestore
   - RESTful endpoints for metrics, activities, insights
   - Firebase authentication
   - Async support with CORS

3. **Frontend** (`frontend/`): React 18 with TypeScript
   - ~50 Radix UI components
   - TailwindCSS styling
   - Protected routing with Firebase Auth

4. **Data Pipeline** (`data_ingestion/`): Vertex AI Kubeflow pipeline
   - Data processing and embedding generation
   - RAG-enabled search capabilities

## Deployment

### Infrastructure Setup

The project uses Terraform for infrastructure as code:

```bash
cd deployment/terraform
terraform init
terraform plan -var-file=vars/staging.tfvars
terraform apply -var-file=vars/staging.tfvars
```

See [deployment/README.md](deployment/README.md) for detailed instructions.

### CI/CD Pipeline

The project includes GitHub Actions workflows:
- **PR Checks**: Automated testing on pull requests
- **Staging Deployment**: Automatic deployment to staging
- **Production Deployment**: Manual approval required

### Manual Deployment

```bash
# Deploy agent to Agent Engine
make backend

# Deploy API to Cloud Run
cd api && gcloud run deploy kene-api --source .

# Deploy frontend to Cloud Run
cd frontend && npm run build
gcloud run deploy kene-frontend --source .
```

## Testing

```bash
# Run all tests
make test

# Run specific test suites
cd api && pytest tests/                    # API tests
cd frontend && npm test                    # Frontend tests
cd api && ./docker.sh test                # Dockerized tests
python -m pytest tests/load_test/          # Load tests
```

## Monitoring and Observability

- **OpenTelemetry**: Distributed tracing across all services
- **Google Cloud Logging**: Centralized log aggregation
- **BigQuery**: Long-term event storage and analytics
- **Looker Studio**: [Dashboard template](https://lookerstudio.google.com/c/reporting/fa742264-4b4b-4c56-81e6-a667dd0f853f/page/tEnnC) for visualization

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Documentation

- [CLAUDE.md](CLAUDE.md) - AI assistant guidance for the codebase
- [Frontend README](frontend/README.md) - Frontend-specific documentation
- [API Documentation](http://localhost:8000/docs) - Interactive API docs
- [Deployment Guide](deployment/README.md) - Infrastructure and deployment details

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [Google Cloud Platform](https://cloud.google.com/)
- Agent framework by [LangGraph](https://github.com/langchain-ai/langgraph) and [CrewAI](https://www.crewai.com/)
- Initially generated with [`googleCloudPlatform/agent-starter-pack`](https://github.com/GoogleCloudPlatform/agent-starter-pack)