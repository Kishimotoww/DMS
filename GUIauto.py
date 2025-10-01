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

# === АВТОМАТИЗАЦИЯ GUI ===
try:
    import pyautogui
    import pyperclip
    GUI_AUTOMATION_AVAILABLE = True
except ImportError:
    import subprocess
    import sys
    st.warning("🔄 Установка библиотек для автоматизации GUI...")
    
    # Устанавливаем pyautogui и pyperclip
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyautogui", "pyperclip"])
        import pyautogui
        import pyperclip
        GUI_AUTOMATION_AVAILABLE = True
        st.success("✅ Библиотеки для автоматизации установлены!")
    except:
        GUI_AUTOMATION_AVAILABLE = False
        st.error("❌ Не удалось установить библиотеки автоматизации")

# Настройка страницы
st.set_page_config(
    page_title="PDF Splitter + AutoGUI",
    page_icon="🤖", 
    layout="wide"
)

# Автоматическая установка Tesseract
@st.cache_resource
def setup_tesseract():
    """Автоматическая установка и настройка Tesseract"""
    try:
        # Пробуем найти tesseract
        result = subprocess.run(['which', 'tesseract'], capture_output=True, text=True)
        if result.returncode == 0:
            tesseract_path = result.stdout.strip()
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
            st.success(f"✅ Tesseract найден: {tesseract_path}")
            return True
    except:
        pass
    
    # Если не найден - пробуем установить
    try:
        st.info("🔄 Установка Tesseract OCR...")
        install_cmd = """
        apt-get update && \
        apt-get install -y tesseract-ocr tesseract-ocr-eng && \
        tesseract --version
        """
        result = subprocess.run(install_cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Находим путь к установленному tesseract
            which_result = subprocess.run(['which', 'tesseract'], capture_output=True, text=True)
            if which_result.returncode == 0:
                tesseract_path = which_result.stdout.strip()
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
                st.success(f"✅ Tesseract установлен: {tesseract_path}")
                return True
        else:
            st.error(f"❌ Ошибка установки Tesseract: {result.stderr}")
            return False
    except Exception as e:
        st.error(f"❌ Ошибка: {e}")
        return False
    
    return False

# Проверяем Tesseract при запуске
if 'tesseract_checked' not in st.session_state:
    st.session_state.tesseract_available = setup_tesseract()
    st.session_state.tesseract_checked = True

tesseract_available = st.session_state.tesseract_available

# Глобальная переменная для остановки
class StopProcessing:
    def __init__(self):
        self._stop = False
    
    def set(self):
        self._stop = True
    
    def is_set(self):
        return self._stop

stop_processing = StopProcessing()

# Класс для автоматизации GUI
class GUIAutomation:
    def __init__(self):
        self.is_running = False
        self.current_file = None
        self.processed_files = []
        self.failed_files = []
        
    def safety_check(self):
        """Проверка безопасности перед запуском"""
        if not GUI_AUTOMATION_AVAILABLE:
            return False, "Библиотеки автоматизации не установлены"
        
        # Предупреждение пользователю
        st.warning("""
        🚨 **ВНИМАНИЕ: АВТОМАТИЗАЦИЯ GUI** 
        
        Перед запуском убедитесь что:
        1. 💻 Приложение для ввода данных открыто на втором мониторе
        2. 🖱️ Курсор мыши находится в безопасном месте
        3. ⏸️ Вы готовы остановить процесс в любой момент
        
        Автоматизация начнется через 5 секунд после запуска!
        """)
        return True, "Готов к запуску"
    
    def countdown(self, seconds=5):
        """Обратный отсчет перед началом"""
        countdown_placeholder = st.empty()
        for i in range(seconds, 0, -1):
            countdown_placeholder.warning(f"🕐 Автоматизация начнется через {i} секунд...")
            time.sleep(1)
        countdown_placeholder.empty()
    
    def copy_to_clipboard(self, text):
        """Копирование текста в буфер обмена"""
        try:
            pyperclip.copy(text)
            return True
        except Exception as e:
            st.error(f"❌ Ошибка копирования: {e}")
            return False
    
    def perform_click_sequence(self, file_number, total_files, order_number):
        """Выполнение последовательности кликов и ввода"""
        try:
            # Пауза между действиями (настраивается)
            click_delay = st.session_state.get('click_delay', 1.0)
            
            # 1. Копируем номер в буфер обмена
            if not self.copy_to_clipboard(order_number):
                return False
            
            time.sleep(0.5)
            
            # 2. Клик в поле ввода (координаты настраиваются)
            input_x = st.session_state.get('input_field_x', 500)
            input_y = st.session_state.get('input_field_y', 300)
            
            pyautogui.click(input_x, input_y)
            time.sleep(0.2)
            
            # 3. Вставляем текст (Ctrl+V)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            
            # 4. Дополнительные клики (настраиваются)
            additional_clicks = st.session_state.get('additional_clicks', [])
            for click_pos in additional_clicks:
                pyautogui.click(click_pos['x'], click_pos['y'])
                time.sleep(click_delay)
            
            # 5. Enter для подтверждения (опционально)
            if st.session_state.get('press_enter', True):
                pyautogui.press('enter')
                time.sleep(0.5)
            
            st.success(f"✅ Обработан файл {file_number}/{total_files}: {order_number}")
            return True
            
        except Exception as e:
            st.error(f"❌ Ошибка автоматизации для {order_number}: {e}")
            return False
    
    def automate_processing(self, file_list, output_dir):
        """Основная функция автоматизации"""
        if not self.safety_check()[0]:
            return False
        
        self.countdown(5)
        
        self.is_running = True
        self.processed_files = []
        self.failed_files = []
        
        total_files = len(file_list)
        
        # Создаем прогресс бар для автоматизации
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, filename in enumerate(file_list):
            if not self.is_running:
                break
                
            # Извлекаем номер из имени файла
            order_number = os.path.splitext(filename)[0]
            
            status_text.text(f"🤖 Автоматизация: {i+1}/{total_files} - {order_number}")
            
            # Выполняем последовательность действий
            success = self.perform_click_sequence(i+1, total_files, order_number)
            
            if success:
                self.processed_files.append({
                    'filename': filename,
                    'order_number': order_number,
                    'timestamp': time.time()
                })
            else:
                self.failed_files.append({
                    'filename': filename, 
                    'order_number': order_number,
                    'timestamp': time.time()
                })
            
            # Обновляем прогресс
            progress = (i + 1) / total_files
            progress_bar.progress(progress)
            
            # Пауза между файлами
            time.sleep(st.session_state.get('file_delay', 2.0))
        
        progress_bar.empty()
        status_text.empty()
        
        # Отчет
        st.success(f"✅ Автоматизация завершена! Обработано: {len(self.processed_files)}/{total_files}")
        if self.failed_files:
            st.error(f"❌ Не удалось обработать: {len(self.failed_files)} файлов")
        
        return True
    
    def stop_automation(self):
        """Остановка автоматизации"""
        self.is_running = False
        st.warning("⏹️ Автоматизация остановлена")

# Инициализация автоматизации
if 'automation' not in st.session_state:
    st.session_state.automation = GUIAutomation()

# CSS стили
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .automation-section {
        background-color: #f0f8ff;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #4ECDC4;
        margin: 10px 0;
    }
    .coordinate-input {
        background-color: #fff3cd;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
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
                'total_time': 0,
                'output_dir': output_dir  # Добавляем путь к выходной папке
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
    st.markdown('<div class="main-header">📄 PDF Splitter + AutoGUI 🤖</div>', unsafe_allow_html=True)
    
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
        else:
            st.warning("⚠️ Tesseract не доступен")
            
        st.markdown(f"**GUI Автоматизация:** {'✅ Доступна' if GUI_AUTOMATION_AVAILABLE else '❌ Не доступна'}")
            
        st.markdown("---")
        if st.button("🛑 Экстренная остановка", use_container_width=True):
            stop_processing.set()
            st.session_state.automation.stop_automation()
            st.warning("Все процессы остановлены!")

    # Основная область - две вкладки
    tab1, tab2 = st.tabs(["📄 Обработка PDF", "🤖 Автоматизация GUI"])
    
    with tab1:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📤 Загрузка PDF файла")
            uploaded_file = st.file_uploader(
                "Выберите PDF файл для обработки",
                type="pdf",
                help="Поддерживаются PDF файлы любого размера",
                key="pdf_uploader"
            )
            
            if uploaded_file is not None:
                st.success(f"✅ Файл загружен: {uploaded_file.name}")
                st.info(f"📊 Размер файла: {uploaded_file.size / 1024 / 1024:.2f} MB")
                
                col_btn1, col_btn2 = st.columns([2, 1])
                
                with col_btn1:
                    process_clicked = st.button("🚀 Начать обработку", type="primary", use_container_width=True, key="process_btn")
                
                with col_btn2:
                    stop_clicked = st.button("🛑 Остановить", use_container_width=True, key="stop_btn")
                
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
                        # Сохраняем статистику для автоматизации
                        st.session_state.last_processed_stats = stats
                        
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
    
    with tab2:
        st.markdown('<div class="automation-section">', unsafe_allow_html=True)
        st.subheader("🤖 Автоматизация GUI")
        
        if not GUI_AUTOMATION_AVAILABLE:
            st.error("""
            ❌ Библиотеки автоматизации не установлены!
            
            Установите зависимости:
            ```bash
            pip install pyautogui pyperclip
            ```
            """)
        else:
            # Настройки автоматизации
            st.markdown("### ⚙️ Настройки автоматизации")
            
            col_set1, col_set2 = st.columns(2)
            
            with col_set1:
                st.markdown('<div class="coordinate-input">', unsafe_allow_html=True)
                st.number_input("X координата поля ввода", 
                              min_value=0, max_value=5000, value=500, key='input_field_x')
                st.number_input("Y координата поля ввода", 
                              min_value=0, max_value=5000, value=300, key='input_field_y')
                st.markdown('</div>', unsafe_allow_html=True)
                
            with col_set2:
                st.number_input("Задержка между кликами (сек)", 
                              min_value=0.1, max_value=5.0, value=1.0, key='click_delay')
                st.number_input("Задержка между файлами (сек)", 
                              min_value=0.5, max_value=10.0, value=2.0, key='file_delay')
                st.checkbox("Нажимать Enter после ввода", value=True, key='press_enter')
            
            # Запуск автоматизации
            st.markdown("### 🚀 Запуск автоматизации")
            
            if 'last_processed_stats' in st.session_state:
                stats = st.session_state.last_processed_stats
                file_list = [f['filename'] for f in stats['files'] if f['order_no']]
                output_dir = stats.get('output_dir', '')
                
                if file_list:
                    st.success(f"✅ Найдено {len(file_list)} файлов для автоматизации")
                    
                    col_auto1, col_auto2 = st.columns([3, 1])
                    
                    with col_auto1:
                        if st.button("🤖 ЗАПУСТИТЬ АВТОМАТИЗАЦИЮ", type="primary", use_container_width=True):
                            success = st.session_state.automation.automate_processing(file_list, output_dir)
                            
                    with col_auto2:
                        if st.button("⏹️ ОСТАНОВИТЬ", use_container_width=True):
                            st.session_state.automation.stop_automation()
                    
                    # Показать список файлов для автоматизации
                    with st.expander("📋 Файлы для автоматической обработки"):
                        for i, filename in enumerate(file_list):
                            st.write(f"{i+1}. {filename}")
                else:
                    st.warning("⚠️ Нет файлов с номерами для автоматизации")
            else:
                st.info("📝 Сначала обработайте PDF файл во вкладке 'Обработка PDF'")
        
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
