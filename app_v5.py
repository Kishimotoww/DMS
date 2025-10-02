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
import json
from datetime import datetime
import pandas as pd
import pyautogui
import keyboard
import threading

# Настройка страницы
st.set_page_config(
    page_title="PDF Auto Assistant - Full Automation", 
    page_icon="🤖",
    layout="wide"
)

# Автоматическая установка Tesseract
def setup_tesseract():
    try:
        import subprocess
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

# Класс для автоматического выполнения
class AutoExecutor:
    def __init__(self):
        self.workflows_file = "auto_workflows.json"
        self.load_workflows()
        self.is_running = False
        self.current_task = None
    
    def load_workflows(self):
        """Загрузка рабочих процессов"""
        try:
            if os.path.exists(self.workflows_file):
                with open(self.workflows_file, 'r', encoding='utf-8') as f:
                    self.workflows = json.load(f)
            else:
                self.workflows = {}
        except:
            self.workflows = {}
    
    def save_workflows(self):
        """Сохранение рабочих процессов"""
        try:
            with open(self.workflows_file, 'w', encoding='utf-8') as f:
                json.dump(self.workflows, f, ensure_ascii=False, indent=2)
            return True
        except:
            return False
    
    def create_workflow(self, workflow_name, steps):
        """Создание рабочего процесса"""
        self.workflows[workflow_name] = {
            'steps': steps,
            'created': datetime.now().isoformat(),
            'total_steps': len(steps)
        }
        self.save_workflows()
        return True
    
    def record_position(self, step_name):
        """Запись позиции мыши"""
        st.info(f"🔹 Наведите курсор на место для '{step_name}' и нажмите F2")
        
        def on_key_event(e):
            if e.name == 'f2':
                x, y = pyautogui.position()
                st.session_state.recorded_positions[step_name] = (x, y)
                st.success(f"✅ Позиция записана: ({x}, {y})")
                return False
            return True
        
        keyboard.on_press_key('f2', on_key_event)
        return True
    
    def execute_step(self, step, order_number):
        """Выполнение одного шага"""
        try:
            if step['type'] == 'click':
                if step['location'] in st.session_state.recorded_positions:
                    x, y = st.session_state.recorded_positions[step['location']]
                    pyautogui.click(x, y)
                    time.sleep(0.5)
                    
            elif step['type'] == 'type':
                if step['location'] in st.session_state.recorded_positions:
                    x, y = st.session_state.recorded_positions[step['location']]
                    pyautogui.click(x, y)
                    time.sleep(0.2)
                    text_to_type = step['text_to_type'].replace('{ORDER_NUMBER}', order_number)
                    pyautogui.write(text_to_type, interval=0.05)
                    time.sleep(0.5)
                    
            elif step['type'] == 'wait':
                seconds = int(step['duration'].split()[0])
                time.sleep(seconds)
                
            elif step['type'] == 'hotkey':
                keys = step['keys'].lower()
                pyautogui.hotkey(*keys.split('+'))
                time.sleep(0.5)
                
            elif step['type'] == 'focus':
                if step['location'] in st.session_state.recorded_positions:
                    x, y = st.session_state.recorded_positions[step['location']]
                    pyautogui.click(x, y)
                    time.sleep(0.5)
                    
            elif step['type'] == 'button':
                if step['location'] in st.session_state.recorded_positions:
                    x, y = st.session_state.recorded_positions[step['location']]
                    pyautogui.click(x, y)
                    time.sleep(1)
            
            return True
        except Exception as e:
            st.error(f"❌ Ошибка выполнения шага: {str(e)}")
            return False
    
    def execute_workflow(self, workflow_name, order_numbers, progress_callback=None):
        """Выполнение рабочего процесса для всех номеров"""
        if workflow_name not in self.workflows:
            return False
        
        self.is_running = True
        total_files = len(order_numbers)
        
        for i, order_number in enumerate(order_numbers):
            if not self.is_running:
                break
                
            self.current_task = f"Обработка {order_number} ({i+1}/{total_files})"
            
            if progress_callback:
                progress_callback(i, total_files, self.current_task)
            
            # Выполняем все шаги для текущего номера
            for step_num, step in enumerate(self.workflows[workflow_name]['steps']):
                if not self.is_running:
                    break
                    
                success = self.execute_step(step, order_number)
                if not success:
                    st.error(f"❌ Ошибка на шаге {step_num + 1}")
                    self.is_running = False
                    return False
                
                time.sleep(0.5)  # Небольшая пауза между шагами
            
            time.sleep(1)  # Пауза между файлами
        
        self.is_running = False
        self.current_task = None
        return True
    
    def stop_execution(self):
        """Остановка выполнения"""
        self.is_running = False

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

if 'executor' not in st.session_state:
    st.session_state.executor = AutoExecutor()

if 'processed_results' not in st.session_state:
    st.session_state.processed_results = None

if 'recorded_positions' not in st.session_state:
    st.session_state.recorded_positions = {}

# CSS стили
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .guide-box {
        background-color: #f0f8ff;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #4ECDC4;
        margin: 10px 0;
    }
    .step-box {
        background-color: #fff;
        padding: 15px;
        margin: 10px 0;
        border-radius: 8px;
        border-left: 4px solid #667eea;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .record-box {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 15px;
        margin: 10px 0;
        border-radius: 8px;
    }
    .auto-box {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 15px;
        margin: 10px 0;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

def main():
    # Инициализация session_state переменных
    if 'confirmed_files' not in st.session_state:
        st.session_state.confirmed_files = []
    if 'edited_files' not in st.session_state:
        st.session_state.edited_files = []
    if 'current_recording' not in st.session_state:
        st.session_state.current_recording = None
        
    st.markdown('<div class="main-header">🤖 PDF Auto Assistant - Full Automation</div>', unsafe_allow_html=True)
    
    # Вкладки
    tab1, tab2, tab3 = st.tabs(["📄 Обработка PDF", "🎯 Настройка авто", "🚀 Авто-выполнение"])
    
    with tab1:
        st.subheader("Обработка PDF и извлечение номеров")
        
        uploaded_file = st.file_uploader("Загрузите PDF файл", type="pdf")
        
        if uploaded_file is not None:
            st.success(f"✅ Файл загружен: {uploaded_file.name}")
            
            if st.button("🔄 Начать обработку PDF", type="primary", use_container_width=True):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                with st.spinner("Обработка PDF..."):
                    results = st.session_state.processor.process_pdf(
                        uploaded_file, progress_bar, status_text
                    )
                
                if results:
                    st.session_state.processed_results = results
                    st.session_state.confirmed_files = []
                    st.session_state.edited_files = results['files'].copy()
                    st.rerun()
        
        # Показываем результаты обработки если они есть
        if st.session_state.processed_results:
            results = st.session_state.processed_results
            
            with st.container():
                st.markdown("---")
                st.subheader("📊 Результаты обработки")
                
                files_with_numbers = [f for f in results['files'] if f['order_number']]
                files_without_numbers = [f for f in results['files'] if not f['order_number']]
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Всего страниц", results['total_pages'])
                col2.metric("С номерами", len(files_with_numbers))
                col3.metric("Без номеров", len(files_without_numbers))
                col4.metric("Время", f"{results['processing_time']:.1f}с")
                
                # Редактирование номеров
                st.markdown("---")
                st.subheader("✏️ Проверка и редактирование номеров")
                
                confirmed_files = st.session_state.get('confirmed_files', [])
                
                for i, file_info in enumerate(st.session_state.edited_files):
                    if file_info['order_number']:
                        col_a, col_b, col_c = st.columns([2, 2, 1])
                        with col_a:
                            st.write(f"**{file_info['filename']}**")
                            st.write(f"Страница: {file_info['page_number']}")
                        with col_b:
                            new_number = st.text_input(
                                "Номер заказа", 
                                value=file_info['order_number'], 
                                key=f"num_{file_info['filename']}",
                                label_visibility="visible"
                            )
                            st.session_state.edited_files[i]['order_number'] = new_number
                        with col_c:
                            is_confirmed = any(f['filename'] == file_info['filename'] for f in confirmed_files)
                            
                            if is_confirmed:
                                st.success("✓")
                            else:
                                if st.button("✅ Подтвердить", key=f"ok_{file_info['filename']}"):
                                    confirmed_files.append(st.session_state.edited_files[i])
                                    st.session_state.confirmed_files = confirmed_files
                                    st.rerun()
                
                if confirmed_files:
                    st.success(f"✅ Подтверждено файлов: {len(confirmed_files)}")
                    
                    with st.expander("📋 Показать подтвержденные файлы"):
                        for cf in confirmed_files:
                            st.write(f"- {cf['filename']}: {cf['order_number']}")
    
    with tab2:
        st.subheader("🎯 Настройка автоматического выполнения")
        
        st.info("""
        **Создайте процесс и запишите позиции элементов интерфейса.**
        Программа запомнит куда кликать и что вводить, затем выполнит всё автоматически.
        """)
        
        workflow_name = st.text_input("Название процесса", value="Авто_обработка_RDS")
        
        st.markdown("### Шаги процесса:")
        
        step_type = st.selectbox("Тип шага", 
                               ["click", "type", "wait", "hotkey", "focus", "button"])
        
        step_description = st.text_input("Описание шага", placeholder="Что нужно сделать на этом шаге?")
        
        step_params = {}
        if step_type == "click":
            step_params['action'] = "Кликнуть"
            step_params['location'] = st.text_input("Название элемента", placeholder="поле_ввода_номера")
            
        elif step_type == "type":
            step_params['action'] = "Ввести текст"
            text_to_type = st.text_input("Текст для ввода", value="{ORDER_NUMBER}")
            step_params['text_to_type'] = text_to_type
            step_params['location'] = st.text_input("Название поля", placeholder="поле_поиска")
            
        elif step_type == "wait":
            step_params['action'] = "Подождать"
            seconds = st.number_input("Секунды", min_value=1, value=2)
            step_params['duration'] = f"{seconds} секунд"
            
        elif step_type == "hotkey":
            step_params['action'] = "Нажать комбинацию клавиш"
            step_params['keys'] = st.text_input("Клавиши", value="ctrl+v", placeholder="ctrl+v, enter, tab")
            
        elif step_type == "focus":
            step_params['action'] = "Перейти в поле"
            step_params['location'] = st.text_input("Название поля", placeholder="поле_номера")
            
        elif step_type == "button":
            step_params['action'] = "Нажать кнопку"
            step_params['location'] = st.text_input("Название кнопки", placeholder="кнопка_поиска")

        # Превью шагов
        if 'workflow_steps' not in st.session_state:
            st.session_state.workflow_steps = []
        
        if st.button("➕ Добавить шаг", type="primary") and step_description:
            step = {
                'type': step_type,
                'description': step_description,
                **step_params
            }
            st.session_state.workflow_steps.append(step)
            st.success(f"✅ Добавлен шаг: {step_description}")
        
        # Показать текущие шаги
        if st.session_state.workflow_steps:
            st.markdown("### Текущий процесс:")
            for i, step in enumerate(st.session_state.workflow_steps, 1):
                st.markdown(f'<div class="step-box">', unsafe_allow_html=True)
                st.write(f"**Шаг {i}: {step['description']}**")
                st.write(f"**Действие:** {step['action']}")
                if 'location' in step:
                    st.write(f"**Элемент:** {step['location']}")
                    # Кнопка записи позиции
                    if st.button(f"🎯 Записать позицию", key=f"record_{i}"):
                        st.session_state.current_recording = step['location']
                        st.info(f"🔹 Наведите курсор на '{step['location']}' и нажмите F2")
                if 'text_to_type' in step:
                    st.write(f"**Текст:** `{step['text_to_type']}`")
                if 'duration' in step:
                    st.write(f"**Время:** {step['duration']}")
                if 'keys' in step:
                    st.write(f"**Клавиши:** {step['keys']}")
                st.markdown('</div>', unsafe_allow_html=True)
            
            # Показать записанные позиции
            if st.session_state.recorded_positions:
                st.markdown("### 📍 Записанные позиции:")
                for element, pos in st.session_state.recorded_positions.items():
                    st.write(f"**{element}:** {pos}")
            
            col_save, col_clear = st.columns(2)
            with col_save:
                if st.button("💾 Сохранить процесс", type="secondary", use_container_width=True):
                    if st.session_state.executor.create_workflow(workflow_name, st.session_state.workflow_steps):
                        st.success(f"✅ Процесс '{workflow_name}' сохранен!")
            with col_clear:
                if st.button("🗑️ Очистить шаги", type="secondary", use_container_width=True):
                    st.session_state.workflow_steps = []
                    st.session_state.recorded_positions = {}
                    st.rerun()
    
    with tab3:
        st.subheader("🚀 Автоматическое выполнение")
        
        if not st.session_state.processed_results:
            st.info("📝 Сначала обработайте PDF файл во вкладке 'Обработка PDF'")
        elif not st.session_state.executor.workflows:
            st.info("🎯 Сначала создайте процесс во вкладке 'Настройка авто'")
        else:
            confirmed_files = st.session_state.get('confirmed_files', [])
            if not confirmed_files:
                st.warning("⚠️ Подтвердите номера во вкладке 'Обработка PDF'")
            else:
                workflow_names = list(st.session_state.executor.workflows.keys())
                selected_workflow = st.selectbox("Выберите процесс", workflow_names)
                
                if selected_workflow:
                    # Проверка записанных позиций
                    workflow = st.session_state.executor.workflows[selected_workflow]
                    missing_positions = []
                    
                    for step in workflow['steps']:
                        if 'location' in step and step['location'] not in st.session_state.recorded_positions:
                            missing_positions.append(step['location'])
                    
                    if missing_positions:
                        st.error(f"❌ Не записаны позиции: {', '.join(missing_positions)}")
                        st.info("Вернитесь во вкладку 'Настройка авто' и запишите позиции для всех элементов")
                    else:
                        st.markdown(f'<div class="auto-box">', unsafe_allow_html=True)
                        st.success("✅ Все позиции записаны! Готово к автоматическому выполнению.")
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        order_numbers = [f['order_number'] for f in confirmed_files]
                        
                        st.write(f"**Файлов для обработки:** {len(order_numbers)}")
                        st.write(f"**Примерное время:** {len(order_numbers) * 10} секунд")
                        
                        # Прогресс выполнения
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        log_container = st.container()
                        
                        col_start, col_stop = st.columns(2)
                        with col_start:
                            if st.button("🚀 Начать автоматическое выполнение", type="primary", use_container_width=True):
                                def run_automation():
                                    def progress_callback(current, total, task):
                                        progress_bar.progress((current + 1) / total)
                                        status_text.text(f"🔄 {task}")
                                    
                                    success = st.session_state.executor.execute_workflow(
                                        selected_workflow, order_numbers, progress_callback
                                    )
                                    
                                    if success:
                                        status_text.text("✅ Автоматическое выполнение завершено!")
                                        st.balloons()
                                    else:
                                        status_text.text("❌ Выполнение прервано")
                                
                                # Запуск в отдельном потоке
                                thread = threading.Thread(target=run_automation)
                                thread.daemon = True
                                thread.start()
                        
                        with col_stop:
                            if st.button("⏹️ Остановить выполнение", type="secondary", use_container_width=True):
                                st.session_state.executor.stop_execution()
                                status_text.text("⏹️ Выполнение остановлено")

if __name__ == "__main__":
    main()
