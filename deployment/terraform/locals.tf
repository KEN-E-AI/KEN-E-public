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

locals {
  cicd_services = [
    "cloudbuild.googleapis.com",
    "discoveryengine.googleapis.com",
    "aiplatform.googleapis.com",
    "serviceusage.googleapis.com",
    "bigquery.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudtrace.googleapis.com"
  ]

  shared_services = [
    "aiplatform.googleapis.com",
    "cloudscheduler.googleapis.com",
    "run.googleapis.com",
    "discoveryengine.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "bigquery.googleapis.com",
    "serviceusage.googleapis.com",
    "logging.googleapis.com",
    "cloudtrace.googleapis.com",
    "monitoring.googleapis.com"
  ]

  # Dev (ken-e-dev) is intentionally excluded. IAM grants on the dev Agent
  # Engine SA (e.g. roles/datastore.user used by analytics_db) are made
  # out-of-band by engineers as the sandbox evolves; bringing dev under this
  # map would also pull in CICD SA roles, log sinks, monitoring, and Vertex
  # SA roles for dev, which is a larger scope than current usage justifies.
  # Dev still receives terraform-managed Firestore indexes via the separate
  # `firestore_index_project_ids` variable in variables.tf — indexes are
  # required for query correctness, IAM is not. See data-management README §7.4.
  deploy_project_ids = {
    prod    = var.prod_project_id
    staging = var.staging_project_id
  }

  # Subset of deploy_project_ids that still routes Traceloop tracing logs to
  # BigQuery. Prod was removed when its destination dataset went away with
  # no downstream consumers.
  telemetry_export_project_ids = {
    staging = var.staging_project_id
  }

  all_project_ids = [
    var.cicd_runner_project_id,
    var.prod_project_id,
    var.staging_project_id
  ]

  # Skills GCS buckets target all three environments including dev (SK-PRD-01 / SK-12).
  # Mirrors the `firestore_index_project_ids` precedent (DM-73): a separate map that
  # includes dev while keeping dev out of `deploy_project_ids` (which would also pull in
  # CICD SA roles, log sinks, Vertex SA roles, etc.). Dev project ID is hardcoded
  # (no `dev_project_id` variable exists) — consistent with firestore_index_project_ids
  # default "ken-e-dev". Keys become the bucket name suffix; see gcs_skills_bucket.tf.
  skills_bucket_project_ids = {
    development = "ken-e-dev"
    staging     = var.staging_project_id
    production  = var.prod_project_id
  }

  # Chat orphan-scan Cloud Scheduler jobs target only the environments where the
  # kene-api service is actually deployed to Cloud Run — staging + production
  # (matches deploy_project_ids). Dev is intentionally excluded: kene-api is NOT
  # deployed to ken-e-dev (no dev CD target; ken-e-dev runs only mer-e-* on Cloud
  # Run), so data.google_cloud_run_service.kene_api["development"] cannot resolve
  # and the scheduler would have no endpoint to POST to. Dev is local-testing only;
  # its orphan-scan can be run on demand via `python -m kene_api.chat.artifact_orphan_scan`
  # and `python -m kene_api.chat.adk_session_orphan_scan`. The scan only reconciles
  # chat artifacts / ADK sessions; it never creates or deletes account or organization
  # records, so dev test accounts/orgs are out of its purview anyway.
  # Keys match the kene-api Cloud Run service names in locals.kene_api_service_names.
  chat_orphan_scan_projects = {
    staging    = var.staging_project_id
    production = var.prod_project_id
  }

  # Cloud Run service names for the kene-api service per environment.
  # Used by cloud_scheduler.tf to look up the service URL via data source.
  kene_api_service_names = {
    development = "kene-api-dev"
    staging     = "kene-api-staging"
    production  = "kene-api-prod"
  }

}

