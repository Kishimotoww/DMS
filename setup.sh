#!/bin/bash
set -e  # Останавливаться при ошибках

echo "🔄 Установка Tesseract OCR..."
apt-get update
apt-get install -y tesseract-ocr tesseract-ocr-eng

echo "✅ Проверка установки Tesseract..."
tesseract --version

echo "🔧 Настройка завершена!"
