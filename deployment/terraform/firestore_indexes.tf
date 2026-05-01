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
  firestore_indexes_raw = jsondecode(file("${path.module}/../firestore.indexes.json")).indexes
}

resource "google_firestore_index" "all" {
  # Key: "{project}_{collectionGroup}_{queryScope}_{offset}" is stable for appends.
  # IMPORTANT: reordering or removing entries from firestore.indexes.json is a
  # breaking change — Terraform will plan to destroy and recreate every resource
  # at or after the changed position. Always append; never reorder or remove.
  for_each = {
    for pair in setproduct(var.firestore_index_project_ids, range(length(local.firestore_indexes_raw))) :
    "${pair[0]}_${local.firestore_indexes_raw[pair[1]].collectionGroup}_${local.firestore_indexes_raw[pair[1]].queryScope}_${pair[1]}" => {
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
