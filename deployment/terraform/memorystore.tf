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

# Enable Redis API for both projects
resource "google_project_service" "redis_api_staging" {
  project                    = var.staging_project_id
  service                    = "redis.googleapis.com"
  disable_dependent_services = false
  disable_on_destroy        = false
}

resource "google_project_service" "redis_api_prod" {
  project                    = var.prod_project_id
  service                    = "redis.googleapis.com"
  disable_dependent_services = false
  disable_on_destroy        = false
}

# Staging Redis Instance
resource "google_redis_instance" "staging" {
  name               = "ken-e-staging-cache"
  tier               = "BASIC"
  memory_size_gb     = 1
  region             = var.region
  project            = var.staging_project_id
  
  location_id        = "${var.region}-a"
  redis_version      = "REDIS_7_0"
  display_name       = "KEN-E Staging Redis Cache"
  
  redis_configs = {
    "maxmemory-policy" = "allkeys-lru"
    "notify-keyspace-events" = ""
    "timeout" = "300"
  }
  
  labels = {
    environment = "staging"
    application = "ken-e"
    tier        = "cache"
  }

  depends_on = [google_project_service.redis_api_staging]
}

# Production Redis Instance
resource "google_redis_instance" "production" {
  name               = "ken-e-production-cache"
  tier               = "STANDARD_HA"
  memory_size_gb     = 5
  region             = var.region
  project            = var.prod_project_id
  
  location_id             = "${var.region}-a"
  alternative_location_id = "${var.region}-c"
  redis_version          = "REDIS_7_0"
  display_name           = "KEN-E Production Redis Cache"
  
  redis_configs = {
    "maxmemory-policy" = "allkeys-lru"
    "notify-keyspace-events" = ""
    "timeout" = "300"
  }
  
  labels = {
    environment = "production"
    application = "ken-e"
    tier        = "cache"
    critical    = "true"
  }

  depends_on = [google_project_service.redis_api_prod]
}

# Outputs
output "redis_staging_host" {
  value       = google_redis_instance.staging.host
  description = "Redis host for staging environment"
  sensitive   = true
}

output "redis_staging_port" {
  value       = google_redis_instance.staging.port
  description = "Redis port for staging environment"
}

output "redis_production_host" {
  value       = google_redis_instance.production.host
  description = "Redis host for production environment"
  sensitive   = true
}

output "redis_production_port" {
  value       = google_redis_instance.production.port
  description = "Redis port for production environment"
}