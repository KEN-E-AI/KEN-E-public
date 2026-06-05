# Configure Google Authentication for Staging Environment

## Current Status
✅ Switched to staging environment (`ken-e-staging`)
✅ Google sign-in provider enabled in Identity Platform
❌ Need to add authorized domains

## Steps to Add Authorized Domains

### 1. Access Identity Platform Settings

Since `ken-e-staging` uses Google Cloud Identity Platform (not Firebase Auth), go to:

**Option A - Google Cloud Console:**
```
https://console.cloud.google.com/customer-identity/settings?project=ken-e-staging
```

**Option B - Direct link to authorized domains:**
```
https://console.cloud.google.com/customer-identity/domains?project=ken-e-staging
```

### 2. Add These Authorized Domains

Add the following domains to the authorized list:

- `localhost` (for local development)
- `localhost:8080` (specific port for frontend dev server)
- `localhost:8000` (if needed for API testing)
- `ken-e-staging.firebaseapp.com` (default Firebase domain)
- `ken-e-staging.web.app` (default Firebase hosting domain)
- Your staging domain (if you have one, e.g., `staging.ken-e.ai`)

### 3. Start the Frontend Dev Server

```bash
cd frontend
npm run dev:staging
```

This will start the dev server on http://localhost:8080 with staging configuration.

### 4. Test Google Sign-in

1. Open http://localhost:8080 in your browser
2. Try signing in with Google
3. The error should be resolved

## Troubleshooting

If you still get the `auth/unauthorized-domain` error:

1. **Check the exact domain**: Make sure you added `localhost:8080` (with the port)
2. **Wait for propagation**: Changes can take 1-2 minutes to take effect
3. **Clear cache**: Hard refresh the browser (Cmd+Shift+R on Mac)
4. **Verify environment**: Check that the app is using staging:
   ```bash
   cat frontend/.env.local | grep VITE_FIREBASE_PROJECT_ID
   # Should show: VITE_FIREBASE_PROJECT_ID="ken-e-staging"
   ```

## Alternative: Using gcloud CLI

If you prefer command line, you can try:

```bash
# List current configuration
gcloud alpha identity-toolkit config describe --project=ken-e-staging

# Note: Adding domains via CLI is not straightforward for Identity Platform
# The web console is the recommended approach
```

## Next Steps

After staging is working:
1. Repeat the same process for production (`ken-e-production`)
2. Add production domains: `ken-e.ai`, `app.ken-e.ai`, etc.
3. Test thoroughly before deploying

## Important Notes

- Identity Platform (used by staging/production) has slightly different settings than Firebase Auth (used by development)
- Make sure the OAuth consent screen is configured if prompted
- You may need to configure OAuth 2.0 credentials if not already done