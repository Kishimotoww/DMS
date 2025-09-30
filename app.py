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
import sys

# Настройка страницы
st.set_page_config(
    page_title="PDF Splitter - Ultra Rapid",
    page_icon="📄",
    layout="wide"
)

# Проверяем и настраиваем Tesseract
def setup_tesseract():
    """Настройка Tesseract для Streamlit Cloud"""
    try:
        # Пробуем найти tesseract в системе
        result = subprocess.run(['which', 'tesseract'], capture_output=True, text=True)
        if result.returncode == 0:
            tesseract_path = result.stdout.strip()
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            st.success(f"✅ Tesseract найден: {tesseract_path}")
            return True
        else:
            # Пробуем установить
            st.warning("🔄 Tesseract не найден, пробуем установить...")
            install_result = subprocess.run([
                'apt-get', 'update', '&&', 
                'apt-get', 'install', '-y', 'tesseract-ocr', 'tesseract-ocr-eng'
            ], shell=True, capture_output=True, text=True)
            
            if install_result.returncode == 0:
                st.success("✅ Tesseract успешно установлен!")
                return True
            else:
                st.error(f"❌ Ошибка установки Tesseract: {install_result.stderr}")
                return False
    except Exception as e:
        st.error(f"❌ Ошибка настройки Tesseract: {e}")
        return False

# Глобальная переменная для остановки
class StopProcessing:
    def __init__(self):
        self._stop = False
    
    def set(self):
        self._stop = True
    
    def is_set(self):
        return self._stop

stop_processing = StopProcessing()

# Настраиваем Tesseract при запуске
tesseract_available = setup_tesseract()

# CSS стили
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stop-button {
        background-color: #ff4444 !important;
        color: white !important;
        border: none !important;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
        margin: 0.5rem 0;
    }
    .success-rate {
        font-size: 1.5rem;
        font-weight: bold;
        color: #28a745;
    }
</style>
""", unsafe_allow_html=True)

class PDFProcessor:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def find_order_number_ultra_fast(self, text):
        """Поиск номера заказа в тексте - ОПТИМИЗИРОВАННЫЙ"""
        patterns = [
            r'\b(202[4-9]\d{6})\b',  # 2024XXXXXX
            r'\b(20\d{8})\b',        # 20XXXXXXXX  
            r'\b(\d{10})\b',         # Любые 10 цифр
            r'\b(\d{8,12})\b',       # 8-12 цифр
            r'\b(ORDER[:\\s]*)(\d{8,12})\b',  # ORDER: 12345678
            r'\b(№[:\\s]*)(\d{8,12})\b',      # № 12345678
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Возвращаем последнюю группу (номер)
                if isinstance(matches[0], tuple):
                    for match in matches[0]:
                        if match and match.isdigit():
                            return match
                else:
                    return matches[0]
        return None

    def extract_text_optimized(self, page):
        """Оптимизированное извлечение текста из PDF"""
        try:
            # Пробуем разные методы извлечения текста
            text_methods = []
            
            # 1. Быстрый метод
            text_raw = page.get_text("text")
            if text_raw and len(text_raw) > 10:
                text_methods.append(text_raw)
            
            # 2. Метод слов (более точный)
            words = page.get_text("words")
            if words:
                text_words = " ".join([word[4] for word in words if len(word) > 4])
                text_methods.append(text_words)
            
            # 3. Метод блоков
            blocks = page.get_text("blocks")  
            if blocks:
                text_blocks = " ".join([block[4] for block in blocks if len(block) > 4])
                text_methods.append(text_blocks)
            
            combined_text = " ".join(text_methods)
            return combined_text
            
        except Exception as e:
            return ""

    def process_page_fast(self, page_num, page):
        """Быстрая обработка одной страницы"""
        if stop_processing.is_set():
            return None, "stopped", page_num
        
        try:
            # Шаг 1: Быстрое извлечение текста (ОЧЕНЬ БЫСТРО)
            text_direct = self.extract_text_optimized(page)
            order_no = self.find_order_number_ultra_fast(text_direct)
            
            if order_no:
                return order_no, "direct", page_num
            
            # Шаг 2: OCR если доступен (медленнее, но точнее)
            if tesseract_available and not order_no:
                try:
                    # ОПТИМИЗИРОВАННОЕ создание изображения
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2))  # Низкое разрешение для скорости
                    img_data = pix.tobytes("png")  # PNG быстрее
                    img = Image.open(io.BytesIO(img_data))
                    
                    # Минимальная обработка изображения
                    img = img.convert('L')  # Grayscale
                    
                    # ОПТИМИЗИРОВАННЫЙ OCR с быстрыми настройками
                    ocr_text = pytesseract.image_to_string(
                        img, 
                        lang='eng',
                        config='--oem 1 --psm 6 -c preserve_interword_spaces=0'
                    )
                    
                    order_no = self.find_order_number_ultra_fast(ocr_text)
                    if order_no:
                        return order_no, "ocr", page_num
                        
                except Exception as e:
                    return None, "ocr_error", page_num
            
            return None, "not_found", page_num
            
        except Exception as e:
            return None, "error", page_num

    def process_pdf_optimized(self, pdf_file, progress_bar, status_text):
        """ОПТИМИЗИРОВАННАЯ обработка PDF"""
        global stop_processing
        stop_processing = StopProcessing()
        
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
                'stopped': 0,
                'files': [],
                'success_rate': 0,
                'total_time': 0
            }
            
            # Обрабатываем страницы с прогрессом
            for page_num in range(total_pages):
                if stop_processing.is_set():
                    stats['stopped'] = total_pages - page_num
                    break
                
                page_start_time = time.time()
                
                page = doc[page_num]
                order_no, method, _ = self.process_page_fast(page_num, page)
                
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
                
                # Обновляем прогресс
                progress = (page_num + 1) / total_pages
                progress_bar.progress(progress)
                
                elapsed = time.time() - start_time
                speed = (page_num + 1) / elapsed if elapsed > 0 else 0
                processed = page_num + 1
                
                status_text.text(
                    f"📊 Обработано: {processed}/{total_pages} | "
                    f"⚡ Скорость: {speed:.1f} стр/сек | "
                    f"✅ Текст: {stats['direct']} | "
                    f"🔍 OCR: {stats['ocr']} | "
                    f"❌ Не найдено: {stats['failed']}"
                )
            
            doc.close()
            
            # Создаем ZIP архив
            if stats['files']:
                zip_path = os.path.join(self.temp_dir, "results.zip")
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for file_info in stats['files']:
                        file_path = os.path.join(output_dir, file_info['filename'])
                        if os.path.exists(file_path):
                            zipf.write(file_path, file_info['filename'])
                
                stats['zip_path'] = zip_path
            
            # Расчет статистики
            total_time = time.time() - start_time
            stats['total_time'] = total_time
            
            success_count = stats['direct'] + stats['ocr']
            stats['success_rate'] = (success_count / stats['total']) * 100 if stats['total'] > 0 else 0
            
            return stats
            
        except Exception as e:
            st.error(f"❌ Ошибка обработки PDF: {str(e)}")
            import traceback
            st.error(f"Детали: {traceback.format_exc()}")
            return None

    def get_download_link(self, file_path, link_text):
        """Создает ссылку для скачивания файла"""
        if not file_path or not os.path.exists(file_path):
            return "❌ Файл не найден"
            
        with open(file_path, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode()
        href = f'<a href="data:application/zip;base64,{b64}" download="pdf_results.zip" style="background-color: #4CAF50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: bold;">{link_text}</a>'
        return href

def main():
    global stop_processing
    
    # Заголовок приложения
    st.markdown('<div class="main-header">📄 PDF Splitter - Ultra Rapid</div>', unsafe_allow_html=True)
    
    # Инициализация процессора
    if 'processor' not in st.session_state:
        st.session_state.processor = PDFProcessor()
    
    # Боковая панель с информацией
    with st.sidebar:
        st.header("ℹ️ Информация")
        
        st.markdown("---")
        st.markdown("**Статус системы:**")
        if tesseract_available:
            st.success("✅ Tesseract OCR доступен")
            st.info("Режим: Текст + OCR")
        else:
            st.warning("⚠️ Tesseract не доступен")
            st.info("Режим: Только текст")
            
        st.markdown("---")
        if st.button("🛑 Экстренная остановка", use_container_width=True):
            stop_processing.set()
            st.warning("Обработка будет остановлена!")

    # Основная область
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📤 Загрузка PDF файла")
        uploaded_file = st.file_uploader(
            "Выберите PDF файл для обработки",
            type="pdf",
            help="Поддерживаются PDF файлы любого размера"
        )
        
        if uploaded_file is not None:
            st.success(f"✅ Файл загружен: {uploaded_file.name}")
            st.info(f"📊 Размер файла: {uploaded_file.size / 1024 / 1024:.2f} MB")
            
            col_btn1, col_btn2 = st.columns([2, 1])
            
            with col_btn1:
                process_clicked = st.button("🚀 Начать обработку", type="primary", use_container_width=True)
            
            with col_btn2:
                stop_clicked = st.button("🛑 Остановить", use_container_width=True)
            
            if stop_clicked:
                stop_processing.set()
                st.warning("Обработка остановлена!")
            
            if process_clicked:
                # Элементы интерфейса
                progress_bar = st.progress(0)
                status_text = st.empty()
                results_placeholder = st.empty()
                
                # Обработка PDF
                with st.spinner("🔄 Обработка PDF..."):
                    stats = st.session_state.processor.process_pdf_optimized(
                        uploaded_file, 
                        progress_bar, 
                        status_text
                    )
                
                if stats:
                    # Детальный отчет
                    with results_placeholder.container():
                        st.markdown("---")
                        st.subheader("📊 Детальный отчет")
                        
                        # Основные метрики
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Всего страниц", stats['total'])
                        with col2:
                            st.metric("Найдено текстом", stats['direct'])
                        with col3:
                            st.metric("Найдено OCR", stats['ocr'])
                        with col4:
                            st.metric("Не найдено", stats['failed'])
                        
                        # Дополнительная статистика
                        col_time, col_rate, col_stopped = st.columns(3)
                        with col_time:
                            st.metric("Общее время", f"{stats['total_time']:.1f}с")
                        with col_rate:
                            st.metric("Успешность", f"{stats['success_rate']:.1f}%")
                        with col_stopped:
                            if stats['stopped'] > 0:
                                st.metric("Остановлено", stats['stopped'])
                        
                        if stats['stopped'] > 0:
                            st.warning(f"⏹️ Обработка была остановлена! {stats['stopped']} страниц не обработано.")
                        
                        # Скачивание результатов
                        if stats.get('zip_path'):
                            st.markdown("---")
                            st.subheader("📥 Скачать результаты")
                            download_link = st.session_state.processor.get_download_link(
                                stats['zip_path'], 
                                "⬇️ Скачать ZIP архив с PDF файлами"
                            )
                            st.markdown(download_link, unsafe_allow_html=True)
                        
                        # Список файлов
                        with st.expander("📋 Показать список созданных файлов"):
                            for file_info in stats['files']:
                                method_icon = "✅" if file_info['method'] == 'direct' else "🔍" if file_info['method'] == 'ocr' else "❌"
                                st.write(f"{method_icon} Страница {file_info['page']}: `{file_info['filename']}`")
    
    with col2:
        st.subheader("⚡ Быстрый старт")
        st.markdown("""
        1. **Загрузите** PDF файл
        2. **Нажмите** кнопку обработки
        3. **Дождитесь** завершения
        4. **Скачайте** результаты
        
        **Функции:**
        - ✅ Автоматическое определение номеров
        - 🔍 Распознавание текста и изображений
        - ⏹️ Остановка в любой момент
        - 📊 Детальная статистика
        - ⚡ Высокая скорость
        """)

if __name__ == "__main__":
    main()
