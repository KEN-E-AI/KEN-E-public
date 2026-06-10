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

# Cloud Scheduler jobs for the chat orphan-scan maintenance endpoints (CH-PRD-05 / CH-51).
#
# Two jobs per environment (4 total — staging + production):
#   chat-orphan-scan-gcs         — POST /api/v1/internal/chat/orphan-scan/gcs     @ 04:00 UTC daily
#   chat-orphan-scan-adk-session — POST /api/v1/internal/chat/orphan-scan/adk-session @ 04:30 UTC daily
#
# Environment map: local.chat_orphan_scan_projects (staging / production).
# Cloud Scheduler API enablement: cloudscheduler.googleapis.com is in local.shared_services
# (staging + prod via terraform); dev is enabled out-of-band consistent with other dev resources.
#
# IAM: roles/run.invoker is granted non-authoritatively via google_cloud_run_service_iam_member
# so that other out-of-band grants on the kene-api service are not destroyed.

# Look up the kene-api Cloud Run service URI per environment.
# Used as the HTTP target URL and OIDC audience for Cloud Scheduler.
data "google_cloud_run_service" "kene_api" {
  for_each = local.chat_orphan_scan_projects
  name     = local.kene_api_service_names[each.key]
  project  = each.value
  location = var.region
}

# Grant roles/run.invoker to the scheduler SA on the kene-api service (non-authoritative).
resource "google_cloud_run_service_iam_member" "chat_orphan_scan_scheduler_invoker" {
  for_each = local.chat_orphan_scan_projects

  service  = data.google_cloud_run_service.kene_api[each.key].name
  project  = each.value
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.chat_orphan_scan_scheduler_sa[each.key].email}"
}

locals {
  # Construct keys for the flat job map: "{env}-{job}" e.g. "staging-gcs".
  _orphan_scan_jobs = {
    for pair in setproduct(
      keys(local.chat_orphan_scan_projects),
      ["gcs", "adk-session"]
    ) : "${pair[0]}-${pair[1]}" => {
      env     = pair[0]
      job     = pair[1]
      project = local.chat_orphan_scan_projects[pair[0]]
    }
  }
}

resource "google_cloud_scheduler_job" "chat_orphan_scan" {
  for_each = local._orphan_scan_jobs

  name        = "chat-orphan-scan-${each.value.env}-${each.value.job}"
  description = "Daily chat orphan-scan: ${each.value.env}/${each.value.job} (CH-PRD-05)"
  project     = each.value.project
  region      = var.region

  # GCS scan at 04:00 UTC; ADK-session scan at 04:30 UTC.
  # Offset gives GCS scan time to finish before ADK scan starts.
  schedule  = each.value.job == "gcs" ? "0 4 * * *" : "30 4 * * *"
  time_zone = "UTC"

  # Retry up to 2 times with exponential backoff. Both orchestrators are
  # idempotent so retries are safe.
  retry_config {
    retry_count          = 2
    min_backoff_duration = "5s"
    max_backoff_duration = "3600s"
    max_doublings        = 5
  }

  http_target {
    http_method = "POST"
    uri = "${data.google_cloud_run_service.kene_api[each.value.env].status[0].url}/api/v1/internal/chat/orphan-scan/${each.value.job}"

    # Cloud Scheduler mints an OIDC token for the scheduler SA and sends it as
    # the Authorization: Bearer header. The kene-api verify_internal_oidc_caller
    # dependency validates the token and checks the SA email against
    # CHAT_INTERNAL_SA_ALLOWLIST.
    oidc_token {
      service_account_email = google_service_account.chat_orphan_scan_scheduler_sa[each.value.env].email
      audience              = data.google_cloud_run_service.kene_api[each.value.env].status[0].url
    }
  }

  # attempt_deadline controls how long Cloud Scheduler waits for a 2xx response.
  # 1800 s (30 min) matches the expected upper bound for a full-corpus scan.
  attempt_deadline = "1800s"

  depends_on = [google_cloud_run_service_iam_member.chat_orphan_scan_scheduler_invoker]
}
