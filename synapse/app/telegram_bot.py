import logging
import os

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
    user_message = update.message.text
    chat_id = str(update.effective_chat.id)
    session_id = chat_id

    logger.info(f"Received message from {chat_id}: {user_message}")

    # Ensure session exists (wrap in try/except to ignore already exists)
    try:
        await session_service.create_session(app_name="app", user_id=chat_id, session_id=session_id)
    except Exception:
        logger.info(f"Session {session_id} already active.")

    # Retrieve historical context
    historical_interactions = memory.get_historical_context(location_id=chat_id)
    context_string = ""
    if historical_interactions:
        context_string += "### Previous Conversation:\n"
        # Display in chronological order
        for interaction in reversed(historical_interactions):
            context_string += f"User: {interaction.get('user_input', 'N/A')}\n"
            context_string += f"Agent: {interaction.get('agent_response', 'N/A')}\n"
        context_string += "### End Previous Conversation\n\n"

    # Prepend historical context to the current user message
    full_user_message = context_string + user_message
    
    # Invoke the agent using the runner in an SDK-aligned way
    try:
        response_text = ""
        # Using run_async with standard SDK types for better alignment
        async for event in runner.run_async(
            user_id=chat_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part.from_text(text=full_user_message)]),
        ):
            if event.is_final_response():
                if event.content and event.content.parts:
                    response_text += event.content.parts[0].text

        if response_text:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=response_text)
        else:
            logger.warning("Agent returned empty response")
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Sorry, I couldn't generate a response.")

    except Exception as e:
        logger.error(f"Error invoking agent: {e}", exc_info=True)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="An error occurred while processing your request.")

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
