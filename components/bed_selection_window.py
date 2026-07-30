"""
Окно выбора кровати
Использует Popup для создания модального окна
"""
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.metrics import dp
from typing import List, Dict, Callable, Optional

from utils.popup_style import apply_popup_theme, style_scrollview_popup
from utils.ui_style import UI_BTN_SECONDARY, UI_BTN_SUCCESS, UI_TEXT_PRIMARY, UI_TEXT_STRONG, apply_rounded_button, apply_rounded_panel


class BedSelectionWindow:
    """Окно для выбора кровати (использует Popup)"""
    
    def __init__(self, beds: List[Dict], current_bed_id: Optional[int] = None, 
                 on_bed_selected: Optional[Callable] = None):
        """
        Инициализация окна выбора кровати
        
        Args:
            beds: Список кроватей [{'id': 1, 'name': 'Кровать 1'}, ...]
            current_bed_id: ID текущей выбранной кровати
            on_bed_selected: Callback функция при выборе кровати (bed_id, bed_name)
        """
        self.beds = beds
        self.current_bed_id = current_bed_id
        self.on_bed_selected = on_bed_selected
        self.popup = None
        
    def open(self):
        """Открытие окна выбора кровати"""
        if self.popup is not None:
            # Если окно уже открыто, просто показываем его
            self.popup.open()
            return
        
        # Создаем основной контейнер
        main_container = BoxLayout(
            orientation='vertical',
            spacing=dp(15),
            padding=dp(20)
        )
        
        # Заголовок
        title_label = Label(
            text='Выбор кровати',
            size_hint_y=None,
            height=dp(50),
            font_size=dp(24),
            bold=True,
            color=UI_TEXT_STRONG
        )
        main_container.add_widget(title_label)
        
        # Информация о текущей кровати
        if self.current_bed_id:
            current_bed = next((b for b in self.beds if b['id'] == self.current_bed_id), None)
            if current_bed:
                current_label = Label(
                    text=f'Текущая кровать: {current_bed["name"]}',
                    size_hint_y=None,
                    height=dp(35),
                    font_size=dp(16),
                    color=(0.65, 0.82, 0.70, 1)
                )
                main_container.add_widget(current_label)
        
        # Прокручиваемая область со списком кроватей
        scroll = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=dp(10)
        )
        style_scrollview_popup(scroll)
        
        # Сетка для кроватей (2 колонки)
        beds_grid = GridLayout(
            cols=2,
            spacing=dp(15),
            size_hint_y=None,
            padding=dp(10)
        )
        
        # Вычисляем высоту сетки
        num_rows = (len(self.beds) + 1) // 2  # Округляем вверх
        beds_grid.height = num_rows * (dp(70) + dp(15)) + dp(20)
        
        # Добавляем кнопки кроватей
        for bed in self.beds:
            is_current = bed['id'] == self.current_bed_id
            bed_button = Button(
                text=bed['name'],
                size_hint_y=None,
                height=dp(70),
                font_size=dp(18),
                background_color=(0, 0, 0, 0),
                background_normal='',
                background_down=''
            )
            bed_button.color = UI_TEXT_PRIMARY
            
            # Подсвечиваем текущую кровать
            if is_current:
                bed_button.text = f"* {bed['name']}"
                apply_rounded_button(bed_button, base_rgba=UI_BTN_SUCCESS)
            else:
                apply_rounded_button(bed_button, base_rgba=UI_BTN_SECONDARY)
            
            # Привязываем обработчик
            bed_button.bind(
                on_press=lambda instance, b=bed: self._on_bed_clicked(b)
            )
            
            beds_grid.add_widget(bed_button)
        
        scroll.add_widget(beds_grid)
        main_container.add_widget(scroll)
        
        # Кнопка закрытия
        button_container = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(60),
            spacing=dp(10)
        )
        
        close_button = Button(
            text='Закрыть',
            size_hint_x=1,
            font_size=dp(18),
            background_color=(0, 0, 0, 0),
            background_normal='',
            background_down=''
        )
        close_button.color = UI_TEXT_PRIMARY
        apply_rounded_button(close_button, base_rgba=UI_BTN_SECONDARY)
        close_button.bind(on_press=self.close)
        button_container.add_widget(close_button)
        
        main_container.add_widget(button_container)
        
        # Создаем Popup
        self.popup = Popup(
            title='',
            content=main_container,
            size_hint=(None, None),
            size=(dp(600), dp(700)),
            auto_dismiss=False,  # Не закрывается при клике вне окна
            separator_height=0
        )
        apply_popup_theme(self.popup)
        
        # Привязываем закрытие к кнопке
        self.popup.bind(on_dismiss=self._on_popup_dismiss)
        
        # Открываем окно
        self.popup.open()
        
    def _on_bed_clicked(self, bed: Dict):
        """Обработчик клика на кровать"""
        if self.on_bed_selected:
            self.on_bed_selected(bed['id'], bed['name'])
        self.close()
    
    def _on_popup_dismiss(self, *args):
        """Обработчик закрытия Popup"""
        self.popup = None
    
    def close(self, *args):
        """Закрытие окна"""
        if self.popup:
            self.popup.dismiss()
    
    def is_open(self) -> bool:
        """Проверка, открыто ли окно"""
        return self.popup is not None

