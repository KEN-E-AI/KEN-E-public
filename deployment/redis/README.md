# KEN-E Redis Configuration

This directory contains configuration files and scripts for Google Cloud Memorystore for Redis deployment and management.

## Quick Start

### 1. Deploy Redis Instances

```bash
# Deploy both staging and production Redis instances
./deployment/scripts/deploy-redis.sh deploy

# Create deployment plan only (no changes)
./deployment/scripts/deploy-redis.sh plan

# Show deployment outputs
./deployment/scripts/deploy-redis.sh outputs
```

### 2. Test Connection

```bash
# Test Redis connection and performance
cd api && uv run -- python scripts/test_redis_connection.py
cd api && uv run -- python scripts/redis_performance_test.py
```

### 3. Update Application Configuration

Update the Cloud Build deployment files with Redis connection details:

**`deployment/cd/staging.yaml`:**
```yaml
--set-env-vars "...,REDIS_HOST=${_REDIS_HOST_STAGING},REDIS_PORT=${_REDIS_PORT_STAGING},REDIS_PASSWORD=${_REDIS_PASSWORD_STAGING}"
```

**`deployment/cd/deploy-to-prod.yaml`:**
```yaml
--set-env-vars "...,REDIS_HOST=${_REDIS_HOST_PROD},REDIS_PORT=${_REDIS_PORT_PROD},REDIS_PASSWORD=${_REDIS_PASSWORD_PROD}"
```

## Configuration Files

### Terraform Configuration
- `../terraform/memorystore_redis.tf` - Redis instance definitions
- `../terraform/variables.tf` - Redis configuration variables
- `../terraform/vars/env.tfvars` - Environment-specific values

### Monitoring and Alerting
- `../monitoring/redis-dashboard.json` - Cloud Monitoring dashboard
- `../monitoring/redis-memory-alert.yaml` - Memory utilization alerts
- `../monitoring/redis-availability-alert.yaml` - Instance availability alerts

### Testing and Utilities
- `../../api/scripts/test_redis_connection.py` - Connection and functionality tests
- `../../api/scripts/redis_performance_test.py` - Performance benchmarking
- `../scripts/deploy-redis.sh` - Automated deployment script

## Instance Configuration

### Staging Environment
- **Instance Name**: `kene-redis-staging`
- **Tier**: Basic (single node, cost-optimized)
- **Memory**: 1GB
- **Region**: us-central1
- **Zone**: us-central1-a
- **Auth**: Enabled
- **Encryption**: Transit encryption enabled
- **Estimated Cost**: ~$30/month

### Production Environment
- **Instance Name**: `kene-redis-prod`
- **Tier**: Standard HA (high availability)
- **Memory**: 5GB
- **Region**: us-central1
- **Zones**: us-central1-a (primary), us-central1-c (replica)
- **Auth**: Enabled
- **Encryption**: Transit encryption enabled
- **Estimated Cost**: ~$180/month

## Environment Variables

### Required Environment Variables

```bash
# Redis connection
REDIS_HOST=<redis-instance-host>
REDIS_PORT=6379
REDIS_PASSWORD=<auth-string-from-secret-manager>
REDIS_DB=0

# Optional configuration
SUPPRESS_REDIS_WARNING=false  # Set to true to suppress connection warnings
```

### Local Development

```bash
# Local Redis instance
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=  # Empty for local development
REDIS_DB=0
```

## Cache Key Patterns

KEN-E uses the following Redis key patterns:

```
industry_keywords:<industry_name>        # Industry-specific keywords
industry_keywords:all                    # All industry keywords
monitoring_topics:<account_id>           # Account monitoring topics  
user_context:<user_id>                   # User authentication context
notifications:<user_id>                  # User notifications cache
subscription_plans:all                   # Cached subscription plans
```

### TTL Configuration

- **Industry Keywords**: 30 minutes (1800 seconds)
- **User Context**: 5 minutes (300 seconds)  
- **Monitoring Topics**: 15 minutes (900 seconds)
- **Notifications**: 10 minutes (600 seconds)
- **Subscription Plans**: 1 hour (3600 seconds)

## Performance Expectations

### Target Performance Metrics

- **Basic Operations**: < 5ms average
- **JSON Operations**: < 10ms average
- **Concurrent Operations**: < 15ms average
- **Memory Utilization**: < 80% under normal load
- **Cache Hit Ratio**: > 85%

### Performance Testing

```bash
# Run performance tests
cd api && uv run -- python scripts/redis_performance_test.py

# Test specific patterns
cd api && uv run -- python scripts/test_redis_connection.py
```

## Monitoring and Alerting

### Key Metrics to Monitor

1. **Memory Utilization**: Alert at 85%, critical at 95%
2. **Connected Clients**: Monitor for connection leaks
3. **Cache Hit Ratio**: Alert if below 80%
4. **Network I/O**: Monitor for bandwidth limits
5. **Instance Availability**: Critical alert for downtime

### Accessing Monitoring

- **Cloud Console**: https://console.cloud.google.com/memorystore/redis
- **Monitoring Dashboard**: Available after deployment
- **Alerts**: Configured for memory and availability

### Manual Monitoring Commands

```bash
# Check instance status
gcloud redis instances list --region=us-central1 --project=ken-e-staging

# Get instance details  
gcloud redis instances describe kene-redis-staging --region=us-central1 --project=ken-e-staging

# View operations
gcloud redis operations list --region=us-central1 --project=ken-e-staging
```

## Troubleshooting

### Common Issues

#### 1. Connection Timeouts
```bash
# Check instance status
gcloud redis instances describe kene-redis-staging --region=us-central1 --project=ken-e-staging

# Verify VPC connectivity
gcloud compute networks subnets list --filter="region:(us-central1)"
```

#### 2. Authentication Failures
```bash
# Get auth string from Secret Manager
gcloud secrets versions access latest --secret=redis-auth-string-staging --project=ken-e-staging

# Test connection with auth string
redis-cli -h <REDIS_HOST> -p 6379 -a <AUTH_STRING> ping
```

#### 3. High Memory Usage
```bash
# Check memory usage
redis-cli -h <REDIS_HOST> -p 6379 -a <AUTH_STRING> info memory

# Find large keys
redis-cli -h <REDIS_HOST> -p 6379 -a <AUTH_STRING> --bigkeys
```

#### 4. Performance Issues
```bash
# Monitor commands in real-time
redis-cli -h <REDIS_HOST> -p 6379 -a <AUTH_STRING> monitor

# Check slow log
redis-cli -h <REDIS_HOST> -p 6379 -a <AUTH_STRING> slowlog get 10
```

### Debug Mode

Enable detailed Redis logging in the API:

```python
import logging
logging.getLogger("redis").setLevel(logging.DEBUG)
```

## Security

### Authentication
- Redis AUTH is enabled on all instances
- Auth strings are stored in Google Secret Manager
- Service accounts have minimal required permissions

### Network Security
- Redis instances are deployed in private VPC
- Only Cloud Run services can access Redis instances
- Transit encryption is enabled for all connections

### Access Control
- Staging Redis: Accessible only from ken-e-staging project
- Production Redis: Accessible only from ken-e-production project
- API service accounts have `roles/redis.viewer` permission
- Secret Manager access limited to API service accounts

## Cost Optimization

### Current Configuration Costs (Estimated)

| Environment | Tier | Memory | Monthly Cost |
|-------------|------|--------|--------------|
| Staging | Basic | 1GB | ~$30 |
| Production | Standard HA | 5GB | ~$180 |
| **Total** | | | **~$210** |

### Optimization Strategies

1. **Right-sizing**: Monitor memory usage and scale instances based on actual needs
2. **TTL Management**: Implement appropriate TTL values to prevent memory bloat
3. **Key Pattern Optimization**: Use efficient key naming and data structures
4. **Monitoring**: Set up alerts for memory usage to prevent over-provisioning

### Budget Alerts

```bash
# Create budget alert for Redis costs
gcloud alpha billing budgets create \
  --billing-account=YOUR_BILLING_ACCOUNT \
  --display-name="KEN-E Redis Budget" \
  --budget-amount=250 \
  --threshold-rules-percent=75,90 \
  --filter-services=services/redis
```

## Maintenance

### Maintenance Windows
- **Scheduled**: Sundays at 3:00 AM UTC
- **Duration**: Up to 4 hours
- **Notification**: 24 hours advance notice via Cloud Console

### Updates and Patches
- **Automatic**: Security patches applied automatically during maintenance windows
- **Manual**: Feature updates require manual approval
- **Rollback**: Automatic rollback on failure

### Backup Strategy
- **Built-in**: Automatic daily snapshots for Standard HA instances
- **Application-level**: Critical cache data can be backed up to Cloud Storage
- **Recovery**: Point-in-time recovery available for Standard HA instances

## Development Workflow

### 1. Local Development
```bash
# Install local Redis
brew install redis  # macOS
docker run -d -p 6379:6379 redis:7.2-alpine  # Docker

# Update .env.development
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
```

### 2. Testing Changes
```bash
# Test Redis integration
cd api && uv run -- python scripts/test_redis_connection.py

# Run API tests with Redis
cd api && pytest tests/ -v
```

### 3. Deployment
```bash
# Deploy via CI/CD (recommended)
git commit -am "Add Redis caching support"
git push origin feature/redis-integration

# Manual deployment (if needed)
./deployment/scripts/deploy-redis.sh deploy
```

## Support and Documentation

### Additional Resources
- [Google Cloud Memorystore Documentation](https://cloud.google.com/memorystore/docs/redis)
- [Redis Documentation](https://redis.io/documentation)
- [KEN-E Architecture Documentation](../CLAUDE.md)

### Getting Help
1. Check this README and troubleshooting section
2. Review monitoring dashboards and alerts
3. Check application logs for Redis-related errors
4. Contact the development team with specific error messages and context