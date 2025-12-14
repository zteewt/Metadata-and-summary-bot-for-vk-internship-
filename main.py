import os
from dotenv import load_dotenv
import logging
from telegram.ext import Application
from handlers import setup_handlers

load_dotenv()
api_key = os.getenv("API_KEY")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


def main():
    app = Application.builder().token(api_key).build()
    setup_handlers(app)
    app.run_polling()

if __name__ == "__main__":
    main()