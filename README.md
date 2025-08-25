# KEN-E

An AI-powered marketing analysis system built on Google Cloud Platform. KEN-E uses Google's Agent Development Kit (ADK) deployed to Vertex AI Agent Engine, integrated with a modern React frontend to provide comprehensive marketing insights and analytics.

## Overview

KEN-E is a sophisticated marketing analysis platform that leverages:
- **AI-Powered Agent**: Google ADK agent deployed on Vertex AI Agent Engine for intelligent marketing assistance
- **Modern Tech Stack**: FastAPI backend, React frontend, Neo4j graph database
- **Cloud-Native**: Fully deployed on Google Cloud Platform with Vertex AI integration
- **Real-time Analytics**: Performance metrics, big bets tracking, and exploration tools
- **Claude Code Shortcuts**: A series of shortcuts have been created for Claude Code, and an example for using them properly can be found [here](https://www.youtube.com/watch?v=SDiDkK0r-9c)

## Project Structure

```
ken-e/
├── app/                    # Utility modules
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

#### Configure API Environment

```bash
# Copy environment files
cd api
cp .env.example .env.development
cp .env.example .env.staging  
cp .env.example .env.production

# Edit each file with:
# - Neo4j credentials for each environment
# - Google Cloud project IDs
# - reCAPTCHA site and secret keys (different for each environment)
# - Firebase service account paths

# Set environment (copies .env.development to .env)
./scripts/set_environment.sh development
cd ..
```

#### Configure Frontend Environment

```bash
# Copy environment files
cd frontend
cp .env.example .env.development
cp .env.example .env.staging
cp .env.example .env.production

# Edit each file with:
# - Firebase configuration for each environment
# - reCAPTCHA site keys (must match API environment)
# - API base URLs

# Set environment (copies .env.development to .env.local)
./scripts/set_environment.sh development
cd ..
```


### 3. Start Development Servers

```bash
# Terminal 1: Start API server
cd api
# Note: Use uv run without --active flag to avoid package reinstallation issues
uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start frontend
cd frontend
# Option 1: Use predefined environment scripts (recommended)
npm run dev:development  # Uses .env.development (port 8080)
npm run dev:staging     # Uses .env.staging (port 8080)
npm run dev:production  # Uses .env.production (port 8080)

# Option 2: Use base command with mode flag
npm run dev             # Uses default .env file
npm run dev -- --mode staging  # Uses .env.staging

# Note: The predefined scripts (dev:development, dev:staging, dev:production) are cleaner 
# and avoid the need for the double dash (--) syntax

# Access applications:
# - Frontend: http://localhost:8080
# - API Docs: http://localhost:8000/docs
```

### 4. Initialize Neo4j Data (Optional)

```bash
# Run migration script to populate Neo4j with sample data
cd api
uv run python scripts/migrate_organizations_to_neo4j.py
```

## Development Commands

### Root Level Commands
| Command              | Description                                                    |
| -------------------- | -------------------------------------------------------------- |
| `make install`       | Install all Python dependencies using uv                       |
| `make test`          | Run unit and integration tests                                 |
| `make lint`          | Run code quality checks (codespell, ruff, mypy)              |
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

# Environment-specific dev servers (recommended)
npm run dev:development  # Start dev server with .env.development (port 8080)
npm run dev:staging     # Start dev server with .env.staging (port 8080)
npm run dev:production  # Start dev server with .env.production (port 8080)

# Alternative: Base command with mode flag
npm run dev             # Uses default .env file
npm run dev -- --mode staging  # Uses .env.staging (requires -- before flags)

# Build commands
npm run build          # Build for production
npm run build:staging  # Build for staging environment
npm run build:production # Build for production environment

# Testing and tooling
npm test              # Run Vitest tests
npm run typecheck     # TypeScript type checking
npm run format.fix    # Format code with Prettier

# Environment switching
./scripts/set_environment.sh [development|staging|production]  # Switch environment files
```

### Data Pipeline
```bash
cd data_ingestion
python data_ingestion_pipeline/submit_pipeline.py  # Submit to Vertex AI
```

## Configuration Options

### Organization Creation Permissions

The API now supports configurable organization creation permissions via the `ORGANIZATION_CREATION_PERMISSION` environment variable:

- `all` (default) - Any authenticated user can create organizations
- `super_admin` - Only super administrators (users with @ken-e.ai emails) can create organizations
- `none` - Organization creation is disabled

To configure this in your API environment file:
```bash
# In api/.env
ORGANIZATION_CREATION_PERMISSION=all  # or super_admin, or none
```

## Architecture

### Core Components

1. **ADK Agent**: Google's Agent Development Kit deployed on Vertex AI Agent Engine
   - Intelligent conversational AI for marketing assistance
   - Session management and conversation persistence
   - Direct integration with frontend via API

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
# ADK Agent is pre-deployed and accessed via API configuration

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

## Secret Manager Integration

KEN-E uses Google Cloud Secret Manager for secure credential storage. All sensitive data (passwords, API keys, service account JSON) are stored in Secret Manager and referenced by their paths in environment files.

### Secret Manager Structure

**Production (Project: 395770269870)**
- `projects/395770269870/secrets/neo4j-password/versions/latest`
- `projects/395770269870/secrets/sendgrid-api-key/versions/latest`
- `projects/395770269870/secrets/superset-password/versions/latest`
- `projects/395770269870/secrets/recaptcha-secret-key/versions/latest`
- `projects/395770269870/secrets/api-service-account-json/versions/latest`
- `projects/395770269870/secrets/firebase-api-key/versions/latest`
- `projects/395770269870/secrets/recaptcha-site-key/versions/latest`

**Staging (Project: 391472102753)** and **Development (Project: 525657242938)** follow the same pattern.

### How It Works

#### API Backend
- **Automatic Resolution**: Environment variables containing Secret Manager paths are automatically resolved at runtime
- **Service Account JSON**: Firestore authentication supports both Secret Manager JSON and file-based credentials
- **Fallback Support**: Falls back to original values if Secret Manager access fails

#### Frontend
- **Build-Time Resolution**: Secrets are resolved during the build process using `scripts/resolve-secrets.js`
- **Environment-Specific**: Each environment (dev/staging/prod) has its own secret paths
- **Secure Builds**: Resolved secrets are stored in `.env.resolved` (git-ignored) during builds

### Authentication Setup

For local development and secret resolution, the project now uses service account files for authentication:

#### Service Account Files

Place your service account JSON files in the `api/` directory:
- `api/ken-e-dev.json` - Development service account
- `api/ken-e-staging.json` - Staging service account  
- `api/ken-e-production.json` - Production service account

**Important Security Notes:**
- Never commit service account files to git (they're already in .gitignore)
- Each service account needs the `Secret Manager Secret Accessor` role
- The frontend build process automatically uses these files for secret resolution

#### Frontend Secret Resolution

The frontend automatically resolves secrets during build/dev commands:
```bash
# When you run these commands, secrets are automatically resolved
npm run dev:development  # Uses api/ken-e-dev.json
npm run dev:staging      # Uses api/ken-e-staging.json
npm run dev:production   # Uses api/ken-e-production.json
npm run build:staging    # Uses api/ken-e-staging.json
npm run build:production # Uses api/ken-e-production.json
```

#### Fallback Authentication

If service account files are not available, you can use Application Default Credentials:
```bash
# Authenticate with Google Cloud (fallback option)
gcloud auth application-default login --project=ken-e-staging
```

**Note**: Service account files are preferred as they avoid re-authentication issues (RAPT errors).

For production deployments, ensure service accounts have the `Secret Manager Secret Accessor` role:
```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
  --role="roles/secretmanager.secretAccessor"
```

### Migration Benefits
- **Enhanced Security**: No plaintext secrets in version control
- **Centralized Management**: All secrets managed through Google Cloud Console
- **Audit Trail**: Complete access logs and versioning
- **Easy Rotation**: Update secrets without code changes
- **Environment Isolation**: Each environment has separate secret instances

## Documentation

- [CLAUDE.md](CLAUDE.md) - AI assistant guidance for the codebase
- [Frontend README](frontend/README.md) - Frontend-specific documentation
- [API Documentation](http://localhost:8000/docs) - Interactive API docs
- [Deployment Guide](deployment/README.md) - Infrastructure and deployment details

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [Google Cloud Platform](https://cloud.google.com/)
- AI powered by [Google's Agent Development Kit (ADK)](https://cloud.google.com/vertex-ai/docs/generative-ai/agent-development-kit)
- Initially generated with [`googleCloudPlatform/agent-starter-pack`](https://github.com/GoogleCloudPlatform/agent-starter-pack)