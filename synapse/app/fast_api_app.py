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
import os
import google.auth
from fastapi import FastAPI, Request
from google.adk.cli.fast_api import get_fast_api_app
from google.cloud import logging as google_cloud_logging
from google import genai
from telegram import Update

from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import Feedback
from app.telegram_bot import create_telegram_application

# Initialize the Gemini API client
client = genai.Client()

setup_telemetry()
_, project_id = google.auth.default()
logging_client = google_cloud_logging.Client()
logger = logging_client.logger(__name__)
allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

# Initialize Telegram application
telegram_app = create_telegram_application()

# Artifact bucket for ADK (created by Terraform, passed via env var)
logs_bucket_name = os.environ.get("LOGS_BUCKET_NAME")

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# In-memory session configuration - no persistent storage
session_service_uri = None

artifact_service_uri = f"gs://{logs_bucket_name}" if logs_bucket_name else None

app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=artifact_service_uri,
    allow_origins=allow_origins,
    session_service_uri=session_service_uri,
    otel_to_cloud=True,
)
app.title = "synapse"
app.description = "API for interacting with the Agent synapse"


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback.

    Args:
        feedback: The feedback data to log

    Returns:
        Success message
    """
    logger.log_struct(feedback.model_dump(), severity="INFO")
    return {"status": "success"}

@app.post("/webhook/{token}")
@app.post("/webhook")
async def telegram_webhook(request: Request, token: str = None):
    # Log incoming request details immediately
    logger.log_struct({
        "message": "Received request at /webhook",
        "path": request.url.path,
        "method": request.method,
        "token_provided": token is not None,
        "headers": dict(request.headers),
    }, severity="INFO")

    if not telegram_app:
        logger.log_text("Telegram bot not initialized", severity="WARNING")
        return {"status": "bot not initialized"}
    
    # Optional: Validate the token if needed
    # if token != os.getenv("TELEGRAM_TOKEN"):
    #     return {"status": "unauthorized"}, 401
    
    try:
        body = await request.body()
        # Log the raw body for debugging
        logger.log_struct({"message": "Webhook body", "body": body.decode('utf-8')}, severity="INFO")
        
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.log_text(f"Error processing webhook: {str(e)}", severity="ERROR")
        return {"status": "error", "message": str(e)}

@app.post("/")
async def root_webhook(request: Request):
    # Log that a request hit the root path
    logger.log_struct({
        "message": "Received request at /",
        "path": request.url.path,
        "method": request.method,
    }, severity="INFO")
    # Redirect to the /webhook handler
    return await telegram_webhook(request)


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
