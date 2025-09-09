# Environment Setup Guide

## Quick Start - Unified Environment Switching

The KEN-E project now includes a unified environment switching system that configures all three components (Agents, API, Frontend) with a single command.

### One Command to Switch Everything

```bash
# Switch to development environment
./set-environment.sh development
# or
make env-dev

# Switch to staging environment
./set-environment.sh staging
# or
make env-staging

# Switch to production environment (use with caution!)
./set-environment.sh production
# or
make env-prod
```

### What the Script Does

The unified script automatically:

1. **Agents (app/adk)**: Copies the appropriate `.env.{environment}` file to `.env`
2. **API**: Runs the environment setup script with service account configuration
3. **Frontend**: Prepares the environment file for the selected environment

### Starting Services After Environment Switch

Once the environment is configured, start each service:

```bash
# 1. Start API (port 8000)
cd api && uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000

# 2. Start Frontend (port 8080)
cd frontend && npm run dev:development  # or dev:staging, dev:production

# 3. Run Agents (if needed)
cd app/adk && uv run python [your_agent_script.py]
```

## Environment Details

### Development Environment
- **Project**: ken-e-dev
- **Purpose**: Local development and testing
- **API URL**: http://localhost:8000
- **Frontend URL**: http://localhost:8080

### Staging Environment
- **Project**: ken-e-staging
- **Purpose**: Pre-production testing
- **API URL**: Staging API endpoint
- **Requires**: Service account credentials

### Production Environment
- **Project**: ken-e-production
- **Purpose**: Live production system
- **API URL**: Production API endpoint
- **Requires**: Service account credentials
- **⚠️ WARNING**: Use with extreme caution!

## Manual Environment Switching (Advanced)

If you need to configure components individually:

### Step 1: Agents Configuration
```bash
cd app/adk
cp .env.development .env  # or .env.staging, .env.production
```

### Step 2: API Configuration
```bash
cd api
./scripts/set_environment_with_sa.sh development  # or staging, production
```

### Step 3: Frontend Configuration
The frontend reads the environment at build/run time:
```bash
cd frontend
npm run dev:development  # or dev:staging, dev:production
```

## Troubleshooting

### Common Issues

1. **Permission Denied Error (403)**
   - **Cause**: Mismatch between environment configuration and authentication
   - **Solution**: Ensure all components are using the same environment
   - **Check**: Run `./set-environment.sh [environment]` to sync all components

2. **Service Account Not Found**
   - **Cause**: Missing service account JSON files
   - **Solution**: Ensure service account files exist in `api/` directory:
     - `ken-e-dev-sa.json`
     - `ken-e-staging-sa.json`
     - `ken-e-production-sa.json`

3. **Environment Variables Not Loading**
   - **Cause**: .env file not properly created
   - **Solution**: Check that the source `.env.{environment}` files exist
   - **Verify**: Look for `.env` files in each component directory after running the script

### Verifying Current Environment

To check which environment is currently configured:

```bash
# Check API environment
grep ENVIRONMENT api/.env

# Check Agents project
grep GOOGLE_CLOUD_PROJECT_ID app/adk/.env

# Check Frontend API URL
grep VITE_API_BASE_URL frontend/.env
```

### Environment File Locations

```
ken-e/
├── set-environment.sh           # Unified switching script
├── app/adk/
│   ├── .env                    # Current environment (generated)
│   ├── .env.development        # Development config
│   ├── .env.staging           # Staging config
│   └── .env.production        # Production config
├── api/
│   ├── .env                    # Current environment (generated)
│   ├── .env.development        # Development config
│   ├── .env.staging           # Staging config
│   ├── .env.production        # Production config
│   └── scripts/
│       └── set_environment_with_sa.sh
└── frontend/
    ├── .env                    # Current environment (generated)
    ├── .env.development        # Development config
    ├── .env.staging           # Staging config
    └── .env.production        # Production config
```

## Best Practices

1. **Always use the unified script** for environment switching to avoid mismatches
2. **Verify the environment** before performing sensitive operations
3. **Use development** for local testing and development
4. **Test in staging** before deploying to production
5. **Be extra careful** when switching to production environment
6. **Check git status** before committing - don't commit `.env` files

## Security Notes

- Never commit `.env` files to version control
- Service account JSON files should be kept secure and not committed
- Use different service accounts for each environment
- Regularly rotate service account keys in production
- Limit production access to authorized personnel only