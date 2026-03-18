# Google Analytics OAuth Integration Setup

## Overview
The Google Analytics integration now uses OAuth 2.0 for authentication instead of service account keys, providing a better user experience with the familiar Google sign-in flow.

## Setup Instructions

### 1. Google Cloud Console Configuration

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select your project or create a new one
3. Enable the Google Analytics Data API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Analytics Data API"
   - Click on it and press "Enable"

### 2. Create OAuth 2.0 Credentials

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "OAuth client ID"
3. If prompted, configure the OAuth consent screen first:
   - Choose "External" for user type
   - Fill in the required app information
   - Add scopes:
     - `https://www.googleapis.com/auth/analytics.readonly`
     - `https://www.googleapis.com/auth/analytics.manage.users.readonly`
   - Add test users if in development
4. For the OAuth client:
   - Application type: "Web application"
   - Name: "KEN-E Google Analytics Integration"
   - Authorized redirect URIs:
     - For local development: `http://localhost:8000/api/oauth/callback/google`
     - For staging: `https://your-staging-api.com/api/oauth/callback/google`
     - For production: `https://your-production-api.com/api/oauth/callback/google`
5. Save the client ID and client secret

### 3. Configure Environment Variables

Add the following to your `api/.env` file:

```env
# Google OAuth 2.0 Configuration
GOOGLE_OAUTH_CLIENT_ID=your_client_id_here
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret_here
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/oauth/callback/google
FRONTEND_URL=http://localhost:8080
```

For staging/production, update the redirect URI and frontend URL accordingly.

### 4. User Flow

1. User navigates to Account Settings > Integrations
2. Clicks on Google Analytics integration
3. Clicks "Connect Google Analytics"
4. Gets redirected to Google sign-in
5. Authorizes the application
6. Gets redirected back to the application
7. Integration is now configured and ready to use

## Security Features

- **Encrypted Storage**: Access tokens and refresh tokens are encrypted using Fernet encryption (local) or Google Cloud KMS (production)
- **Token Refresh**: Automatic token refresh when access tokens expire
- **Secure State Management**: CSRF protection using state tokens
- **Minimal Permissions**: Only read-only access to Google Analytics data

## API Endpoints

- `GET /api/oauth/authorize/google-analytics` - Initiate OAuth flow
- `GET /api/oauth/callback/google` - Handle OAuth callback
- `POST /api/oauth/refresh/{account_id}/google-analytics` - Refresh access token
- `DELETE /api/oauth/disconnect/{account_id}/google-analytics` - Disconnect integration
- `GET /api/oauth/status/{account_id}/google-analytics` - Check integration status

## Troubleshooting

### "Google OAuth is not configured" error
- Ensure `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` are set in `.env`
- Restart the API server after updating environment variables

### Redirect URI mismatch error
- Verify the redirect URI in Google Cloud Console matches exactly with `GOOGLE_OAUTH_REDIRECT_URI` in `.env`
- Check for trailing slashes and protocol (http vs https)

### Token expired errors
- The system should automatically refresh tokens
- If issues persist, user can disconnect and reconnect the integration

## Future Enhancements

- [ ] Add support for multiple Google Analytics accounts
- [ ] Implement property/view selection UI
- [ ] Add data import scheduling
- [ ] Integrate with ADK agents for automated analysis