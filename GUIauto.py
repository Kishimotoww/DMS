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
import json
from datetime import datetime
import pandas as pd

# Настройка страницы
st.set_page_config(
    page_title="PDF Auto Learner + Web Executor", 
    page_icon="🎓",
    layout="wide"
)

# Веб-автоматизация через Selenium
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    WEB_AUTOMATION_AVAILABLE = True
except ImportError:
    WEB_AUTOMATION_AVAILABLE = False
    st.warning("🌐 Для веб-автоматизации установите: pip install selenium webdriver-manager")

# Автоматическая установка Tesseract
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
    
    try:
        install_cmd = "apt-get update && apt-get install -y tesseract-ocr tesseract-ocr-eng"
        result = subprocess.run(install_cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            return True
    except:
        pass
    
    return False

# Инициализация
if 'tesseract_checked' not in st.session_state:
    st.session_state.tesseract_available = setup_tesseract()
    st.session_state.tesseract_checked = True

tesseract_available = st.session_state.tesseract_available

# Класс системы обучения и выполнения
class WebActionLearner:
    def __init__(self):
        self.learning_mode = False
        self.recorded_actions = []
        self.current_scenario = None
        self.scenarios_file = "saved_scenarios.json"
        self.is_executing = False
        self.driver = None
        self.load_scenarios()
    
    def load_scenarios(self):
        """Загрузка сохраненных сценариев"""
        try:
            if os.path.exists(self.scenarios_file):
                with open(self.scenarios_file, 'r', encoding='utf-8') as f:
                    self.scenarios = json.load(f)
            else:
                self.scenarios = {}
        except:
            self.scenarios = {}
    
    def save_scenarios(self):
        """Сохранение сценариев"""
        try:
            with open(self.scenarios_file, 'w', encoding='utf-8') as f:
                json.dump(self.scenarios, f, ensure_ascii=False, indent=2)
            return True
        except:
            return False
    
    def setup_driver(self):
        """Настройка веб-драйвера"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            self.driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)
            return True
        except Exception as e:
            st.error(f"❌ Ошибка настройки веб-драйвера: {e}")
            return False
    
    def start_learning(self, scenario_name, target_url):
        """Начало записи сценария"""
        if not self.setup_driver():
            return False
            
        self.learning_mode = True
        self.recorded_actions = []
        self.current_scenario = scenario_name
        
        # Первое действие - переход на целевую страницу
        self.recorded_actions.append({
            'type': 'navigate',
            'url': target_url,
            'description': f"Переход на {target_url}"
        })
        
        st.session_state.learning_active = True
        return True
    
    def stop_learning(self):
        """Остановка записи сценария"""
        self.learning_mode = False
        if self.driver:
            self.driver.quit()
            self.driver = None
            
        if self.current_scenario and self.recorded_actions:
            self.scenarios[self.current_scenario] = {
                'actions': self.recorded_actions.copy(),
                'created': datetime.now().isoformat(),
                'total_actions': len(self.recorded_actions)
            }
            self.save_scenarios()
            st.success(f"✅ Сценарий '{self.current_scenario}' сохранен! Действий: {len(self.recorded_actions)}")
        
        self.recorded_actions = []
        self.current_scenario = None
        st.session_state.learning_active = False
    
    def add_action(self, action_type, **params):
        """Добавление действия в сценарий"""
        if self.learning_mode:
            action = {
                'type': action_type,
                'timestamp': time.time(),
                **params
            }
            self.recorded_actions.append(action)
            return True
        return False
    
    def execute_scenario(self, scenario_name, order_number, progress_callback=None):
        """Выполнение сценария для одного номера"""
        if scenario_name not in self.scenarios:
            return False, "Сценарий не найден"
        
        if not self.setup_driver():
            return False, "Ошибка настройки веб-драйвера"
        
        self.is_executing = True
        successful_actions = 0
        total_actions = len(self.scenarios[scenario_name]['actions'])
        
        try:
            for i, action in enumerate(self.scenarios[scenario_name]['actions']):
                if not self.is_executing:
                    break
                    
                action_type = action['type']
                description = action.get('description', f'Действие {i+1}')
                
                if progress_callback:
                    progress_callback(i + 1, total_actions, description)
                
                if action_type == 'navigate':
                    self.driver.get(action['url'])
                    successful_actions += 1
                    
                elif action_type == 'click':
                    element = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, action['selector']))
                    )
                    element.click()
                    successful_actions += 1
                    
                elif action_type == 'type':
                    element = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, action['selector']))
                    )
                    element.clear()
                    text = action['text'].replace('{ORDER_NUMBER}', order_number)
                    element.send_keys(text)
                    successful_actions += 1
                    
                elif action_type == 'wait':
                    time.sleep(action['seconds'])
                    successful_actions += 1
                
                elif action_type == 'press_enter':
                    element = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, action['selector']))
                    )
                    element.send_keys(Keys.ENTER)
                    successful_actions += 1
                
                # Задержка между действиями
                time.sleep(1)
                
            self.driver.quit()
            self.driver = None
            self.is_executing = False
            
            return True, f"Успешно выполнено {successful_actions}/{total_actions} действий"
            
        except Exception as e:
            if self.driver:
                self.driver.quit()
                self.driver = None
            self.is_executing = False
            return False, f"Ошибка в действии {i+1}: {str(e)}"
    
    def stop_execution(self):
        """Остановка выполнения"""
        self.is_executing = False
        if self.driver:
            self.driver.quit()
            self.driver = None

# Класс обработки PDF (остается без изменений)
class PDFProcessor:
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def find_order_numbers(self, text):
        """Поиск номеров в тексте"""
        patterns = [
            r'\b(202[4-9]\d{6})\b',
            r'\b(20\d{8})\b', 
            r'\b(\d{10})\b',
            r'\b(\d{8,12})\b',
            r'\b(ORDER[:\\s]*)(\d{8,12})\b',
            r'\b(№[:\\s]*)(\d{8,12})\b',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                if isinstance(matches[0], tuple):
                    for match in matches[0]:
                        if match and match.isdigit():
                            return match
                else:
                    return matches[0]
        return None
    
    def extract_text_comprehensive(self, page):
        """Извлечение текста из страницы"""
        try:
            text_methods = []
            
            text_raw = page.get_text("text")
            if text_raw and len(text_raw.strip()) > 5:
                text_methods.append(text_raw)
            
            words = page.get_text("words")
            if words:
                text_words = " ".join([word[4] for word in words if len(word) > 4 and word[4].strip()])
                text_methods.append(text_words)
            
            return " ".join(text_methods)
        except:
            return ""
    
    def process_pdf(self, pdf_file, progress_bar, status_text):
        """Обработка PDF и извлечение номеров"""
        start_time = time.time()
        
        temp_pdf_path = os.path.join(self.temp_dir, "input.pdf")
        with open(temp_pdf_path, 'wb') as f:
            f.write(pdf_file.getvalue())
        
        try:
            doc = fitz.open(temp_pdf_path)
            total_pages = len(doc)
            
            results = {
                'total_pages': total_pages,
                'files': [],
                'processing_time': 0,
                'output_dir': os.path.join(self.temp_dir, "output")
            }
            
            os.makedirs(results['output_dir'], exist_ok=True)
            
            for page_num in range(total_pages):
                page = doc[page_num]
                
                text = self.extract_text_comprehensive(page)
                order_no = self.find_order_numbers(text)
                
                if not order_no and tesseract_available:
                    try:
                        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                        img_data = pix.tobytes("png")
                        img = Image.open(io.BytesIO(img_data))
                        img = img.convert('L')
                        
                        ocr_text = pytesseract.image_to_string(img, lang='eng')
                        order_no = self.find_order_numbers(ocr_text)
                    except:
                        pass
                
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                
                filename = f"{order_no}.pdf" if order_no else f"page_{page_num + 1}.pdf"
                output_path = os.path.join(results['output_dir'], filename)
                
                counter = 1
                base_name = os.path.splitext(filename)[0]
                while os.path.exists(output_path):
                    output_path = os.path.join(results['output_dir'], f"{base_name}_{counter}.pdf")
                    counter += 1
                
                new_doc.save(output_path)
                new_doc.close()
                
                file_info = {
                    'filename': os.path.basename(output_path),
                    'page_number': page_num + 1,
                    'order_number': order_no,
                    'file_path': output_path,
                    'status': 'has_number' if order_no else 'no_number'
                }
                
                results['files'].append(file_info)
                
                progress = (page_num + 1) / total_pages
                progress_bar.progress(progress)
                
                elapsed = time.time() - start_time
                speed = (page_num + 1) / elapsed if elapsed > 0 else 0
                
                found_count = len([f for f in results['files'] if f['order_number']])
                
                status_text.text(
                    f"📊 Обработано: {page_num + 1}/{total_pages} | "
                    f"⚡ Скорость: {speed:.1f} стр/сек | "
                    f"✅ С номерами: {found_count} | "
                    f"❌ Без номеров: {page_num + 1 - found_count}"
                )
            
            doc.close()
            results['processing_time'] = time.time() - start_time
            
            return results
            
        except Exception as e:
            st.error(f"❌ Ошибка обработки: {str(e)}")
            return None

# Инициализация
if 'processor' not in st.session_state:
    st.session_state.processor = PDFProcessor()

if 'learner' not in st.session_state:
    st.session_state.learner = WebActionLearner()

if 'processed_results' not in st.session_state:
    st.session_state.processed_results = None

if 'learning_active' not in st.session_state:
    st.session_state.learning_active = False

# CSS стили
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .learning-mode {
        background: linear-gradient(45deg, #FF6B6B, #4ECDC4);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
    }
    .file-card {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 8px;
        margin: 5px 0;
        border-left: 4px solid #28a745;
    }
</style>
""", unsafe_allow_html=True)

def main():
    st.markdown('<div class="main-header">🎓 PDF Auto Learner + Web Executor</div>', unsafe_allow_html=True)
    
    # Вкладки
    tab1, tab2, tab3 = st.tabs(["📄 Обработка PDF", "🎓 Обучение", "🚀 Автозапуск"])
    
    with tab1:
        st.subheader("Обработка PDF и извлечение номеров")
        
        uploaded_file = st.file_uploader("Загрузите PDF файл", type="pdf")
        
        if uploaded_file is not None:
            st.success(f"✅ Файл загружен: {uploaded_file.name}")
            
            if st.button("🔄 Начать обработку PDF", type="primary", use_container_width=True):
                progress_bar = st.progress(0)
                status_text = st.empty()
                results_placeholder = st.empty()
                
                with st.spinner("Обработка PDF..."):
                    results = st.session_state.processor.process_pdf(
                        uploaded_file, progress_bar, status_text
                    )
                
                if results:
                    st.session_state.processed_results = results
                    
                    with results_placeholder.container():
                        st.markdown("---")
                        st.subheader("📊 Результаты обработки")
                        
                        files_with_numbers = [f for f in results['files'] if f['order_number']]
                        files_without_numbers = [f for f in results['files'] if not f['order_number']]
                        
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Всего страниц", results['total_pages'])
                        col2.metric("С номерами", len(files_with_numbers))
                        col3.metric("Без номеров", len(files_without_numbers))
                        col4.metric("Время", f"{results['processing_time']:.1f}с")
                        
                        # Ручная проверка
                        st.markdown("---")
                        st.subheader("🔍 Ручная проверка номеров")
                        
                        for file_info in results['files']:
                            if file_info['order_number']:
                                col_a, col_b = st.columns([3, 1])
                                with col_a:
                                    st.markdown(f'<div class="file-card">', unsafe_allow_html=True)
                                    st.write(f"**{file_info['filename']}**")
                                    st.write(f"Страница: {file_info['page_number']}")
                                    st.markdown('</div>', unsafe_allow_html=True)
                                with col_b:
                                    if st.button("✅ Подтвердить", key=f"confirm_{file_info['filename']}"):
                                        st.success(f"Подтвержден: {file_info['order_number']}")
    
    with tab2:
        st.subheader("🎓 Обучение веб-сценарию")
        
        if not WEB_AUTOMATION_AVAILABLE:
            st.warning("Установите библиотеки веб-автоматизации для работы этого раздела")
        else:
            col_learn1, col_learn2 = st.columns(2)
            
            with col_learn1:
                scenario_name = st.text_input("Название сценария", value="Мой_веб_сценарий")
                target_url = st.text_input("URL целевого сайта", value="https://example.com")
                description = st.text_area("Описание сценария")
            
            with col_learn2:
                st.info("""
                **Инструкция по обучению:**
                1. Введите название и URL сайта
                2. Нажмите "Начать обучение"  
                3. Программа откроет сайт в фоновом режиме
                4. Добавляйте действия через кнопки ниже
                5. Завершите обучение когда закончите
                """)
            
            col_start, col_stop = st.columns(2)
            
            with col_start:
                if st.button("🎬 Начать обучение", type="primary", use_container_width=True) and scenario_name and target_url:
                    if st.session_state.learner.start_learning(scenario_name, target_url):
                        st.session_state.learning_active = True
                        st.success("🎥 Запись начата! Добавляйте действия ниже...")
            
            with col_stop:
                if st.button("⏹️ Завершить обучение", type="secondary", use_container_width=True):
                    st.session_state.learner.stop_learning()
                    st.session_state.learning_active = False
            
            if st.session_state.learning_active:
                st.markdown('<div class="learning-mode">🎥 ИДЕТ ЗАПИСЬ ДЕЙСТВИЙ...</div>', unsafe_allow_html=True)
                
                # Форма для добавления действий
                st.markdown("### Добавить действие:")
                
                action_type = st.selectbox("Тип действия", 
                                         ["click", "type", "wait", "press_enter"])
                
                if action_type in ["click", "type", "press_enter"]:
                    selector = st.text_input("CSS селектор", placeholder="#input-field, .button, input[name='order']")
                    desc = st.text_input("Описание действия", placeholder="Клик в поле ввода")
                
                if action_type == "type":
                    text = st.text_input("Текст для ввода", value="{ORDER_NUMBER}")
                
                if action_type == "wait":
                    seconds = st.number_input("Секунды ожидания", min_value=1, max_value=10, value=2)
                    desc = st.text_input("Описание действия", value=f"Ожидание {seconds} секунд")
                
                if st.button("➕ Добавить действие", type="primary"):
                    if action_type in ["click", "type", "press_enter"] and not selector:
                        st.error("Введите CSS селектор")
                    else:
                        action_params = {
                            'click': {'selector': selector, 'description': desc},
                            'type': {'selector': selector, 'text': text, 'description': desc},
                            'wait': {'seconds': seconds, 'description': desc},
                            'press_enter': {'selector': selector, 'description': desc}
                        }
                        
                        if st.session_state.learner.add_action(action_type, **action_params[action_type]):
                            st.success(f"✅ Добавлено: {desc}")
            
            # Сохраненные сценарии
            if st.session_state.learner.scenarios:
                st.markdown("---")
                st.subheader("💾 Сохраненные сценарии")
                
                for name, scenario in st.session_state.learner.scenarios.items():
                    with st.expander(f"📁 {name} ({scenario['total_actions']} действий)"):
                        for i, action in enumerate(scenario['actions'], 1):
                            st.write(f"{i}. {action.get('description', 'Действие')}")
    
    with tab3:
        st.subheader("🚀 Автоматический веб-запуск")
        
        if not WEB_AUTOMATION_AVAILABLE:
            st.warning("Установите библиотеки веб-автоматизации")
        elif not st.session_state.processed_results:
            st.info("📝 Сначала обработайте PDF файл во вкладке 'Обработка PDF'")
        elif not st.session_state.learner.scenarios:
            st.info("🎓 Сначала создайте сценарий во вкладке 'Обучение'")
        else:
            scenario_names = list(st.session_state.learner.scenarios.keys())
            selected_scenario = st.selectbox("Выберите сценарий", scenario_names)
            
            if selected_scenario:
                scenario = st.session_state.learner.scenarios[selected_scenario]
                st.info(f"📋 Сценарий '{selected_scenario}': {scenario['total_actions']} действий")
                
                files_to_process = [f for f in st.session_state.processed_results['files'] if f['order_number']]
                
                if files_to_process:
                    st.success(f"✅ Готово к обработке: {len(files_to_process)} файлов")
                    
                    with st.expander("📋 Файлы для обработки"):
                        for file_info in files_to_process:
                            st.write(f"• {file_info['filename']}")
                    
                    col_exec1, col_exec2 = st.columns([2, 1])
                    
                    with col_exec1:
                        if st.button("🚀 ЗАПУСТИТЬ ВЕБ-АВТОМАТИЗАЦИЮ", type="primary", use_container_width=True):
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            successful = 0
                            failed = 0
                            
                            for i, file_info in enumerate(files_to_process):
                                if not st.session_state.learner.is_executing:
                                    break
                                
                                order_number = file_info['order_number']
                                
                                def update_progress(current, total, message):
                                    status_text.text(f"{message} - {order_number} ({current}/{total} действий)")
                                
                                success, message = st.session_state.learner.execute_scenario(
                                    selected_scenario, 
                                    order_number,
                                    progress_callback=update_progress
                                )
                                
                                if success:
                                    successful += 1
                                    st.success(f"✅ {order_number} - {message}")
                                else:
                                    failed += 1
                                    st.error(f"❌ {order_number} - {message}")
                                
                                progress = (i + 1) / len(files_to_process)
                                progress_bar.progress(progress)
                                
                                time.sleep(2)
                            
                            progress_bar.empty()
                            status_text.empty()
                            
                            st.success(f"🎉 Веб-автоматизация завершена! Успешно: {successful}, Ошибок: {failed}")
                    
                    with col_exec2:
                        if st.button("⏹️ ОСТАНОВИТЬ", type="secondary", use_container_width=True):
                            st.session_state.learner.stop_execution()
                            st.warning("Автоматизация остановлена")

if __name__ == "__main__":
    main()
