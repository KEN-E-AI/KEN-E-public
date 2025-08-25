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

# Enable VPC Access API for both projects
resource "google_project_service" "vpcaccess_api_staging" {
  project                    = var.staging_project_id
  service                    = "vpcaccess.googleapis.com"
  disable_dependent_services = false
  disable_on_destroy        = false
}

resource "google_project_service" "vpcaccess_api_prod" {
  project                    = var.prod_project_id
  service                    = "vpcaccess.googleapis.com"
  disable_dependent_services = false
  disable_on_destroy        = false
}

# VPC Connector for Staging
resource "google_vpc_access_connector" "staging_connector" {
  name          = "ken-e-staging-connector"
  project       = var.staging_project_id
  region        = var.region
  network       = "default"
  ip_cidr_range = "10.8.0.0/28"  # Small range for connector
  
  # Throughput configuration
  min_throughput = 200
  max_throughput = 300
  
  depends_on = [google_project_service.vpcaccess_api_staging]
}

# VPC Connector for Production
resource "google_vpc_access_connector" "production_connector" {
  name          = "ken-e-prod-connector"
  project       = var.prod_project_id
  region        = var.region
  network       = "default"
  ip_cidr_range = "10.9.0.0/28"  # Different range from staging
  
  # Higher throughput for production
  min_throughput = 200
  max_throughput = 1000
  
  depends_on = [google_project_service.vpcaccess_api_prod]
}

# Outputs for VPC Connectors
output "vpc_connector_staging" {
  value       = google_vpc_access_connector.staging_connector.id
  description = "VPC Connector ID for staging environment"
}

output "vpc_connector_production" {
  value       = google_vpc_access_connector.production_connector.id
  description = "VPC Connector ID for production environment"
}

output "vpc_connector_staging_name" {
  value       = google_vpc_access_connector.staging_connector.name
  description = "VPC Connector name for staging environment"
}

output "vpc_connector_production_name" {
  value       = google_vpc_access_connector.production_connector.name
  description = "VPC Connector name for production environment"
}