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

variable "container_image" {
  type        = string
  description = "The container image to deploy to Cloud Run."
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "project_name" {
  type        = string
  description = "Project name used as a base for resource naming"
  default     = "synapse"
}

variable "project_id" {
  type        = string
  description = "Google Cloud Project ID for resource deployment."
}

variable "region" {
  type        = string
  description = "Google Cloud region for resource deployment."
  default     = "us-east1"
}

variable "telegram_token_secret_id" {
  type        = string
  description = "The secret ID for the Telegram token in Secret Manager"
  default     = "TELEGRAM_TOKEN"
}

variable "google_refresh_token_secret_id" {
  type        = string
  description = "The secret ID for the Google OAuth2 refresh token in Secret Manager"
  default     = "GOOGLE_REFRESH_TOKEN"
}

variable "google_client_id_secret_id" {
  type        = string
  description = "The secret ID for the Google OAuth2 client ID in Secret Manager"
  default     = "GOOGLE_CLIENT_ID"
}

variable "google_client_secret_secret_id" {
  type        = string
  description = "The secret ID for the Google OAuth2 client secret in Secret Manager"
  default     = "GOOGLE_CLIENT_SECRET"
}

variable "telemetry_logs_filter" {
  type        = string
  description = "Log Sink filter for capturing telemetry data. Captures logs with the `traceloop.association.properties.log_type` attribute set to `tracing`."
  default     = "labels.service_name=\"synapse\" labels.type=\"agent_telemetry\""
}

variable "feedback_logs_filter" {
  type        = string
  description = "Log Sink filter for capturing feedback data. Captures logs where the `log_type` field is `feedback`."
  default     = "jsonPayload.log_type=\"feedback\" jsonPayload.service_name=\"synapse\""
}

variable "app_sa_roles" {
  description = "List of roles to assign to the application service account"
  type        = list(string)
  default = [
    "roles/aiplatform.user",
    "roles/logging.logWriter",
    "roles/cloudtrace.agent",
    "roles/storage.admin",
    "roles/serviceusage.serviceUsageConsumer",
    "roles/secretmanager.secretAccessor",
  ]
}
