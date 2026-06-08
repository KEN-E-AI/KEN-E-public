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

resource "google_storage_bucket" "bucket_load_test_results" {
  name                        = "${var.cicd_runner_project_id}-${var.suffix_bucket_name_load_test_results}"
  location                    = var.region
  project                     = var.cicd_runner_project_id
  uniform_bucket_level_access = true
  force_destroy               = true
  depends_on                  = [resource.google_project_service.cicd_services, resource.google_project_service.shared_services]
}

resource "google_storage_bucket" "logs_data_bucket" {
  for_each                    = toset(local.all_project_ids)
  name                        = "${each.value}-logs-data"
  location                    = var.region
  project                     = each.value
  uniform_bucket_level_access = true
  force_destroy               = true

  depends_on = [resource.google_project_service.cicd_services, resource.google_project_service.shared_services]
}

# mypy cache bucket — persists .mypy_cache across PR CI builds so mypy runs warm
# (~10-20s) instead of cold (~183s). Provisioned in the CI/CD runner project only
# (pr_checks.yaml runs against ${PROJECT_ID} = cicd_runner_project_id). 30-day
# lifecycle rule bounds cache growth; stale signatures are naturally evicted when
# the file content changes. AH-151 Lever 3.
resource "google_storage_bucket" "ci_mypy_cache" {
  name                        = "${var.cicd_runner_project_id}-ci-mypy-cache"
  location                    = var.region
  project                     = var.cicd_runner_project_id
  uniform_bucket_level_access = true
  force_destroy               = true

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }

  soft_delete_policy {
    retention_duration_seconds = 0
  }

  depends_on = [resource.google_project_service.cicd_services]
}
