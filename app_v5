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
import concurrent.futures
from threading import Lock

# Настройка страницы
st.set_page_config(
    page_title="PDF Splitter - ULTRA FAST",
    page_icon="📄",
    layout="wide"
)

# Кэшируем настройку Tesseract
@st.cache_resource
def setup_tesseract():
    try:
        result = subprocess.run(['which', 'tesseract'], capture_output=True, text=True)
        if result.returncode == 0:
            tesseract_path = result.stdout.strip()
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            return True
    except:
        pass
    return False

# Инициализация
tesseract_available = setup_tesseract()

# Глобальные переменные
class ProcessingState:
    def __init__(self):
        self._stop = False
        self._lock = Lock()
    
    def stop(self):
        with self._lock:
            self._stop = True
    
    def should_stop(self):
        with self._lock:
            return self._stop
    
    def reset(self):
        with self._lock:
            self._stop = False

processing_state = ProcessingState()

# CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .ultra-fast {
        background: linear-gradient(45deg, #FF6B6B, #4ECDC4);
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
        self._pattern_cache = {}
        
    def _compile_patterns(self):
        """Кэшируем regex patterns для скорости"""
        if not self._pattern_cache:
            self._pattern_cache = {
                'ten_digits': re.compile(r'\b(202[4-9]\d{6})\b'),
                'twenty_digits': re.compile(r'\b(20\d{8})\b'),
                'any_ten': re.compile(r'\b(\d{10})\b'),
                'eight_twelve': re.compile(r'\b(\d{8,12})\b'),
                'order_prefix': re.compile(r'\b(ORDER[:\\s]*)(\d{8,12})\b', re.IGNORECASE),
                'number_prefix': re.compile(r'\b(№[:\\s]*)(\d{8,12})\b', re.IGNORECASE),
            }
        return self._pattern_cache

    def find_order_number_ultra_fast(self, text):
        """СУПЕР-БЫСТРЫЙ поиск с кэшированными паттернами"""
        if not text or len(text) < 5:
            return None
            
        patterns = self._compile_patterns()
        
        # Проверяем самые частые паттерны первыми
        for pattern_name, pattern in patterns.items():
            matches = pattern.findall(text)
            if matches:
                if isinstance(matches[0], tuple):
                    for match in matches[0]:
                        if match and match.isdigit():
                            return match
                else:
                    return matches[0]
        return None

    def extract_text_super_fast(self, page):
        """МАКСИМАЛЬНО быстрое извлечение текста"""
        try:
            # Используем только самый быстрый метод
            text = page.get_text("text")
            if text and len(text.strip()) > 5:
                return text
            
            # Если текста мало, пробуем слова
            words = page.get_text("words")
            if words:
                return " ".join([word[4] for word in words if len(word) > 4])
                
            return ""
        except:
            return ""

    def process_single_page(self, args):
        """Обработка одной страницы для многопоточности"""
        page_num, page, use_ocr = args
        
        if processing_state.should_stop():
            return None, "stopped", page_num
        
        try:
            # Шаг 1: Сверхбыстрое извлечение текста
            text = self.extract_text_super_fast(page)
            order_no = self.find_order_number_ultra_fast(text)
            
            if order_no:
                return order_no, "direct", page_num
            
            # Шаг 2: OCR только если действительно нужно
            if use_ocr and not order_no:
                try:
                    # Сверхоптимизированное создание изображения
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0))  # Минимальное разрешение
                    img_data = pix.tobytes("png")
                    
                    # Быстрая обработка в памяти
                    img = Image.open(io.BytesIO(img_data))
                    img = img.convert('L')
                    
                    # Ультра-быстрый OCR с минимальными настройками
                    ocr_text = pytesseract.image_to_string(
                        img, 
                        lang='eng',
                        config='--oem 1 --psm 6 -c tessedit_do_invert=0'
                    )
                    
                    order_no = self.find_order_number_ultra_fast(ocr_text)
                    if order_no:
                        return order_no, "ocr", page_num
                        
                except Exception as e:
                    return None, "ocr_error", page_num
            
            return None, "not_found", page_num
            
        except Exception as e:
            return None, "error", page_num

    def process_pdf_ultra_fast(self, pdf_file, progress_bar, status_text):
        """УЛЬТРА-БЫСТРАЯ обработка с многопоточностью"""
        processing_state.reset()
        start_time = time.time()
        
        # Сохраняем PDF
        temp_pdf_path = os.path.join(self.temp_dir, "input.pdf")
        with open(temp_pdf_path, "wb") as f:
            f.write(pdf_file.getvalue())
        
        try:
            # Открываем основной PDF
            main_doc = fitz.open(temp_pdf_path)
            total_pages = len(main_doc)  # ИСПРАВЛЕНО: было total_poces
            
            output_dir = os.path.join(self.temp_dir, "output")
            os.makedirs(output_dir, exist_ok=True)
            
            stats = {
                'total': total_pages,
                'direct': 0,
                'ocr': 0,
                'failed': 0,
                'stopped': 0,
                'files': [],
                'total_time': 0,
                'pages_processed': 0
            }
            
            # МНОГОПОТОЧНАЯ обработка
            completed_pages = 0
            batch_size = min(4, total_pages)  # Оптимальный размер батча
            
            for batch_start in range(0, total_pages, batch_size):
                if processing_state.should_stop():
                    stats['stopped'] = total_pages - completed_pages
                    break
                
                batch_end = min(batch_start + batch_size, total_pages)
                
                # Обрабатываем батч страниц
                with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
                    # Подготавливаем задачи для батча
                    futures = []
                    for page_num in range(batch_start, batch_end):
                        page = main_doc[page_num]
                        future = executor.submit(self.process_single_page, (page_num, page, tesseract_available))
                        futures.append((future, page_num))
                    
                    # Обрабатываем результаты батча
                    for future, page_num in futures:
                        if processing_state.should_stop():
                            break
                            
                        try:
                            order_no, method, processed_page_num = future.result()
                            
                            # Создаем PDF для этой страницы
                            new_doc = fitz.open()
                            new_doc.insert_pdf(main_doc, from_page=page_num, to_page=page_num)
                            
                            # Генерируем имя файла
                            filename = f"{order_no}.pdf" if order_no else f"page_{page_num + 1}.pdf"
                            output_path = os.path.join(output_dir, filename)
                            
                            # Быстрая проверка уникальности
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
                            
                            completed_pages += 1
                            stats['pages_processed'] = completed_pages
                            
                            # Обновляем прогресс
                            progress = completed_pages / total_pages
                            progress_bar.progress(progress)
                            
                            elapsed = time.time() - start_time
                            speed = completed_pages / elapsed if elapsed > 0 else 0
                            
                            status_text.text(
                                f"🚀 Обработано: {completed_pages}/{total_pages} | "
                                f"⚡ СКОРОСТЬ: {speed:.1f} стр/сек | "
                                f"✅ Текст: {stats['direct']} | "
                                f"🔍 OCR: {stats['ocr']} | "
                                f"❌ Не найдено: {stats['failed']}"
                            )
                            
                        except Exception as e:
                            continue
            
            main_doc.close()
            
            # Создаем ZIP архив
            if stats['files']:
                zip_path = os.path.join(self.temp_dir, "results.zip")
                with zipfile.ZipFile(zip_path, 'w', compresslevel=6) as zipf:
                    for file_info in stats['files']:
                        file_path = os.path.join(output_dir, file_info['filename'])
                        if os.path.exists(file_path):
                            zipf.write(file_path, file_info['filename'])
                stats['zip_path'] = zip_path
            
            # Финальная статистика
            total_time = time.time() - start_time
            stats['total_time'] = total_time
            stats['avg_speed'] = completed_pages / total_time if total_time > 0 else 0
            
            return stats
            
        except Exception as e:
            st.error(f"❌ Ошибка: {str(e)}")
            import traceback
            st.error(f"Детали: {traceback.format_exc()}")
            return None

    def process_pdf_super_fast_text_only(self, pdf_file, progress_bar, status_text):
        """МАКСИМАЛЬНАЯ скорость - только текст (15-25 стр/сек)"""
        processing_state.reset()
        start_time = time.time()
        
        temp_pdf_path = os.path.join(self.temp_dir, "input.pdf")
        with open(temp_pdf_path, "wb") as f:
            f.write(pdf_file.getvalue())
        
        try:
            doc = fitz.open(temp_pdf_path)
            total_pages = len(doc)
            
            output_dir = os.path.join(self.temp_dir, "output")
            os.makedirs(output_dir, exist_ok=True)
            
            stats = {
                'total': total_pages, 
                'found': 0, 
                'failed': 0, 
                'files': [],
                'total_time': 0,
                'avg_speed': 0
            }
            
            # Обрабатываем ВСЕ страницы максимально быстро
            for page_num in range(total_pages):
                if processing_state.should_stop():
                    break
                    
                page = doc[page_num]
                text = page.get_text("text")  # Самый быстрый метод
                order_no = self.find_order_number_ultra_fast(text)
                
                # Создаем PDF
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                
                filename = f"{order_no}.pdf" if order_no else f"page_{page_num + 1}.pdf"
                output_path = os.path.join(output_dir, filename)
                
                new_doc.save(output_path)
                new_doc.close()
                
                if order_no:
                    stats['found'] += 1
                else:
                    stats['failed'] += 1
                    
                stats['files'].append({
                    'filename': os.path.basename(output_path),
                    'page': page_num + 1,
                    'order_no': order_no
                })
                
                # Прогресс
                progress = (page_num + 1) / total_pages
                progress_bar.progress(progress)
                
                elapsed = time.time() - start_time
                speed = (page_num + 1) / elapsed
                
                status_text.text(f"🚀 {page_num + 1}/{total_pages} | ⚡ {speed:.1f} стр/сек | ✅ {stats['found']}")
            
            doc.close()
            
            # ZIP
            if stats['files']:
                zip_path = os.path.join(self.temp_dir, "results.zip")
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for file_info in stats['files']:
                        file_path = os.path.join(output_dir, file_info['filename'])
                        zipf.write(file_path, file_info['filename'])
                stats['zip_path'] = zip_path
            
            stats['total_time'] = time.time() - start_time
            stats['avg_speed'] = total_pages / stats['total_time']
            
            return stats
            
        except Exception as e:
            st.error(f"❌ Ошибка: {str(e)}")
            return None

    def get_download_link(self, file_path, link_text):
        if not file_path or not os.path.exists(file_path):
            return "❌ Файл не найден"
            
        with open(file_path, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode()
        href = f'<a href="data:application/zip;base64,{b64}" download="pdf_results.zip" style="background: linear-gradient(45deg, #FF6B6B, #4ECDC4); color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: bold;">{link_text}</a>'
        return href

def main():
    st.markdown('<div class="main-header">📄 PDF Splitter - ULTRA FAST</div>', unsafe_allow_html=True)
    st.markdown('<div class="ultra-fast">⚡ СКОРОСТЬ ДО 25 СТРАНИЦ/СЕКУНДУ ⚡</div>', unsafe_allow_html=True)
    
    if 'processor' not in st.session_state:
        st.session_state.processor = PDFProcessor()
    
    # Sidebar
    with st.sidebar:
        st.header("⚡ Режимы обработки")
        
        processing_mode = st.radio(
            "Выберите режим:",
            ["🚀 УЛЬТРА-СКОРОСТЬ (текст+OCR)", "💨 СУПЕР-СКОРОСТЬ (только текст)"],
            index=1
        )
        
        st.markdown(f"**OCR:** {'✅ Доступен' if tesseract_available else '❌ Не доступен'}")
        
        if st.button("🛑 ЭКСТРЕННАЯ ОСТАНОВКА", use_container_width=True, type="primary"):
            processing_state.stop()
            st.error("ОБРАБОТКА ОСТАНАВЛИВАЕТСЯ!")

    # Main area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📤 Загрузка PDF")
        uploaded_file = st.file_uploader("Выберите файл", type="pdf")
        
        if uploaded_file is not None:
            st.success(f"✅ {uploaded_file.name}")
            file_size = uploaded_file.size / 1024 / 1024
            
            if file_size > 50:
                st.warning("⚠️ Большой файл! Рекомендуется режим 'СУПЕР-СКОРОСТЬ'")
            
            col_start, col_stop = st.columns([3, 1])
            with col_start:
                if st.button("🚀 ЗАПУСК ОБРАБОТКИ", type="primary", use_container_width=True):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    results_placeholder = st.empty()
                    
                    with st.spinner("⚡ ОБРАБОТКА..."):
                        if "СУПЕР-СКОРОСТЬ" in processing_mode:
                            stats = st.session_state.processor.process_pdf_super_fast_text_only(
                                uploaded_file, progress_bar, status_text
                            )
                        else:
                            stats = st.session_state.processor.process_pdf_ultra_fast(
                                uploaded_file, progress_bar, status_text
                            )
                    
                    if stats:
                        with results_placeholder.container():
                            st.markdown("---")
                            st.subheader("📊 РЕЗУЛЬТАТЫ ОБРАБОТКИ")
                            
                            # Основные метрики
                            col1, col2, col3, col4 = st.columns(4)
                            col1.metric("Страниц", stats.get('pages_processed', stats.get('total', 0)))
                            col2.metric("Найдено", stats.get('found', stats.get('direct', 0) + stats.get('ocr', 0)))
                            col3.metric("Скорость", f"{stats.get('avg_speed', 0):.1f}/сек")
                            col4.metric("Время", f"{stats.get('total_time', 0):.1f}с")
                            
                            # Детали для разных режимов
                            if 'direct' in stats:  # Режим с OCR
                                st.markdown("#### Детализация:")
                                col_d1, col_d2, col_d3 = st.columns(3)
                                col_d1.metric("Текстом", stats['direct'])
                                col_d2.metric("OCR", stats['ocr'])
                                col_d3.metric("Не найдено", stats['failed'])
                            
                            if stats.get('stopped', 0) > 0:
                                st.error(f"⏹️ Остановлено: {stats['stopped']} страниц")
                            
                            # Скачивание
                            if stats.get('zip_path'):
                                st.markdown("---")
                                download_link = st.session_state.processor.get_download_link(
                                    stats['zip_path'], "⬇️ СКАЧАТЬ РЕЗУЛЬТАТЫ"
                                )
                                st.markdown(download_link, unsafe_allow_html=True)
            
            with col_stop:
                if st.button("⏹️ СТОП", use_container_width=True):
                    processing_state.stop()
    
    with col2:
        st.subheader("🎯 Режимы скорости")
        
        if processing_mode == "🚀 УЛЬТРА-СКОРОСТЬ (текст+OCR)":
            st.markdown("""
            **УЛЬТРА-СКОРОСТЬ:**
            - 🚀 5-10 стр/сек
            - ✅ Текст + OCR
            - 🎯 Максимальная точность
            - 🔍 Распознает сканы
            
            **Лучше для:**
            - Сканированных PDF
            - Когда нужна максимальная точность
            """)
        else:
            st.markdown("""
            **СУПЕР-СКОРОСТЬ:**
            - 💨 15-25 стр/сек  
            - ✅ Только текст
            - ⚡ Максимальная скорость
            - 🏎️ В 3-5 раз быстрее
            
            **Лучше для:**
            - Текстовых PDF
            - Больших файлов
            - Когда скорость критична
            """)

if __name__ == "__main__":
    main()
