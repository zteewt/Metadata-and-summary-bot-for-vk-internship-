import json
import requests
import os
from telegram.ext import CommandHandler, MessageHandler, filters
from utils import FileProcessor
import tempfile

async def start(update, context):
    await context.bot.send_message(chat_id=update.effective_chat.id, text='Отправьте файл (PDF, DOCX, TXT или MD)')
   

async def handle_document(update, context):
    try:
        document = update.message.document
        file_name = document.file_name
        
        if not file_name:
            await update.message.reply_text("Файл не имеет имени.")
            return
        
        file_extension = os.path.splitext(file_name)[1].lower()
        
        allowed_extensions = [".pdf", ".docx", ".txt", ".md"]
        
        if file_extension not in allowed_extensions:
            await update.message.reply_text(
                f"Неподдерживаемый формат файла: {file_extension}\n"
                "Поддерживаемые форматы: PDF, DOCX, TXT, MD"
            )
            return

        file_obj = await document.get_file()

        # Создаем временный файл
        with tempfile.NamedTemporaryFile(
            delete=False, 
            suffix=file_extension,
            prefix="bot_"
        ) as tmp_file:
            temp_path = tmp_file.name

        try:
            # Скачиваем файл
            await file_obj.download_to_drive(temp_path)
            
            # 1. Получаем базовые метаданные (быстро)
            metadata = FileProcessor.get_file_metadata(temp_path, file_name)
            
            # 2. Отправляем уведомление о начале обработки
            processing_msg = await update.message.reply_text(
                "⏳ Анализирую файл...",
                reply_to_message_id=update.message.message_id
            )
            
            # 3. Отправляем файл в n8n для расширенной обработки
            n8n_success = await send_to_n8n(
                file_path=temp_path,
                file_name=file_name,
                telegram_update=update,
                temp_message=processing_msg
            )
            
            # 4. Формируем финальный ответ
            if n8n_success:
                # Показываем базовые метаданные + статус
                basic_response = format_metadata_response(metadata)
                final_response = (
                    f"✅ *Файл успешно отправлен на обработку*\n\n"
                    f"{basic_response}\n\n"
                    f"📊 *Дополнительный анализ:*\n"
                    f"• Текст будет извлечён (OCR для сканов)\n"
                    f"• Создана краткая выжимка\n"
                    f"• Выделены ключевые слова\n"
                    f"• Результаты сохранены в Google Sheets\n\n"
                    f"🔄 *Статус:* Обработка завершена"
                )
            else:
                basic_response = format_metadata_response(metadata)
                final_response = (
                    f"⚠️ *Базовые метаданные файла*\n\n"
                    f"{basic_response}\n\n"
                    f"❌ *Дополнительный анализ:* Не удалось отправить на обработку"
                )
            await processing_msg.edit_text(final_response, parse_mode='Markdown')
            
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Ошибка в handle_document: {e}\n{error_details}")
        
        await update.message.reply_text(
            f"❌ Произошла ошибка при обработке файла:\n`{str(e)[:200]}`",
            parse_mode='Markdown'
        )


async def send_to_n8n(file_path, file_name, telegram_update, temp_message):
    try:
        n8n_webhook_url = os.getenv("N8N_WEBHOOK_URL")
        
        if not n8n_webhook_url:
            print("⚠️ N8N_WEBHOOK_URL не указан в .env")
            return False
        
        user = telegram_update.message.from_user
        chat = telegram_update.message.chat
        
        user_info = {
            "id": user.id,
            "username": user.username or f"user_{user.id}",
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "full_name": user.full_name or "Неизвестный пользователь"
        }
        
        chat_info = {
            "id": chat.id,
            "type": chat.type,
            "title": getattr(chat, 'title', '')
        }
        
        message_info = {
            "message_id": telegram_update.message.message_id,
            "date": telegram_update.message.date.isoformat() if telegram_update.message.date else None
        }

        metadata_payload = {
            "event": "file_upload",
            "user": user_info,
            "chat": chat_info,
            "message": message_info,
            "file": {
                "name": file_name,
                "size": os.path.getsize(file_path),
                "type": os.path.splitext(file_name)[1].lower()
            },
            "temp_message_id": temp_message.message_id if temp_message else None
        }
    
        with open(file_path, 'rb') as f:
            files = {
                'file': (file_name, f, 'application/octet-stream')
            }
            
            response = requests.post(
                n8n_webhook_url,
                files=files,
                data={
                    'metadata': json.dumps(metadata_payload, ensure_ascii=False)
                },
                timeout=60
            )
        
        if response.status_code == 200:
            print(f"✅ Файл {file_name} успешно отправлен в n8n")
            
            try:
                n8n_response = response.json()
                print(f"Ответ n8n: {n8n_response}")
            except:
                pass
                
            return True
        else:
            print(f"❌ Ошибка отправки в n8n: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Сетевая ошибка при отправке в n8n: {e}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка при отправке в n8n: {e}")
        import traceback
        print(traceback.format_exc())
        return False
    

def format_metadata_response(metadata):
    size = metadata["size"]
    if size > 1024*1024:
        size_str = f"{size/1024/1024:.2f} MB"
    elif size > 1024:
        size_str = f"{size/1024:.2f} KB"
    else:
        size_str = f"{size} байт"

    language_map = {
        'ru': '🇷🇺 Русский',
        'en': '🇬🇧 Английский',
        'uk': '🇺🇦 Украинский',
        'de': '🇩🇪 Немецкий',
        'fr': '🇫🇷 Французский',
        'es': '🇪🇸 Испанский',
        'it': '🇮🇹 Итальянский',
        'unknown': '❓ Неизвестен',
        'text_too_short': '📝 Текст слишком короткий',
        'unsupported_format': '🚫 Неподдерживаемый формат'
    }
    
    language = language_map.get(metadata["language"], metadata["language"])
    
    response = (
        f"📄 *Имя файла:* {metadata['name']}\n"
        f"📦 *Размер:* {size_str}\n"
        f"🔤 *Тип:* {metadata['type']}\n"
        f"🌐 *Язык:* {language}"
    )

    return response



def setup_file_handlers(app):
    start_handler = CommandHandler("start", start)
    app.add_handler(start_handler)
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))