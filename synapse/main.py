import os
import httpx
from fastapi import FastAPI, Request
from agent import process_user_message

app = FastAPI()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

@app.post("/webhook")
async def webhook(request: Request):
    if not TELEGRAM_BOT_TOKEN:
        return {"status": "error", "message": "Missing TELEGRAM_BOT_TOKEN"}
        
    payload = await request.json()
    message = payload.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text")

    if not chat_id or not text:
        return {"status": "ok"}

    agent_response = await process_user_message(str(chat_id), text)

    async with httpx.AsyncClient() as client:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        await client.post(url, json={"chat_id": chat_id, "text": agent_response})
        
    return {"status": "ok"}
