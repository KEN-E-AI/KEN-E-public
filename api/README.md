# KEN-E API

A modern FastAPI web service built with Python, featuring automatic API documentation, request/response validation, and async support.

> **⚠️ Important:** This is a Python project that uses `pyproject.toml` for dependency management. There is no `package.json` file. Do not use npm/node commands in this directory. Use `uv` or `python` commands as described below.

## Features

- **FastAPI Framework**: High-performance, easy-to-use web framework
- **Neo4j Integration**: Graph database support for complex relationship queries
- **Firebase Authentication**: Secure JWT-based authentication with RBAC
- **Automatic API Documentation**: Interactive docs at `/docs` and `/redoc`
- **Pydantic Models**: Request/response validation and serialization
- **Async Support**: Built for high-performance async operations
- **Testing Suite**: Comprehensive tests with pytest and httpx
- **Modern Python**: Uses uv for fast dependency management
- **CORS Support**: Configurable cross-origin resource sharing
- **Environment Configuration**: Flexible settings management
- **Redis Caching**: Performance optimization for user permissions
- **Audit Logging**: Comprehensive security event tracking
- **Rate Limiting**: Protection against brute force attacks

## Project Structure

```
src/kene_api/
├── main.py              # Main FastAPI application
├── config.py            # Application configuration
├── database.py          # Neo4j database service
├── auth/                # Authentication and authorization
│   ├── user_context.py  # User context and permissions
│   ├── firebase_admin.py # Firebase token verification
│   ├── audit_logger.py  # Security event logging
│   ├── token_revocation.py # Token revocation service
│   └── rate_limiting.py # Rate limiting for auth endpoints
├── models/
│   ├── kene_models.py   # Business domain models
│   └── schemas.py       # Pydantic models
└── routers/
    ├── auth.py          # Authentication endpoints
    ├── activities.py    # Activity management endpoints
    ├── insights.py      # Insight relationships endpoints
    ├── intuitions.py    # Intuition management endpoints
    ├── metrics.py       # Metrics endpoints
    └── ...              # Other API route handlers
tests/
├── unit/                # Unit tests
└── integration/         # Integration tests
docs/
└── AUTHENTICATION.md    # Authentication documentation
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** - Fast Python package manager
- **Neo4j database** - Local installation or cloud instance (Neo4j Aura)
- **Google Cloud Project** - For Firestore and other GCP services

### Local Development Setup

1. **Clone the repository and navigate to the API directory**
   ```bash
   git clone <repository-url>
   cd ken-e/api
   ```

2. **Install dependencies**
   ```bash
   uv sync
   ```

3. **Configure environment**

   The API requires environment configuration for database connections and services.

   **For environments with Google Secret Manager (staging/production):**

   If you have service account credentials files (`ken-e-dev.json`, `ken-e-staging.json`, `ken-e-production.json`), use the service account script:

   ```bash
   # Test your service account permissions first
   python scripts/test_service_account.py ken-e-staging.json

   # If the test passes, use the service account script for staging
   ./scripts/use_staging_with_sa_fixed.sh

   # Or use the general script for any environment
   ./scripts/set_environment_with_sa.sh development
   ./scripts/set_environment_with_sa.sh staging
   ./scripts/set_environment_with_sa.sh production
   ```

   **For environments without service accounts or Secret Manager access:**

   ```bash
   # Option 1: Create a local environment file (recommended for staging/production)
   python scripts/create_local_staging_env.py
   # Edit .env.staging.local with actual credentials
   nano .env.staging.local
   # Use it
   cp .env.staging.local .env

   # Option 2: Use the basic script (works for development)
   ./scripts/set_environment.sh development
   ```

   **Manual configuration:**
   ```bash
   # Copy from example file
   cp .env.example .env
   
   # Then edit .env with your configuration
   ```

4. **Start the development server**

   After setting your environment, start the API server:

   ```bash
   # Option 1: Using uv directly (recommended)
   uv run --active -- uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000

   # Option 2: Using the Python script
   python run_dev.py

   # Option 3: Using Docker
   ./docker.sh dev
   ```

5. **Access the API**
   - API endpoints: `http://localhost:8000`
   - Interactive docs: `http://localhost:8000/docs`
   - Alternative docs: `http://localhost:8000/redoc`

## 🔐 Authentication

The API uses Firebase Authentication with JWT tokens. All protected endpoints require a valid Firebase ID token in the Authorization header.

### Quick Start
```bash
# Include token in requests
curl -H "Authorization: Bearer $FIREBASE_ID_TOKEN" \
     http://localhost:8000/api/v1/accounts/
```

### Key Features
- Firebase ID token verification
- Role-based access control (RBAC)
- Rate limiting on auth endpoints
- Token revocation support
- Redis caching for performance
- Comprehensive audit logging

For detailed authentication documentation, see [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md).

### Environment Details

| Environment | Neo4j Instance | Debug Mode | Usage |
|------------|----------------|------------|-------|
| Development | Dev Aura instance | Enabled | Local development |
| Staging | Staging Aura instance | Disabled | Testing with staging data |
| Production | Production Aura instance | Disabled | Production data (careful!) |

### Switching Between Environments

To switch between environments during development:

**With Service Account Credentials (Recommended):**
```bash
# Check current environment
grep ENVIRONMENT .env

# Switch to a different environment using service account
./scripts/set_environment_with_sa.sh development
./scripts/set_environment_with_sa.sh staging
./scripts/set_environment_with_sa.sh production

# For staging specifically, you can also use:
./scripts/use_staging_with_sa_fixed.sh

# Restart the API server to use the new environment
```

**Without Service Account Credentials:**
```bash
# Check current environment
./scripts/set_environment.sh

# Switch to development (no secrets needed)
./scripts/set_environment.sh development

# For staging/production without service accounts, use local env files
cp .env.staging.local .env  # or .env.production.local

# Restart the API server to use the new environment
```

### Environment Files

The project uses the following environment files:

- `.env.development` - Development environment configuration
- `.env.staging` - Staging environment configuration  
- `.env.production` - Production environment configuration
- `.env` - Active environment (created by set_environment.sh, gitignored)

### Service Account Configuration

For staging and production environments, the API uses Google Cloud service accounts to access Secret Manager. Place your service account JSON files in the `api/` directory:

- `ken-e-dev.json` - Development service account (optional)
- `ken-e-staging.json` - Staging service account
- `ken-e-production.json` - Production service account

**Important Security Notes:**
- Never commit service account files to git (they're already in .gitignore)
- Store these files securely and share them through secure channels
- Rotate service account keys periodically
- Each service account needs the `Secret Manager Secret Accessor` role

**Testing Service Account Permissions:**
```bash
# Test a specific service account
python scripts/test_service_account.py ken-e-staging.json

# Test all available service accounts
python scripts/test_service_account.py
```

If your service account lacks Secret Manager permissions, you can either:
1. Request the `roles/secretmanager.secretAccessor` role from your admin
2. Use local environment files with manually configured secrets
- `.env.example` - Template with all required environment variables

**Note:** Never commit `.env` or any file containing actual credentials to version control.

### Neo4j Setup

#### Option 1: Local Neo4j Installation

1. Download and install Neo4j Desktop from [neo4j.com](https://neo4j.com/download/)
2. Create a new database project
3. Start the database and note the connection details
4. Update your `.env` file:
   ```bash
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your_password_here
   NEO4J_DATABASE=neo4j
   ```

#### Option 2: Neo4j AuraDB (Cloud)

1. Sign up for a free account at [neo4j.com/aura](https://neo4j.com/aura/)
2. Create a new database instance
3. Download the connection details
4. Update your `.env` file:
   ```bash
   NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your_aura_password_here
   NEO4J_DATABASE=neo4j
   ```

#### Option 3: Docker Neo4j

```bash
docker run \
    --name neo4j \
    -p 7474:7474 -p 7687:7687 \
    -d \
    -v $HOME/neo4j/data:/data \
    -v $HOME/neo4j/logs:/logs \
    -v $HOME/neo4j/import:/var/lib/neo4j/import \
    -v $HOME/neo4j/plugins:/plugins \
    --env NEO4J_AUTH=neo4j/test \
    neo4j:latest
```

### Running the Application

For running the application, please refer to the [Quick Start](#-quick-start) section above.

#### Production Deployment
```bash
# For production deployment (without auto-reload)
uv run --active uvicorn src.kene_api.main:app --host 0.0.0.0 --port 8000
```

## Command Line Interface (CLI)

**Status: ✅ COMPLETED AND FULLY FUNCTIONAL**

The project includes a comprehensive CLI tool (`cli_manager.py`) for managing activities, metrics, insights, and intuitions through the command line with rich console output and confirmation steps.

### Quick Start

```bash
# Run the interactive CLI
uv run python cli_manager.py

# Test CLI functionality
uv run python test_cli_demo.py

# Make it executable and run directly
chmod +x cli_manager.py
./cli_manager.py
```

### CLI Features

The CLI provides full CRUD operations for:

- **Activities**: Create, view, edit, and delete activities with confirmation prompts
- **Metrics**: Manage metrics with validation for required fields and data types  
- **Insights**: Create and manage insight relationships between activities and metrics
- **Intuitions**: Create intuitions associated with insights (editing/deletion through insight relationships)

### Interface Features

- **Rich Console Output**: Beautiful tables, colored text, and formatted displays using the Rich library
- **Menu-driven Navigation**: Numbered options with easy navigation between sections
- **Data Validation**: Input validation and type checking for all fields
- **Preview Before Save**: Shows a formatted preview of data before confirmation
- **Confirmation Prompts**: All destructive operations (edit/delete) require user confirmation
- **Error Handling**: User-friendly error messages with API connectivity feedback
- **Context-aware Help**: Shows available options and relationships when creating data
- **Metrics**: Manage metrics with validation for required fields and data types  
- **Insights**: Create and manage insight relationships between activities and metrics
- **Intuitions**: Handle intuition relationships with direction specification (positive/negative)

### CLI Interface

The CLI includes:
- **Rich console output** with colored tables and formatted displays
- **Menu-driven navigation** with numbered options
- **Data validation** and preview before saving changes
- **Confirmation prompts** for all destructive operations (edit/delete)
- **Error handling** with user-friendly messages
- **Context-aware help** showing available activities/metrics when creating relationships

### Example CLI Usage

1. **Start the CLI**: The tool will prompt for an API base URL (defaults to localhost:8000) and account ID
2. **Main Menu**: Choose between Activities, Metrics, Insights, Intuitions, or viewing all data
3. **CRUD Operations**: Each entity type supports view, create, edit, and delete operations
4. **Confirmation Steps**: All create/edit/delete operations show a preview and require confirmation
5. **Navigation**: Easy navigation with numbered menus and option to return to previous levels

The CLI is designed to be user-friendly for both technical and non-technical users who need to manage Kene API data through the command line.

### Testing

Run the test suite:
```bash
uv run pytest tests/ -v
```

## API Endpoints

### Core Endpoints

- `GET /` - Welcome message
- `GET /health` - Health check endpoint (includes Neo4j status)

### Activities API
- `GET /api/v1/activities/` - Get all activities
- `POST /api/v1/activities/` - Create a new activity

### Metrics API
- `GET /api/v1/metrics/` - Get all metrics
- `POST /api/v1/metrics/` - Create a new metric

### Accounts API
- `GET /api/v1/accounts/` - Get all accounts
- `GET /api/v1/accounts/{account_id}` - Get a specific account
- `POST /api/v1/accounts/` - Create a new account (restricted for agency organizations)
- `PUT /api/v1/accounts/{account_id}` - Update an account
- `DELETE /api/v1/accounts/{account_id}` - Delete an account

**Note:** Account creation is restricted for agency organizations. Only regular organizations (where `agency=false`) can create accounts. Agency organizations will receive a 403 Forbidden error when attempting to create accounts.

### Insights API
- `GET /api/v1/insights/` - Get all insights
- `POST /api/v1/insights/search` - Search insights with filters
- `POST /api/v1/insights/` - Create a new insight relationship
- `PUT /api/v1/insights/` - Update an insight relationship
- `DELETE /api/v1/insights/` - Delete an insight relationship

### Intuitions API
- `POST /api/v1/intuitions/` - Create a new intuition
- `PUT /api/v1/intuitions/` - Update an intuition
- `DELETE /api/v1/intuitions/` - Delete an intuition

### Items API

- `POST /api/v1/items/` - Create a new item
- `GET /api/v1/items/` - Get all items
- `GET /api/v1/items/{item_id}` - Get a specific item
- `PUT /api/v1/items/{item_id}` - Update an item
- `DELETE /api/v1/items/{item_id}` - Delete an item

## ⚙️ Configuration

The application is configured using environment variables. Use the environment switching script or manually edit your `.env` file.

### Core Environment Variables

#### Application Settings
- `ENVIRONMENT`: Current environment (development|staging|production)
- `DEBUG`: Enable debug mode (true for development, false for staging/production)
- `HOST`: Server host (default: 0.0.0.0)
- `PORT`: Server port (default: 8000)
- `LOG_LEVEL`: Logging level (DEBUG|INFO|WARNING|ERROR)

#### Neo4j Database Settings
- `NEO4J_URI`: Neo4j connection URI (e.g., `neo4j+s://your-instance.databases.neo4j.io`)
- `NEO4J_USER`: Database username (typically: neo4j)
- `NEO4J_PASSWORD`: Database password (required)
- `NEO4J_DATABASE`: Database name (default: neo4j)

#### Google Cloud Settings
- `GOOGLE_CLOUD_PROJECT_ID`: Your GCP project ID
- `FIRESTORE_DATABASE_ID`: Firestore database ID (default: "(default)")

#### CORS Settings
- `CORS_ORIGINS`: Comma-separated list of allowed origins (e.g., `http://localhost:8080,https://app.ken-e.ai`)

#### Optional Settings
- `RECAPTCHA_SITE_KEY`: Google reCAPTCHA site key (if using reCAPTCHA)
- `RECAPTCHA_SECRET_KEY`: Google reCAPTCHA secret key (if using reCAPTCHA)

### Example .env File

```env
# Environment
ENVIRONMENT=development

# Application
DEBUG=true
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=DEBUG

# Neo4j
NEO4J_URI=neo4j+s://your-dev-instance.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-secure-password
NEO4J_DATABASE=neo4j

# Google Cloud
GOOGLE_CLOUD_PROJECT_ID=ken-e-dev
FIRESTORE_DATABASE_ID=(default)

# CORS
CORS_ORIGINS=http://localhost:8080,http://localhost:5173

# Optional
RECAPTCHA_SITE_KEY=
RECAPTCHA_SECRET_KEY=
```

## Docker Deployment

The application supports Docker deployment with multiple compose files for different environments.

### Prerequisites

1. **Environment Configuration**: Copy `.env.example` to `.env` and configure your settings:
   ```bash
   cp .env.example .env
   # Edit .env with your Neo4j credentials and other settings
   ```

2. **Neo4j Database**: Ensure your Neo4j instance is accessible from the Docker container.

### Docker Compose Files

- `docker-compose.yml` - Base configuration with environment variable support
- `docker-compose.dev.yml` - Development environment with hot reload
- `docker-compose.prod.yml` - Production environment with Nginx reverse proxy

### Development Deployment

```bash
# Build and start development environment
docker compose -f docker-compose.dev.yml up --build

# Or using the helper script
./docker.sh dev:up
```

Features:
- Hot reload enabled
- Source code mounted as volumes
- Debug mode enabled
- Environment variables loaded from `.env`

### Production Deployment

```bash
# Build and start production environment
docker compose -f docker-compose.prod.yml up --build -d

# Or using the helper script
./docker.sh prod:up
```

Features:
- Optimized production build
- Nginx reverse proxy
- Health checks enabled
- Environment variables loaded from `.env`
- Automatic container restart

### Basic Deployment

```bash
# Build and start with base configuration
docker compose up --build

# Or using the helper script
./docker.sh dev:build && ./docker.sh dev:up
```

### Docker Commands

The `docker.sh` script provides convenient commands:
```bash
# Development
./docker.sh dev:build    # Build development image
./docker.sh dev:up       # Start development containers
./docker.sh dev:down     # Stop development containers

# Production  
./docker.sh prod:build   # Build production image
./docker.sh prod:up      # Start production containers

# Testing
./docker.sh test         # Run tests in container

# Cleanup
./docker.sh clean        # Remove containers and images
```

### Environment Variables in Docker

All Docker Compose files now support environment variables from your `.env` file:

- **Application settings**: `DEBUG`, `HOST`, `PORT`, `RELOAD`
- **Neo4j configuration**: `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`
- **CORS settings**: `ALLOWED_ORIGINS`, `ALLOWED_METHODS`, `ALLOWED_HEADERS`

The containers will automatically use values from your `.env` file with sensible defaults for missing variables.

## Development

### Adding Dependencies

```bash
# Production dependencies
uv add package-name

# Development dependencies
uv add --dev package-name
```

### Code Style

This project follows FastAPI best practices:
- Use async/await for all endpoints
- Implement proper Pydantic models for request/response validation
- Include comprehensive docstrings
- Use appropriate HTTP status codes
- Implement proper error handling

## 🆘 Troubleshooting

### Common Issues

**Environment configuration not working:**

```bash
# Make sure the script is executable
chmod +x ./scripts/set_environment.sh

# Check if environment files exist
ls -la .env.*

# Manually check current environment
cat .env | grep ENVIRONMENT
```

**Neo4j connection errors:**

- Verify Neo4j credentials in your `.env` file
- For Neo4j Aura, ensure you're using the correct URI format: `neo4j+s://`
- Check that your IP address is whitelisted in Neo4j Aura settings
- Test connection with Neo4j Browser first

**Module import errors:**

```bash
# Ensure you're in the api directory
cd api

# Reinstall dependencies
uv sync

# Check Python version
python --version  # Should be 3.12+
```

**Port already in use:**

```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use a different port
uv run --active -- uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8001
```

**CORS errors from frontend:**

- Check `CORS_ORIGINS` in your `.env` file includes `http://localhost:8080`
- Ensure the API is running on the expected port
- Verify no proxy is interfering with requests

**Google Cloud authentication errors:**

- Ensure `GOOGLE_CLOUD_PROJECT_ID` is set correctly
- Check that you have the necessary credentials configured
- For local development with service accounts:
  ```bash
  # Test your service account
  python scripts/test_service_account.py ken-e-staging.json
  
  # Use the service account for environment setup
  ./scripts/use_staging_with_sa_fixed.sh
  ```

**Secret Manager access errors:**

If you get "Failed to resolve secrets from Google Secret Manager":
1. Verify service account has `Secret Manager Secret Accessor` role
2. Check project ID is correct (should be 391472102753 for staging)
3. Use local environment file as fallback:
   ```bash
   python scripts/create_local_staging_env.py
   cp .env.staging.local .env
   ```

**Environment switching errors:**

- If `set_environment.sh` fails, use `set_environment_with_sa.sh` instead
- Ensure service account JSON files are in the api/ directory
- Check file permissions: `chmod +x scripts/*.sh`

## Breaking Changes

See [BREAKING_CHANGES.md](./BREAKING_CHANGES.md) for a list of breaking changes and migration guides.

### Creating New Endpoints

1. Define Pydantic models in `src/kene_api/models/schemas.py`
2. Create route handlers in `src/kene_api/routers/`
3. Include the router in `src/kene_api/main.py`
4. Add tests in `tests/`
