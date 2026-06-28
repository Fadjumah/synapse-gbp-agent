import os
import json
import requests
import traceback
from google.cloud import aiplatform
from google.cloud import secretmanager

# Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
LOCATION = os.environ.get("LOCATION", "us-east1")
REASONING_ENGINE_ID = os.environ.get("REASONING_ENGINE_ID")
SECRET_NAME = os.environ.get("TELEGRAM_TOKEN_SECRET_NAME", "TELEGRAM_TOKEN")

# Initialize stable AI Platform SDK
aiplatform.init(project=PROJECT_ID, location=LOCATION)

def get_secret(secret_name):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

def telegram_webhook(request):
    """HTTP Cloud Function handler."""
    # Cloud Functions passes the Flask request object directly as an argument
    data = request.get_json(silent=True)
    print(f"Received payload: {json.dumps(data)}")
    
    if not data or 'message' not in data:
        return 'OK', 200
    
    chat_id = data['message']['chat']['id']
    user_text = data['message'].get('text', '')
    
    if not user_text:
        return 'OK', 200

    try:
        # 1. Get Telegram Token
        telegram_token = get_secret(SECRET_NAME)
        
        # 2. Call Vertex AI Reasoning Engine using the correct preview class
        remote_app = aiplatform.preview.ReasoningEngine(REASONING_ENGINE_ID)
        print(f"Querying Reasoning Engine: {REASONING_ENGINE_ID} with input: {user_text}")
        
        # Call the reasoning engine's query method
        response_text = remote_app.query(
            input=user_text
        )
        print(f"Got response: {response_text}")
        
        # 3. Send response back to Telegram
        telegram_api_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        resp = requests.post(telegram_api_url, json={
            "chat_id": chat_id,
            "text": str(response_text)
        })
        print(f"Telegram response: {resp.status_code} {resp.text}")
        
        return 'OK', 200
        
    except Exception as e:
        print(f"Error caught: {e}")
        print(traceback.format_exc())
        return f"Error: {str(e)}", 500
