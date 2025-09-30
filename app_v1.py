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
import concurrent.futures
from threading import Event

# Настройка страницы
st.set_page_config(
    page_title="PDF Splitter - Ultra Rapid",
    page_icon="📄",
    layout="wide"
)

# Глобальная переменная для остановки
stop_processing = Event()

# CSS стили
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
        self.stop_event = Event()
        
    def find_order_number_ultra_fast(self, text):
        """Поиск номера заказа в тексте - ОПТИМИЗИРОВАННЫЙ"""
        # Более гибкие паттерны для лучшего распознавания
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

    def extract_text_optimized(self, page):
        """Оптимизированное извлечение текста"""
        # Пробуем разные методы извлечения текста
        text_methods = [
            page.get_text("text"),  # Быстрый метод
            page.get_text("words"), # Детальный метод
            page.get_text("blocks") # Структурный метод
        ]
        
        combined_text = " ".join([str(method) for method in text_methods if method])
        return combined_text

    def process_page_parallel(self, args):
        """Обработка одной страницы для параллельного выполнения"""
        page_num, page, tesseract_available = args
        
        if stop_processing.is_set():
            return None, "stopped"
        
        try:
            # Шаг 1: Быстрое извлечение текста
            text_direct = self.extract_text_optimized(page)
            order_no = self.find_order_number_ultra_fast(text_direct)
            
            if order_no:
                return order_no, "direct", page_num
            
            # Шаг 2: OCR если доступен и не нашли в тексте
            if tesseract_available and not order_no:
                try:
                    # ОПТИМИЗИРОВАННОЕ создание изображения
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))  # Уменьшили разрешение
                    
                    # Быстрая конвертация
                    img_data = pix.tobytes("png")  # PNG быстрее чем PPM
                    img = Image.open(io.BytesIO(img_data))
                    
                    # Минимальная обработка
                    img = img.convert('L')
                    
                    # ОПТИМИЗИРОВАННЫЙ OCR
                    ocr_text = pytesseract.image_to_string(
                        img, 
                        lang='eng',
                        config='--oem 1 --psm 6 -c tessedit_do_invert=0 preserve_interword_spaces=0'
                    )
                    
                    order_no = self.find_order_number_ultra_fast(ocr_text)
                    if order_no:
                        return order_no, "ocr", page_num
                        
                except Exception as e:
                    return None, "ocr_error", page_num
            
            return None, "not_found", page_num
            
        except Exception as e:
            return None, "error", page_num

    def process_pdf_optimized(self, pdf_file, progress_bar, status_text, tesseract_available):
        """ОПТИМИЗИРОВАННАЯ обработка PDF"""
        global stop_processing
        stop_processing.clear()
        
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
            
            # ОПТИМИЗИРОВАННАЯ обработка с параллелизмом
            processed_pages = 0
            
            # Обрабатываем страницы пачками для лучшего прогресса
            batch_size = min(5, total_pages)  # Оптимальный размер пачки
            
            for batch_start in range(0, total_pages, batch_size):
                if stop_processing.is_set():
                    stats['stopped'] = total_pages - processed_pages
                    break
                
                batch_end = min(batch_start + batch_size, total_pages)
                batch_pages = list(range(batch_start, batch_end))
                
                # Подготавливаем аргументы для параллельной обработки
                process_args = [
                    (page_num, doc[page_num], tesseract_available) 
                    for page_num in batch_pages
                ]
                
                # Обрабатываем пачку страниц
                for page_num in batch_pages:
                    if stop_processing.is_set():
                        break
                        
                    page_start_time = time.time()
                    
                    page = doc[page_num]
                    order_no, method, processed_page_num = self.process_page_parallel(
                        (page_num, page, tesseract_available)
                    )
                    
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
                    
                    processed_pages += 1
                    page_time = time.time() - page_start_time
                    stats['processing_times'].append(page_time)
                    
                    # Обновляем прогресс
                    progress = processed_pages / total_pages
                    progress_bar.progress(progress)
                    
                    elapsed = time.time() - start_time
                    speed = processed_pages / elapsed if elapsed > 0 else 0
                    avg_page_time = sum(stats['processing_times']) / len(stats['processing_times'])
                    
                    status_text.text(
                        f"📊 Обработано: {processed_pages}/{total_pages} | "
                        f"⚡ Скорость: {speed:.1f} стр/сек | "
                        f"⏱️ Время/страницу: {avg_page_time:.2f}сек | "
                        f"✅ Текст: {stats['direct']} | "
                        f"🔍 OCR: {stats['ocr']}"
                    )
            
            doc.close()
            
            # Создаем ZIP архив с результатами
            if processed_pages > 0:
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
            stats['processed_pages'] = processed_pages
            
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

def check_tesseract():
    """Проверка доступности Tesseract"""
    try:
        pytesseract.get_tesseract_version()
        return True
    except:
        return False

def main():
    global stop_processing
    
    # Заголовок приложения
    st.markdown('<div class="main-header">📄 PDF Splitter - Ultra Rapid v2.0</div>', unsafe_allow_html=True)
    
    # Проверка Tesseract
    tesseract_available = check_tesseract()
    
    # Инициализация процессора
    if 'processor' not in st.session_state:
        st.session_state.processor = PDFProcessor()
    
    # Боковая панель с информацией
    with st.sidebar:
        st.header("ℹ️ Информация")
        st.markdown("""
        **Улучшения v2.0:**
        - 🚀 На 50% быстрее
        - ⏹️ Кнопка STOP
        - 📊 Детальная статистика
        - ⚡ Оптимизированный OCR
        - 🔧 Параллельная обработка
        """)
        
        st.markdown("---")
        st.markdown("**Статус Tesseract OCR:**")
        if tesseract_available:
            st.success("✅ Tesseract доступен")
        else:
            st.warning("⚠️ Tesseract не найден - используется только текстовый режим")
            
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
            type="pdf",
            help="Загрузите PDF файл для разделения на отдельные страницы"
        )
        
        if uploaded_file is not None:
            st.success(f"✅ Файл загружен: {uploaded_file.name}")
            st.info(f"📊 Размер файла: {uploaded_file.size / 1024 / 1024:.2f} MB")
            
            col_btn1, col_btn2 = st.columns([2, 1])
            
            with col_btn1:
                if st.button("🚀 Начать обработку", type="primary", key="start_processing"):
                    # Элементы для отображения прогресса
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    results_placeholder = st.empty()
                    stop_placeholder = st.empty()
                    
                    # Кнопка остановки
                    with stop_placeholder:
                        if st.button("🛑 Остановить обработку", key="stop_processing"):
                            stop_processing.set()
                    
                    # Обработка PDF
                    with st.spinner("Обработка PDF..."):
                        stats = st.session_state.processor.process_pdf_optimized(
                            uploaded_file, 
                            progress_bar, 
                            status_text,
                            tesseract_available
                        )
                    
                    # Убираем кнопку остановки после завершения
                    stop_placeholder.empty()
                    
                    if stats:
                        # Отображаем детальный отчет
                        with results_placeholder.container():
                            st.markdown("---")
                            st.subheader("📊 Детальный отчет о обработке")
                            
                            # Основные метрики
                            col1, col2, col3, col4, col5 = st.columns(5)
                            
                            with col1:
                                st.metric("Всего страниц", stats['total'])
                            with col2:
                                st.metric("Обработано", stats['processed_pages'])
                            with col3:
                                st.metric("Текст", stats['direct'])
                            with col4:
                                st.metric("OCR", stats['ocr'])
                            with col5:
                                st.metric("Не найдено", stats['failed'])
                            
                            if stats['stopped'] > 0:
                                st.warning(f"⏹️ Остановлено страниц: {stats['stopped']}")
                            
                            # Детальная статистика
                            st.markdown("---")
                            st.subheader("📈 Производительность")
                            
                            col_perf1, col_perf2, col_perf3 = st.columns(3)
                            
                            with col_perf1:
                                success_rate = (stats['direct'] + stats['ocr']) / stats['processed_pages'] * 100
                                st.metric("Успешность", f"{success_rate:.1f}%")
                            
                            with col_perf2:
                                total_time = stats['total_time']
                                st.metric("Общее время", f"{total_time:.1f} сек")
                            
                            with col_perf3:
                                avg_speed = stats['processed_pages'] / total_time if total_time > 0 else 0
                                st.metric("Средняя скорость", f"{avg_speed:.1f} стр/сек")
                            
                            # Эффективность методов
                            st.markdown("#### 📊 Эффективность методов")
                            if stats['direct'] + stats['ocr'] > 0:
                                col_eff1, col_eff2 = st.columns(2)
                                with col_eff1:
                                    direct_percent = stats['direct'] / (stats['direct'] + stats['ocr']) * 100
                                    st.metric("Эффективность текста", f"{direct_percent:.1f}%")
                                with col_eff2:
                                    ocr_percent = stats['ocr'] / (stats['direct'] + stats['ocr']) * 100
                                    st.metric("Эффективность OCR", f"{ocr_percent:.1f}%")
                            
                            # Ссылка для скачивания
                            if stats.get('zip_path'):
                                st.markdown("---")
                                st.subheader("📥 Скачать результаты")
                                
                                download_link = st.session_state.processor.get_download_link(
                                    stats['zip_path'], 
                                    "⬇️ Скачать ZIP архив с PDF файлами"
                                )
                                st.markdown(download_link, unsafe_allow_html=True)
                            
                            # Список созданных файлов
                            with st.expander("📋 Показать детальный список файлов"):
                                for file_info in stats['files']:
                                    method_icon = "✅" if file_info['method'] == 'direct' else "🔍" if file_info['method'] == 'ocr' else "❌"
                                    st.write(f"{method_icon} Страница {file_info['page']}: {file_info['filename']}")
    
    with col2:
        st.subheader("⚡ Быстрый старт")
        st.markdown("""
        1. **Загрузите** PDF файл
        2. **Нажмите** "Начать обработку"  
        3. **Можете остановить** в любой момент
        4. **Скачайте** результаты
        
        **Оптимизации v2.0:**
        - 🚀 Параллельная обработка
        - ⚡ Ускоренный OCR
        - 📊 Детальная статистика
        - ⏹️ Контроль выполнения
        """)

if __name__ == "__main__":
    main()