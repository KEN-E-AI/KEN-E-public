# Environment Configuration

This directory contains environment-specific configuration files for the Kene API.

## Environment Files

- **`.env.example`** - Template file with all available environment variables
- **`.env.dev`** - Development environment configuration
- **`.env.prod`** - Production environment configuration

## Docker Compose Usage

### Development
```bash
# Use development configuration
docker-compose -f docker-compose.dev.yml up

# Or use the main docker-compose.yml (defaults to dev)
docker-compose up
```

### Production
```bash
# Use production configuration
docker-compose -f docker-compose.prod.yml up
```

## Setting Up Environment Files

1. Copy the template file:
   ```bash
   cp .env.example .env.dev
   cp .env.example .env.prod
   ```

2. Edit each file with the appropriate values for that environment.

## Environment Variables

### Application Settings
- `DEBUG` - Enable/disable debug mode
- `HOST` - Host to bind the application to
- `PORT` - Port to run the application on
- `RELOAD` - Enable/disable auto-reload for development

### Database Configuration
- `NEO4J_URI` - Neo4j database connection URI
- `NEO4J_USERNAME` - Neo4j username
- `NEO4J_PASSWORD` - Neo4j password
- `NEO4J_DATABASE` - Neo4j database name

### Superset Integration
- `SUPERSET_BASE_URL` - Apache Superset instance URL
- `SUPERSET_USERNAME` - Superset username
- `SUPERSET_PASSWORD` - Superset password

### Google Cloud Firestore
- `GOOGLE_APPLICATION_CREDENTIALS` - Path to service account key file
- `GOOGLE_CLOUD_PROJECT_ID` - Google Cloud project ID
- `FIRESTORE_DATABASE_ID` - Firestore database ID

### CORS Settings
- `ALLOWED_ORIGINS` - Comma-separated list of allowed origins
- `ALLOWED_METHODS` - Comma-separated list of allowed HTTP methods
- `ALLOWED_HEADERS` - Allowed headers for CORS

## Security Notes

- Never commit actual environment files (`.env.dev`, `.env.prod`) to version control
- Use strong passwords and secure connection strings in production
- Restrict CORS settings appropriately for each environment
- Use environment-specific service accounts and databases
