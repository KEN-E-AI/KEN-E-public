# Troubleshooting 503 Error - Organization Creation in Staging

## Problem Summary
When attempting to create a new organization in the staging environment, the API returns a 503 Service Unavailable error. This indicates that the API service is unable to handle the request, most likely due to a database connectivity issue.

## Root Cause Analysis

Based on the code analysis:

1. **API Endpoint**: `/api/v1/organizations/` (POST)
2. **Error Location**: The 503 error is thrown when Neo4j database is unavailable (line 250 in `organizations.py`)
3. **Error Message**: "Database service unavailable. Please try again later."

The code specifically checks Neo4j health before attempting to create an organization:
```python
# Check Neo4j connectivity
is_healthy = await db.health_check()
if not is_healthy:
    raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)
```

## Diagnostic Scripts

I've created two diagnostic scripts to help troubleshoot:

### 1. Check Neo4j Connectivity
```bash
cd api
ENVIRONMENT=staging python scripts/check_neo4j_connectivity.py
```

This script will:
- Test Neo4j connection with staging credentials
- Verify database accessibility
- Check if Organization nodes exist
- Validate CREATE query syntax

### 2. Test Organization Creation
```bash
cd api
ENVIRONMENT=staging python scripts/check_create_organization.py
```

This script will:
- Attempt to create a test organization via the API
- Show detailed error messages
- Provide specific troubleshooting steps

## Immediate Solutions

### Option 1: Check API Health Endpoint
First, verify the overall API health:
```bash
curl https://staging.app.ken-e.ai/health
```

Expected response should show Neo4j status:
```json
{
  "status": "healthy" or "degraded",
  "services": {
    "neo4j": "healthy" or "unhealthy",
    "firestore": "healthy" or "unhealthy"
  }
}
```

### Option 2: Verify Neo4j Environment Variables
The API needs these environment variables configured in staging:
- `NEO4J_URI`: The connection string (e.g., `bolt://neo4j-host:7687`)
- `NEO4J_USERNAME`: Database username
- `NEO4J_PASSWORD`: Database password
- `NEO4J_DATABASE`: Database name (default: `neo4j`)

### Option 3: Check Cloud Run Service Configuration
1. Go to Google Cloud Console
2. Navigate to Cloud Run > kene-api-staging
3. Check the Environment Variables tab
4. Verify Neo4j configuration is correct

### Option 4: Review Cloud Run Logs
```bash
gcloud run services logs read kene-api-staging --limit=50 --project=<staging-project-id>
```

Look for errors like:
- "Failed to connect to Neo4j"
- "Neo4j Error"
- Connection timeout messages

## Common Issues and Fixes

### 1. Neo4j Not Accessible from Cloud Run
**Symptoms**: Connection timeouts, network errors
**Fix**: 
- Ensure Neo4j is accessible from Cloud Run's network
- Check firewall rules
- Verify Neo4j is configured to accept external connections

### 2. Wrong Neo4j Credentials
**Symptoms**: Authentication errors in logs
**Fix**:
- Update NEO4J_PASSWORD in Cloud Run environment variables
- Ensure password is stored in Secret Manager if using that approach

### 3. Neo4j Database Not Running
**Symptoms**: Connection refused errors
**Fix**:
- Check Neo4j service status
- Restart Neo4j if needed
- Verify Neo4j has enough resources (memory/CPU)

### 4. Database Name Mismatch
**Symptoms**: Database not found errors
**Fix**:
- Verify NEO4J_DATABASE environment variable matches actual database name
- Default is usually "neo4j"

## Temporary Workaround

If you need to create organizations urgently while fixing the database issue:

1. **Use Development Environment**:
   ```bash
   cd frontend
   npm run dev:development
   ```
   Then create organizations in the development environment.

2. **Direct Database Access**:
   If you have direct Neo4j access, you can create organizations manually using Cypher queries.

3. **API Restart**:
   Sometimes a simple service restart helps:
   ```bash
   gcloud run services update kene-api-staging --project=<project-id> --region=<region>
   ```

## Long-term Fixes

1. **Add Better Error Handling**: The API should provide more specific error messages when Neo4j is unavailable.

2. **Implement Retry Logic**: Add automatic retry for transient connection issues.

3. **Add Connection Pooling**: Ensure the Neo4j driver is properly managing connections.

4. **Monitor Database Health**: Set up alerts for when Neo4j becomes unavailable.

## Next Steps

1. Run the diagnostic scripts to identify the specific issue
2. Check Cloud Run logs for detailed error messages
3. Verify Neo4j is running and accessible
4. Update environment variables if needed
5. Contact the infrastructure team if Neo4j is down

## Contact for Help

If the above steps don't resolve the issue:
1. Check the #infrastructure Slack channel
2. Look for recent deployments that might have changed configuration
3. Verify with the DevOps team that Neo4j is operational in staging