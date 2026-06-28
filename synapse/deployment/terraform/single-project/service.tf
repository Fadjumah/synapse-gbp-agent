# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


resource "google_cloud_run_v2_service" "app" {
  name                = var.project_name
  location            = var.region
  project             = var.project_id
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"
  labels = {
    "created-by"                  = "adk"
  }

  template {
    containers {
      image = var.container_image
      resources {
        limits = {
          cpu    = "1"
          memory = "4Gi"
        }
      }

      env {
        name  = "LOGS_BUCKET_NAME"
        value = google_storage_bucket.logs_data_bucket.name
      }

      env {
        name  = "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"
        value = "NO_CONTENT"
      }

      env {
        name  = "FIRESTORE_PROJECT_ID"
        value = var.project_id
      }

      env {
        name = "TELEGRAM_TOKEN"
        value_source {
          secret_key_ref {
            secret  = var.telegram_token_secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "GOOGLE_REFRESH_TOKEN"
        value_source {
          secret_key_ref {
            secret  = var.google_refresh_token_secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "GOOGLE_CLIENT_ID"
        value_source {
          secret_key_ref {
            secret  = var.google_client_id_secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "GOOGLE_CLIENT_SECRET"
        value_source {
          secret_key_ref {
            secret  = var.google_client_secret_secret_id
            version = "latest"
          }
        }
      }
    }

    service_account = google_service_account.app_sa.email
    max_instance_request_concurrency = 8

    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }

    session_affinity = true
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  # Make dependencies conditional to avoid errors.
  depends_on = [
    resource.google_project_service.services,
  ]
}
