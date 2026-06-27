import os
import logging
from dotenv import load_dotenv
from app.telegram_bot import create_telegram_application

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    # Load environment variables
    load_dotenv()
    
    logger.info("Starting Telegram bot in POLLING mode...")
    
    # Create the application
    application = create_telegram_application()
    
    if not application:
        logger.error("Failed to create Telegram application. Check your TELEGRAM_TOKEN.")
        return

    # Run the bot in polling mode
    logger.info("Bot is now polling. Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == "__main__":
    main()
