import os
import logging
from fastapi import FastAPI, Request, Response
from telegram import Update
from app.telegram_bot import create_telegram_application

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Initialize the Telegram Application
telegram_app = create_telegram_application()

@app.on_event("startup")
async def startup():
    if telegram_app:
        await telegram_app.initialize()
        await telegram_app.start()

@app.on_event("shutdown")
async def shutdown():
    if telegram_app:
        await telegram_app.stop()
        await telegram_app.shutdown()

@app.post("/webhook")
async def webhook(request: Request):
    if not telegram_app:
        return {"status": "error", "message": "Bot not initialized"}
        
    payload = await request.json()
    
    # Process the update through the Telegram application
    update = Update.de_json(payload, telegram_app.bot)
    await telegram_app.process_update(update)
    
    return Response(status_code=200)

@app.get("/health")
async def health():
    return {"status": "ok"}
