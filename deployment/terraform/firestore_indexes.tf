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

locals {
  firestore_json                = jsondecode(file("${path.module}/../firestore.indexes.json"))
  firestore_indexes_raw         = try(local.firestore_json.indexes, [])
  firestore_field_overrides_raw = try(local.firestore_json.fieldOverrides, [])
}

resource "google_firestore_index" "all" {
  # Key: "{project}_{collectionGroup}_{queryScope}_{field_signature}" is content-derived
  # so JSON reorders and removals do not move resources around in Terraform state.
  # field_signature joins field-path/order pairs with "__" — stable for any field set.
  for_each = {
    for pair in setproduct(var.firestore_index_project_ids, range(length(local.firestore_indexes_raw))) :
    "${pair[0]}_${local.firestore_indexes_raw[pair[1]].collectionGroup}_${local.firestore_indexes_raw[pair[1]].queryScope}_${join("__", [for f in local.firestore_indexes_raw[pair[1]].fields : "${f.fieldPath}-${try(f.order, f.arrayConfig)}"])}" => {
      project_id = pair[0]
      index      = local.firestore_indexes_raw[pair[1]]
    }
  }

  project     = each.value.project_id
  database    = "(default)"
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
  for_each = {
    for pair in setproduct(var.firestore_index_project_ids, range(length(local.firestore_field_overrides_raw))) :
    "${pair[0]}_${local.firestore_field_overrides_raw[pair[1]].collectionGroup}_${local.firestore_field_overrides_raw[pair[1]].fieldPath}" => {
      project_id = pair[0]
      override   = local.firestore_field_overrides_raw[pair[1]]
    }
  }

  project    = each.value.project_id
  database   = "(default)"
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
