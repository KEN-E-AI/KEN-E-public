# Redis/Memorystore Configuration for KEN-E Deployments

## Overview
This document explains how to configure Redis (Google Cloud Memorystore) for staging and production deployments.

## Local Development
For local development, Redis runs in Docker:
```bash
# Start Redis
docker-compose up -d redis

# Stop Redis
docker-compose down redis

# Check Redis status
docker ps | grep redis
```

## Cloud Deployments

### 1. Deploy Memorystore Infrastructure

First, deploy the Memorystore instances using Terraform:

#### Staging
```bash
cd deployment/terraform/environments/staging
terraform init
terraform plan
terraform apply

# Note the Redis IP from output:
# Example: redis_host = "10.0.0.3"
```

#### Production
```bash
cd deployment/terraform/environments/production
terraform init
terraform plan
terraform apply

# Note the Redis IP from output:
# Example: redis_host = "10.0.0.4"
```

### 2. Configure Cloud Build Triggers

After Terraform deployment, you need to set the Redis host IPs in your Cloud Build triggers.

#### Staging Trigger Configuration
1. Go to [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers) in the Google Cloud Console
2. Edit the staging deployment trigger
3. Under "Substitution variables", add or update:
   - Variable: `_REDIS_HOST_STAGING`
   - Value: The IP address from Terraform output (e.g., `10.0.0.3`)

#### Production Trigger Configuration
1. Edit the production deployment trigger
2. Under "Substitution variables", add or update:
   - Variable: `_REDIS_HOST_PROD`
   - Value: The IP address from Terraform output (e.g., `10.0.0.4`)

### 3. Environment Variables Set by Cloud Build

The following Redis environment variables are automatically set during deployment:

| Variable | Staging | Production | Description |
|----------|---------|------------|-------------|
| `REDIS_HOST` | `${_REDIS_HOST_STAGING}` | `${_REDIS_HOST_PROD}` | Memorystore IP address |
| `REDIS_PORT` | `6379` | `6379` | Redis port (standard) |
| `REDIS_DB` | `0` | `0` | Redis database number |
| `SUPPRESS_REDIS_WARNING` | `false` | `false` | Show Redis connection warnings |

### 4. Verify Redis Connection

After deployment, check the health endpoint to verify Redis connectivity:

```bash
# Staging
curl https://kene-api-staging-391472102753.us-central1.run.app/health | jq .services.redis

# Production
curl https://kene-api-prod-395770269870.us-central1.run.app/health | jq .services.redis
```

Expected response:
- `"healthy"` - Redis is connected and working
- `"unavailable"` - Redis is not available (API continues to work without caching)

## Memorystore Configuration Details

### Staging (BASIC Tier)
- **Memory**: 1 GB
- **Tier**: BASIC (no high availability)
- **Cost**: ~$30/month
- **Use case**: Development and testing

### Production (STANDARD_HA Tier)
- **Memory**: 5 GB
- **Tier**: STANDARD_HA (high availability with automatic failover)
- **Cost**: ~$180/month
- **Use case**: Production workloads
- **Features**: Automatic failover, read replicas

## Monitoring

### View Memorystore Metrics
```bash
# List instances
gcloud redis instances list --region=us-central1

# Get instance details
gcloud redis instances describe ken-e-staging-cache --region=us-central1
gcloud redis instances describe ken-e-production-cache --region=us-central1
```

### Cloud Monitoring Dashboard
Production deployments include automatic alerts for:
- Memory usage > 80%
- Instance availability issues

## Troubleshooting

### Connection Issues
1. Verify the Memorystore IP is correct in Cloud Build triggers
2. Check that Cloud Run service account has network access
3. Verify VPC connector is configured (if using private IP)

### Performance Issues
1. Check memory usage: High memory usage may cause evictions
2. Review cache hit rate in application logs
3. Consider increasing memory size if needed

### Testing Without Redis
The API gracefully degrades when Redis is unavailable:
- Authentication still works (using Firestore)
- Performance is reduced but functionality remains
- Health endpoint shows `"redis": "unavailable"`

## Cache Patterns Used

The following data is cached in Redis:

| Pattern | Key Format | TTL | Purpose |
|---------|------------|-----|---------|
| User Context | `user_context:{user_id}` | 300s | Cache user permissions |
| Token Revocation | `revoked_token:{token_id}` | 3600s | Fast token validation |
| All User Tokens | `revoked_all_tokens:{user_id}` | 3600s | Bulk token revocation |

## Future Enhancements

Consider adding caching for:
- API response caching
- Expensive database query results
- Computed metrics and reports
- Session data