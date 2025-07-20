# Kene API

A modern FastAPI web service built with Python, featuring automatic API documentation, request/response validation, and async support.

> **⚠️ Important:** This is a Python project that uses `pyproject.toml` for dependency management. There is no `package.json` file. Do not use npm/node commands in this directory. Use `uv` or `python` commands as described below.

## Features

- **FastAPI Framework**: High-performance, easy-to-use web framework
- **Neo4j Integration**: Graph database support for complex relationship queries
- **Automatic API Documentation**: Interactive docs at `/docs` and `/redoc`
- **Pydantic Models**: Request/response validation and serialization
- **Async Support**: Built for high-performance async operations
- **Testing Suite**: Comprehensive tests with pytest and httpx
- **Modern Python**: Uses uv for fast dependency management
- **CORS Support**: Configurable cross-origin resource sharing
- **Environment Configuration**: Flexible settings management

## Project Structure

```
src/kene_api/
├── main.py              # Main FastAPI application
├── config.py            # Application configuration
├── database.py          # Neo4j database service
├── models/
│   ├── kene_models.py   # Business domain models
│   └── schemas.py       # Pydantic models
└── routers/
    ├── activities.py    # Activity management endpoints
    ├── insights.py      # Insight relationships endpoints
    ├── intuitions.py    # Intuition management endpoints
    ├── metrics.py       # Metrics endpoints
    └── ...              # Other API route handlers
tests/
└── test_main.py         # Test suite
```

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Neo4j database (local installation or cloud instance)

### Installation

1. Clone the repository and navigate to the project directory
2. Install dependencies:
   ```bash
   uv sync
   ```
3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your Neo4j connection details
   ```

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

#### Environment Setup

1. **Set up environment-specific configurations**:
   ```bash
   # Copy example to create environment-specific files
   cp .env.example .env.development
   cp .env.example .env.staging
   cp .env.example .env.production
   
   # Edit each file with appropriate settings
   # Then set the active environment:
   ./scripts/set_environment.sh development
   ```

2. **Configure Neo4j Aura instances**:
   - Create separate Neo4j Aura instances for dev/staging/prod
   - Update each .env file with the appropriate credentials

#### Development Server

**Option 1: Using uv directly (recommended)**
```bash
# From the api directory:
cd api && uv run --active -- uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000
```

**Option 2: Using the Python development script**
```bash
# From the api directory:
cd api && python run_dev.py
```

**Option 3: Using Docker**
```bash
# From the api directory:
cd api && ./docker.sh dev
```

**Note:** This is a Python project using `pyproject.toml`. There is no `package.json` file - do not use npm commands in this directory.

#### Production
```bash
uv run --active uvicorn src.kene_api.main:app --host 0.0.0.0 --port 8000
```

#### Switching Environments
```bash
# Switch to staging
./scripts/set_environment.sh staging

# Switch to production
./scripts/set_environment.sh production

# Switch back to development
./scripts/set_environment.sh development
```

The API will be available at:
- **Application**: http://localhost:8000
- **Interactive API docs**: http://localhost:8000/docs
- **Alternative docs**: http://localhost:8000/redoc

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

## Configuration

The application can be configured using environment variables:

### Application Settings
- `DEBUG`: Enable debug mode (default: false)
- `HOST`: Server host (default: 0.0.0.0)
- `PORT`: Server port (default: 8000)
- `RELOAD`: Enable auto-reload in development (default: false)

### Neo4j Database Settings
- `NEO4J_URI`: Neo4j connection URI (default: bolt://localhost:7687)
- `NEO4J_USERNAME`: Database username (default: neo4j)
- `NEO4J_PASSWORD`: Database password (required)
- `NEO4J_DATABASE`: Database name (default: neo4j)

Copy `.env.example` to `.env` and adjust the values as needed for your environment.

### CORS Settings
- `ALLOWED_ORIGINS`: Comma-separated list of allowed origins
- `ALLOWED_METHODS`: Comma-separated list of allowed HTTP methods
- `ALLOWED_HEADERS`: Allowed headers (* for all)

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

## Breaking Changes

See [BREAKING_CHANGES.md](./BREAKING_CHANGES.md) for a list of breaking changes and migration guides.

### Creating New Endpoints

1. Define Pydantic models in `src/kene_api/models/schemas.py`
2. Create route handlers in `src/kene_api/routers/`
3. Include the router in `src/kene_api/main.py`
4. Add tests in `tests/`
