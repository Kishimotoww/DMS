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

# Настройка страницы
st.set_page_config(
    page_title="PDF Auto Assistant - Manual Mode", 
    page_icon="🎓",
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

# Класс для ручного помощника
class ManualAssistant:
    def __init__(self):
        self.workflows_file = "workflows.json"
        self.load_workflows()
    
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
    
    def generate_manual_guide(self, workflow_name, order_numbers):
        """Генерация руководства для ручного выполнения"""
        if workflow_name not in self.workflows:
            return None
        
        guide = {
            'workflow_name': workflow_name,
            'total_files': len(order_numbers),
            'completion_time': len(order_numbers) * 2,
            'instructions': [],
            'generated_at': datetime.now().isoformat()
        }
        
        for i, order_number in enumerate(order_numbers):
            file_guide = {
                'file_number': i + 1,
                'order_number': order_number,
                'steps': []
            }
            
            for step in self.workflows[workflow_name]['steps']:
                step_copy = step.copy()
                if 'text_to_type' in step_copy:
                    step_copy['text_to_type'] = step_copy['text_to_type'].replace('{ORDER_NUMBER}', order_number)
                file_guide['steps'].append(step_copy)
            
            guide['instructions'].append(file_guide)
        
        return guide

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

if 'assistant' not in st.session_state:
    st.session_state.assistant = ManualAssistant()

if 'processed_results' not in st.session_state:
    st.session_state.processed_results = None

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
    .current-step {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
    }
    .file-header {
        background-color: #e8f4fd;
        padding: 15px;
        border-radius: 8px;
        margin: 15px 0;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

def main():
    # Инициализация session_state переменных
    if 'confirmed_files' not in st.session_state:
        st.session_state.confirmed_files = []
    if 'current_file_index' not in st.session_state:
        st.session_state.current_file_index = 0
    if 'current_step_index' not in st.session_state:
        st.session_state.current_step_index = 0
    if 'edited_files' not in st.session_state:
        st.session_state.edited_files = []
    
    # ... остальной код
        
    st.markdown('<div class="main-header">🎓 PDF Manual Assistant - No Installation Needed</div>', unsafe_allow_html=True)
    
    # Вкладки
    tab1, tab2, tab3 = st.tabs(["📄 Обработка PDF", "🎓 Создание процесса", "👨‍💻 Ручное выполнение"])
    
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
                # Сбрасываем подтвержденные файлы при новой обработке
                st.session_state.confirmed_files = []
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
            
            # Ручная проверка и редактирование
            st.markdown("---")
            st.subheader("✏️ Проверка и редактирование номеров")
            st.info("Проверьте и при необходимости исправьте номера перед созданием инструкций")
            
            # Используем session_state для хранения отредактированных номеров
            if 'edited_files' not in st.session_state:
                st.session_state.edited_files = results['files'].copy()
            
            confirmed_files = st.session_state.get('confirmed_files', [])
            
            for i, file_info in enumerate(st.session_state.edited_files):
                if file_info['order_number']:  # Показываем только файлы с номерами
                    col_a, col_b, col_c = st.columns([2, 2, 1])
                    with col_a:
                        st.write(f"**{file_info['filename']}**")
                        st.write(f"Страница: {file_info['page_number']}")
                    with col_b:
                        # Поле для редактирования номера
                        new_number = st.text_input(
                            "Номер заказа", 
                            value=file_info['order_number'], 
                            key=f"num_{file_info['filename']}",
                            label_visibility="visible"
                        )
                        # Обновляем номер в отредактированных файлах
                        st.session_state.edited_files[i]['order_number'] = new_number
                    with col_c:
                        # Проверяем, подтвержден ли уже этот файл
                        is_confirmed = any(f['filename'] == file_info['filename'] for f in confirmed_files)
                        
                        if is_confirmed:
                            st.success("✓")
                        else:
                            if st.button("✅ Подтвердить", key=f"ok_{file_info['filename']}"):
                                # Добавляем текущую версию файла (с возможными правками) в подтвержденные
                                confirmed_files.append(st.session_state.edited_files[i])
                                st.session_state.confirmed_files = confirmed_files
                                st.rerun()
            
            # Показываем статистику по подтвержденным файлам
            if confirmed_files:
                st.success(f"✅ Подтверждено файлов: {len(confirmed_files)}")
                
                # Показываем список подтвержденных файлов
                with st.expander("📋 Показать подтвержденные файлы"):
                    for cf in confirmed_files:
                        st.write(f"- {cf['filename']}: {cf['order_number']}")
                
                # Кнопки управления
                col_reset, col_refresh = st.columns(2)
                with col_reset:
                    if st.button("🔄 Сбросить все подтверждения", type="secondary"):
                        st.session_state.confirmed_files = []
                        st.rerun()
                with col_refresh:
                    if st.button("🔄 Обновить список", type="secondary"):
                        st.rerun()
    
    with tab2:
        st.subheader("🎓 Создание процесса обработки")
        
        st.info("""
        **Создайте пошаговый процесс для ручного выполнения.**
        Программа сгенерирует подробные инструкции для каждого файла.
        """)
        
        workflow_name = st.text_input("Название процесса", value="Обработка_заказов_RDS")
        
        st.markdown("### Добавление шагов процесса:")
        
        # Форма для добавления шагов
        step_type = st.selectbox("Тип шага", 
                               ["click", "type", "wait", "hotkey", "focus", "select", "button"])
        
        step_description = st.text_input("Описание шага", placeholder="Что нужно сделать на этом шаге?")
        
        step_params = {}
        if step_type == "click":
            step_params['action'] = "Кликнуть"
            step_params['location'] = st.text_input("Где кликнуть?", placeholder="В поле ввода номера заказа")
        
        elif step_type == "type":
            step_params['action'] = "Ввести текст"
            text_to_type = st.text_input("Текст для ввода", value="{ORDER_NUMBER}")
            step_params['text_to_type'] = text_to_type
            step_params['location'] = st.text_input("Куда вводить?", placeholder="В поле поиска")
        
        elif step_type == "wait":
            step_params['action'] = "Подождать"
            seconds = st.number_input("Секунды", min_value=1, value=2)
            step_params['duration'] = f"{seconds} секунд"
        
        elif step_type == "hotkey":
            step_params['action'] = "Нажать комбинацию клавиш"
            step_params['keys'] = st.text_input("Клавиши", value="Ctrl+V", placeholder="Ctrl+V, Enter, Tab...")
        
        elif step_type == "focus":
            step_params['action'] = "Перейти в поле"
            step_params['location'] = st.text_input("Какое поле?", placeholder="Поле ввода номера заказа")
        
        elif step_type == "select":
            step_params['action'] = "Выбрать из списка"
            step_params['location'] = st.text_input("Какой список?", placeholder="Выпадающий список статуса")
        
        elif step_type == "button":
            step_params['action'] = "Нажать кнопку"
            step_params['location'] = st.text_input("Какую кнопку?", placeholder="Кнопка 'Поиск', 'Сохранить'")
        
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
                    st.write(f"**Место:** {step['location']}")
                if 'text_to_type' in step:
                    st.write(f"**Текст:** `{step['text_to_type']}`")
                if 'duration' in step:
                    st.write(f"**Время:** {step['duration']}")
                if 'keys' in step:
                    st.write(f"**Клавиши:** {step['keys']}")
                st.markdown('</div>', unsafe_allow_html=True)
            
            col_save, col_clear = st.columns(2)
            with col_save:
                if st.button("💾 Сохранить процесс", type="secondary", use_container_width=True):
                    if st.session_state.assistant.create_workflow(workflow_name, st.session_state.workflow_steps):
                        st.success(f"✅ Процесс '{workflow_name}' сохранен!")
            with col_clear:
                if st.button("🗑️ Очистить шаги", type="secondary", use_container_width=True):
                    st.session_state.workflow_steps = []
                    st.rerun()
    
    with tab3:
     st.subheader("👨‍💻 Ручное выполнение с инструкциями")
    
    if not st.session_state.processed_results:
        st.info("📝 Сначала обработайте PDF файл во вкладке 'Обработка PDF'")
    elif not st.session_state.assistant.workflows:
        st.info("🎓 Сначала создайте процесс во вкладке 'Создание процесса'")
        else:
        confirmed_files = st.session_state.get('confirmed_files', [])
        if not confirmed_files:
            st.warning("⚠️ Подтвердите номера во вкладке 'Обработка PDF'")
            st.info("""
            **Как подтвердить файлы:**
            1. Перейдите во вкладку "📄 Обработка PDF"
            2. Проверьте автоматически найденные номера
            3. При необходимости отредактируйте номера в полях ввода
            4. Нажмите кнопки "✅ Подтвердить" для каждого нужного файла
            5. Вернитесь в эту вкладку
            """)
            if st.button("🔄 Проверить подтвержденные файлы", key="check_confirmed"):
                st.rerun()
        else:
                    order_numbers = [f['order_number'] for f in confirmed_files]
                    
                    # Генерация руководства
                    guide = st.session_state.assistant.generate_manual_guide(
                        selected_workflow, order_numbers
                    )
                    
                    if guide:
                        st.markdown(f'<div class="guide-box">', unsafe_allow_html=True)
                        st.subheader("📋 Руководство по выполнению")
                        st.write(f"**Процесс:** {guide['workflow_name']}")
                        st.write(f"**Файлов для обработки:** {guide['total_files']}")
                        st.write(f"**Примерное время:** {guide['completion_time']} минут")
                        st.write(f"**Сгенерировано:** {datetime.fromisoformat(guide['generated_at']).strftime('%d.%m.%Y %H:%M')}")
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        # Инструкции для каждого файла
                        st.markdown("### Пошаговые инструкции:")
                        
                        current_file_index = st.session_state.current_file_index
                        current_step_index = st.session_state.current_step_index
                        
                        if current_file_index < len(guide['instructions']):
                            current_file = guide['instructions'][current_file_index]
                            
                            st.markdown(f'<div class="file-header">', unsafe_allow_html=True)
                            st.subheader(f"📄 Файл {current_file['file_number']} из {len(guide['instructions'])}")
                            st.write(f"**Номер заказа:** {current_file['order_number']}")
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            # Показываем шаги для текущего файла
                            for i, step in enumerate(current_file['steps']):
                                step_class = "current-step" if i == current_step_index else "step-box"
                                st.markdown(f'<div class="{step_class}">', unsafe_allow_html=True)
                                
                                # Номер шага и статус
                                status = "🟢 ТЕКУЩИЙ ШАГ" if i == current_step_index else "⚪"
                                st.write(f"**{status} Шаг {i+1}: {step['description']}**")
                                
                                # Детали шага
                                st.write(f"**Действие:** {step['action']}")
                                if 'location' in step:
                                    st.write(f"**Место:** {step['location']}")
                                if 'text_to_type' in step and 'text_to_type' in step:
                                    display_text = step['text_to_type'].replace('{ORDER_NUMBER}', current_file['order_number'])
                                    st.write(f"**Текст:** `{display_text}`")
                                if 'duration' in step:
                                    st.write(f"**Время:** {step['duration']}")
                                if 'keys' in step:
                                    st.write(f"**Клавиши:** {step['keys']}")
                                
                                st.markdown('</div>', unsafe_allow_html=True)
                            
                            # Управление прогрессом
                            st.markdown("### Управление выполнением:")
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                if st.button("⏮️ Предыдущий шаг", use_container_width=True) and current_step_index > 0:
                                    st.session_state.current_step_index -= 1
                                    st.rerun()
                            
                            with col2:
                                if st.button("✅ Шаг выполнен", type="primary", use_container_width=True):
                                    if current_step_index < len(current_file['steps']) - 1:
                                        st.session_state.current_step_index += 1
                                        st.success("✓ Шаг выполнен!")
                                        st.rerun()
                                    else:
                                        # Переход к следующему файлу
                                        if current_file_index < len(guide['instructions']) - 1:
                                            st.session_state.current_file_index += 1
                                            st.session_state.current_step_index = 0
                                            st.success("🎉 Файл обработан! Переход к следующему...")
                                            st.rerun()
                                        else:
                                            st.balloons()
                                            st.success("🎉 Все файлы обработаны! Задание завершено!")
                            
                            with col3:
                                if st.button("⏭️ Следующий файл", use_container_width=True):
                                    if current_file_index < len(guide['instructions']) - 1:
                                        st.session_state.current_file_index += 1
                                        st.session_state.current_step_index = 0
                                        st.rerun()
                                    else:
                                        st.info("📝 Это последний файл")
                            
                            # Быстрая навигация
                            st.markdown("#### Быстрая навигация:")
                            nav_cols = st.columns(4)
                            with nav_cols[0]:
                                if st.button("🔄 Начать заново", use_container_width=True):
                                    st.session_state.current_file_index = 0
                                    st.session_state.current_step_index = 0
                                    st.rerun()
                            
                            # Прогресс
                            total_steps = sum(len(f['steps']) for f in guide['instructions'])
                            completed_steps = sum(len(f['steps']) for f in guide['instructions'][:current_file_index]) + current_step_index
                            progress = completed_steps / total_steps if total_steps > 0 else 0
                            
                            st.progress(progress)
                            st.write(f"**Общий прогресс:** {completed_steps}/{total_steps} шагов ({progress:.1%})")
                        
                        else:
                            st.balloons()
                            st.success("🎉 Все файлы обработаны! Задание завершено!")

if __name__ == "__main__":
    main()
