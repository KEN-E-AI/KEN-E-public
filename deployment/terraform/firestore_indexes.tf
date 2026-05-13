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

# Provisions every entry in deployment/firestore.indexes.json as a
# google_firestore_index resource. The JSON file is the single source of
# truth — adding a new index in any PRD is a one-line JSON change; no
# Terraform edits are required.
#
# Target projects are controlled by var.firestore_index_project_ids
# (default: ["ken-e-dev"]). DM-PRD-06 staging cutover overrides the
# variable to add ken-e-staging (and later prod) without touching this file.
#
# Multi-database support: each index entry may specify an optional
# top-level `"database"` field (defaults to `"(default)"`). The
# `(default)` database keys are backwards-compatible with the
# pre-multi-database scheme so existing terraform state does not move
# (and existing indexes are not destroy-and-recreated, which would take
# hours and break queries). Named-database entries (e.g.
# `"database": "analytics"`) get the database name interpolated into
# the for_each key, making them visibly distinct in `terraform plan`
# output. Added in the DM-40 follow-up after the analytics-named-DB
# discovery in DM-39 / DM-40 — `performance_profiler` and
# `async_analytics_queue` write to `database="analytics"`, not
# `(default)`, so per-DB indexes are required.

locals {
  firestore_json                = jsondecode(file("${path.module}/../firestore.indexes.json"))
  firestore_indexes_raw         = try(local.firestore_json.indexes, [])
  firestore_field_overrides_raw = try(local.firestore_json.fieldOverrides, [])
}

resource "google_firestore_index" "all" {
  # Key construction:
  #   - "(default)" entries: "{project}_{collectionGroup}_{queryScope}_{field_signature}"
  #     (the legacy pre-multi-database key — stable, do not change).
  #   - Named-database entries: "{project}_{database}_{collectionGroup}_{queryScope}_{field_signature}".
  # field_signature joins field-path/order pairs with "__" — stable for any field set.
  for_each = {
    for pair in setproduct(var.firestore_index_project_ids, range(length(local.firestore_indexes_raw))) :
    (try(local.firestore_indexes_raw[pair[1]].database, "(default)") == "(default)"
      ? "${pair[0]}_${local.firestore_indexes_raw[pair[1]].collectionGroup}_${local.firestore_indexes_raw[pair[1]].queryScope}_${join("__", [for f in local.firestore_indexes_raw[pair[1]].fields : "${f.fieldPath}-${try(f.order, f.arrayConfig)}"])}"
      : "${pair[0]}_${try(local.firestore_indexes_raw[pair[1]].database, "(default)")}_${local.firestore_indexes_raw[pair[1]].collectionGroup}_${local.firestore_indexes_raw[pair[1]].queryScope}_${join("__", [for f in local.firestore_indexes_raw[pair[1]].fields : "${f.fieldPath}-${try(f.order, f.arrayConfig)}"])}"
    ) => {
      project_id = pair[0]
      database   = try(local.firestore_indexes_raw[pair[1]].database, "(default)")
      index      = local.firestore_indexes_raw[pair[1]]
    }
  }

  project     = each.value.project_id
  database    = each.value.database
  collection  = each.value.index.collectionGroup
  query_scope = each.value.index.queryScope

  dynamic "fields" {
    for_each = each.value.index.fields
    content {
      field_path   = fields.value.fieldPath
      order        = try(fields.value.order, null)
      array_config = try(fields.value.arrayConfig, null)
    }
  }
}

# Single-field index controls (Firebase CLI "fieldOverrides" schema).
#
# Used for cases google_firestore_index cannot express:
#   - Single-field COLLECTION_GROUP indexes (e.g. project_plan_audit.at)
#     — these are NOT auto-indexed by Firestore and require an explicit
#     field-level config.
#
# Do NOT add single-field COLLECTION-scope entries here — Firestore auto-indexes
# every field at COLLECTION scope, and submitting one will fail with
# "Error 400: this index is not necessary, configure using single field index controls".
resource "google_firestore_field" "field_overrides" {
  # Same multi-database scheme as google_firestore_index above: `(default)`
  # entries keep the legacy key; named-database entries get the database
  # name interpolated. Defaults to `(default)` for backwards compat.
  for_each = {
    for pair in setproduct(var.firestore_index_project_ids, range(length(local.firestore_field_overrides_raw))) :
    (try(local.firestore_field_overrides_raw[pair[1]].database, "(default)") == "(default)"
      ? "${pair[0]}_${local.firestore_field_overrides_raw[pair[1]].collectionGroup}_${local.firestore_field_overrides_raw[pair[1]].fieldPath}"
      : "${pair[0]}_${try(local.firestore_field_overrides_raw[pair[1]].database, "(default)")}_${local.firestore_field_overrides_raw[pair[1]].collectionGroup}_${local.firestore_field_overrides_raw[pair[1]].fieldPath}"
    ) => {
      project_id = pair[0]
      database   = try(local.firestore_field_overrides_raw[pair[1]].database, "(default)")
      override   = local.firestore_field_overrides_raw[pair[1]]
    }
  }

  project    = each.value.project_id
  database   = each.value.database
  collection = each.value.override.collectionGroup
  field      = each.value.override.fieldPath

  index_config {
    dynamic "indexes" {
      for_each = each.value.override.indexes
      content {
        query_scope  = indexes.value.queryScope
        order        = try(indexes.value.order, null)
        array_config = try(indexes.value.arrayConfig, null)
      }
    }
  }
}
