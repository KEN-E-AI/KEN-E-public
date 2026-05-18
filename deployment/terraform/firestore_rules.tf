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

# Provisions deployment/firestore.rules as the live security ruleset for the
# (default) Firestore database. The .rules file is the single source of truth
# — adding rules for a new component is a one-file change; no Terraform edits
# are required.
#
# This mirrors firestore_indexes.tf: target projects are controlled by
# var.firestore_index_project_ids so rules and indexes deploy in lockstep
# (vars/env.tfvars expands it to ken-e-dev, ken-e-staging, ken-e-production).
#
# Prerequisite: the Firebase Rules API (firebaserules.googleapis.com) must be
# enabled on each target project — same out-of-band assumption firestore_
# indexes.tf makes for firestore.googleapis.com.
#
# Operational note: if a project already has a manually-created
# `cloud.firestore` release (e.g. from a prior `firebase deploy`), import it
# once with `terraform import` before the first apply, otherwise apply fails
# with AlreadyExists.

resource "google_firebaserules_ruleset" "firestore" {
  for_each = toset(var.firestore_index_project_ids)
  project  = each.value

  source {
    files {
      name    = "firestore.rules"
      content = file("${path.module}/../firestore.rules")
    }
  }

  # Rulesets are immutable — a content change creates a new ruleset. Create the
  # replacement before destroying the old one so the release never references a
  # deleted ruleset mid-apply.
  lifecycle {
    create_before_destroy = true
  }
}

resource "google_firebaserules_release" "firestore" {
  for_each = toset(var.firestore_index_project_ids)
  project  = each.value

  # "cloud.firestore" is the release name for the (default) database. A named
  # database would use "cloud.firestore/<database>"; all CH-PRD-01 collections
  # live in (default).
  name         = "cloud.firestore"
  ruleset_name = google_firebaserules_ruleset.firestore[each.key].name
}
