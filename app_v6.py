import streamlit as st
import fitz
import pytesseract
from PIL import Image
import io
import re
import tempfile
import os
import zipfile
import base64
import time
import subprocess

# Настройка страницы
st.set_page_config(
    page_title="PDF Splitter - RELIABLE",
    page_icon="📄",
    layout="wide"
)

# Простая проверка Tesseract
def setup_tesseract():
    try:
        # Пробуем найти tesseract
        result = subprocess.run(['which', 'tesseract'], capture_output=True, text=True)
        if result.returncode == 0:
            tesseract_path = result.stdout.strip()
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            return True
        return False
    except:
        return False

tesseract_available = setup_tesseract()

# Простой класс для остановки
class StopProcessing:
    def __init__(self):
        self.stop = False
    
    def set(self):
        self.stop = True
    
    def is_set(self):
        return self.stop

stop_processing = StopProcessing()

# CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .reliable {
        background: linear-gradient(45deg, #667eea, #764ba2);
        color: white;
        padding: 10px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

class PDFProcessor:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def find_order_number(self, text):
        """Простой и надежный поиск номеров"""
        if not text:
            return None
            
        # Основные паттерны
        patterns = [
            r'\b(202[4-9]\d{6})\b',  # 2024XXXXXX
            r'\b(20\d{8})\b',        # 20XXXXXXXX
            r'\b(\d{10})\b',         # Любые 10 цифр
            r'\b(\d{8,12})\b',       # 8-12 цифр
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                return matches[0]
        return None

    def extract_text_simple(self, page):
        """Простое извлечение текста"""
        try:
            return page.get_text()
        except:
            return ""

    def process_page_simple(self, page_num, page):
        """Простая обработка страницы"""
        if stop_processing.is_set():
            return None, "stopped"
        
        try:
            # Шаг 1: Текст из PDF
            text = self.extract_text_simple(page)
            order_no = self.find_order_number(text)
            
            if order_no:
                return order_no, "direct"
            
            # Шаг 2: Простой OCR
            if tesseract_available:
                try:
                    # Создаем изображение
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    img = img.convert('L')
                    
                    # Простой OCR
                    ocr_text = pytesseract.image_to_string(img, lang='eng')
                    order_no = self.find_order_number(ocr_text)
                    
                    if order_no:
                        return order_no, "ocr"
                except:
                    pass
            
            return None, "not_found"
            
        except Exception as e:
            return None, "error"

    def process_pdf_simple(self, pdf_file, progress_bar, status_text):
        """ПРОСТАЯ и НАДЕЖНАЯ обработка PDF"""
        stop_processing.stop = False
        start_time = time.time()
        
        try:
            # Сохраняем PDF во временный файл
            temp_pdf_path = os.path.join(self.temp_dir, "input.pdf")
            with open(temp_pdf_path, "wb") as f:
                f.write(pdf_file.getvalue())
            
            # Открываем PDF
            doc = fitz.open(temp_pdf_path)
            total_pages = len(doc)
            
            # Создаем папку для результатов
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
                if stop_processing.is_set():
                    break
                
                page = doc[page_num]
                order_no, method = self.process_page_simple(page_num, page)
                
                # Создаем отдельный PDF
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                
                # Имя файла
                if order_no:
                    filename = f"{order_no}.pdf"
                else:
                    filename = f"page_{page_num + 1}.pdf"
                
                output_path = os.path.join(output_dir, filename)
                
                # Избегаем дубликатов
                counter = 1
                base_name = os.path.splitext(filename)[0]
                while os.path.exists(output_path):
                    output_path = os.path.join(output_dir, f"{base_name}_{counter}.pdf")
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
                
                stats['files'].append({
                    'filename': os.path.basename(output_path),
                    'page': page_num + 1,
                    'method': method,
                    'order_no': order_no
                })
                
                # Прогресс
                progress = (page_num + 1) / total_pages
                progress_bar.progress(progress)
                
                # Статус
                elapsed = time.time() - start_time
                speed = (page_num + 1) / elapsed if elapsed > 0 else 0
                
                status_text.text(
                    f"📄 Обработано: {page_num + 1}/{total_pages} | "
                    f"⚡ Скорость: {speed:.1f} стр/сек | "
                    f"✅ Найдено: {stats['direct'] + stats['ocr']} | "
                    f"❌ Не найдено: {stats['failed']}"
                )
            
            doc.close()
            
            # Создаем ZIP
            if stats['files']:
                zip_path = os.path.join(self.temp_dir, "results.zip")
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for file_info in stats['files']:
                        file_path = os.path.join(output_dir, file_info['filename'])
                        zipf.write(file_path, file_info['filename'])
                stats['zip_path'] = zip_path
            
            # Финальная статистика
            stats['total_time'] = time.time() - start_time
            stats['success_rate'] = ((stats['direct'] + stats['ocr']) / total_pages) * 100
            
            return stats
            
        except Exception as e:
            st.error(f"❌ Ошибка: {str(e)}")
            import traceback
            st.error(f"Детали: {traceback.format_exc()}")
            return None

    def get_download_link(self, file_path, link_text):
        """Создает ссылку для скачивания"""
        if not file_path or not os.path.exists(file_path):
            return "❌ Файл не найден"
            
        with open(file_path, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode()
        href = f'<a href="data:application/zip;base64,{b64}" download="pdf_results.zip" style="background-color: #4CAF50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: bold;">{link_text}</a>'
        return href

def main():
    st.markdown('<div class="main-header">📄 PDF Splitter - RELIABLE</div>', unsafe_allow_html=True)
    st.markdown('<div class="reliable">🔧 ПРОСТАЯ И НАДЕЖНАЯ ВЕРСИЯ</div>', unsafe_allow_html=True)
    
    if 'processor' not in st.session_state:
        st.session_state.processor = PDFProcessor()
    
    # Sidebar
    with st.sidebar:
        st.header("ℹ️ Информация")
        st.markdown("""
        **Особенности:**
        - ✅ Простая и надежная
        - 🔧 Минимальный код
        - 🚀 Стабильная работа
        - 📄 Поддержка всех PDF
        """)
        
        st.markdown(f"**OCR:** {'✅ Доступен' if tesseract_available else '❌ Не доступен'}")
        
        if st.button("🛑 Остановить", use_container_width=True):
            stop_processing.set()
            st.warning("Обработка будет остановлена!")

    # Main area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📤 Загрузка PDF")
        uploaded_file = st.file_uploader("Выберите PDF файл", type="pdf")
        
        if uploaded_file is not None:
            st.success(f"✅ Файл загружен: {uploaded_file.name}")
            st.info(f"📊 Размер: {uploaded_file.size / 1024 / 1024:.2f} MB")
            
            if st.button("🚀 Начать обработку", type="primary", use_container_width=True):
                progress_bar = st.progress(0)
                status_text = st.empty()
                results_placeholder = st.empty()
                
                with st.spinner("Обработка PDF..."):
                    stats = st.session_state.processor.process_pdf_simple(
                        uploaded_file, progress_bar, status_text
                    )
                
                if stats:
                    with results_placeholder.container():
                        st.markdown("---")
                        st.subheader("📊 Результаты обработки")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Всего страниц", stats['total'])
                        col2.metric("Текстом", stats['direct'])
                        col3.metric("OCR", stats['ocr'])
                        col4.metric("Не найдено", stats['failed'])
                        
                        st.metric("Успешность", f"{stats['success_rate']:.1f}%")
                        st.metric("Время обработки", f"{stats['total_time']:.1f} сек")
                        
                        # Скачивание
                        if stats.get('zip_path'):
                            st.markdown("---")
                            st.subheader("📥 Скачать результаты")
                            download_link = st.session_state.processor.get_download_link(
                                stats['zip_path'], "⬇️ Скачать ZIP архив"
                            )
                            st.markdown(download_link, unsafe_allow_html=True)
                        
                        # Список файлов
                        with st.expander("📋 Показать список файлов"):
                            for file_info in stats['files']:
                                method_icon = "✅" if file_info['method'] == 'direct' else "🔍" if file_info['method'] == 'ocr' else "❌"
                                status = "УСПЕХ" if file_info['order_no'] else "НЕ НАЙДЕНО"
                                st.write(f"{method_icon} Страница {file_info['page']}: {file_info['filename']} ({status})")
    
    with col2:
        st.subheader("⚡ О приложении")
        st.markdown("""
        **Как работает:**
        1. **Загрузите** PDF файл
        2. **Нажмите** кнопку обработки
        3. **Система** автоматически найдет номера
        4. **Скачайте** разделенные PDF
        
        **Функции:**
        - Автоопределение номеров
        - Резервный OCR
        - Простой интерфейс
        - Надежная работа
        """)

if __name__ == "__main__":
    main()
