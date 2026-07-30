"""
Виджет одного монитора пациента
"""
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.popup import Popup
from kivy.uix.gridlayout import GridLayout
from kivy.clock import Clock
from kivy.metrics import dp
from datetime import datetime
from components.graph_widget import GraphWidget
from components.camera_widget import CameraWidget
from components.value_display_widget import ValueDisplayWidget
from utils.time_range import TimeRange
from utils.data_source import DataSource
from utils.data_storage import DataStorage
from utils.config_loader import ConfigLoader
from utils.data_source_factory import create_configured_data_source
from utils.database_source import DatabaseDataSource
from utils.popup_style import apply_popup_theme
from utils.ui_style import UI_BTN_MUTED, UI_TEXT_PRIMARY, apply_rounded_button, apply_rounded_panel
from typing import Optional, Callable


class PatientMonitorWidget(BoxLayout):
    """Виджет одного монитора пациента"""
    
    def __init__(self, bed_id: Optional[int] = None, bed_name: Optional[str] = None,
                 on_bed_selected: Optional[Callable] = None, **kwargs):
        """
        Инициализация виджета монитора пациента
        
        Args:
            bed_id: ID кровати (опционально)
            bed_name: Название кровати (опционально)
            on_bed_selected: Callback для выбора кровати
        """
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.spacing = dp(5)
        self.padding = dp(5)
        
        self.bed_id = bed_id
        self.bed_name = bed_name
        self.on_bed_selected = on_bed_selected
        
        # Загрузка конфигурации
        self.config = ConfigLoader()
        
        # Источник данных
        self.data_source: DataSource = self._create_data_source()
        
        # Хранилище данных
        self.data_storage = DataStorage()
        
        # Текущий временной диапазон
        self.current_time_range = TimeRange.get_default()
        
        # Создание UI
        self._create_ui()
        
        # Загрузка исторических данных
        self._load_historical_data()
        
        # Запуск обновления данных
        self.data_update_event = Clock.schedule_interval(self._update_data, 1.0)
        # Увеличиваем интервал обновления графиков для оптимизации производительности
        # При 6 экранах с 6 мониторами = 144 графика, обновление каждые 2 секунды вместо 0.5
        self.graph_update_event = Clock.schedule_interval(self._update_graphs, 2.0)
        
        # Флаг для отслеживания изменений данных
        self._data_changed = False
        
        # Флаг активности виджета (для остановки обновлений невидимых мониторов)
        self._is_active = True
    
    def _create_data_source(self) -> DataSource:
        """Создать источник без автоматического перехода на синтетику."""
        result = create_configured_data_source(self.config, bed_id=self.bed_id)
        self._db_available = bool(result.available and result.mode == "database")
        self._data_mode = result.mode
        if result.mode == "database" and not result.available:
            print(f"[PatientMonitorWidget] OFFLINE: {result.error}")
        return result.source
    
    def _create_ui(self):
        """Создание пользовательского интерфейса"""
        # Верхняя часть - панель выбора кровати и камера (уменьшена для увеличения графиков)
        top_container = BoxLayout(
            orientation='horizontal',
            spacing=dp(5),
            size_hint_y=0.3,  # Уменьшено с 0.4 до 0.3 для увеличения места под графики
            padding=dp(2)  # Минимальный padding для маленьких экранов
        )
        
        # Отслеживаем размер для адаптации элементов
        self.bind(size=self._adapt_ui_to_size)
        
        # Левая часть - панель выбора кровати (адаптивная ширина)
        bed_panel = self._create_bed_selection_panel()
        top_container.add_widget(bed_panel)
        
        # Средняя часть - камера (может быть скрыта при маленьком размере)
        camera_container = AnchorLayout(
            anchor_x='center',
            anchor_y='center',
            size_hint_x=0.5
        )
        self.camera_widget = CameraWidget()
        camera_container.add_widget(self.camera_widget)
        top_container.add_widget(camera_container)
        
        # Делаем камеру квадратной и адаптивной
        def make_square(instance, size):
            if size[0] > 0 and size[1] > 0:
                # Адаптивный размер камеры в зависимости от размера контейнера
                max_size = min(size[0], size[1])
                # При очень маленьком размере уменьшаем камеру или скрываем
                if max_size < dp(60):
                    square_size = 0  # Скрываем камеру при очень маленьком размере
                elif max_size < dp(100):
                    square_size = max_size * 0.6  # Уменьшаем камеру
                else:
                    square_size = max_size * 0.8  # Нормальный размер
                
                self.camera_widget.size_hint = (None, None)
                self.camera_widget.width = square_size
                self.camera_widget.height = square_size
                self.camera_widget.opacity = 1.0 if square_size > 0 else 0.0
        camera_container.bind(size=make_square)
        
        # Правая часть - цифровые значения (адаптивная ширина)
        values_container = BoxLayout(
            orientation='vertical',
            spacing=dp(2),  # Уменьшенный spacing для маленьких экранов
            size_hint_x=0.3,
            padding=dp(2)  # Минимальный padding
        )
        
        param_info = self._get_param_info()
        param1_name = self.config.get_display_value_1()
        param2_name = self.config.get_display_value_2()
        
        info1 = param_info.get(param1_name, {'title': 'Параметр 1', 'color': '#FF4444', 'unit': '%'})
        info2 = param_info.get(param2_name, {'title': 'Параметр 2', 'color': '#44FF44', 'unit': 'уд/мин'})
        
        self.value_display_1 = ValueDisplayWidget(
            title=info1['title'],
            color=info1['color'],
            unit=info1['unit']
        )
        self.display_param_1 = param1_name
        values_container.add_widget(self.value_display_1)
        
        self.value_display_2 = ValueDisplayWidget(
            title=info2['title'],
            color=info2['color'],
            unit=info2['unit']
        )
        self.display_param_2 = param2_name
        values_container.add_widget(self.value_display_2)
        
        top_container.add_widget(values_container)
        self.add_widget(top_container)
        
        # Нижняя часть - графики (увеличена высота)
        graphs_container = BoxLayout(
            orientation='vertical',
            spacing=dp(2),  # Уменьшенный spacing для маленьких экранов
            size_hint_y=0.65,  # Увеличено с 0.55 до 0.65 для большей высоты графиков
            padding=dp(2)  # Минимальный padding
        )
        
        param_info = self._get_param_info()
        spo2_info = param_info.get('spo2', {'title': 'SPO2', 'color': '#FF4444'})
        pulse_info = param_info.get('pulse', {'title': 'Пульс', 'color': '#44FF44'})
        breathing_info = param_info.get('breathing', {'title': 'Дыхание', 'color': '#4444FF'})
        temperature_info = param_info.get('temperature', {'title': 'Температура', 'color': '#FFFF44'})
        
        self.spo2_graph = GraphWidget(
            title=spo2_info['title'],
            color=spo2_info['color'],
            min_value=90,
            max_value=100
        )
        self.pulse_graph = GraphWidget(
            title=pulse_info['title'],
            color=pulse_info['color'],
            min_value=50,
            max_value=110
        )
        self.breathing_graph = GraphWidget(
            title=breathing_info['title'],
            color=breathing_info['color'],
            min_value=10,
            max_value=25
        )
        self.temperature_graph = GraphWidget(
            title=temperature_info['title'],
            color=temperature_info['color'],
            min_value=35.5,
            max_value=38.0
        )
        
        self.all_graphs = {
            'spo2': self.spo2_graph,
            'pulse': self.pulse_graph,
            'breathing': self.breathing_graph,
            'temperature': self.temperature_graph
        }
        
        # Первая строка - один график
        first_row = BoxLayout(orientation='horizontal', size_hint_y=0.5)
        first_row.add_widget(self.spo2_graph)
        graphs_container.add_widget(first_row)
        
        # Вторая строка - один график
        second_row = BoxLayout(orientation='horizontal', size_hint_y=0.5)
        second_row.add_widget(self.pulse_graph)
        graphs_container.add_widget(second_row)
        
        self.add_widget(graphs_container)
        
        # Панель выбора временного диапазона
        self._create_time_range_panel()
        
        # Инициализация камеры (увеличен интервал для оптимизации производительности)
        camera_path = self.config.get_camera_image_path()
        if camera_path:
            # Увеличиваем интервал обновления камеры с 1.0 до 3.0 секунд для оптимизации
            self.camera_widget.start_auto_update(interval=3.0, image_path=camera_path)
        
        # Адаптируем UI после создания (если размер уже известен)
        # Используем Clock.schedule_once для вызова после полной инициализации
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: self._adapt_ui_to_size(self, self.size) if self.size[0] > 0 else None, 0.1)

    def _style_action_button(self, btn: Button) -> None:
        btn.color = UI_TEXT_PRIMARY
        apply_rounded_button(btn, base_rgba=UI_BTN_MUTED, radius_px=dp(8), border_alpha=0.06)
    
    def _get_param_info(self) -> dict:
        """Получить информацию о параметрах с названиями из БД"""
        base_info = {
            'spo2': {'color': '#FF4444', 'unit': '%'},
            'pulse': {'color': '#44FF44', 'unit': 'уд/мин'},
            'breathing': {'color': '#4444FF', 'unit': 'вдох/мин'},
            'temperature': {'color': '#FFFF44', 'unit': '°C'}
        }
        
        param_info = {}
        
        if isinstance(self.data_source, DatabaseDataSource):
            for param_key in ['spo2', 'pulse', 'breathing', 'temperature']:
                signal_name = self.data_source.get_signal_name_by_key(param_key)
                param_info[param_key] = {
                    'title': signal_name,
                    'color': base_info[param_key]['color'],
                    'unit': base_info[param_key]['unit']
                }
        else:
            defaults = {
                'spo2': 'SPO2',
                'pulse': 'Пульс',
                'breathing': 'Дыхание',
                'temperature': 'Температура'
            }
            for param_key in ['spo2', 'pulse', 'breathing', 'temperature']:
                param_info[param_key] = {
                    'title': defaults[param_key],
                    'color': base_info[param_key]['color'],
                    'unit': base_info[param_key]['unit']
                }
        
        return param_info
    
    def _create_bed_selection_panel(self):
        """Создание панели выбора кровати (адаптивной)"""
        bed_panel = BoxLayout(
            orientation='vertical',
            size_hint_x=None,
            width=dp(120),  # Будет изменяться адаптивно
            spacing=dp(2),  # Уменьшенный spacing
            padding=dp(2)  # Минимальный padding
        )
        
        self.bed_label = Label(
            text="Кровать:",
            size_hint_y=None,
            height=dp(20),
            color=(0.8, 0.8, 0.8, 1),
            font_size=dp(12),  # Будет изменяться адаптивно
            halign='left',
            text_size=(dp(110), None)
        )
        bed_panel.add_widget(self.bed_label)
        
        self.bed_button = Button(
            text=self.bed_name or "Загрузка...",
            size_hint_y=None,
            height=dp(30),  # Будет изменяться адаптивно
            font_size=dp(11),  # Будет изменяться адаптивно
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
            padding=(dp(2), dp(2))  # Минимальный padding
        )
        self._style_action_button(self.bed_button)
        self.bed_button.bind(on_press=self._show_bed_selection_menu)
        bed_panel.add_widget(self.bed_button)
        
        self.bed_panel = bed_panel  # Сохраняем ссылку для адаптации
        
        if getattr(self, "_data_mode", None) == "demo":
            self.bed_button.text = "ДЕМО"
            self.bed_button.disabled = True
        elif isinstance(self.data_source, DatabaseDataSource) and getattr(self, "_db_available", False):
            self._load_beds()
        else:
            self.bed_button.text = "БД недоступна"
            self.bed_button.disabled = True
        
        return bed_panel
    
    def _load_beds(self):
        """Загрузка списка кроватей"""
        if not isinstance(self.data_source, DatabaseDataSource):
            return
        if not getattr(self, "_db_available", False):
            self.available_beds = []
            self.bed_button.text = "БД недоступна"
            self.bed_button.disabled = True
            return
        
        try:
            beds = self.data_source.get_available_beds()
            if beds:
                self.available_beds = beds
                self.bed_button.disabled = False
                if self.bed_id:
                    current_bed = next(
                        (b for b in beds if str(b.get("id")) == str(self.bed_id)),
                        None,
                    )
                    if current_bed:
                        self.bed_button.text = current_bed['name']
                    else:
                        self.bed_button.text = f"Кровать {self.bed_id}"
                else:
                    current_bed_id = self.data_source.get_current_bed_id()
                    if current_bed_id:
                        current_bed = next(
                            (b for b in beds if str(b.get("id")) == str(current_bed_id)),
                            None,
                        )
                        if current_bed:
                            self.bed_button.text = current_bed['name']
                        else:
                            self.bed_button.text = beds[0]['name'] if beds else "Не выбрана"
                    else:
                        self.bed_button.text = beds[0]['name'] if beds else "Не выбрана"
            else:
                self.available_beds = []
                self.bed_button.text = "Нет доступных"
        except Exception as e:
            print(f"Ошибка загрузки списка кроватей: {e}")
            self.available_beds = []
            self.bed_button.text = "Ошибка загрузки"
    
    def _show_bed_selection_menu(self, instance):
        """Показать меню выбора кровати"""
        if not hasattr(self, 'available_beds') or not self.available_beds:
            return
        
        if self.on_bed_selected:
            # Передаем список кроватей и текущую кровать
            current_bed_id = None
            if isinstance(self.data_source, DatabaseDataSource):
                current_bed_id = self.data_source.get_current_bed_id()
            self.on_bed_selected(self, self.available_beds, current_bed_id)
    
    def set_bed(self, bed_id: int, bed_name: str):
        """Установить кровать для монитора"""
        if not isinstance(self.data_source, DatabaseDataSource):
            return
        
        try:
            self.data_source.set_bed_id(bed_id)
            self.bed_id = bed_id
            self.bed_name = bed_name
            self.bed_button.text = bed_name
            
            # Очищаем данные графиков
            for graph in self.all_graphs.values():
                graph.clear_data()
            
            # Загружаем исторические данные
            self._load_historical_data()
        except Exception as e:
            print(f"Ошибка при выборе кровати: {e}")
    
    def _create_time_range_panel(self):
        """Создание кнопки для выбора временного диапазона (открывает popup)"""
        time_panel = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(30),
            spacing=dp(4),
            padding=dp(2)
        )
        
        # Кнопка для открытия popup выбора диапазона
        self.time_range_button = Button(
            text=f'Диапазон: {self.current_time_range.label}',
            size_hint_x=1,
            font_size=dp(10),
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
        )
        self._style_action_button(self.time_range_button)
        self.time_range_button.bind(on_press=self._show_time_range_dialog)
        time_panel.add_widget(self.time_range_button)
        
        self.add_widget(time_panel)
    
    def _show_time_range_dialog(self, instance):
        """Показать диалог выбора временного диапазона"""
        content = BoxLayout(
            orientation='vertical',
            spacing=dp(12),
            padding=dp(18)
        )
        apply_rounded_panel(content, base_rgba=(0.11, 0.12, 0.15, 1), radius_px=dp(12), border_alpha=0.12)

        label = Label(
            text='Выберите временной диапазон:',
            size_hint_y=None,
            height=dp(40),
            font_size=dp(16),
            bold=True,
            color=(0.94, 0.94, 0.98, 1)
        )
        content.add_widget(label)
        
        # Получаем все диапазоны для расчета размера сетки
        all_ranges = TimeRange.get_all_ranges()
        num_ranges = len(all_ranges)
        
        # Вычисляем количество строк (3 колонки)
        num_rows = (num_ranges + 2) // 3  # Округляем вверх
        
        # Сетка для кнопок диапазонов
        buttons_grid = GridLayout(
            cols=3,
            spacing=dp(10),
            size_hint_y=None,
            height=num_rows * dp(50) + (num_rows - 1) * dp(10)  # Высота кнопок + spacing
        )
        
        # Вычисляем общую высоту popup
        popup_height = dp(40) + buttons_grid.height + dp(40) + dp(20)  # label + buttons + padding
        
        popup = Popup(
            title='',
            content=content,
            size_hint=(None, None),
            size=(dp(500), popup_height),
            auto_dismiss=True,
            separator_height=0,
        )
        apply_popup_theme(popup)

        # Создаем кнопки с правильной привязкой к popup
        self.time_range_buttons = {}
        for time_range in all_ranges:
            sel = time_range == self.current_time_range
            btn = Button(
                text=time_range.label,
                font_size=dp(14),
                background_normal="",
                background_down="",
                background_color=UI_BTN_SUCCESS if sel else (0.20, 0.21, 0.25, 1),
            )
            btn.color = (0.96, 0.96, 0.99, 1)
            # Используем замыкание для передачи popup
            btn.bind(on_press=lambda instance, tr=time_range, p=popup: self._on_time_range_selected(tr, p))
            self.time_range_buttons[time_range] = btn
            buttons_grid.add_widget(btn)
        
        content.add_widget(buttons_grid)
        popup.open()
    
    def _on_time_range_selected(self, time_range, popup=None):
        """Обработчик выбора временного диапазона"""
        self.current_time_range = time_range
        
        # Обновляем текст кнопки
        if hasattr(self, 'time_range_button'):
            self.time_range_button.text = f'Диапазон: {time_range.label}'
        
        # Обновляем цвета кнопок в popup
        if hasattr(self, 'time_range_buttons'):
            for tr, btn in self.time_range_buttons.items():
                if tr == time_range:
                    btn.background_color = UI_BTN_SUCCESS
                else:
                    btn.background_color = (0.20, 0.21, 0.25, 1)
        
        # Закрываем popup
        if popup:
            popup.dismiss()
        
        self._filter_graphs_by_time_range()
    
    def _filter_graphs_by_time_range(self):
        """Фильтрация данных графиков по текущему временному диапазону"""
        minutes = self.current_time_range.minutes
        for graph in self.all_graphs.values():
            graph.filter_data_by_time_range(minutes)
    
    def _load_historical_data(self):
        """Загрузка исторических данных"""
        try:
            if isinstance(self.data_source, DatabaseDataSource):
                bed_id = self.data_source.get_current_bed_id()
                if bed_id is None:
                    return
                
                signal_ids = self.data_source.signal_ids
                
                spo2_data = self.data_source.get_historical_data(signal_ids.get('spo2', 1), hours=6)
                pulse_data = self.data_source.get_historical_data(signal_ids.get('pulse', 2), hours=6)
                breathing_data = self.data_source.get_historical_data(signal_ids.get('breathing', 3), hours=6)
                temperature_data = self.data_source.get_historical_data(signal_ids.get('temperature', 4), hours=6)
                
                if spo2_data:
                    values, times = zip(*spo2_data)
                    self.spo2_graph.load_historical_data(list(values), list(times))
                
                if pulse_data:
                    values, times = zip(*pulse_data)
                    self.pulse_graph.load_historical_data(list(values), list(times))
                
                if breathing_data:
                    values, times = zip(*breathing_data)
                    self.breathing_graph.load_historical_data(list(values), list(times))
                
                if temperature_data:
                    values, times = zip(*temperature_data)
                    self.temperature_graph.load_historical_data(list(values), list(times))
            else:
                from pathlib import Path
                if not Path(self.data_storage.data_file).exists():
                    self.data_storage.generate_test_data(hours=6)
                
                spo2_data = self.data_storage.load_data('spo2', hours=6)
                pulse_data = self.data_storage.load_data('pulse', hours=6)
                breathing_data = self.data_storage.load_data('breathing', hours=6)
                temperature_data = self.data_storage.load_data('temperature', hours=6)
                
                if spo2_data:
                    values, times = zip(*spo2_data)
                    self.spo2_graph.load_historical_data(list(values), list(times))
                
                if pulse_data:
                    values, times = zip(*pulse_data)
                    self.pulse_graph.load_historical_data(list(values), list(times))
                
                if breathing_data:
                    values, times = zip(*breathing_data)
                    self.breathing_graph.load_historical_data(list(values), list(times))
                
                if temperature_data:
                    values, times = zip(*temperature_data)
                    self.temperature_graph.load_historical_data(list(values), list(times))
            
            minutes = self.current_time_range.minutes
            for graph in self.all_graphs.values():
                graph.filter_data_by_time_range(minutes)
        except Exception as e:
            print(f"Ошибка загрузки исторических данных: {e}")
    
    def _update_data(self, dt):
        """Обновление данных каждую секунду (только если виджет активен)"""
        if not self._is_active:
            return  # Пропускаем обновление данных для неактивных виджетов
        
        if hasattr(self.data_source, 'update'):
            self.data_source.update(dt)
        
        try:
            spo2_value: float = self.data_source.get_spo2()
            pulse_value: float = self.data_source.get_pulse()
            breathing_value: float = self.data_source.get_breathing()
            temperature_value: float = self.data_source.get_temperature()
        except Exception as e:
            print(f"Ошибка получения данных: {e}")
            return
        
        param_values = {
            'spo2': spo2_value,
            'pulse': pulse_value,
            'breathing': breathing_value,
            'temperature': temperature_value
        }
        
        if hasattr(self, 'display_param_1'):
            self.value_display_1.set_value(param_values.get(self.display_param_1))
        if hasattr(self, 'display_param_2'):
            self.value_display_2.set_value(param_values.get(self.display_param_2))
        
        if not isinstance(self.data_source, DatabaseDataSource):
            current_time = datetime.now()
            self.data_storage.save_data_point('spo2', spo2_value, current_time)
            self.data_storage.save_data_point('pulse', pulse_value, current_time)
            self.data_storage.save_data_point('breathing', breathing_value, current_time)
            self.data_storage.save_data_point('temperature', temperature_value, current_time)
        
        current_time = datetime.now()
        self.spo2_graph.add_data_point(spo2_value, current_time)
        self.pulse_graph.add_data_point(pulse_value, current_time)
        self.breathing_graph.add_data_point(breathing_value, current_time)
        self.temperature_graph.add_data_point(temperature_value, current_time)
        
        # Помечаем, что данные изменились
        self._data_changed = True
    
    def _update_graphs(self, dt):
        """Обновление отображения графиков (только если данные изменились и виджет активен)"""
        if not self._is_active:
            return  # Пропускаем обновление, если виджет неактивен (управляется через on_enter/on_leave)
        
        if not self._data_changed:
            return  # Пропускаем обновление, если данные не изменились
        
        # Обновляем только видимые графики
        for graph in self.all_graphs.values():
            if graph.parent is not None:  # Проверяем, что график видим
                graph.update_graph()
        
        self._data_changed = False
    
    def _adapt_ui_to_size(self, instance, size):
        """Адаптация размеров элементов UI в зависимости от размера виджета"""
        width = size[0]
        height = size[1]
        
        # Определяем размер экрана (ширина одного монитора)
        if width < dp(300):
            # Очень маленький размер (6 мониторов в ряд) - минимальные размеры
            scale_factor = 0.6
            if hasattr(self, 'bed_panel'):
                self.bed_panel.width = dp(70)
                self.bed_panel.spacing = dp(1)
                self.bed_panel.padding = dp(1)
            if hasattr(self, 'bed_label'):
                self.bed_label.height = dp(15)
                self.bed_label.font_size = dp(8)
                self.bed_label.text_size = (dp(65), None)
            if hasattr(self, 'bed_button'):
                self.bed_button.height = dp(20)
                self.bed_button.font_size = dp(8)
                self.bed_button.padding = (dp(1), dp(1))
        elif width < dp(500):
            # Маленький размер (4 монитора) - уменьшенные размеры
            scale_factor = 0.75
            if hasattr(self, 'bed_panel'):
                self.bed_panel.width = dp(90)
                self.bed_panel.spacing = dp(2)
                self.bed_panel.padding = dp(2)
            if hasattr(self, 'bed_label'):
                self.bed_label.height = dp(18)
                self.bed_label.font_size = dp(10)
                self.bed_label.text_size = (dp(85), None)
            if hasattr(self, 'bed_button'):
                self.bed_button.height = dp(25)
                self.bed_button.font_size = dp(9)
                self.bed_button.padding = (dp(2), dp(2))
        else:
            # Нормальный размер - стандартные размеры
            scale_factor = 1.0
            if hasattr(self, 'bed_panel'):
                self.bed_panel.width = dp(120)
                self.bed_panel.spacing = dp(5)
                self.bed_panel.padding = dp(5)
            if hasattr(self, 'bed_label'):
                self.bed_label.height = dp(20)
                self.bed_label.font_size = dp(12)
                self.bed_label.text_size = (dp(110), None)
            if hasattr(self, 'bed_button'):
                self.bed_button.height = dp(30)
                self.bed_button.font_size = dp(11)
                self.bed_button.padding = (dp(2), dp(2))
    
    def set_active(self, active: bool):
        """Установить активность виджета (для остановки обновлений невидимых мониторов)"""
        self._is_active = active
        # Управляем активностью камеры
        if hasattr(self, 'camera_widget'):
            self.camera_widget.set_active(active)
    
    def cleanup(self):
        """Очистка ресурсов при закрытии"""
        if hasattr(self, 'data_update_event') and self.data_update_event:
            Clock.unschedule(self.data_update_event)
        if hasattr(self, 'graph_update_event') and self.graph_update_event:
            Clock.unschedule(self.graph_update_event)
        
        if isinstance(self.data_source, DatabaseDataSource):
            self.data_source.close()

