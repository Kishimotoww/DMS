import streamlit as st
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import re
import tempfile
import os
import zipfile
import base64
import time
from datetime import datetime

# Настройка страницы
st.set_page_config(
    page_title="PDF Splitter - Ultra Rapid",
    page_icon="📄",
    layout="wide"
)

# CSS для улучшения внешнего вида
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .info-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
    }
    .progress-bar {
        width: 100%;
        background-color: #f0f0f0;
        border-radius: 10px;
        margin: 10px 0;
    }
    .progress-fill {
        height: 20px;
        background-color: #4CAF50;
        border-radius: 10px;
        text-align: center;
        color: white;
        line-height: 20px;
    }
</style>
""", unsafe_allow_html=True)

class PDFProcessor:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def find_order_number_ultra_fast(self, text):
        """Поиск номера заказа в тексте"""
        # Паттерн для 10 цифр, начинающихся с 20
        matches = re.findall(r'\b(202[4-9]\d{6})\b', text)
        if matches:
            return matches[0]
        
        matches_backup = re.findall(r'\b(20\d{8})\b', text)
        if matches_backup:
            return matches_backup[0]
        
        return None

    def extract_order_number_hybrid(self, page):
        """Гибридный метод извлечения номера"""
        # Шаг 1: Прямое извлечение текста из PDF
        text_direct = page.get_text()
        order_no = self.find_order_number_ultra_fast(text_direct)
        if order_no:
            return order_no, "direct"
        
        # Шаг 2: OCR если нужно
        try:
            # Создаем изображение с оптимизированным разрешением
            pix = page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2))
            
            # Конвертируем в PIL Image
            img_data = pix.tobytes("ppm")
            img = Image.open(io.BytesIO(img_data))
            
            # Быстрая обработка
            img = img.convert('L')  # Grayscale
            
            # Быстрый OCR
            ocr_text = pytesseract.image_to_string(
                img, 
                lang='eng',
                config='--oem 1 --psm 6 -c tessedit_do_invert=0'
            )
            
            order_no = self.find_order_number_ultra_fast(ocr_text)
            if order_no:
                return order_no, "ocr"
                
        except Exception as e:
            st.warning(f"OCR error on page: {e}")
        
        return None, "none"

    def process_pdf(self, pdf_file, progress_bar, status_text):
        """Основная функция обработки PDF"""
        start_time = time.time()
        
        # Сохраняем временный файл
        temp_pdf_path = os.path.join(self.temp_dir, "input.pdf")
        with open(temp_pdf_path, "wb") as f:
            f.write(pdf_file.getvalue())
        
        try:
            # Открываем PDF
            doc = fitz.open(temp_pdf_path)
            total_pages = len(doc)
            
            # Создаем временную папку для результатов
            output_dir = os.path.join(self.temp_dir, "output")
            os.makedirs(output_dir, exist_ok=True)
            
            # Статистика
            stats = {
                'total': total_pages,
                'direct': 0,
                'ocr': 0,
                'failed': 0,
                'files': []
            }
            
            # Обрабатываем каждую страницу
            for page_num in range(total_pages):
                page = doc[page_num]
                
                # Извлекаем номер заказа
                order_no, method = self.extract_order_number_hybrid(page)
                
                # Создаем отдельный PDF
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                
                # Генерируем имя файла
                if order_no:
                    filename = f"{order_no}.pdf"
                else:
                    filename = f"page_{page_num + 1}.pdf"
                
                output_path = os.path.join(output_dir, filename)
                
                # Избегаем перезаписи
                counter = 1
                while os.path.exists(output_path):
                    name, ext = os.path.splitext(filename)
                    output_path = os.path.join(output_dir, f"{name}_{counter}{ext}")
                    counter += 1
                
                new_doc.save(output_path)
                new_doc.close()
                
                # Обновляем статистику
                if order_no:
                    if method == "direct":
                        stats['direct'] += 1
                    else:
                        stats['ocr'] += 1
                else:
                    stats['failed'] += 1
                
                stats['files'].append(os.path.basename(output_path))
                
                # Обновляем прогресс
                progress = (page_num + 1) / total_pages
                progress_bar.progress(progress)
                
                elapsed = time.time() - start_time
                speed = (page_num + 1) / elapsed if elapsed > 0 else 0
                status_text.text(
                    f"Обработано: {page_num + 1}/{total_pages} | "
                    f"Скорость: {speed:.1f} стр/сек | "
                    f"Прямой текст: {stats['direct']} | OCR: {stats['ocr']}"
                )
            
            doc.close()
            
            # Создаем ZIP архив с результатами
            zip_path = os.path.join(self.temp_dir, "results.zip")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for file in os.listdir(output_dir):
                    file_path = os.path.join(output_dir, file)
                    zipf.write(file_path, file)
            
            total_time = time.time() - start_time
            stats['total_time'] = total_time
            stats['zip_path'] = zip_path
            
            return stats
            
        except Exception as e:
            st.error(f"Ошибка обработки PDF: {e}")
            return None

    def cleanup(self):
        """Очистка временных файлов"""
        try:
            if os.path.exists(self.temp_dir):
                import shutil
                shutil.rmtree(self.temp_dir)
        except:
            pass

    def get_download_link(self, file_path, link_text):
        """Создает ссылку для скачивания файла"""
        with open(file_path, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode()
        href = f'<a href="data:application/zip;base64,{b64}" download="pdf_results.zip">{link_text}</a>'
        return href

def main():
    # Заголовок приложения
    st.markdown('<div class="main-header">📄 PDF Splitter - Ultra Rapid</div>', unsafe_allow_html=True)
    
    # Инициализация процессора
    if 'processor' not in st.session_state:
        st.session_state.processor = PDFProcessor()
    
    # Боковая панель с информацией
    with st.sidebar:
        st.header("ℹ️ Информация")
        st.markdown("""
        **Функции:**
        - 📖 Разделение PDF на отдельные страницы
        - 🔍 Автоматическое определение номеров заказов
        - ⚡ Быстрая обработка (текст + OCR)
        - 📥 Скачивание результатов в ZIP
        
        **Поддерживаемые форматы номеров:**
        - 2024XXXXXX (10 цифр)
        - 20XXXXXXXX (10 цифр)
        """)
        
        st.markdown("---")
        st.markdown("**Статус Tesseract OCR:**")
        try:
            pytesseract.get_tesseract_version()
            st.success("✅ Tesseract доступен")
        except:
            st.warning("⚠️ Tesseract не найден - OCR недоступен")
    
    # Основная область
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📤 Загрузка PDF файла")
        uploaded_file = st.file_uploader(
            "Выберите PDF файл для обработки",
            type="pdf",
            help="Загрузите PDF файл для разделения на отдельные страницы"
        )
        
        if uploaded_file is not None:
            st.success(f"✅ Файл загружен: {uploaded_file.name}")
            st.info(f"📊 Размер файла: {uploaded_file.size / 1024 / 1024:.2f} MB")
            
            if st.button("🚀 Начать обработку", type="primary"):
                # Элементы для отображения прогресса
                progress_bar = st.progress(0)
                status_text = st.empty()
                results_placeholder = st.empty()
                
                # Обработка PDF
                with st.spinner("Обработка PDF..."):
                    stats = st.session_state.processor.process_pdf(
                        uploaded_file, 
                        progress_bar, 
                        status_text
                    )
                
                if stats:
                    # Отображаем результаты
                    with results_placeholder.container():
                        st.markdown("---")
                        st.subheader("📊 Результаты обработки")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("Всего страниц", stats['total'])
                        with col2:
                            st.metric("Прямой текст", stats['direct'])
                        with col3:
                            st.metric("OCR", stats['ocr'])
                        with col4:
                            st.metric("Без номера", stats['failed'])
                        
                        st.metric("Общее время", f"{stats['total_time']:.1f} сек")
                        
                        # Ссылка для скачивания
                        st.markdown("---")
                        st.subheader("📥 Скачать результаты")
                        
                        download_link = st.session_state.processor.get_download_link(
                            stats['zip_path'], 
                            "⬇️ Скачать ZIP архив с PDF файлами"
                        )
                        st.markdown(download_link, unsafe_allow_html=True)
                        
                        # Список созданных файлов
                        with st.expander("📋 Показать список созданных файлов"):
                            for i, filename in enumerate(stats['files'], 1):
                                st.write(f"{i}. {filename}")
    
    with col2:
        st.subheader("⚡ Быстрый старт")
        st.markdown("""
        1. **Загрузите** PDF файл
        2. **Нажмите** "Начать обработку"
        3. **Скачайте** результаты
        
        **Методы определения номеров:**
        - ✅ **Прямой текст**: Мгновенное извлечение
        - 🔍 **OCR**: Для сканированных документов
        - ⚡ **Автоматически**: Выбирается лучший метод
        """)
        
        st.markdown("---")
        st.subheader("🛠️ Технологии")
        st.markdown("""
        - **PyMuPDF**: Обработка PDF
        - **Tesseract**: OCR распознавание
        - **Streamlit**: Веб-интерфейс
        - **Pillow**: Обработка изображений
        """)

# Очистка при завершении
import atexit
atexit.register(lambda: st.session_state.get('processor', PDFProcessor()).cleanup())

if __name__ == "__main__":
    main()