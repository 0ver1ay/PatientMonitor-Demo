"""
Экран выбора временного диапазона
Отдельный экран с навигацией назад
"""
from typing import Callable, Optional

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
from utils.time_range import TimeRange
from utils.ui_style import (
    UI_BTN_DANGER,
    UI_BTN_SECONDARY,
    UI_BTN_SUCCESS,
    UI_CONTENT_PADDING_UNDER_TITLEBAR,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    UI_TEXT_STRONG,
    apply_rounded_button,
    apply_rounded_panel,
)


class TimeRangeSelectionScreen(Screen):
    """Экран для выбора временного диапазона"""

    _ULTRA_W = dp(520)
    _ULTRA_H = dp(420)
    _COMPACT_W = dp(640)
    _COMPACT_H = dp(540)
    
    def __init__(self, current_time_range: Optional[TimeRange] = None,
                 on_time_range_selected: Optional[Callable] = None, 
                 previous_screen: Optional[str] = None,
                 show_header_nav: bool = True,
                 **kwargs):
        """
        Инициализация экрана выбора временного диапазона
        
        Args:
            current_time_range: Текущий выбранный диапазон
            on_time_range_selected: Callback функция при выборе диапазона (time_range)
            previous_screen: Имя экрана, на который нужно вернуться
        """
        super().__init__(**kwargs)
        # Устанавливаем имя только если оно не было задано
        if 'name' not in kwargs:
            self.name = 'time_range_selection'
        self.current_time_range = current_time_range or TimeRange.get_default()
        self.on_time_range_selected = on_time_range_selected
        self.previous_screen = previous_screen
        self.show_header_nav = show_header_nav
        self._ranges_refresh_trigger = Clock.create_trigger(lambda _dt: self._update_ranges_list(), 0)
        self._esc_handler_bound = False
        self._range_btn_height = dp(40)
        self._range_btn_fs = dp(12)
        self._section_inner_spacing = dp(5)
        self._section_card_padding = (dp(8), dp(7), dp(8), dp(8))
        self._section_label_h = dp(20)
        self._section_label_fs = dp(12)
        self._range_grid_spacing = dp(6)
        self._last_layout_tier: int | None = None

        self._create_ui()
        self.bind(size=lambda *_args: self._on_screen_size_changed())

    def on_pre_enter(self, *args):
        self._bind_escape_handler()
        self._last_layout_tier = None
        Clock.schedule_once(lambda _dt: self._apply_responsive_layout(), 0)
        Clock.schedule_once(lambda _dt: self._schedule_ranges_refresh(), 0)
        return super().on_pre_enter(*args)

    def on_pre_leave(self, *args):
        self._unbind_escape_handler()
        return super().on_pre_leave(*args)
    
    def set_current_time_range(self, time_range: TimeRange):
        """Установка текущего выбранного диапазона"""
        self.current_time_range = time_range
        self._schedule_ranges_refresh()
    
    def set_on_time_range_selected(self, callback: Callable):
        """Установка callback функции при выборе диапазона"""
        self.on_time_range_selected = callback

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
    
    def _on_screen_size_changed(self) -> None:
        self._apply_responsive_layout()
        self._schedule_ranges_refresh()

    def _layout_tier(self) -> int:
        w = float(self.width or 0)
        h = float(self.height or 0)
        if w <= float(self._ULTRA_W) or h <= float(self._ULTRA_H):
            return 2
        if w <= float(self._COMPACT_W) or h <= float(self._COMPACT_H):
            return 1
        return 0

    def _apply_responsive_layout(self) -> None:
        tier = self._layout_tier()
        if tier == self._last_layout_tier:
            return
        self._last_layout_tier = tier

        if tier == 2:
            self._main_container.spacing = dp(4)
            self._main_container.padding = (
                (dp(8), dp(6), dp(8), dp(6)) if self.show_header_nav else (0, dp(6), 0, dp(8))
            )
            self._summary_card.spacing = dp(3)
            self._summary_card.padding = (dp(8), dp(6), dp(8), dp(6))
            tr_h, title_fs = dp(28), dp(14)
            back_w, back_fs = dp(72), dp(12)
            sub_h, sub_op = 0, 0.0
            cur_h, cur_fs = dp(24), dp(11)
            list_card_sp = dp(4)
            list_card_pad = (dp(6), dp(6), dp(6), dp(6))
            list_title_h, list_title_fs = dp(18), dp(11)
            self._range_btn_height = dp(34)
            self._range_btn_fs = dp(11)
            self._section_inner_spacing = dp(4)
            self._section_card_padding = (dp(6), dp(6), dp(6), dp(6))
            self._section_label_h = dp(17)
            self._section_label_fs = dp(11)
            self.scroll.bar_width = dp(6)
            self._range_grid_spacing = dp(4)
        elif tier == 1:
            self._main_container.spacing = dp(5)
            self._main_container.padding = (
                (dp(9), dp(8), dp(9), dp(8)) if self.show_header_nav else UI_CONTENT_PADDING_UNDER_TITLEBAR
            )
            self._summary_card.spacing = dp(4)
            self._summary_card.padding = (dp(10), dp(7), dp(10), dp(7))
            tr_h, title_fs = dp(30), dp(15)
            back_w, back_fs = dp(84), dp(12)
            sub_h, sub_op = dp(14), 1.0
            cur_h, cur_fs = dp(26), dp(11)
            list_card_sp = dp(5)
            list_card_pad = (dp(7), dp(7), dp(7), dp(7))
            list_title_h, list_title_fs = dp(20), dp(12)
            self._range_btn_height = dp(38)
            self._range_btn_fs = dp(12)
            self._section_inner_spacing = dp(5)
            self._section_card_padding = (dp(7), dp(7), dp(7), dp(7))
            self._section_label_h = dp(19)
            self._section_label_fs = dp(11)
            self.scroll.bar_width = dp(7)
            self._range_grid_spacing = dp(5)
        else:
            self._main_container.spacing = dp(6)
            self._main_container.padding = dp(10) if self.show_header_nav else UI_CONTENT_PADDING_UNDER_TITLEBAR
            self._summary_card.spacing = dp(4)
            self._summary_card.padding = (dp(10), dp(8), dp(10), dp(8))
            tr_h, title_fs = dp(32), dp(16)
            back_w, back_fs = dp(86), dp(13)
            sub_h, sub_op = dp(16), 1.0
            cur_h, cur_fs = dp(28), dp(12)
            list_card_sp = dp(6)
            list_card_pad = (dp(8), dp(8), dp(8), dp(8))
            list_title_h, list_title_fs = dp(22), dp(13)
            self._range_btn_height = dp(40)
            self._range_btn_fs = dp(12)
            self._section_inner_spacing = dp(5)
            self._section_card_padding = (dp(8), dp(7), dp(8), dp(8))
            self._section_label_h = dp(20)
            self._section_label_fs = dp(12)
            self.scroll.bar_width = dp(8)
            self._range_grid_spacing = dp(6)

        self._title_row.height = tr_h
        self._title_row.spacing = dp(6) if tier == 2 else dp(8)
        if self._title_label is not None:
            self._title_label.height = tr_h
            self._title_label.font_size = title_fs
        self._back_button.width = back_w
        self._back_button.height = tr_h
        self._back_button.font_size = back_fs

        self._subtitle_label.height = sub_h
        self._subtitle_label.opacity = sub_op
        self._subtitle_label.disabled = sub_op == 0
        if sub_op > 0:
            self._subtitle_label.font_size = dp(10) if tier == 1 else dp(11)

        self.current_label.height = cur_h
        self.current_label.font_size = cur_fs

        self._list_card.spacing = list_card_sp
        self._list_card.padding = list_card_pad
        self._list_title.height = list_title_h
        self._list_title.font_size = list_title_fs

    def _create_ui(self):
        """Создание пользовательского интерфейса"""
        self._btn_base = UI_BTN_SECONDARY
        self._btn_current = UI_BTN_SUCCESS
        self._btn_text = UI_TEXT_PRIMARY

        main_container = BoxLayout(
            orientation='vertical',
            spacing=dp(6),
            padding=dp(10) if self.show_header_nav else UI_CONTENT_PADDING_UNDER_TITLEBAR
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
                text='Выбор временного периода',
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
            self._title_label = title_label
        else:
            title_row.add_widget(Widget())
            self._title_label = None

        back_button = Button(
            text='Назад',
            size_hint_x=None,
            width=dp(86),
            height=dp(32),
            font_size=dp(13),
            background_color=(0, 0, 0, 0),
            background_normal='',
            background_down=''
        )
        back_button.color = self._btn_text
        apply_rounded_button(back_button, base_rgba=UI_BTN_DANGER, radius_px=dp(8))
        back_button.bind(on_press=self._on_back_clicked)
        title_row.add_widget(back_button)
        summary_card.add_widget(title_row)

        subtitle_label = Label(
            text='Выберите, за какой промежуток показывать данные',
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

        list_title = Label(
            text="Готовые периоды",
            size_hint_y=None,
            height=dp(22),
            font_size=dp(13),
            bold=True,
            color=UI_TEXT_STRONG,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        list_title.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        list_card.add_widget(list_title)

        self.scroll = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False,
            do_scroll_y=True,
            scroll_type=["content", "bars"],
            bar_width=dp(8),
            bar_color=(0.36, 0.36, 0.37, 0.85),
            bar_inactive_color=(0.24, 0.24, 0.25, 0.25),
        )
        self.ranges_container = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(6),
            padding=(0, 0, 0, dp(3)),
        )
        self.ranges_container.bind(minimum_height=self.ranges_container.setter("height"))
        self.scroll.add_widget(self.ranges_container)
        list_card.add_widget(self.scroll)
        main_container.add_widget(list_card)

        self._main_container = main_container
        self._summary_card = summary_card
        self._title_row = title_row
        self._back_button = back_button
        self._subtitle_label = subtitle_label
        self._list_card = list_card
        self._list_title = list_title

        self.add_widget(main_container)
        self._last_layout_tier = None
        self._apply_responsive_layout()
        self._update_ranges_list()

    def _schedule_ranges_refresh(self):
        try:
            self._ranges_refresh_trigger()
        except Exception:
            self._update_ranges_list()

    def _get_grid_cols(self) -> int:
        try:
            width = float(getattr(self, "width", 0) or 0)
            height = float(getattr(self, "height", 0) or 0)
        except Exception:
            width, height = 0.0, 0.0
        if height <= float(dp(400)):
            return 1
        if width <= float(dp(620)):
            return 1
        if width <= float(dp(980)):
            return 2
        if height <= float(dp(520)) and width <= float(dp(1100)):
            return 2
        return 3

    @staticmethod
    def _get_range_sections():
        all_ranges = TimeRange.get_all_ranges()
        return [
            ("Минуты", [tr for tr in all_ranges if tr.minutes < 60]),
            ("Часы", [tr for tr in all_ranges if tr.minutes >= 60]),
        ]
    
    def _update_current_label(self):
        """Обновление метки текущего диапазона"""
        if self.current_time_range:
            self.current_label.text = f'Сейчас выбрано: {self.current_time_range.label}'
        else:
            self.current_label.text = 'Период пока не выбран'
    
    def _update_ranges_list(self):
        """Обновление списка диапазонов"""
        self.ranges_container.clear_widgets()
        cols = self._get_grid_cols()

        for section_title, section_ranges in self._get_range_sections():
            if not section_ranges:
                continue

            section_card = BoxLayout(
                orientation="vertical",
                size_hint_y=None,
                spacing=self._section_inner_spacing,
                padding=self._section_card_padding,
            )
            section_card.bind(minimum_height=section_card.setter("height"))
            apply_rounded_panel(section_card, base_rgba=(0.145, 0.145, 0.155, 1), radius_px=dp(8), border_alpha=0.05)

            section_label = Label(
                text=section_title,
                size_hint_y=None,
                height=self._section_label_h,
                font_size=self._section_label_fs,
                bold=True,
                color=UI_TEXT_STRONG,
                halign="left",
                valign="middle",
                text_size=(0, None),
            )
            section_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
            section_card.add_widget(section_label)

            section_grid = GridLayout(
                cols=cols,
                spacing=self._range_grid_spacing,
                size_hint_y=None,
                padding=(0, dp(1)),
            )
            section_grid.bind(minimum_height=section_grid.setter("height"))

            for time_range in section_ranges:
                is_current = time_range == self.current_time_range
                range_button = Button(
                    text=('Текущий: ' if is_current else '') + time_range.label,
                    size_hint_y=None,
                    height=self._range_btn_height,
                    font_size=self._range_btn_fs,
                    background_color=(0, 0, 0, 0),
                    background_normal='',
                    background_down='',
                    shorten=True,
                    shorten_from='right',
                    halign='center',
                    valign='middle',
                    text_size=(0, 0),
                )
                range_button.color = self._btn_text
                apply_rounded_button(
                    range_button,
                    base_rgba=self._btn_current if is_current else self._btn_base,
                    radius_px=dp(8),
                )
                range_button.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0] - dp(10), s[1] - dp(6))))
                range_button.bind(on_press=lambda instance, tr=time_range: self._on_range_clicked(tr))
                section_grid.add_widget(range_button)

            fillers = (cols - (len(section_ranges) % cols)) % cols
            bh = self._range_btn_height
            for _ in range(fillers):
                section_grid.add_widget(Widget(size_hint_y=None, height=bh))

            section_card.add_widget(section_grid)
            self.ranges_container.add_widget(section_card)

        self._update_current_label()
    
    def _on_range_clicked(self, time_range: TimeRange):
        """Обработчик клика на диапазон"""
        if self.on_time_range_selected:
            self.on_time_range_selected(time_range)
        
        # Возвращаемся на главный экран
        self._on_back_clicked()
    
    def _on_back_clicked(self, *args):
        """Обработчик кнопки "Назад" - возврат на предыдущий экран"""
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

