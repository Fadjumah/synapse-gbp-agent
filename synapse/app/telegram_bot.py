import os
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from google.adk.agents.llm_agent import Agent

# Assuming root_agent is imported from agent.py
from app.agent import root_agent

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    # Invoke the agent
    response = await root_agent.ainvoke(user_message)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=response)

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
