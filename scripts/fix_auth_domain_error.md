# Fix for Firebase auth/unauthorized-domain Error

## Current Issue
You're getting `auth/unauthorized-domain` error when trying to sign in with Google. This happens because the domain you're accessing from isn't in the authorized domains list.

## Current Setup
- Your frontend is currently using: `ken-e-dev` (development environment)
- You need to authorize domains for the environment you're testing

## Solution Steps

### 1. Check Which Environment You're Using

```bash
cd frontend
cat .env.local | grep VITE_FIREBASE_PROJECT_ID
```

### 2. Add Authorized Domains

Based on which environment you're using, add domains to the appropriate project:

#### For Development (ken-e-dev):
1. Go to: https://console.firebase.google.com/project/ken-e-dev/authentication/settings
2. Add these domains:
   - `localhost`
   - `localhost:8080`
   - `localhost:8000`
   - Any other domains you're testing from

#### For Staging (ken-e-staging):
1. Go to: https://console.cloud.google.com/customer-identity/settings?project=ken-e-staging
2. Or: https://console.firebase.google.com/project/ken-e-staging/authentication/settings
3. Add these domains:
   - `localhost`
   - `localhost:8080`
   - Your staging domain (e.g., `staging.ken-e.ai`)
   - `ken-e-staging.firebaseapp.com`
   - `ken-e-staging.web.app`

#### For Production (ken-e-production):
1. Go to: https://console.cloud.google.com/customer-identity/settings?project=ken-e-production
2. Or: https://console.firebase.google.com/project/ken-e-production/authentication/settings
3. Add these domains:
   - `ken-e.ai`
   - `app.ken-e.ai`
   - `www.ken-e.ai`
   - `ken-e-production.firebaseapp.com`
   - `ken-e-production.web.app`

### 3. Switch Environments (if needed)

To test staging or production authentication:

```bash
# Switch to staging
cd frontend
./scripts/set_environment.sh staging
npm run dev:staging

# Or switch to production
./scripts/set_environment.sh production
npm run dev:production
```

### 4. Verify OAuth Configuration

Make sure Google sign-in is enabled for each environment:

#### Using Firebase Console:
1. Go to Authentication → Sign-in method
2. Ensure Google is enabled
3. Check that Web SDK configuration is properly set

#### Using Google Cloud Console:
1. Go to APIs & Services → Credentials
2. Check OAuth 2.0 Client IDs exist
3. Verify authorized JavaScript origins include your domains

### 5. Clear Cache and Test

After making changes:
1. Wait 1-2 minutes for changes to propagate
2. Clear browser cache (Cmd+Shift+R on Mac)
3. Try signing in again

## Common Issues

1. **Wrong environment**: Make sure your frontend is pointing to the correct Firebase project
2. **Missing domain**: The exact domain (including port) must be in the authorized list
3. **HTTP vs HTTPS**: Some environments require HTTPS for OAuth to work
4. **Propagation delay**: Changes can take a few minutes to take effect

## Quick Debug Commands

```bash
# Check current environment
cd frontend && grep VITE_FIREBASE_PROJECT_ID .env.local

# Check if you're using the right Firebase config
grep VITE_FIREBASE_AUTH_DOMAIN .env.local

# Run with specific environment
npm run dev:development  # Uses ken-e-dev
npm run dev:staging     # Uses ken-e-staging
npm run dev:production  # Uses ken-e-production
```