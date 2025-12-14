import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler

async def start(update, context):
    await context.bot.send_message(chat_id=update.effective_chat.id, text='Отправьте файл (PDF, DOCX, TXT или MD)')
   

def setup_file_handlers(app):
    start_handler = CommandHandler("start", start)
    app.add_handler(start_handler)