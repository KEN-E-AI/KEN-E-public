# Email Service Setup for Local Development

This guide explains how to configure SendGrid for sending invitation emails in local development.

## Option 1: Use Secret Manager (Recommended - Matches Production)

This approach fetches the SendGrid API key from Google Cloud Secret Manager, just like staging and production do.

### Steps:

1. **Authenticate with Google Cloud:**
   ```bash
   gcloud auth application-default login
   ```

2. **The `.env` file is already configured** with:
   ```bash
   GOOGLE_CLOUD_PROJECT=ken-e-dev
   SENDGRID_API_KEY=sm://sendgrid-api-key
   EMAIL_FROM_ADDRESS=noreply@ken-e.ai
   EMAIL_FROM_NAME=KEN-E Team
   APP_BASE_URL=http://localhost:8080
   ```

3. **Start the API server:**
   ```bash
   cd api && uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Verify it works:**
   ```bash
   # Open a new terminal
   cd api
   export GOOGLE_CLOUD_PROJECT=ken-e-dev
   uv run python scripts/diagnose_email_service.py
   ```

   You should see: `✅ Email service appears to be configured correctly`

### Troubleshooting Option 1:

**If you see "SendGrid API key not found":**

The issue is that `uv run` may not be loading the `.env` file. Try:

```bash
# Export the env var in your shell
export GOOGLE_CLOUD_PROJECT=ken-e-dev

# Then start the server
cd api && uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000
```

**Or use python-dotenv to load .env automatically:**
```bash
cd api
uv add python-dotenv
uv run python -c "from dotenv import load_dotenv; load_dotenv(); import os; print('Project:', os.getenv('GOOGLE_CLOUD_PROJECT'))"
```

---

## Option 2: Direct API Key (Simpler - For Local Dev Only)

This approach bypasses Secret Manager and uses the API key directly.

### Steps:

1. **Get the SendGrid API key:**
   ```bash
   # Option A: From Secret Manager
   gcloud auth application-default login
   gcloud secrets versions access latest --secret="sendgrid-api-key" --project=ken-e-dev

   # Option B: Create a dev-only key at https://app.sendgrid.com/settings/api_keys
   ```

2. **Update `api/.env`:**
   ```bash
   # Change this line:
   SENDGRID_API_KEY=sm://sendgrid-api-key

   # To this (with your actual key):
   SENDGRID_API_KEY=SG.your-actual-sendgrid-api-key-here
   ```

3. **Start the API server:**
   ```bash
   cd api && uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Test:**
   ```bash
   cd api && uv run python scripts/diagnose_email_service.py
   ```

**Pro:** Simple, works immediately
**Con:** API key in local file (don't commit it!)

---

## Option 3: Environment Variable (CI/CD Style)

Set the environment variable directly in your shell.

### Steps:

1. **Get the key and export it:**
   ```bash
   export SENDGRID_API_KEY=$(gcloud secrets versions access latest --secret="sendgrid-api-key" --project=ken-e-dev)
   ```

2. **Start the API server in the same shell:**
   ```bash
   cd api && uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000
   ```

**Pro:** No files to modify, key not stored
**Con:** Need to export in every shell session

---

## Automated Setup Script

We've created a setup script that automates Option 1:

```bash
./api/scripts/setup_local_dev.sh
```

This script will:
- Check if gcloud is installed
- Authenticate you with Google Cloud
- Verify Secret Manager access
- Test email service configuration

---

## Testing the Setup

After configuration, test that emails can be sent:

### 1. Run the diagnostic script:
```bash
cd api && uv run python scripts/diagnose_email_service.py
```

Expected output:
```
✅ Email service appears to be configured correctly
```

### 2. Test invitation flow:
1. Start the API server
2. Start the frontend (`cd frontend && npm run dev:development`)
3. Sign in as an organization admin
4. Try inviting a new user
5. Check that the invitation email is sent (check SendGrid dashboard or your email)

---

## Common Issues

### "SendGrid API key not found"
- **Cause:** `GOOGLE_CLOUD_PROJECT` environment variable not set or `.env` not loaded
- **Fix:**
  ```bash
  export GOOGLE_CLOUD_PROJECT=ken-e-dev
  # Restart API server
  ```

### "Failed to fetch secret from Secret Manager"
- **Cause:** Not authenticated with gcloud
- **Fix:**
  ```bash
  gcloud auth application-default login
  ```

### "Permission denied" when accessing secret
- **Cause:** Missing Secret Manager Secret Accessor role
- **Fix:** Ask a project admin to grant you access:
  ```bash
  gcloud secrets add-iam-policy-binding sendgrid-api-key \
      --member="user:your-email@example.com" \
      --role="roles/secretmanager.secretAccessor" \
      --project=ken-e-dev
  ```

### API key format warning
- **Cause:** SendGrid API keys should start with `SG.`
- **Fix:** Verify you're using a valid SendGrid API key

---

## What Changed

The following files were updated to support Option 1:

1. **`api/.env`** - Added `GOOGLE_CLOUD_PROJECT=ken-e-dev` and email configuration
2. **`api/.env.example`** - Added documentation for Secret Manager configuration
3. **`api/scripts/setup_local_dev.sh`** - New automated setup script
4. **`api/scripts/diagnose_email_service.py`** - Diagnostic tool (already existed)
5. **`CLAUDE.md`** - Added "Email Service Setup" section with complete guide

---

## Recommendation

**For local development:** Use **Option 1** (Secret Manager) to match your staging/production setup exactly.

**For quick testing:** Use **Option 2** (Direct API key) if you need to get up and running immediately.

---

## Next Steps

After setup:
1. ✅ Run `./api/scripts/setup_local_dev.sh` (Option 1) or update `.env` directly (Option 2)
2. ✅ Start the API server
3. ✅ Test with `python api/scripts/diagnose_email_service.py`
4. ✅ Try inviting a user from the frontend to verify end-to-end

Questions? Check the troubleshooting section above or see `CLAUDE.md` for more details.
