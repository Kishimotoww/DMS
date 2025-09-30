import streamlit as st
import fitz
from PIL import Image
import io
import re
import tempfile
import os
import zipfile
import base64
import time

# Настройка страницы
st.set_page_config(
    page_title="PDF Splitter - Ultra Rapid",
    page_icon="📄",
    layout="wide"
)

# Глобальная переменная для остановки
class StopProcessing:
    def __init__(self):
        self._stop = False
    
    def set(self):
        self._stop = True
    
    def is_set(self):
        return self._stop

stop_processing = StopProcessing()

# Проверяем доступность Tesseract
def check_tesseract():
    try:
        import pytesseract
        # Пробуем найти tesseract в системе
        try:
            pytesseract.get_tesseract_version()
            return True, pytesseract
        except:
            # Если не нашли, пробуем установить через apt
            try:
                import subprocess
                subprocess.run(['which', 'tesseract'], check=True, capture_output=True)
                return True, pytesseract
            except:
                return False, None
    except ImportError:
        return False, None

tesseract_available, pytesseract = check_tesseract()

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
</style>
""", unsafe_allow_html=True)

class PDFProcessor:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def find_order_number_ultra_fast(self, text):
        """Поиск номера заказа в тексте - ОПТИМИЗИРОВАННЫЙ"""
        patterns = [
            r'\b(202[4-9]\d{6})\b',
            r'\b(20\d{8})\b',
            r'\b(\d{10})\b',
            r'\b(\d{8,12})\b',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                return matches[0]
        return None

    def extract_text_optimized(self, page):
        """Оптимизированное извлечение текста"""
        text_methods = [
            page.get_text("text"),
            page.get_text("words"), 
            page.get_text("blocks")
        ]
        
        combined_text = " ".join([str(method) for method in text_methods if method])
        return combined_text

    def process_page_fast(self, page_num, page):
        """Быстрая обработка одной страницы"""
        if stop_processing.is_set():
            return None, "stopped", page_num
        
        try:
            # Шаг 1: Быстрое извлечение текста
            text_direct = self.extract_text_optimized(page)
            order_no = self.find_order_number_ultra_fast(text_direct)
            
            if order_no:
                return order_no, "direct", page_num
            
            # Шаг 2: OCR если доступен
            if tesseract_available and pytesseract and not order_no:
                try:
                    # Быстрое создание изображения
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    img = img.convert('L')
                    
                    # OCR с оптимизацией
                    ocr_text = pytesseract.image_to_string(
                        img, 
                        lang='eng',
                        config='--oem 1 --psm 6'
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
                'processing_times': []
            }
            
            # Обрабатываем страницы
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
                
                stats['files'].append({
                    'filename': os.path.basename(output_path),
                    'page': page_num + 1,
                    'method': method,
                    'order_no': order_no
                })
                
                page_time = time.time() - page_start_time
                stats['processing_times'].append(page_time)
                
                # Обновляем прогресс
                progress = (page_num + 1) / total_pages
                progress_bar.progress(progress)
                
                elapsed = time.time() - start_time
                speed = (page_num + 1) / elapsed if elapsed > 0 else 0
                
                status_text.text(
                    f"📊 Обработано: {page_num + 1}/{total_pages} | "
                    f"⚡ Скорость: {speed:.1f} стр/сек | "
                    f"✅ Текст: {stats['direct']} | "
                    f"🔍 OCR: {stats['ocr']}"
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
            else:
                stats['zip_path'] = None
            
            total_time = time.time() - start_time
            stats['total_time'] = total_time
            
            return stats
            
        except Exception as e:
            st.error(f"❌ Ошибка обработки PDF: {str(e)}")
            return None

    def get_download_link(self, file_path, link_text):
        """Создает ссылку для скачивания файла"""
        if not file_path or not os.path.exists(file_path):
            return "Файл не найден"
            
        with open(file_path, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode()
        href = f'<a href="data:application/zip;base64,{b64}" download="pdf_results.zip" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">{link_text}</a>'
        return href

def main():
    global stop_processing
    
    # Заголовок приложения
    st.markdown('<div class="main-header">📄 PDF Splitter - Ultra Rapid</div>', unsafe_allow_html=True)
    
    # Инициализация процессора
    if 'processor' not in st.session_state:
        st.session_state.processor = PDFProcessor()
    
    # Боковая панель
    with st.sidebar:
        st.header("ℹ️ Информация")
        
        st.markdown("---")
        st.markdown("**Статус Tesseract OCR:**")
        if tesseract_available:
            st.success("✅ Tesseract доступен")
        else:
            st.warning("⚠️ Tesseract не найден")
            st.info("Используется только текстовый режим")
            
        st.markdown("---")
        if st.button("🛑 Экстренная остановка", key="emergency_stop"):
            stop_processing.set()
            st.warning("Обработка остановлена!")

    # Основная область
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📤 Загрузка PDF файла")
        uploaded_file = st.file_uploader(
            "Выберите PDF файл для обработки",
            type="pdf"
        )
        
        if uploaded_file is not None:
            st.success(f"✅ Файл загружен: {uploaded_file.name}")
            
            col_btn1, col_btn2 = st.columns([2, 1])
            
            with col_btn1:
                if st.button("🚀 Начать обработку", type="primary", key="start_processing"):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    results_placeholder = st.empty()
                    stop_placeholder = st.empty()
                    
                    with stop_placeholder:
                        if st.button("🛑 Остановить обработку", key="stop_processing"):
                            stop_processing.set()
                    
                    with st.spinner("Обработка PDF..."):
                        stats = st.session_state.processor.process_pdf_optimized(
                            uploaded_file, 
                            progress_bar, 
                            status_text
                        )
                    
                    stop_placeholder.empty()
                    
                    if stats:
                        with results_placeholder.container():
                            st.markdown("---")
                            st.subheader("📊 Результаты обработки")
                            
                            # Показываем результаты
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Всего страниц", stats['total'])
                            with col2:
                                st.metric("Текст", stats['direct'])
                            with col3:
                                st.metric("OCR", stats['ocr'])
                            with col4:
                                st.metric("Не найдено", stats['failed'])
                            
                            if stats['stopped'] > 0:
                                st.warning(f"⏹️ Остановлено: {stats['stopped']} страниц")
                            
                            st.metric("Общее время", f"{stats['total_time']:.1f} сек")
                            
                            # Скачивание
                            if stats.get('zip_path'):
                                st.markdown("---")
                                st.subheader("📥 Скачать результаты")
                                download_link = st.session_state.processor.get_download_link(
                                    stats['zip_path'], 
                                    "⬇️ Скачать ZIP архив"
                                )
                                st.markdown(download_link, unsafe_allow_html=True)
    
    with col2:
        st.subheader("⚡ Быстрый старт")
        st.markdown("""
        1. **Загрузите** PDF
        2. **Нажмите** обработку
        3. **Скачайте** результат
        
        **Функции:**
        - ✅ Автоопределение номеров
        - 🔍 OCR (если доступен)
        - ⏹️ Остановка процесса
        - 📊 Детальная статистика
        """)

if __name__ == "__main__":
    main()
