import os
import fitz  
from docx import Document  
import chardet  
from langdetect import detect, LangDetectException
from pathlib import Path

class FileProcessor:

    @staticmethod
    def get_file_metadata(file_path, original_name):
        
        file_size = os.path.getsize(file_path)
        file_extension = Path(original_name).suffix.lower()

        metadata = {
            "name": original_name,
            "size": file_size,
            "type": file_extension,
            "language": "unknown"
        }

        try:
            if file_extension == '.pdf':
                metadata = FileProcessor._process_pdf(file_path, metadata)
            elif file_extension == '.docx':
                metadata = FileProcessor._process_docx(file_path, metadata)
            elif file_extension in ['.txt', '.md']:
                metadata = FileProcessor._process_text(file_path, metadata)
            else:
                metadata["language"] = "unsupported_format"
            
        except Exception as e:
            metadata["error"] = str(e)
        return metadata

    @staticmethod
    def _process_pdf(file_path, metadata):
        with fitz.open(file_path) as doc:
            text_for_lang = ""
            for i in range(min(2, doc.page_count)):  
                page_text = doc[i].get_text().strip()
                if page_text:
                    text_for_lang += page_text + " "

            if text_for_lang.strip():
                metadata["language"] = FileProcessor._detect_language(text_for_lang)
            
        return metadata

    @staticmethod
    def _process_docx(file_path, metadata):
        doc = Document(file_path)

        text_for_lang = ""
        for i, paragraph in enumerate(doc.paragraphs):
            if i >= 5:  # Ограничиваем количество. Берем 5 абазацев
                break
            if paragraph.text.strip():
                text_for_lang += paragraph.text + " "
        
        if text_for_lang.strip():
            metadata["language"] = FileProcessor._detect_language(text_for_lang)

        return metadata

    @staticmethod
    def _process_text(file_path, metadata):
        with open(file_path, 'rb') as f:
            raw_data = f.read()
        
        encoding_info = chardet.detect(raw_data)
        encoding = encoding_info['encoding'] if encoding_info['confidence'] > 0.7 else 'utf-8'
        
        try:
            text = raw_data.decode(encoding, errors='replace')
        except:
            text = raw_data.decode('utf-8', errors='replace')
        
        if text.strip():
            # Берем первые 5000 символов для анализа
            sample = text[:5000]
            metadata["language"] = FileProcessor._detect_language(sample)
        
        return metadata
    
    @staticmethod
    def _detect_language(text):
        cleaned_text = text.strip()
        if len(cleaned_text) < 50:
            return "text_too_short"
        try:
            detected = detect(cleaned_text)
            if detected in ['ru', 'en', 'uk', 'de', 'fr', 'es', 'it']:
                return detected
        except LangDetectException:
            return "unknown"
        return FileProcessor._guess_language_by_chars(cleaned_text)

    @staticmethod
    def _guess_language_by_chars(text):
        cyrillic = sum(1 for char in text if '\u0400' <= char <= '\u04FF')
        latin = sum(1 for char in text if 'a' <= char.lower() <= 'z')
        
        if cyrillic > latin * 3:
            return 'ru'
        elif latin > cyrillic * 3:
            return 'en'
        elif cyrillic > 0:
            return 'ru'
        else:
            return 'unknown'