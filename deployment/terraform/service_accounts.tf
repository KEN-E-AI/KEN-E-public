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

resource "google_service_account" "cicd_runner_sa" {
  account_id   = var.cicd_runner_sa_name
  display_name = "CICD Runner SA"
  project      = var.cicd_runner_project_id
  depends_on   = [resource.google_project_service.cicd_services, resource.google_project_service.shared_services]
}

# Chat orphan-scan Cloud Scheduler invoker SA — one per environment (CH-PRD-05 / CH-51).
# Dedicated SA per env (blast-radius isolation). Cloud Scheduler impersonates this SA
# to mint the OIDC token for the kene-api Cloud Run target.
# roles/run.invoker is granted non-authoritatively in cloud_scheduler.tf so that
# out-of-band grants on the Cloud Run service are not destroyed.
resource "google_service_account" "chat_orphan_scan_scheduler_sa" {
  for_each = local.chat_orphan_scan_projects

  account_id   = "chat-orphan-scan-scheduler"
  display_name = "Chat Orphan Scan Scheduler (${each.key})"
  project      = each.value
}
