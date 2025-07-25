# Authentication Documentation

This document describes the authentication and authorization system used in the KEN-E API.

## Overview

The KEN-E API uses Firebase Authentication with JWT tokens for securing endpoints. The system includes:

- Firebase ID token verification
- Role-based access control (RBAC)
- Rate limiting
- Token revocation
- Redis caching for performance
- Comprehensive audit logging

## Authentication Flow

1. Client authenticates with Firebase Authentication
2. Client receives a Firebase ID token
3. Client includes the token in the `Authorization` header for API requests
4. API verifies the token and loads user permissions
5. API checks permissions for the requested resource

## Request Headers

All authenticated requests must include:

```
Authorization: Bearer <firebase-id-token>
```

## User Context

After successful authentication, a `UserContext` object is created containing:

- `user_id`: Firebase user ID
- `email`: User's email address
- `accessible_accounts`: List of account IDs the user can access
- `permissions`: Map of account IDs to roles
- `organization_permissions`: Map of organization IDs to roles

## Permissions and Roles

### Account Roles
- `admin`: Full access to account
- `editor`: Can modify account data
- `viewer`: Read-only access

### Organization Roles
- `admin`: Full access to organization and all its accounts
- `member`: Basic access to organization

## Rate Limiting

Authentication endpoints are rate-limited to prevent brute force attacks:

- **Token verification**: 10 requests per minute, 50 per hour
- **Token refresh**: 5 requests per minute, 20 per hour
- **ReCAPTCHA verification**: 20 requests per minute, 100 per hour

Rate limits are enforced per IP address. When exceeded, a `429 Too Many Requests` response is returned with a `Retry-After` header.

## Token Revocation

Users can revoke their tokens through the API:

### Revoke Current Token
```http
POST /api/v1/auth/revoke-token
Authorization: Bearer <token>
Content-Type: application/json

{
  "reason": "Logged out from device"
}
```

### Revoke All Tokens
```http
POST /api/v1/auth/revoke-token
Authorization: Bearer <token>
Content-Type: application/json

{
  "revoke_all": true,
  "reason": "Security concern"
}
```

### Check Token Validity
```http
GET /api/v1/auth/check-token
Authorization: Bearer <token>
```

Response:
```json
{
  "valid": true,
  "user_id": "user123",
  "email": "user@example.com"
}
```

## Security Features

### 1. Token Verification
- All tokens are verified using Firebase Admin SDK
- Tokens are checked against revocation list
- Token expiration is enforced

### 2. Audit Logging
The following security events are logged:
- Successful logins
- Failed login attempts
- Token verification failures
- Access denied events
- Rate limit exceeded
- Token revocations
- New user creation

Audit logs are stored in Firestore and Google Cloud Logging for analysis.

### 3. Redis Caching
- User permissions are cached for 5 minutes
- Revoked tokens are cached for 1 hour
- Cache is automatically invalidated on permission changes

### 4. Error Handling
Authentication errors return appropriate HTTP status codes:
- `401 Unauthorized`: Missing or invalid token
- `403 Forbidden`: Valid token but insufficient permissions
- `429 Too Many Requests`: Rate limit exceeded

## API Endpoints

### Authentication Endpoints

#### Verify ReCAPTCHA
```http
POST /api/v1/auth/verify-recaptcha
Content-Type: application/json

{
  "token": "recaptcha-token",
  "action": "login"
}
```

#### Get ReCAPTCHA Site Key
```http
GET /api/v1/auth/recaptcha-site-key
```

### Protected Endpoints

All endpoints under the following paths require authentication:
- `/api/v1/organizations/*`
- `/api/v1/accounts/*`
- `/api/v1/metrics/*`
- `/api/v1/activities/*`
- `/api/v1/insights/*`
- `/api/v1/notifications/*`

## Code Examples

### Python (using requests)
```python
import requests

# Get Firebase ID token (implementation depends on your auth flow)
id_token = get_firebase_id_token()

# Make authenticated request
headers = {
    "Authorization": f"Bearer {id_token}",
    "Content-Type": "application/json"
}

response = requests.get(
    "https://api.ken-e.com/api/v1/accounts/",
    headers=headers
)
```

### JavaScript (using fetch)
```javascript
// Get Firebase ID token
const user = firebase.auth().currentUser;
const idToken = await user.getIdToken();

// Make authenticated request
const response = await fetch('https://api.ken-e.com/api/v1/accounts/', {
  headers: {
    'Authorization': `Bearer ${idToken}`,
    'Content-Type': 'application/json'
  }
});
```

### cURL
```bash
# Get accounts
curl -H "Authorization: Bearer $ID_TOKEN" \
     -H "Content-Type: application/json" \
     https://api.ken-e.com/api/v1/accounts/
```

## Troubleshooting

### Common Issues

1. **401 Unauthorized - Missing authentication credentials**
   - Ensure the `Authorization` header is present
   - Check that the header format is exactly `Bearer <token>`

2. **401 Unauthorized - Invalid authentication token**
   - Token may be expired (tokens expire after 1 hour)
   - Token may be malformed
   - Token may have been revoked

3. **403 Forbidden - Access denied**
   - User doesn't have permission for the requested resource
   - Check user's roles in the organization/account

4. **429 Too Many Requests**
   - Rate limit exceeded
   - Wait for the time specified in `Retry-After` header
   - Implement exponential backoff in your client

### Debug Tips

1. Check token expiration:
   ```javascript
   const decodedToken = jwt_decode(idToken);
   console.log('Token expires at:', new Date(decodedToken.exp * 1000));
   ```

2. Verify token is not revoked:
   ```http
   GET /api/v1/auth/check-token
   ```

3. Check audit logs in Google Cloud Console for detailed error information

## Security Best Practices

1. **Token Storage**
   - Never store tokens in localStorage (use memory or secure cookies)
   - Implement token refresh before expiration
   - Clear tokens on logout

2. **Error Handling**
   - Don't expose sensitive information in error messages
   - Log security events for monitoring
   - Implement proper error recovery

3. **Rate Limiting**
   - Implement client-side rate limiting
   - Use exponential backoff for retries
   - Monitor for unusual patterns

4. **Token Revocation**
   - Revoke tokens on logout
   - Revoke all tokens if account is compromised
   - Implement token rotation for long-lived sessions

## Migration Guide

If you're migrating from a previous authentication system:

1. Update all API calls to include the `Authorization` header
2. Implement Firebase Authentication in your client
3. Update error handling for new status codes
4. Test rate limiting behavior
5. Implement token refresh logic

## Support

For authentication issues:
1. Check the troubleshooting section above
2. Review audit logs in Google Cloud Console
3. Contact support with request ID and timestamp