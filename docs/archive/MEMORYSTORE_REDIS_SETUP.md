# Google Cloud Memorystore for Redis Setup Guide

This guide provides comprehensive setup instructions for Google Cloud Memorystore for Redis in the KEN-E project, following existing infrastructure patterns and integrating with the current staging/production architecture.

## Table of Contents

1. [Overview](#overview)
2. [Terraform Configuration](#terraform-configuration)
3. [Environment-Specific Configurations](#environment-specific-configurations)
4. [Cloud Run Service Connection](#cloud-run-service-connection)
5. [Local Development Setup](#local-development-setup)
6. [Cost Optimization](#cost-optimization)
7. [Monitoring and Maintenance](#monitoring-and-maintenance)
8. [Troubleshooting](#troubleshooting)

## Overview

Google Cloud Memorystore for Redis provides a fully-managed Redis service that integrates seamlessly with other Google Cloud services. This setup enables high-performance caching for the KEN-E API while maintaining consistency with the existing multi-environment infrastructure.

### Architecture Integration

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   Frontend      │────│   Cloud Run API  │────│  Memorystore Redis  │
│   (React)       │    │   (FastAPI)      │    │   (Caching Layer)   │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   Neo4j/         │
                       │   Firestore      │
                       │   (Primary Data) │
                       └──────────────────┘
```

## Terraform Configuration

### 1. Add Memorystore API to APIs Configuration

Add the following to `deployment/terraform/apis.tf`:

```hcl
# Enable Redis APIs for staging and prod
resource "google_project_service" "redis_api_staging" {
  project                    = var.staging_project_id
  service                   = "redis.googleapis.com"
  disable_dependent_services = false
  disable_on_destroy        = false
}

resource "google_project_service" "redis_api_prod" {
  project                    = var.prod_project_id
  service                   = "redis.googleapis.com"
  disable_dependent_services = false
  disable_on_destroy        = false
}
```

### 2. Create Redis Configuration File

Create `deployment/terraform/memorystore_redis.tf`:

```hcl
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Staging Redis Instance
resource "google_redis_instance" "staging_redis" {
  name           = "kene-redis-staging"
  tier           = var.redis_tier_staging
  memory_size_gb = var.redis_memory_size_gb_staging
  region         = var.region
  project        = var.staging_project_id
  
  location_id             = var.redis_zone_staging
  alternative_location_id = var.redis_alt_zone_staging
  
  redis_version     = var.redis_version
  display_name      = "KEN-E Redis Staging"
  reserved_ip_range = var.redis_reserved_ip_range_staging
  
  # Enable AUTH for security
  auth_enabled = true
  
  # Enable Transit Encryption for data in transit
  transit_encryption_mode = "SERVER_AUTHENTICATION"
  
  # Maintenance policy - run during low traffic hours
  maintenance_policy {
    weekly_maintenance_window {
      day = "SUNDAY"
      start_time {
        hours   = 3
        minutes = 0
        seconds = 0
        nanos   = 0
      }
    }
  }
  
  # Labels for resource management
  labels = {
    environment = "staging"
    application = "ken-e"
    tier        = "cache"
  }

  depends_on = [google_project_service.redis_api_staging]
}

# Production Redis Instance
resource "google_redis_instance" "prod_redis" {
  name           = "kene-redis-prod"
  tier           = var.redis_tier_prod
  memory_size_gb = var.redis_memory_size_gb_prod
  region         = var.region
  project        = var.prod_project_id
  
  location_id             = var.redis_zone_prod
  alternative_location_id = var.redis_alt_zone_prod
  
  redis_version     = var.redis_version
  display_name      = "KEN-E Redis Production"
  reserved_ip_range = var.redis_reserved_ip_range_prod
  
  # Enable AUTH for security
  auth_enabled = true
  
  # Enable Transit Encryption for data in transit
  transit_encryption_mode = "SERVER_AUTHENTICATION"
  
  # Maintenance policy - run during low traffic hours
  maintenance_policy {
    weekly_maintenance_window {
      day = "SUNDAY"
      start_time {
        hours   = 3
        minutes = 0
        seconds = 0
        nanos   = 0
      }
    }
  }
  
  # Labels for resource management
  labels = {
    environment = "production"
    application = "ken-e"
    tier        = "cache"
  }

  depends_on = [google_project_service.redis_api_prod]
}

# Create secrets for Redis auth strings
resource "google_secret_manager_secret" "redis_auth_staging" {
  project   = var.staging_project_id
  secret_id = "redis-auth-string-staging"
  
  replication {
    auto {}
  }
  
  labels = {
    environment = "staging"
    service     = "redis"
  }
}

resource "google_secret_manager_secret_version" "redis_auth_staging" {
  secret      = google_secret_manager_secret.redis_auth_staging.id
  secret_data = google_redis_instance.staging_redis.auth_string
}

resource "google_secret_manager_secret" "redis_auth_prod" {
  project   = var.prod_project_id
  secret_id = "redis-auth-string-prod"
  
  replication {
    auto {}
  }
  
  labels = {
    environment = "production"
    service     = "redis"
  }
}

resource "google_secret_manager_secret_version" "redis_auth_prod" {
  secret      = google_secret_manager_secret.redis_auth_prod.id
  secret_data = google_redis_instance.prod_redis.auth_string
}

# Output Redis connection info
output "staging_redis_host" {
  value       = google_redis_instance.staging_redis.host
  description = "Redis host for staging environment"
}

output "staging_redis_port" {
  value       = google_redis_instance.staging_redis.port
  description = "Redis port for staging environment"
}

output "prod_redis_host" {
  value       = google_redis_instance.prod_redis.host
  description = "Redis host for production environment"
}

output "prod_redis_port" {
  value       = google_redis_instance.prod_redis.port
  description = "Redis port for production environment"
}

output "staging_redis_auth_secret" {
  value       = google_secret_manager_secret.redis_auth_staging.secret_id
  description = "Secret ID for staging Redis auth string"
}

output "prod_redis_auth_secret" {
  value       = google_secret_manager_secret.redis_auth_prod.secret_id
  description = "Secret ID for production Redis auth string"
}
```

### 3. Add Variables to Variables File

Add the following to `deployment/terraform/variables.tf`:

```hcl
# Redis Configuration Variables
variable "redis_version" {
  type        = string
  description = "Redis version to use"
  default     = "REDIS_7_2"
}

variable "redis_tier_staging" {
  type        = string
  description = "Redis tier for staging (BASIC or STANDARD_HA)"
  default     = "BASIC"
}

variable "redis_tier_prod" {
  type        = string
  description = "Redis tier for production (BASIC or STANDARD_HA)"
  default     = "STANDARD_HA"
}

variable "redis_memory_size_gb_staging" {
  type        = number
  description = "Memory size in GB for staging Redis instance"
  default     = 1
}

variable "redis_memory_size_gb_prod" {
  type        = number
  description = "Memory size in GB for production Redis instance"
  default     = 5
}

variable "redis_zone_staging" {
  type        = string
  description = "Primary zone for staging Redis instance"
  default     = "us-central1-a"
}

variable "redis_alt_zone_staging" {
  type        = string
  description = "Alternative zone for staging Redis instance (HA only)"
  default     = "us-central1-b"
}

variable "redis_zone_prod" {
  type        = string
  description = "Primary zone for production Redis instance"
  default     = "us-central1-a"
}

variable "redis_alt_zone_prod" {
  type        = string
  description = "Alternative zone for production Redis instance (HA only)"
  default     = "us-central1-c"
}

variable "redis_reserved_ip_range_staging" {
  type        = string
  description = "Reserved IP range for staging Redis instance"
  default     = "10.137.0.0/29"
}

variable "redis_reserved_ip_range_prod" {
  type        = string
  description = "Reserved IP range for production Redis instance"
  default     = "10.138.0.0/29"
}
```

### 4. Update Environment Variables File

Add to `deployment/terraform/vars/env.tfvars`:

```hcl
# Redis Configuration
redis_version = "REDIS_7_2"

# Staging Redis Configuration (cost-optimized)
redis_tier_staging = "BASIC"
redis_memory_size_gb_staging = 1
redis_zone_staging = "us-central1-a"
redis_reserved_ip_range_staging = "10.137.0.0/29"

# Production Redis Configuration (high availability)
redis_tier_prod = "STANDARD_HA"
redis_memory_size_gb_prod = 5
redis_zone_prod = "us-central1-a"
redis_alt_zone_prod = "us-central1-c"
redis_reserved_ip_range_prod = "10.138.0.0/29"
```

### 5. Update Service Account Permissions

Add Redis permissions to service accounts in `deployment/terraform/service_accounts.tf`:

```hcl
# Add Redis access to API service account roles
resource "google_project_iam_member" "api_sa_redis_staging" {
  project = var.staging_project_id
  role    = "roles/redis.viewer"
  member  = "serviceAccount:ken-e-api@${var.staging_project_id}.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "api_sa_redis_prod" {
  project = var.prod_project_id
  role    = "roles/redis.viewer"
  member  = "serviceAccount:ken-e-api@${var.prod_project_id}.iam.gserviceaccount.com"
}

# Allow API service accounts to access Redis auth secrets
resource "google_secret_manager_secret_iam_member" "redis_auth_staging_access" {
  project   = var.staging_project_id
  secret_id = google_secret_manager_secret.redis_auth_staging.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:ken-e-api@${var.staging_project_id}.iam.gserviceaccount.com"
}

resource "google_secret_manager_secret_iam_member" "redis_auth_prod_access" {
  project   = var.prod_project_id
  secret_id = google_secret_manager_secret.redis_auth_prod.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:ken-e-api@${var.prod_project_id}.iam.gserviceaccount.com"
}
```

## Environment-Specific Configurations

### Staging Environment
- **Tier**: BASIC (cost-optimized, single node)
- **Memory**: 1GB
- **Availability**: Single zone (us-central1-a)
- **Use Case**: Development, testing, light caching load

### Production Environment
- **Tier**: STANDARD_HA (high availability, automatic failover)
- **Memory**: 5GB (scalable based on usage)
- **Availability**: Multi-zone (primary: us-central1-a, secondary: us-central1-c)
- **Use Case**: Production workloads, critical caching, high availability

## Cloud Run Service Connection

### 1. Update Cloud Build Deployment Pipeline

Add Redis environment variables to `deployment/cd/staging.yaml`:

```yaml
# Add to the existing set-env-vars in the deploy-api-to-cloud-run step
--set-env-vars "...,REDIS_HOST=${_REDIS_HOST_STAGING},REDIS_PORT=${_REDIS_PORT_STAGING},REDIS_PASSWORD=${_REDIS_PASSWORD_STAGING},REDIS_DB=0,SUPPRESS_REDIS_WARNING=false"
```

Add to substitutions section:
```yaml
substitutions:
  # ... existing substitutions ...
  _REDIS_HOST_STAGING: 10.137.0.2  # Replace with actual Redis host from terraform output
  _REDIS_PORT_STAGING: 6379
  _REDIS_PASSWORD_STAGING: projects/391472102753/secrets/redis-auth-string-staging/versions/latest
```

### 2. Update Production Pipeline

Add to `deployment/cd/deploy-to-prod.yaml`:

```yaml
# Add Redis environment variables to production deployment
--set-env-vars "...,REDIS_HOST=${_REDIS_HOST_PROD},REDIS_PORT=${_REDIS_PORT_PROD},REDIS_PASSWORD=${_REDIS_PASSWORD_PROD},REDIS_DB=0,SUPPRESS_REDIS_WARNING=false"
```

Add to substitutions:
```yaml
substitutions:
  # ... existing substitutions ...
  _REDIS_HOST_PROD: 10.138.0.2  # Replace with actual Redis host from terraform output
  _REDIS_PORT_PROD: 6379
  _REDIS_PASSWORD_PROD: projects/YOUR_PROD_PROJECT_ID/secrets/redis-auth-string-prod/versions/latest
```

### 3. API Environment Files

Update `api/.env.staging`:
```bash
# Redis Configuration
REDIS_HOST=10.137.0.2  # Staging Redis host
REDIS_PORT=6379
REDIS_PASSWORD=<staging-auth-string>
REDIS_DB=0
SUPPRESS_REDIS_WARNING=false
```

Update `api/.env.production`:
```bash
# Redis Configuration
REDIS_HOST=10.138.0.2  # Production Redis host
REDIS_PORT=6379
REDIS_PASSWORD=<production-auth-string>
REDIS_DB=0
SUPPRESS_REDIS_WARNING=false
```

## Local Development Setup

### 1. Option A: Local Redis Instance (Recommended for Development)

Install Redis locally:

```bash
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt update
sudo apt install redis-server
sudo systemctl start redis-server

# Docker (cross-platform)
docker run --name ken-e-redis -p 6379:6379 -d redis:7.2-alpine redis-server --requirepass mypassword
```

Update `api/.env.development`:
```bash
# Local Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=  # Leave empty for local Redis without auth
REDIS_DB=0
SUPPRESS_REDIS_WARNING=false
```

### 2. Option B: Connect to Staging Redis (Advanced)

For testing with real data, you can connect to the staging Redis instance:

```bash
# Create a Cloud SQL Proxy-like connection for Redis
# Note: This requires VPC peering or VPN connection to access Memorystore
# Not recommended for typical development workflow

# Instead, use port forwarding through a Compute Engine instance
gcloud compute instances create redis-proxy-vm \
  --zone=us-central1-a \
  --machine-type=e2-micro \
  --image-family=debian-11 \
  --image-project=debian-cloud \
  --project=ken-e-staging

# SSH with port forwarding
gcloud compute ssh redis-proxy-vm \
  --zone=us-central1-a \
  --project=ken-e-staging \
  -- -L 6379:10.137.0.2:6379
```

### 3. Development Environment Variables

Create `api/.env.local` for local development:
```bash
# Local Development Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
SUPPRESS_REDIS_WARNING=false
```

### 4. Testing Redis Connection

Create a test script `api/scripts/check_redis_connection.py`:

```python
#!/usr/bin/env python3
"""Test Redis connection with current environment configuration."""

import os
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kene_api.redis_client import get_redis_service

def test_redis_connection():
    """Test Redis connection and basic operations."""
    redis_service = get_redis_service()
    
    print(f"Redis Host: {os.getenv('REDIS_HOST', 'localhost')}")
    print(f"Redis Port: {os.getenv('REDIS_PORT', '6379')}")
    print(f"Redis DB: {os.getenv('REDIS_DB', '0')}")
    
    if not redis_service.is_available():
        print("❌ Redis is not available")
        return False
    
    print("✅ Redis connection successful")
    
    # Test basic operations
    test_key = "ken-e:test"
    test_value = "Hello Redis!"
    
    # Set test value
    if redis_service.set(test_key, test_value, ttl=60):
        print(f"✅ Successfully set key: {test_key}")
    else:
        print(f"❌ Failed to set key: {test_key}")
        return False
    
    # Get test value
    retrieved = redis_service.get(test_key)
    if retrieved == test_value:
        print(f"✅ Successfully retrieved value: {retrieved}")
    else:
        print(f"❌ Value mismatch. Expected: {test_value}, Got: {retrieved}")
        return False
    
    # Test JSON operations
    test_json = {"message": "Hello Redis JSON!", "timestamp": "2025-01-31T12:00:00Z"}
    json_key = "ken-e:test:json"
    
    if redis_service.set_json(json_key, test_json, ttl=60):
        print(f"✅ Successfully set JSON key: {json_key}")
    else:
        print(f"❌ Failed to set JSON key: {json_key}")
        return False
    
    retrieved_json = redis_service.get_json(json_key)
    if retrieved_json == test_json:
        print(f"✅ Successfully retrieved JSON: {retrieved_json}")
    else:
        print(f"❌ JSON mismatch. Expected: {test_json}, Got: {retrieved_json}")
        return False
    
    # Clean up
    redis_service.delete(test_key)
    redis_service.delete(json_key)
    print("✅ Cleanup completed")
    
    return True

if __name__ == "__main__":
    success = test_redis_connection()
    sys.exit(0 if success else 1)
```

Run the test:
```bash
cd api && uv run -- python scripts/check_redis_connection.py
```

## Cost Optimization

### 1. Instance Sizing Strategy

**Staging Environment:**
- Start with 1GB Basic tier (~$30/month)
- Monitor memory usage with Cloud Monitoring
- Scale up if memory utilization consistently > 80%

**Production Environment:**
- Start with 5GB Standard HA (~$180/month)
- Monitor cache hit ratio and memory usage
- Scale based on actual usage patterns

### 2. Memory Management

Configure Redis max memory policies in application:

```python
# In your Redis configuration
redis_service.client.config_set('maxmemory-policy', 'allkeys-lru')
```

### 3. TTL Strategy

Implement smart TTL policies:

```python
# Cache TTL configuration
CACHE_TTL_SHORT = 5 * 60      # 5 minutes for frequently changing data
CACHE_TTL_MEDIUM = 30 * 60    # 30 minutes for moderately changing data  
CACHE_TTL_LONG = 24 * 60 * 60 # 24 hours for stable data

# Example usage in API
redis_service.set_json(f"user:profile:{user_id}", profile_data, ttl=CACHE_TTL_MEDIUM)
redis_service.set_json(f"metrics:daily:{date}", metrics, ttl=CACHE_TTL_LONG)
```

### 4. Cost Monitoring

Set up billing alerts:

```bash
# Create budget alert
gcloud alpha billing budgets create \
  --billing-account=YOUR_BILLING_ACCOUNT \
  --display-name="KEN-E Redis Budget" \
  --budget-amount=200 \
  --threshold-rules-percent=50,75,90 \
  --threshold-rules-spend-basis=CURRENT_SPEND \
  --filter-projects=ken-e-staging,ken-e-production \
  --filter-services=services/redis
```

## Monitoring and Maintenance

### 1. Cloud Monitoring Dashboards

Create Redis monitoring dashboard:

```bash
# Import Redis monitoring dashboard
gcloud monitoring dashboards create --config-from-file=redis-dashboard.json
```

Key metrics to monitor:
- Memory utilization
- Connected clients
- Cache hit ratio
- Network I/O
- Command stats

### 2. Alerting Policies

Set up critical alerts:

```bash
# High memory utilization alert
gcloud alpha monitoring policies create \
  --policy-from-file=redis-memory-alert.yaml
```

### 3. Maintenance Windows

Configure maintenance during low traffic:
- **Time**: Sunday 3:00 AM UTC (Saturday 10 PM EST/7 PM PST)
- **Duration**: 4 hours maximum
- **Notification**: 24 hours advance notice

### 4. Backup Strategy

For critical cached data, implement application-level backup:

```python
def backup_critical_cache():
    """Backup critical cache data to Cloud Storage."""
    critical_keys = redis_service.client.keys("critical:*")
    backup_data = {}
    
    for key in critical_keys:
        backup_data[key] = redis_service.get(key)
    
    # Upload to Cloud Storage
    storage_service.upload_json(
        f"redis-backups/{datetime.utcnow().isoformat()}-backup.json",
        backup_data
    )
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Connection Timeouts

```bash
# Check VPC connectivity
gcloud compute networks subnets list --filter="region:(us-central1)"

# Verify Redis instance status
gcloud redis instances list --region=us-central1 --project=ken-e-staging
```

**Solution**: Ensure Cloud Run and Redis are in the same VPC network.

#### 2. Authentication Failures

```python
# Test auth string
redis_service = redis.Redis(
    host="your-redis-host",
    port=6379,
    password="your-auth-string",
    decode_responses=True
)
redis_service.ping()
```

**Solution**: Verify auth string in Secret Manager matches Redis instance.

#### 3. High Memory Usage

```bash
# Check memory usage
redis-cli info memory
```

**Solution**: 
- Implement key expiration policies
- Review cache key patterns
- Consider memory scaling

#### 4. Performance Issues

```python
# Check Redis performance
def check_redis_performance():
    start_time = time.time()
    redis_service.set("perf_test", "test_value")
    set_time = time.time() - start_time
    
    start_time = time.time()
    redis_service.get("perf_test")
    get_time = time.time() - start_time
    
    print(f"SET operation: {set_time:.4f}s")
    print(f"GET operation: {get_time:.4f}s")
```

**Solution**: Check network latency, Redis configuration, and consider instance scaling.

### Debugging Tools

1. **Redis CLI Access** (via bastion host):
```bash
redis-cli -h REDIS_HOST -p 6379 -a AUTH_STRING
```

2. **Application-level debugging**:
```python
# Enable Redis client logging
import logging
logging.getLogger("redis").setLevel(logging.DEBUG)
```

3. **Monitoring queries**:
```bash
# Check Redis info
redis-cli info all

# Monitor commands in real-time
redis-cli monitor

# Check slow log
redis-cli slowlog get 10
```

## Deployment Checklist

### Pre-deployment
- [ ] Terraform variables configured in `vars/env.tfvars`
- [ ] Service account permissions updated
- [ ] Network connectivity verified
- [ ] Secret Manager secrets created

### Terraform Deployment
```bash
cd deployment/terraform
terraform init
terraform plan -var-file=vars/env.tfvars
terraform apply -var-file=vars/env.tfvars
```

### Post-deployment
- [ ] Redis instances created successfully
- [ ] Auth strings stored in Secret Manager
- [ ] Cloud Build pipelines updated
- [ ] API environment variables configured
- [ ] Connection testing completed
- [ ] Monitoring dashboards configured
- [ ] Alerting policies activated

### Validation Commands

```bash
# Check Terraform state
terraform show | grep redis

# Verify Redis instances
gcloud redis instances list --project=ken-e-staging
gcloud redis instances list --project=ken-e-production

# Test API with Redis
curl https://kene-api-staging-391472102753.us-central1.run.app/health
```

This completes the comprehensive setup guide for Google Cloud Memorystore for Redis integration with the KEN-E project. The configuration follows existing infrastructure patterns and provides both development and production-ready configurations with proper cost optimization and monitoring.