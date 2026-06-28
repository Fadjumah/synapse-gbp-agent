import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Load environment variables from .env if present
load_dotenv()

# Assuming root_agent is imported from agent.py
from app.agent import root_agent, memory # Import memory here

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Setup logging
logger = logging.getLogger(__name__)

# Initialize Runner
session_service = InMemorySessionService()
runner = Runner(agent=root_agent, app_name="app", session_service=session_service)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_message = update.message.text
    chat_id = str(update.effective_chat.id)
    session_id = f"tg_{chat_id}"

    logger.info(f"Received message from {chat_id}: {user_message}")

    # Ensure session exists
    session = await session_service.get_session(app_name="app", user_id=chat_id, session_id=session_id)
    if not session:
        try:
            await session_service.create_session(app_name="app", user_id=chat_id, session_id=session_id)
            logger.info(f"Created new session for {chat_id}")
        except Exception as e:
            logger.error(f"Failed to create session: {e}")

    # Retrieve historical context
    historical_interactions = []
    try:
        historical_interactions = memory.get_historical_context(location_id=chat_id)
    except Exception as e:
        logger.error(f"Memory error: {e}")
    
    # Ground the agent with current date/time
    current_time_str = datetime.now().strftime("%A, %B %d, %Y")
    context_string = f"### System Context:\n- Current Date: {current_time_str}\n\n"

    if historical_interactions:
        context_string += "### Previous Conversation:\n"
        # Display in chronological order
        for interaction in reversed(historical_interactions):
            context_string += f"User: {interaction.get('user_input', 'N/A')}\n"
            context_string += f"Agent: {interaction.get('agent_response', 'N/A')}\n"
        context_string += "### End Previous Conversation\n\n"

    # Prepend context to the current user message
    full_user_message = context_string + user_message
    
    # Invoke the agent using the runner in an SDK-aligned way
    try:
        response_text = ""
        logger.info(f"Invoking agent for {chat_id}...")
        async for event in runner.run_async(
            user_id=chat_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part.from_text(text=full_user_message)]),
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    response_text += event.content.parts[0].text

        if response_text:
            logger.info(f"Agent responded for {chat_id}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=response_text)
        else:
            logger.warning(f"Agent returned empty response for {chat_id}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I couldn't generate a response.")

    except Exception as e:
        logger.error(f"Error invoking agent for {chat_id}: {e}", exc_info=True)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="An error occurred while processing your request.")

async def set_telegram_webhook(url: str):
    """Utility to set the webhook for the Telegram bot."""
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN not set, cannot set webhook")
        return False
    
    application = create_telegram_application()
    if not application:
        return False
        
    await application.initialize()
    webhook_url = f"{url.rstrip('/')}/webhook"
    logger.info(f"Setting Telegram webhook to: {webhook_url}")
    result = await application.bot.set_webhook(url=webhook_url)
    return result

def create_telegram_application():
    if not TELEGRAM_TOKEN:
        print("TELEGRAM_TOKEN not set, skipping bot initialization")
        return None

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    start_handler = CommandHandler('start', start)
    message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)

    application.add_handler(start_handler)
    application.add_handler(message_handler)

    return application
