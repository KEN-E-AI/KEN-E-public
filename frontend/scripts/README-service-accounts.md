# Service Account Setup for Frontend Secret Resolution

The `resolve-secrets.js` script has been updated to use service account files for authenticating with Google Secret Manager instead of Application Default Credentials (ADC).

## Required Service Account Files

The script expects service account JSON files to be located in the `api/` directory:

- `api/ken-e-dev.json` - For development environment
- `api/ken-e-staging.json` - For staging environment
- `api/ken-e-production.json` - For production environment

## Service Account Permissions

Ensure the service accounts have the necessary permissions:

- `Secret Manager Secret Accessor` role for reading secrets
- Access to the specific secrets referenced in your `.env.*` files

## How It Works

When you run commands like `npm run dev:staging`, the resolve-secrets.js script will:

1. Detect which environment you're using (development/staging/production)
2. Look for the corresponding service account file in `api/service-accounts/`
3. Use that service account to authenticate with Google Secret Manager
4. Resolve any secret references in your environment files

## Fallback Behavior

If the service account file is not found, the script will:

1. Log a warning message
2. Fall back to using Application Default Credentials (ADC)
3. You may need to run `gcloud auth application-default login` if you see authentication errors

## Security Notes

- **NEVER** commit service account JSON files to version control
- The service account files (`ken-e-*.json`) are already in `.gitignore`
- Service account files should have minimal required permissions
- Consider using workload identity in production environments

## Troubleshooting

If you see the error about "invalid_grant" or "invalid_rapt":

1. First check if your service account files are in place
2. If not using service accounts, re-authenticate with: `gcloud auth application-default login`
3. Make sure your service account has the correct permissions in the GCP project
