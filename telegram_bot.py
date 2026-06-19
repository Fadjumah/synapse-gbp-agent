import os
import logging
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Import your agent
# Assuming app/agent.py exists and has root_agent
try:
    from app.agent import root_agent
except ImportError:
    # Fallback if running from a different directory context
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from app.agent import root_agent

# Initialize ADK components
session_service = InMemorySessionService()
runner = Runner(
    agent=root_agent,
    app_name="synapse-gbp-agent",
    session_service=session_service
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Hello! I am Synapse, your Google Business Profile growth agent. How can I help you today?"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    session_id = f"tg_{update.effective_chat.id}"
    user_text = update.message.text

    if not user_text:
        return

    logging.info(f"Received message from {user_id} in {session_id}: {user_text}")

    # Prepare ADK message
    new_message = types.Content(role='user', parts=[types.Part(text=user_text)])

    # Send typing action
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response_text = ""
        # Run the agent asynchronously
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=new_message
        ):
            # Collect final response
            if event.is_final_response() and event.content and event.content.parts:
                response_text += "".join(p.text for p in event.content.parts if p.text)
        
        if not response_text:
            response_text = "I'm sorry, I couldn't generate a response."

        await context.bot.send_message(chat_id=update.effective_chat.id, text=response_text)
    except Exception as e:
        logging.error(f"Error running agent: {e}", exc_info=True)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Oops! Something went wrong while processing your request.")

if __name__ == '__main__':
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not found in environment variables.")
        exit(1)

    application = ApplicationBuilder().token(token).build()
    
    start_handler = CommandHandler('start', start)
    message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    
    application.add_handler(start_handler)
    application.add_handler(message_handler)
    
    print("Synapse Telegram Bot is starting...")
    application.run_polling()
