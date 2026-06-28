import os
import json
import requests
import traceback
import google.auth
import google.auth.transport.requests
from google.cloud import secretmanager

# Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
LOCATION = os.environ.get("LOCATION", "us-east1")
REASONING_ENGINE_ID = os.environ.get("REASONING_ENGINE_ID")
SECRET_NAME = os.environ.get("TELEGRAM_TOKEN_SECRET_NAME", "TELEGRAM_TOKEN")

def get_secret(secret_name):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

def get_google_access_token():
    """Fetches a Google OAuth2 access token using the function's service account credentials."""
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token

def telegram_webhook(request):
    """HTTP Cloud Function handler calling Vertex AI REST API directly."""
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
        
        # 2. Get Google Access Token
        google_token = get_google_access_token()
        
        # 3. Call Vertex AI Reasoning Engine REST Endpoint directly
        # REASONING_ENGINE_ID is in the format: projects/PROJECT_ID/locations/LOCATION/reasoningEngines/ID
        url = f"https://{LOCATION}-aiplatform.googleapis.com/v1/{REASONING_ENGINE_ID}:query"
        
        headers = {
            "Authorization": f"Bearer {google_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "input": {
                "input": user_text
            }
        }
        
        print(f"Calling Vertex AI REST Endpoint: {url}")
        vertex_resp = requests.post(url, json=payload, headers=headers)
        
        if vertex_resp.status_code != 200:
            raise Exception(f"Vertex AI returned error {vertex_resp.status_code}: {vertex_resp.text}")
            
        vertex_data = vertex_resp.json()
        print(f"Vertex response payload: {json.dumps(vertex_data)}")
        
        # Extract response text (adapts dynamically to return format)
        output_data = vertex_data.get("output", {})
        if isinstance(output_data, dict):
            response_text = output_data.get("output", output_data.get("text", str(output_data)))
        else:
            response_text = str(output_data)
            
        print(f"Extracted response: {response_text}")
        
        # 4. Send response back to Telegram
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
