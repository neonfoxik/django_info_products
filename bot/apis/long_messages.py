import os
from pathlib import Path

from docx import Document

from django.conf import settings


def split_message(message, chunk_size=4096):
    chunks = []
    while message:
        chunk = message[:chunk_size]
        chunks.append(chunk)
        message = message[chunk_size:]
    return chunks


def save_message_to_file(message, extension):
    # Создаем директорию temp/files, если она не существует
    temp_dir = settings.BASE_DIR / 'temp' / 'files'
    
    # Создаем все директории в пути, если они не существуют
    os.makedirs(temp_dir, exist_ok=True)
    
    # Проверяем существование директории перед подсчетом файлов
    if not os.path.exists(temp_dir):
        file_count = 0
    else:    
        file_count = len([f for f in os.listdir(temp_dir) if os.path.isfile(os.path.join(temp_dir, f))])
    
    if extension == "txt":
        filename = f"message_{file_count + 1}.{extension}"
        file_path = temp_dir / filename
        
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(message)
    elif extension == "docx":
        doc = Document()
        doc.add_paragraph(message)
        filename = f"message_{file_count + 1}.{extension}"
        file_path = temp_dir / filename
        doc.save(file_path)
    
    # Возвращаем полный путь к файлу
    return str(file_path)
