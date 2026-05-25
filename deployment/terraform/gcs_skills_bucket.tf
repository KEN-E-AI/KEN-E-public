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

# Skills GCS buckets — SK-PRD-01 (SK-12).
#
# Two buckets per environment:
#   kene-skills-{env}         — primary content bucket (SKILL.md + references/assets/scripts)
#   kene-skills-{env}-trash   — soft-delete holding area; 30-day lifecycle purge
#
# Environment map is defined in locals.tf (`skills_bucket_project_ids`) alongside the
# other env→project-ID maps. Bucket name suffix = map key (development/staging/production)
# so names resolve to kene-skills-development, kene-skills-staging, kene-skills-production.
#
# Note: `depends_on` for GCS API enablement is omitted — the Storage API is already
# enabled on all three projects (existing resources confirm this), and
# `google_project_service.shared_services` only covers staging/prod, not dev.

# Primary content bucket — stores all skill bundles under
# accounts/{account_id}/{skill_id}/{version}/ (immutable per-version at app layer).
# No lifecycle rule: versions are retained until explicit soft-delete.
# force_destroy=false protects user-authored skill content from accidental destroy.
resource "google_storage_bucket" "skills_content" {
  for_each = local.skills_bucket_project_ids

  name                        = "kene-skills-${each.key}"
  location                    = var.region
  project                     = each.value
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  dynamic "encryption" {
    for_each = can(var.skills_bucket_kms_key_name[each.key]) ? [var.skills_bucket_kms_key_name[each.key]] : []
    content {
      default_kms_key_name = encryption.value
    }
  }
}

# Trash bucket — receives soft-deleted skill prefixes via server-side copy;
# 30-day lifecycle rule purges them automatically. Soft-delete is effectively
# permanent: no UI restore in v1.
#
# soft_delete_policy retention=0 disables GCS native soft-delete (7-day default
# hold) so the lifecycle Delete rule fires at exactly day 30 without stacking.
resource "google_storage_bucket" "skills_trash" {
  for_each = local.skills_bucket_project_ids

  name                        = "kene-skills-${each.key}-trash"
  location                    = var.region
  project                     = each.value
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

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

  dynamic "encryption" {
    for_each = can(var.skills_bucket_kms_key_name[each.key]) ? [var.skills_bucket_kms_key_name[each.key]] : []
    content {
      default_kms_key_name = encryption.value
    }
  }
}

# Grant the API runtime service account objectAdmin on the primary content bucket.
# objectAdmin is required because the soft-delete move operation deletes the source
# object from this bucket after copying it to the trash bucket.
# SA pattern `ken-e-api@{project_id}.iam.gserviceaccount.com` matches api_sa_datastore_owner in iam.tf.
resource "google_storage_bucket_iam_member" "skills_content_api_sa" {
  for_each = local.skills_bucket_project_ids

  bucket = google_storage_bucket.skills_content[each.key].name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:ken-e-api@${each.value}.iam.gserviceaccount.com"
}

# Grant the API runtime service account objectCreator on the trash bucket.
# The soft-delete move only writes objects into this bucket; GCS lifecycle handles
# deletion. Limiting to objectCreator (not objectAdmin) prevents the API SA from
# performing hard deletes on trash objects before the 30-day window expires.
resource "google_storage_bucket_iam_member" "skills_trash_api_sa" {
  for_each = local.skills_bucket_project_ids

  bucket = google_storage_bucket.skills_trash[each.key].name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:ken-e-api@${each.value}.iam.gserviceaccount.com"
}
