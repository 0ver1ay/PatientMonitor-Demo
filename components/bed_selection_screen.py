"""
Экран выбора кровати
Отдельный экран с навигацией назад
"""
from typing import Callable, Dict, List, Optional

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from components.esc_back_navigation import has_open_modal_or_dropdown
from utils.ui_style import (
    UI_BTN_DANGER,
    UI_BTN_SECONDARY,
    UI_BTN_SUCCESS,
    UI_CONTENT_PADDING_UNDER_TITLEBAR,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    UI_TEXT_SECONDARY,
    UI_TEXT_STRONG,
    apply_rounded_button,
    apply_rounded_panel,
)


class BedSelectionScreen(Screen):
    """Экран для выбора кровати"""
    
    def __init__(self, beds: List[Dict] = None, current_bed_id: Optional[int] = None,
                 on_bed_selected: Optional[Callable] = None,
                 previous_screen: Optional[str] = None,
                 next_screen_on_select: Optional[str] = None,
                 on_back: Optional[Callable[[], None]] = None,
                 show_header_nav: bool = True,
                 **kwargs):
        """
        Инициализация экрана выбора кровати
        
        Args:
            beds: Список кроватей [{'id': 1, 'name': 'Кровать 1'}, ...]
            current_bed_id: ID текущей выбранной кровати
            on_bed_selected: Callback функция при выборе кровати (bed_id, bed_name)
            previous_screen: Имя экрана, на который нужно вернуться
            next_screen_on_select: Имя экрана, на который перейти после выбора (для сценариев "вперед")
            on_back: Callback для кнопки "Назад" (например, закрыть приложение)
            show_header_nav: Показать строку «Назад»+заголовок в контенте (False если навигация в CustomTitleBar).
        """
        super().__init__(**kwargs)
        # Устанавливаем имя только если оно не было задано
        if 'name' not in kwargs:
            self.name = 'bed_selection'
        self.beds = beds or []
        self.current_bed_id = current_bed_id
        self.on_bed_selected = on_bed_selected
        self.previous_screen = previous_screen
        self.next_screen_on_select = next_screen_on_select
        self.on_back = on_back
        self.show_header_nav = show_header_nav
        self._list_refresh_trigger = Clock.create_trigger(lambda _dt: self._update_beds_list(), 0)
        self._esc_handler_bound = False

        self._create_ui()
        self.bind(size=lambda *_args: self._schedule_beds_refresh())

    def on_pre_enter(self, *args):
        self._bind_escape_handler()
        return super().on_pre_enter(*args)

    def on_pre_leave(self, *args):
        self._unbind_escape_handler()
        return super().on_pre_leave(*args)
    
    def set_beds(self, beds: List[Dict]):
        """Установка списка кроватей"""
        self.beds = beds
        self._schedule_beds_refresh()
    
    def set_current_bed_id(self, bed_id: Optional[int]):
        """Установка текущей выбранной кровати"""
        self.current_bed_id = bed_id
        self._schedule_beds_refresh()
    
    def set_on_bed_selected(self, callback: Callable):
        """Установка callback функции при выборе кровати"""
        self.on_bed_selected = callback

    def _bind_escape_handler(self) -> None:
        if self._esc_handler_bound:
            return
        try:
            Window.bind(on_keyboard=self._on_window_keyboard)
            self._esc_handler_bound = True
        except Exception:
            self._esc_handler_bound = False

    def _unbind_escape_handler(self) -> None:
        if not self._esc_handler_bound:
            return
        try:
            Window.unbind(on_keyboard=self._on_window_keyboard)
        except Exception:
            pass
        self._esc_handler_bound = False

    def _on_window_keyboard(self, _window, key, _scancode, _codepoint, _modifiers):
        try:
            if int(key) != 27:
                return False
        except Exception:
            return False

        if has_open_modal_or_dropdown(_window):
            return False

        if not self.manager or self.manager.current != self.name:
            return False

        self._on_back_clicked()
        return True
    
    def _create_ui(self):
        """Создание пользовательского интерфейса"""
        self._btn_base = UI_BTN_SECONDARY
        self._btn_current = UI_BTN_SUCCESS

        main_container = BoxLayout(
            orientation='vertical',
            spacing=dp(6),
            padding=dp(10) if self.show_header_nav else UI_CONTENT_PADDING_UNDER_TITLEBAR,
        )

        summary_card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(4),
            padding=(dp(10), dp(8), dp(10), dp(8)),
        )
        summary_card.bind(minimum_height=summary_card.setter("height"))
        apply_rounded_panel(summary_card, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(10), border_alpha=0.06)

        title_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(32),
            spacing=dp(8),
        )
        if self.show_header_nav:
            title_label = Label(
                text='Выбор койко-места',
                size_hint=(1, None),
                height=dp(32),
                font_size=dp(16),
                bold=True,
                color=UI_TEXT_STRONG,
                halign='left',
                valign='middle',
                text_size=(0, None),
            )
            title_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
            title_row.add_widget(title_label)
        else:
            title_row.add_widget(Widget())

        back_button = Button(
            text='Назад',
            size_hint_x=None,
            width=dp(86),
            height=dp(32),
            font_size=dp(13),
            background_color=(0, 0, 0, 0),
            background_normal='',
            background_down='',
        )
        back_button.color = UI_TEXT_PRIMARY
        apply_rounded_button(back_button, base_rgba=UI_BTN_DANGER, radius_px=dp(8))
        back_button.bind(on_press=self._on_back_clicked)
        title_row.add_widget(back_button)
        summary_card.add_widget(title_row)

        subtitle_label = Label(
            text='Выберите кровать из списка по комнатам',
            size_hint_y=None,
            height=dp(16),
            font_size=dp(11),
            color=UI_TEXT_MUTED,
            halign='left',
            valign='middle',
            text_size=(0, None),
        )
        subtitle_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        summary_card.add_widget(subtitle_label)

        self.current_label = Label(
            text='',
            size_hint_y=None,
            height=dp(28),
            font_size=dp(12),
            color=UI_TEXT_PRIMARY,
            halign='left',
            valign='middle',
            text_size=(0, None),
        )
        self.current_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        apply_rounded_panel(self.current_label, base_rgba=(0.18, 0.18, 0.19, 1), radius_px=dp(8), border_alpha=0.05)
        self._update_current_label()
        summary_card.add_widget(self.current_label)
        main_container.add_widget(summary_card)

        list_card = BoxLayout(
            orientation="vertical",
            size_hint=(1, 1),
            spacing=dp(6),
            padding=(dp(8), dp(8), dp(8), dp(8)),
        )
        apply_rounded_panel(list_card, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(10), border_alpha=0.06)

        list_header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(22),
            spacing=dp(6),
        )
        list_title = Label(
            text="Доступные койко-места",
            size_hint=(1, None),
            height=dp(22),
            font_size=dp(13),
            bold=True,
            color=UI_TEXT_STRONG,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        list_title.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        list_header.add_widget(list_title)
        list_card.add_widget(list_header)

        self.scroll = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False,
            do_scroll_y=True,
            scroll_type=["content", "bars"],
            bar_width=dp(8),
            bar_color=(0.36, 0.36, 0.37, 0.85),
            bar_inactive_color=(0.24, 0.24, 0.25, 0.25),
        )

        self.beds_container = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=dp(6),
            padding=(0, 0, 0, dp(3)),
        )
        self.beds_container.bind(minimum_height=self.beds_container.setter('height'))
        self.scroll.add_widget(self.beds_container)
        list_card.add_widget(self.scroll)
        main_container.add_widget(list_card)

        self._update_beds_list()
        self.add_widget(main_container)

    def _schedule_beds_refresh(self):
        try:
            self._list_refresh_trigger()
        except Exception:
            self._update_beds_list()

    def _get_room_grid_cols(self) -> int:
        try:
            width = float(getattr(self, "width", 0) or 0)
        except Exception:
            width = 0
        if width <= float(dp(620)):
            return 1
        if width <= float(dp(920)):
            return 2
        if width <= float(dp(1320)):
            return 3
        return 4
    
    def _update_current_label(self):
        """Обновление метки текущей кровати"""
        if self.current_bed_id:
            current_bed = next((b for b in self.beds if str(b.get('id')) == str(self.current_bed_id)), None)
            if current_bed:
                self.current_label.text = f'Сейчас выбрано: {current_bed["name"]}'
            else:
                self.current_label.text = f'Сейчас выбрано: ID {self.current_bed_id}'
        else:
            self.current_label.text = 'Кровать пока не выбрана'
    
    def _update_beds_list(self):
        """Обновление списка кроватей с группировкой по комнатам"""
        # Очищаем контейнер
        self.beds_container.clear_widgets()
        
        if not self.beds:
            no_beds_label = Label(
                text='Нет доступных кроватей',
                size_hint_y=None,
                height=dp(72),
                font_size=dp(14),
                color=UI_TEXT_SECONDARY,
            )
            self.beds_container.add_widget(no_beds_label)
            self.beds_container.height = dp(72)
            return
        
        # Группировка по room_id
        beds_by_room = {}
        for bed in self.beds:
            room_id = bed.get('room_id')
            try:
                room_key = int(room_id) if room_id is not None else 0
            except Exception:
                room_key = 0
            beds_by_room.setdefault(room_key, []).append(bed)

        for room_key in sorted(beds_by_room.keys()):
            room_card = BoxLayout(
                orientation="vertical",
                size_hint_y=None,
                spacing=dp(5),
                padding=(dp(8), dp(7), dp(8), dp(8)),
            )
            room_card.bind(minimum_height=room_card.setter("height"))
            apply_rounded_panel(room_card, base_rgba=(0.145, 0.145, 0.155, 1), radius_px=dp(8), border_alpha=0.05)

            room_title = f"Комната {room_key}" if room_key > 0 else "Без комнаты"
            room_header = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(20),
                spacing=dp(6),
            )
            room_label = Label(
                text=room_title,
                size_hint=(1, None),
                height=dp(20),
                font_size=dp(12),
                bold=True,
                color=UI_TEXT_STRONG,
                halign='left',
                valign='middle',
                text_size=(0, 0),
            )
            room_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
            room_header.add_widget(room_label)

            room_count = len(beds_by_room[room_key])
            count_badge = Label(
                text=str(room_count),
                size_hint=(None, None),
                width=dp(28),
                height=dp(20),
                font_size=dp(10),
                color=UI_TEXT_PRIMARY,
                halign="center",
                valign="middle",
                text_size=(dp(28), dp(20)),
            )
            apply_rounded_panel(count_badge, base_rgba=(0.18, 0.18, 0.19, 1), radius_px=dp(6), border_alpha=0.05)
            room_header.add_widget(count_badge)
            room_card.add_widget(room_header)

            beds_grid = GridLayout(
                cols=self._get_room_grid_cols(),
                spacing=dp(6),
                size_hint_y=None,
                padding=(0, dp(1)),
            )
            beds_grid.bind(minimum_height=beds_grid.setter("height"))

            for bed in beds_by_room[room_key]:
                is_current = str(bed.get('id')) == str(self.current_bed_id)
                bed_button = Button(
                    text=('Текущая: ' if is_current else '') + str(bed['name']),
                    size_hint_y=None,
                    height=dp(40),
                    font_size=dp(12),
                    background_color=(0, 0, 0, 0),
                    background_normal='',
                    background_down='',
                    shorten=True,
                    shorten_from='right',
                    halign='center',
                    valign='middle',
                    text_size=(0, 0),
                )
                bed_button.color = UI_TEXT_PRIMARY
                apply_rounded_button(
                    bed_button,
                    base_rgba=self._btn_current if is_current else self._btn_base,
                    radius_px=dp(8),
                )
                bed_button.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0] - dp(10), s[1] - dp(6))))
                bed_button.bind(on_press=lambda instance, b=bed: self._on_bed_clicked(b))
                beds_grid.add_widget(bed_button)

            fillers = (beds_grid.cols - (room_count % beds_grid.cols)) % beds_grid.cols
            for _ in range(fillers):
                spacer = Widget(size_hint_y=None, height=dp(40))
                beds_grid.add_widget(spacer)

            room_card.add_widget(beds_grid)
            self.beds_container.add_widget(room_card)

        # Прокрутка в начало, чтобы был виден первый заголовок
        if hasattr(self, "scroll"):
            try:
                self.scroll.scroll_y = 1.0
            except Exception:
                pass
        
        # Обновляем метку текущей кровати
        self._update_current_label()
    
    def _on_bed_clicked(self, bed: Dict):
        """Обработчик клика на кровать"""
        if self.on_bed_selected:
            self.on_bed_selected(bed['id'], bed['name'])

        # В некоторых сценариях после выбора нужно пойти "вперед"
        if self.manager and self.next_screen_on_select and self.manager.has_screen(self.next_screen_on_select):
            self.manager.current = self.next_screen_on_select
            return

        # По умолчанию - возвращаемся назад
        self._on_back_clicked()
    
    def _on_back_clicked(self, *args):
        """Обработчик кнопки "Назад" - возврат на предыдущий экран"""
        if self.on_back:
            self.on_back()
            return

        if self.manager:
            if self.previous_screen:
                self.manager.current = self.previous_screen
            else:
                # Если предыдущий экран не указан, пытаемся вернуться на главный экран управления окнами
                if self.manager.has_screen('main_window_manager'):
                    self.manager.current = 'main_window_manager'
                else:
                    # Если главного экрана нет, возвращаемся на первый доступный экран окна
                    for screen in self.manager.screens:
                        if screen.name.startswith('monitor_window_'):
                            self.manager.current = screen.name
                            break



