import logging

from fastapi import FastAPI, Request, Response
from telegram import Update
from apscheduler.schedulers.background import BackgroundScheduler # New Import

from app.telegram_bot import create_telegram_application

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Initialize the Telegram Application
telegram_app = create_telegram_application()

# Initialize Scheduler
scheduler = BackgroundScheduler()

def perform_scheduled_task():
    logger.info("Performing a scheduled task!")
    # In the future, this is where we'd call agent tools or other logic.

# Add a job for testing purposes (e.g., runs every 10 seconds)
scheduler.add_job(perform_scheduled_task, 'interval', seconds=10, id='simple_scheduled_task')


@app.on_event("startup")
async def startup():
    if telegram_app:
        await telegram_app.initialize()
        await telegram_app.start()
    scheduler.start() # Start the scheduler

@app.on_event("shutdown")
async def shutdown():
    if telegram_app:
        await telegram_app.stop()
        await telegram_app.shutdown()
    scheduler.shutdown() # Shut down the scheduler

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
