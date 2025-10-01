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
    page_title="PDF Auto Learner + Executor", 
    page_icon="🎓",
    layout="wide"
)

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
class ActionLearner:
    def __init__(self):
        self.learning_mode = False
        self.recorded_actions = []
        self.current_scenario = None
        self.scenarios_file = "saved_scenarios.json"
        self.is_executing = False
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
    
    def start_learning(self, scenario_name):
        """Начало записи сценария"""
        self.learning_mode = True
        self.recorded_actions = []
        self.current_scenario = scenario_name
        st.session_state.learning_active = True
        return True
    
    def stop_learning(self):
        """Остановка записи сценария"""
        self.learning_mode = False
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
        
        try:
            import pyautogui
            import pyperclip
        except ImportError:
            return False, "Установите pyautogui и pyperclip для автоматизации"
        
        self.is_executing = True
        successful_actions = 0
        total_actions = len(self.scenarios[scenario_name]['actions'])
        
        # Копируем номер в буфер обмена
        pyperclip.copy(order_number)
        
        for i, action in enumerate(self.scenarios[scenario_name]['actions']):
            if not self.is_executing:
                break
                
            try:
                action_type = action['type']
                
                if action_type == 'click':
                    pyautogui.click(action['x'], action['y'])
                    successful_actions += 1
                    
                elif action_type == 'type':
                    # Заменяем {ORDER_NUMBER} на реальный номер
                    text = action['text'].replace('{ORDER_NUMBER}', order_number)
                    pyautogui.write(text)
                    successful_actions += 1
                    
                elif action_type == 'paste':
                    pyautogui.hotkey('ctrl', 'v')
                    successful_actions += 1
                    
                elif action_type == 'enter':
                    pyautogui.press('enter')
                    successful_actions += 1
                    
                elif action_type == 'wait':
                    time.sleep(action['seconds'])
                    successful_actions += 1
                
                elif action_type == 'keypress':
                    pyautogui.press(action['key'])
                    successful_actions += 1
                
                # Обновляем прогресс
                if progress_callback:
                    progress_callback(i + 1, total_actions, f"Действие {i+1}/{total_actions}")
                
                # Задержка между действиями
                time.sleep(0.5)
                
            except Exception as e:
                return False, f"Ошибка в действии {i+1}: {str(e)}"
        
        self.is_executing = False
        return True, f"Успешно выполнено {successful_actions}/{total_actions} действий"
    
    def stop_execution(self):
        """Остановка выполнения"""
        self.is_executing = False

# Класс обработки PDF
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
        
        # Сохраняем временный файл
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
                
                # Извлекаем текст
                text = self.extract_text_comprehensive(page)
                order_no = self.find_order_numbers(text)
                
                # OCR если не нашли
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
                
                # Создаем отдельный PDF
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                
                filename = f"{order_no}.pdf" if order_no else f"page_{page_num + 1}.pdf"
                output_path = os.path.join(results['output_dir'], filename)
                
                # Избегаем дубликатов
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
                
                # Обновляем прогресс
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
    st.session_state.learner = ActionLearner()

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
    .file-card-warning {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
    }
</style>
""", unsafe_allow_html=True)

def main():
    st.markdown('<div class="main-header">🎓 PDF Auto Learner + Executor</div>', unsafe_allow_html=True)
    
    # Проверка библиотек автоматизации
    try:
        import pyautogui
        import pyperclip
        automation_available = True
    except ImportError:
        automation_available = False
        st.error("""
        ❌ Библиотеки автоматизации не установлены!
        
        Для работы установите:
        ```bash
        pip install pyautogui pyperclip
        ```
        """)
    
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
                        
                        # Показываем файлы для ручной проверки
                        st.markdown("---")
                        st.subheader("🔍 Ручная проверка номеров")
                        st.info("Проверьте правильность распознанных номеров перед автозапуском")
                        
                        for file_info in results['files']:
                            if file_info['order_number']:
                                col_a, col_b, col_c = st.columns([3, 1, 1])
                                with col_a:
                                    st.markdown(f'<div class="file-card">', unsafe_allow_html=True)
                                    st.write(f"**{file_info['filename']}**")
                                    st.write(f"Страница: {file_info['page_number']}")
                                    st.markdown('</div>', unsafe_allow_html=True)
                                with col_b:
                                    st.text_input("Номер", value=file_info['order_number'], key=f"num_{file_info['filename']}", label_visibility="collapsed")
                                with col_c:
                                    if st.button("✅", key=f"ok_{file_info['filename']}"):
                                        st.success(f"Подтвержден: {file_info['order_number']}")
    
    with tab2:
        st.subheader("🎓 Обучение сценарию")
        
        if not automation_available:
            st.warning("Установите библиотеки автоматизации для работы этого раздела")
        else:
            col_learn1, col_learn2 = st.columns(2)
            
            with col_learn1:
                scenario_name = st.text_input("Название сценария", value="Мой_сценарий")
                description = st.text_area("Описание сценария", placeholder="Что делает этот сценарий?")
            
            with col_learn2:
                st.info("""
                **Инструкция по обучению:**
                1. Введите название сценария
                2. Нажмите "Начать обучение"  
                3. Перейдите на второй монитор в браузер
                4. Выполните нужные действия
                5. Вернитесь и нажмите "Завершить обучение"
                """)
            
            col_start, col_stop, col_info = st.columns([1, 1, 2])
            
            with col_start:
                if st.button("🎬 Начать обучение", type="primary", use_container_width=True) and scenario_name:
                    if st.session_state.learner.start_learning(scenario_name):
                        st.session_state.learning_active = True
                        st.success("🎥 Запись начата! Выполните действия в браузере...")
            
            with col_stop:
                if st.button("⏹️ Завершить обучение", type="secondary", use_container_width=True):
                    st.session_state.learner.stop_learning()
                    st.session_state.learning_active = False
            
            if st.session_state.learning_active:
                st.markdown('<div class="learning-mode">🎥 ИДЕТ ЗАПИСЬ ДЕЙСТВИЙ... Выполняйте действия в браузере</div>', unsafe_allow_html=True)
                
                # Кнопки для записи действий
                st.markdown("### Быстрые действия для записи:")
                col_act1, col_act2, col_act3, col_act4 = st.columns(4)
                
                with col_act1:
                    if st.button("📋 Записать вставку", use_container_width=True):
                        st.session_state.learner.add_action('paste', description="Вставка номера")
                        st.success("✅ Записано: Вставка номера")
                
                with col_act2:
                    if st.button("↵ Записать Enter", use_container_width=True):
                        st.session_state.learner.add_action('enter', description="Нажатие Enter")
                        st.success("✅ Записано: Нажатие Enter")
                
                with col_act3:
                    wait_seconds = st.number_input("Секунды ожидания", min_value=1, max_value=10, value=2)
                    if st.button("⏱️ Записать ожидание", use_container_width=True):
                        st.session_state.learner.add_action('wait', seconds=wait_seconds, description=f"Ожидание {wait_seconds}сек")
                        st.success(f"✅ Записано: Ожидание {wait_seconds}сек")
                
                with col_act4:
                    key_to_press = st.selectbox("Клавиша", ["tab", "space", "escape"])
                    if st.button("⌨️ Записать клавишу", use_container_width=True):
                        st.session_state.learner.add_action('keypress', key=key_to_press, description=f"Нажатие {key_to_press}")
                        st.success(f"✅ Записано: Нажатие {key_to_press}")
            
            # Показать сохраненные сценарии
            if st.session_state.learner.scenarios:
                st.markdown("---")
                st.subheader("💾 Сохраненные сценарии")
                
                for name, scenario in st.session_state.learner.scenarios.items():
                    with st.expander(f"📁 {name} ({scenario['total_actions']} действий)"):
                        st.write(f"Создан: {datetime.fromisoformat(scenario['created']).strftime('%d.%m.%Y %H:%M')}")
                        for i, action in enumerate(scenario['actions'], 1):
                            st.write(f"{i}. {action.get('description', 'Действие')}")
    
    with tab3:
        st.subheader("🚀 Автоматический запуск")
        
        if not automation_available:
            st.warning("Установите библиотеки автоматизации")
        elif not st.session_state.processed_results:
            st.info("📝 Сначала обработайте PDF файл во вкладке 'Обработка PDF'")
        elif not st.session_state.learner.scenarios:
            st.info("🎓 Сначала создайте сценарий во вкладке 'Обучение'")
        else:
            # Выбор сценария
            scenario_names = list(st.session_state.learner.scenarios.keys())
            selected_scenario = st.selectbox("Выберите сценарий", scenario_names)
            
            if selected_scenario:
                scenario = st.session_state.learner.scenarios[selected_scenario]
                st.info(f"📋 Сценарий '{selected_scenario}': {scenario['total_actions']} действий")
                
                # Файлы для обработки
                files_to_process = [f for f in st.session_state.processed_results['files'] if f['order_number']]
                
                if files_to_process:
                    st.success(f"✅ Готово к обработке: {len(files_to_process)} файлов")
                    
                    # Предпросмотр файлов
                    with st.expander("📋 Файлы для обработки"):
                        for file_info in files_to_process:
                            st.write(f"• {file_info['filename']}")
                    
                    # Запуск автоматизации
                    col_exec1, col_exec2 = st.columns([2, 1])
                    
                    with col_exec1:
                        if st.button("🚀 ЗАПУСТИТЬ АВТОМАТИЗАЦИЮ", type="primary", use_container_width=True):
                            st.warning("🔄 Автоматизация начнется через 5 секунд...")
                            time.sleep(5)
                            
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            results_placeholder = st.empty()
                            
                            successful = 0
                            failed = 0
                            
                            for i, file_info in enumerate(files_to_process):
                                if not st.session_state.learner.is_executing:
                                    break
                                
                                order_number = file_info['order_number']
                                status_text.text(f"🤖 Обработка {i+1}/{len(files_to_process)}: {order_number}")
                                
                                success, message = st.session_state.learner.execute_scenario(
                                    selected_scenario, 
                                    order_number,
                                    progress_callback=lambda curr, total, msg: status_text.text(f"{msg} - {order_number}")
                                )
                                
                                if success:
                                    successful += 1
                                    st.success(f"✅ {order_number} - {message}")
                                else:
                                    failed += 1
                                    st.error(f"❌ {order_number} - {message}")
                                
                                # Обновляем прогресс
                                progress = (i + 1) / len(files_to_process)
                                progress_bar.progress(progress)
                                
                                # Пауза между файлами
                                time.sleep(2)
                            
                            progress_bar.empty()
                            status_text.empty()
                            
                            st.success(f"🎉 Автоматизация завершена! Успешно: {successful}, Ошибок: {failed}")
                    
                    with col_exec2:
                        if st.button("⏹️ ОСТАНОВИТЬ", type="secondary", use_container_width=True):
                            st.session_state.learner.stop_execution()
                            st.warning("Автоматизация остановлена")

if __name__ == "__main__":
    main()
