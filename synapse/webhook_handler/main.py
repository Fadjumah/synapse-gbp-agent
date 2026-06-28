import os
import requests
from flask import Flask, request, jsonify
from google.cloud import secretmanager
from vertexai.preview import reasoning_engines

app = Flask(__name__)

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

@app.route('/', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'status': 'ok'}), 200
    
    chat_id = data['message']['chat']['id']
    user_text = data['message'].get('text', '')
    
    if not user_text:
        return jsonify({'status': 'ok'}), 200

    try:
        # 1. Get Telegram Token
        telegram_token = get_secret(SECRET_NAME)
        
        # 2. Call Reasoning Engine
        remote_app = reasoning_engines.ReasoningEngine(REASONING_ENGINE_ID)
        response = remote_app.query(input=user_text)
        
        # 3. Send response back to Telegram
        telegram_api_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        requests.post(telegram_api_url, json={
            "chat_id": chat_id,
            "text": response
        })
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    # Cloud Run/Functions automatically set the PORT environment variable
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
