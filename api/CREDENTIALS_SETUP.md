# Service Account Credentials Setup

## Important Security Notice

**NEVER commit service account key files to the repository!** The `.gitignore` file is configured to exclude all JSON files except for specific exceptions like `package.json`.

## Setup Instructions

### 1. Create Service Account Keys

For each environment, you'll need to create a service account key:

#### Development
```bash
gcloud iam service-accounts keys create ken-e-dev-sa.json \
    --iam-account=ken-e-api@ken-e-dev.iam.gserviceaccount.com \
    --project=ken-e-dev
```

#### Staging
```bash
gcloud iam service-accounts keys create ken-e-staging-sa.json \
    --iam-account=ken-e-api@ken-e-staging.iam.gserviceaccount.com \
    --project=ken-e-staging
```

#### Production
```bash
gcloud iam service-accounts keys create ken-e-production-sa.json \
    --iam-account=ken-e-api@ken-e-production.iam.gserviceaccount.com \
    --project=ken-e-production
```

### 2. Update Environment Files

Update the `GOOGLE_APPLICATION_CREDENTIALS` in your `.env` files:

- `.env.development`: `GOOGLE_APPLICATION_CREDENTIALS=ken-e-dev-sa.json`
- `.env.staging`: `GOOGLE_APPLICATION_CREDENTIALS=ken-e-staging-sa.json`
- `.env.production`: `GOOGLE_APPLICATION_CREDENTIALS=ken-e-production-sa.json`

### 3. Required Permissions

The service accounts need the following roles:
- `roles/secretmanager.secretAccessor` - To access secrets in Secret Manager
- `roles/datastore.user` - To access Firestore
- Additional roles as needed for your application

### 4. Key Rotation

Regularly rotate service account keys:

1. Create a new key
2. Update the application to use the new key
3. Delete the old key after confirming the new one works

### 5. List and Delete Old Keys

To list existing keys:
```bash
gcloud iam service-accounts keys list \
    --iam-account=ken-e-api@ken-e-dev.iam.gserviceaccount.com \
    --project=ken-e-dev
```

To delete a key:
```bash
gcloud iam service-accounts keys delete KEY_ID \
    --iam-account=ken-e-api@ken-e-dev.iam.gserviceaccount.com \
    --project=ken-e-dev
```

## Template

See `google-cloud-service-account-key.json.template` for the expected format of service account key files.