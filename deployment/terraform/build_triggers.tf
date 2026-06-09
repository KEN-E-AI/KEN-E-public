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

# a. Create PR checks trigger
resource "google_cloudbuild_trigger" "pr_checks" {
  name            = "pr-checks"
  project         = var.cicd_runner_project_id
  location        = var.region
  description     = "Trigger for PR checks"
  service_account = resource.google_service_account.cicd_runner_sa.id

  repository_event_config {
    repository = "projects/${var.cicd_runner_project_id}/locations/${var.region}/connections/${var.host_connection_name}/repositories/${var.repository_name}"
    pull_request {
      branch = "main"
    }
  }

  filename = "deployment/ci/pr_checks.yaml"
  # `docs/**` and `*.md` are included so that docs-only PRs still run the
  # lychee link-integrity gate in tests/unit/test_lychee_config.py. Without
  # these globs the trigger returns NEUTRAL on docs-only PRs and broken links
  # land on main undetected (see PR #593 → #595 regression for the precedent).
  # `cd_pipeline` below intentionally omits docs from its filter — docs
  # changes do not require a staging redeploy.
  included_files = [
    "app/**",
    "api/**",
    "frontend/**",
    "shared/**",
    "tests/**",
    "deployment/**",
    "docs/**",
    "*.md",
    "uv.lock",
  ]
  depends_on = [resource.google_project_service.cicd_services, resource.google_project_service.shared_services]
}

# a2. Create PR E2E checks trigger (split out of pr-checks).
# The Playwright E2E step used to live inside pr_checks.yaml behind an inline
# git-diff path-filter, but that filter could never work: the E2E step runs in
# the Playwright image with a depth-1 detached checkout, no git remote, and no
# git credentials, so `git fetch origin main` always failed and the merge-base
# guard always fell open to the full suite. `included_files` gates at the trigger
# level instead — this trigger fires only when a PR touches the frontend or the
# feature-flag source the E2E suite exercises, so backend/docs-only PRs never
# start it. The harness files (pr_checks_e2e.yaml, start_e2e_stack.sh) are
# included so changes to the E2E setup itself re-run the suite.
resource "google_cloudbuild_trigger" "pr_checks_e2e" {
  name            = "pr-checks-e2e"
  project         = var.cicd_runner_project_id
  location        = var.region
  description     = "Trigger for PR Playwright E2E checks (frontend + feature-flag scope)"
  service_account = resource.google_service_account.cicd_runner_sa.id

  repository_event_config {
    repository = "projects/${var.cicd_runner_project_id}/locations/${var.region}/connections/${var.host_connection_name}/repositories/${var.repository_name}"
    pull_request {
      branch = "main"
    }
  }

  filename = "deployment/ci/pr_checks_e2e.yaml"
  included_files = [
    "frontend/**",
    "api/src/kene_api/services/feature_flag_service.py",
    "api/src/kene_api/routers/feature_flags.py",
    "api/src/kene_api/routers/admin_feature_flags.py",
    "deployment/ci/pr_checks_e2e.yaml",
    "deployment/ci/scripts/start_e2e_stack.sh",
  ]
  depends_on = [resource.google_project_service.cicd_services, resource.google_project_service.shared_services]
}

# b. Create CD pipeline trigger
resource "google_cloudbuild_trigger" "cd_pipeline" {
  name            = "cd-pipeline"
  project         = var.cicd_runner_project_id
  location        = var.region
  service_account = resource.google_service_account.cicd_runner_sa.id
  description     = "Trigger for CD pipeline"

  repository_event_config {
    repository = "projects/${var.cicd_runner_project_id}/locations/${var.region}/connections/${var.host_connection_name}/repositories/${var.repository_name}"
    push {
      branch = "main"
    }
  }

  filename = "deployment/cd/staging.yaml"
  included_files = [
    "app/**",
    "api/**",
    "frontend/**",
    "shared/**",
    "tests/**",
    "deployment/**",
    "uv.lock"
  ]
  substitutions = {
    _STAGING_PROJECT_ID            = var.staging_project_id
    _BUCKET_NAME_LOAD_TEST_RESULTS = resource.google_storage_bucket.bucket_load_test_results.name
    _REGION                        = var.region
    # Memorystore Redis host — the staging.yaml default is self-referential
    # (`_REDIS_HOST_STAGING: ${_REDIS_HOST_STAGING}`) so must be overridden here
    # or the build fails with "cycle in evaluating substitutions".
    _REDIS_HOST_STAGING = google_redis_instance.staging.host
    # CH-24 chat-sidebar loadtest UID — the staging.yaml validate-loadtest-vars
    # step fails fast if this is empty (deployment/cd/staging.yaml:170). Seeded
    # out-of-band when CH-24 shipped; tracked in TF now so the trigger config
    # stays reproducible.
    _CHAT_LOADTEST_UID = "O9x67v0VXQQmACoXlW4A4i0nqMm1"
  }
  depends_on = [resource.google_project_service.cicd_services, resource.google_project_service.shared_services]

}

# c. Deploy to production trigger — MANUAL INVOCATION ONLY (AH-154)
#
# This trigger does NOT fire automatically on main-branch pushes. Operators
# invoke prod deploys explicitly via:
#   gcloud builds triggers run deploy-to-prod-pipeline --branch=main --project=ken-e-cicd
# after staging is green. The approval gate (approval_required = true) then
# requires a second operator to approve before the build runs — two-person rule.
#
# See docs/runs/AH-121-adk2-prod-cutover.md §2.1 for the canonical deploy flow.
resource "google_cloudbuild_trigger" "deploy_to_prod_pipeline" {
  name            = "deploy-to-prod-pipeline"
  project         = var.cicd_runner_project_id
  location        = var.region
  description     = "Trigger for deployment to production — manual invocation only"
  service_account = resource.google_service_account.cicd_runner_sa.id

  # Manual-invocation surface: no repository_event_config (which fires on every
  # push to the connected repo's default branch). source_to_build + git_file_source
  # make this a pure manual trigger invocable via `gcloud builds triggers run`.
  source_to_build {
    repository = "projects/${var.cicd_runner_project_id}/locations/${var.region}/connections/${var.host_connection_name}/repositories/${var.repository_name}"
    ref        = "refs/heads/main"
    repo_type  = "GITHUB"
  }

  git_file_source {
    path       = "deployment/cd/deploy-to-prod.yaml"
    revision   = "refs/heads/main"
    repository = "projects/${var.cicd_runner_project_id}/locations/${var.region}/connections/${var.host_connection_name}/repositories/${var.repository_name}"
    repo_type  = "GITHUB"
  }

  approval_config {
    approval_required = true
  }
  substitutions = {
    _PROD_PROJECT_ID = var.prod_project_id
    _REGION          = var.region
    # Memorystore Redis host — the deploy-to-prod.yaml default is self-referential
    # (`_REDIS_HOST_PROD: ${_REDIS_HOST_PROD}`) so must be overridden here or the
    # build fails with "cycle in evaluating substitutions".
    _REDIS_HOST_PROD = google_redis_instance.production.host
  }
  depends_on = [resource.google_project_service.cicd_services, resource.google_project_service.shared_services]
}
