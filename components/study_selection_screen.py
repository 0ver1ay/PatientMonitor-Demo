"""
Экран выбора Study (таблица study в PostgreSQL).

Используется в просмотрщике истории: можно выбрать конкретное study и
автоматически открыть историю по пациенту/кровати в пределах begin/end.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Callable, Dict, List, Optional

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from components.esc_back_navigation import EscBackNavigationMixin
from utils.popup_style import apply_popup_theme, style_scrollview_popup, style_text_input_dark
from utils.ui_style import (
    UI_CONTENT_PADDING_UNDER_TITLEBAR,
    UI_CURSOR_NEUTRAL,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    UI_TEXT_STRONG,
    apply_rounded_button,
    apply_rounded_panel,
)


class TableScrollView(ScrollView):
    """ScrollView for the study table that ignores middle-button drag."""

    @staticmethod
    def _is_middle_mouse_touch(touch) -> bool:
        return getattr(touch, "button", None) == "middle"

    def on_touch_down(self, touch):
        if self._is_middle_mouse_touch(touch) and self.collide_point(*touch.pos):
            return False
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self._is_middle_mouse_touch(touch):
            return False
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self._is_middle_mouse_touch(touch):
            return False
        return super().on_touch_up(touch)


class StudySelectionScreen(EscBackNavigationMixin, Screen):
    """Экран для выбора study записи."""

    def __init__(
        self,
        studies: Optional[List[Dict]] = None,
        current_study_id: Optional[int] = None,
        on_study_selected: Optional[Callable[[Dict], None]] = None,
        on_refresh: Optional[Callable[[], Optional[List[Dict]]]] = None,
        on_search_studies: Optional[Callable[[Dict[str, str]], Optional[List[Dict]]]] = None,
        on_open_study_id: Optional[Callable[[int], Optional[Dict]]] = None,
        beds_screen: Optional[str] = None,
        previous_screen: Optional[str] = None,
        next_screen_on_select: Optional[str] = None,
        on_back: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if "name" not in kwargs:
            self.name = "study_selection"
        self._init_esc_back_navigation()

        self.studies: List[Dict] = studies or []
        self.filtered_studies: List[Dict] = list(self.studies)
        self.current_study_id = current_study_id

        # Фильтр по датам (без клавиатуры)
        self.date_filter_from: datetime | None = None
        self.date_filter_to: datetime | None = None

        self.on_study_selected = on_study_selected
        self.on_refresh = on_refresh
        self.on_search_studies = on_search_studies
        self.on_open_study_id = on_open_study_id

        self.beds_screen = beds_screen
        self.previous_screen = previous_screen
        self.next_screen_on_select = next_screen_on_select
        self.on_back = on_back

        # Колонки большой таблицы (ключ, заголовок, ширина)
        self._table_columns = [
            ("study_id", "ID", dp(90)),
            ("study_numb", "№ Исследования", dp(170)),
            ("patient_name", "ФИО", dp(230)),
            ("bed_name", "Кровать", dp(180)),
            ("begin_dt", "Начало", dp(170)),
            ("descr", "Описание", dp(280)),
        ]
        self._table_columns_base = list(self._table_columns)
        self._table_total_width = sum(float(w) for _k, _t, w in self._table_columns) + dp(1) * (len(self._table_columns) - 1)
        self._table_reflow_trigger = Clock.create_trigger(self._reflow_table_width, 0)
        self._search_trigger = Clock.create_trigger(self._run_debounced_search, 0.4)
        self.results_count_badge: Label | None = None
        self._header_row_height = dp(46)
        self._filter_row_height = dp(50)
        self._row_height = dp(42)
        self._table_section_gap = dp(6)
        self._header_filter_overlap = dp(9)
        self._filter_shell_pad_x = dp(0)
        self._filter_shell_pad_y = dp(0)
        self._filter_column_gap = dp(1)
        self._syncing_table_scroll_x = False
        self._table_card_max_width = dp(1700)
        self._table_card_min_width = dp(0)
        self._table_descr_extra_cap = dp(520)
        self._table_status_mode = "ready"
        self._table_status_message = ""
        self._table_layout_mode = "wide"

        self._create_ui()

    def set_table_status(self, mode: str, message: str = "") -> None:
        """Режимы: loading | empty | error | ready."""
        self._table_status_mode = str(mode or "ready")
        self._table_status_message = str(message or "")
        if self._table_status_mode != "ready":
            self.studies = []
            self.filtered_studies = []
            self._update_current_label()
            self._update_studies_list()

    def set_studies(self, studies: List[Dict]):
        self._table_status_mode = "ready"
        self._table_status_message = ""
        self.studies = studies or []
        self.filtered_studies = list(self.studies)
        self._update_current_label()
        self._apply_filter()

    def set_current_study_id(self, study_id: Optional[int]):
        self.current_study_id = study_id
        self._update_current_label()
        self._apply_filter()

    def set_on_study_selected(self, callback: Callable[[Dict], None]):
        self.on_study_selected = callback

    def set_on_refresh(self, callback: Callable[[], Optional[List[Dict]]]):
        self.on_refresh = callback

    def set_on_search_studies(self, callback: Callable[[Dict[str, str]], Optional[List[Dict]]]):
        self.on_search_studies = callback

    def set_on_open_study_id(self, callback: Callable[[int], Optional[Dict]]):
        self.on_open_study_id = callback
    
    def set_beds_screen(self, screen_name: Optional[str]):
        self.beds_screen = screen_name

    def _replace_managed_screen(self, screen) -> bool:
        if self.manager is None:
            return False
        try:
            if self.manager.has_screen(screen.name):
                existing = self.manager.get_screen(screen.name)
                self.manager.remove_widget(existing)
            self.manager.add_widget(screen)
            self.manager.current = screen.name
            return True
        except Exception:
            return False

    def _create_ui(self):
        # Заголовок экрана — в CustomTitleBar (run_bed_viewer); здесь только таблица на всю высоту.
        main_container = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
            padding=UI_CONTENT_PADDING_UNDER_TITLEBAR,
        )

        self.back_button = None

        # Deprecated блоки (текущий study / open by id / глобальный поиск / фильтр дат) убраны.

        self.table_card = BoxLayout(
            orientation="vertical",
            size_hint=(None, 1),
            width=dp(1320),
            spacing=dp(12),
            padding=(dp(12), dp(12), dp(12), dp(12)),
        )
        apply_rounded_panel(self.table_card, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(12), border_alpha=0.06)

        table_header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(34),
            spacing=dp(8),
        )
        table_title = Label(
            text="Список исследований",
            size_hint=(1, None),
            height=dp(34),
            font_size=dp(15),
            bold=True,
            color=UI_TEXT_STRONG,
            halign="left",
            valign="middle",
            text_size=(None, None),
        )
        table_title.bind(size=table_title.setter("text_size"))
        table_header.add_widget(table_title)

        self.results_count_badge = Label(
            text="0",
            size_hint=(None, None),
            width=dp(42),
            height=dp(30),
            font_size=dp(12),
            color=UI_TEXT_PRIMARY,
            halign="center",
            valign="middle",
            text_size=(dp(42), dp(30)),
        )
        apply_rounded_panel(self.results_count_badge, base_rgba=(0.18, 0.18, 0.19, 1), radius_px=dp(8), border_alpha=0.05)
        table_header.add_widget(self.results_count_badge)
        self.table_card.add_widget(table_header)

        table_shell = BoxLayout(
            orientation="vertical",
            size_hint=(1, 1),
            spacing=self._table_section_gap,
        )

        self.table_header_scroll = ScrollView(
            size_hint=(1, None),
            height=self._get_header_stack_height(),
            do_scroll_x=True,
            do_scroll_y=False,
            scroll_type=["content"],
            bar_width=0,
            bar_color=(0, 0, 0, 0),
            bar_inactive_color=(0, 0, 0, 0),
        )
        self.table_rows_scroll = TableScrollView(
            size_hint=(1, 1),
            do_scroll_x=True,
            do_scroll_y=True,
            scroll_type=["content", "bars"],
            bar_width=dp(16),
            bar_color=(0.36, 0.36, 0.37, 0.85),
            bar_inactive_color=(0.24, 0.24, 0.25, 0.25),
        )
        style_scrollview_popup(self.table_header_scroll)
        style_scrollview_popup(self.table_rows_scroll)
        self.table_header_content = BoxLayout(
            orientation="vertical",
            spacing=0,
            size_hint=(None, None),
            width=self._table_total_width,
            height=self._get_header_stack_height(),
        )
        self.header_stack = FloatLayout(
            size_hint=(None, None),
            width=self._table_total_width,
            height=self._get_header_stack_height(),
        )
        self.header_shell = BoxLayout(
            orientation="vertical",
            size_hint=(None, None),
            width=self._table_total_width,
            height=self._header_row_height,
        )
        apply_rounded_panel(self.header_shell, base_rgba=(0.16, 0.16, 0.17, 1), radius_px=dp(10), border_alpha=0.04)
        self.header_grid = GridLayout(
            cols=len(self._table_columns),
            size_hint=(None, None),
            width=self._table_total_width,
            height=self._header_row_height,
            row_default_height=self._header_row_height,
            row_force_default=True,
            spacing=dp(1),
        )
        self.header_shell.add_widget(self.header_grid)

        # Column filters row
        self.filter_shell = BoxLayout(
            orientation="vertical",
            size_hint=(None, None),
            width=self._table_total_width,
            height=self._filter_row_height,
            padding=(
                self._filter_shell_pad_x,
                self._filter_shell_pad_y,
                self._filter_shell_pad_x,
                self._filter_shell_pad_y,
            ),
        )
        apply_rounded_panel(self.filter_shell, base_rgba=(0.14, 0.14, 0.15, 1), radius_px=dp(10), border_alpha=0.04)
        self.filter_grid = GridLayout(
            cols=len(self._table_columns),
            size_hint=(None, None),
            width=self._table_total_width - self._filter_shell_pad_x * 2,
            height=self._filter_row_height - self._filter_shell_pad_y * 2,
            row_default_height=self._filter_row_height - self._filter_shell_pad_y * 2,
            row_force_default=True,
            spacing=self._filter_column_gap,
        )
        self.filter_shell.add_widget(self.filter_grid)
        self.header_stack.add_widget(self.filter_shell)
        self.header_stack.add_widget(self.header_shell)
        self.table_header_content.add_widget(self.header_stack)
        self._layout_header_stack()

        self.rows_grid = GridLayout(
            cols=1,
            spacing=dp(1),
            size_hint=(None, None),
            width=self._table_total_width,
        )
        self.rows_grid.bind(minimum_height=self.rows_grid.setter("height"))
        self.table_header_scroll.add_widget(self.table_header_content)
        self.table_rows_scroll.add_widget(self.rows_grid)
        self.table_header_scroll.bind(scroll_x=self._sync_table_scroll_from_header)
        self.table_rows_scroll.bind(scroll_x=self._sync_table_scroll_from_rows)
        table_shell.add_widget(self.table_header_scroll)
        table_shell.add_widget(self.table_rows_scroll)
        self.table_card.add_widget(table_shell)

        self.table_card_host = BoxLayout(
            orientation="horizontal",
            size_hint=(1, 1),
            padding=(dp(8), 0, dp(8), 0),
        )
        self.table_card_host.add_widget(Widget(size_hint_x=1))
        self.table_card_host.add_widget(self.table_card)
        self.table_card_host.add_widget(Widget(size_hint_x=1))
        main_container.add_widget(self.table_card_host)

        self.table_card_host.bind(size=lambda *_: self._update_table_card_width())
        self.bind(size=lambda *_: self._update_table_card_width())
        self.table_header_scroll.bind(size=lambda *_: self._table_reflow_trigger())
        self.table_rows_scroll.bind(size=lambda *_: self._table_reflow_trigger())

        self._build_table_header_and_filters()
        self._update_table_card_width()
        self._table_reflow_trigger()

        self.add_widget(main_container)
        self._update_studies_list()
        self._sync_back_button_text()

    def _apply_table_button_style(self, btn: Button, base_rgba=(0.22, 0.22, 0.24, 1.0)):
        """Единый стиль кнопок под палитру таблицы (как bed_viewer)."""
        btn.color = UI_TEXT_PRIMARY
        apply_rounded_button(btn, base_rgba=base_rgba)

    def on_pre_enter(self, *args):
        # При повторном входе на экран (например, из монитора) логика "Назад/Выход" может меняться.
        self._bind_escape_handler()
        self._sync_back_button_text()
        return super().on_pre_enter(*args)

    def on_pre_leave(self, *args):
        self._unbind_escape_handler()
        return super().on_pre_leave(*args)

    def _sync_back_button_text(self):
        """Если кнопка 'Назад' фактически закрывает приложение — показываем 'Выход'."""
        if not hasattr(self, "back_button") or self.back_button is None:
            return
        try:
            can_go_back = bool(self.manager and self.previous_screen and self.manager.has_screen(self.previous_screen))
        except Exception:
            can_go_back = False

        if (not can_go_back) and self.on_back:
            self.back_button.text = "Выход"
        else:
            self.back_button.text = "Назад"

    def _update_current_label(self):
        if not hasattr(self, "current_label"):
            return
        if self.current_study_id:
            self.current_label.text = f"Текущий Study: #{self.current_study_id}"
        else:
            self.current_label.text = "Study не выбран"

    def _get_header_stack_height(self) -> float:
        return self._header_row_height + self._filter_row_height - self._header_filter_overlap

    def _layout_header_stack(self) -> None:
        if not hasattr(self, "header_stack"):
            return

        stack_height = self._get_header_stack_height()
        self.header_stack.width = self._table_total_width
        self.header_stack.height = stack_height
        self.header_shell.width = self._table_total_width
        self.header_shell.pos = (0, stack_height - self._header_row_height)
        self.filter_shell.width = self._table_total_width
        self.filter_shell.pos = (0, 0)

    def _table_layout_mode_for_width(self, width: float) -> str:
        if width <= 1100:
            return "ultra"
        if width <= 1360:
            return "compact"
        return "wide"

    def _responsive_table_columns(self, mode: str) -> list:
        scale = {
            "ultra": {
                "study_id": dp(70),
                "study_numb": dp(120),
                "patient_name": dp(150),
                "bed_name": dp(110),
                "begin_dt": dp(110),
                "descr": dp(0),
            },
            "compact": {
                "study_id": dp(80),
                "study_numb": dp(140),
                "patient_name": dp(180),
                "bed_name": dp(140),
                "begin_dt": dp(140),
                "descr": dp(180),
            },
        }.get(mode, {})
        cols = []
        for key, title, width in self._table_columns_base:
            if mode == "ultra" and key == "descr":
                continue
            cols.append((key, title, float(scale.get(key, width))))
        return cols

    def _reflow_table_width(self, *_args):
        """Растянуть таблицу на ширину окна с адаптивными колонками."""
        if not hasattr(self, "table_rows_scroll"):
            return
        viewport_w = max(
            1.0,
            min(float(self.table_header_scroll.width), float(self.table_rows_scroll.width)) - dp(6),
        )
        mode = self._table_layout_mode_for_width(float(self.width or viewport_w))
        self._table_layout_mode = mode
        if mode == "ultra":
            self._row_height = dp(38)
            self._header_row_height = dp(40)
            self._filter_row_height = dp(44)
        elif mode == "compact":
            self._row_height = dp(40)
            self._header_row_height = dp(42)
            self._filter_row_height = dp(46)
        else:
            self._row_height = dp(42)
            self._header_row_height = dp(46)
            self._filter_row_height = dp(50)

        base_cols = self._responsive_table_columns(mode)
        base_w = sum(float(w) for _k, _t, w in base_cols) + dp(1) * max(0, len(base_cols) - 1)
        extra = 0.0
        if mode != "ultra":
            extra = min(max(0.0, viewport_w - base_w), float(self._table_descr_extra_cap))

        cols = []
        for key, title, w in base_cols:
            if key == "descr":
                cols.append((key, title, float(w) + extra))
            else:
                cols.append((key, title, float(w)))
        self._table_columns = cols
        self._table_total_width = sum(float(w) for _k, _t, w in cols) + dp(1) * max(0, len(cols) - 1)

        # Сохраним введённые фильтры по колонкам перед перестроением.
        saved_filters = {}
        if hasattr(self, "column_filter_inputs"):
            for key, inp in self.column_filter_inputs.items():
                saved_filters[key] = inp.text

        self.table_header_content.width = self._table_total_width
        self.table_header_scroll.height = self._get_header_stack_height()
        self.table_header_content.height = self._get_header_stack_height()
        self.header_stack.width = self._table_total_width
        self.header_stack.height = self._get_header_stack_height()
        self.header_shell.width = self._table_total_width
        self.header_grid.width = self._table_total_width
        self.filter_shell.width = self._table_total_width
        self.filter_grid.width = max(1.0, self._table_total_width - self._filter_shell_pad_x * 2)
        self.rows_grid.width = self._table_total_width
        self._layout_header_stack()
        self._build_table_header_and_filters()

        if hasattr(self, "column_filter_inputs"):
            for key, val in saved_filters.items():
                if key in self.column_filter_inputs:
                    self.column_filter_inputs[key].text = val

        self._apply_filter()

    def _update_table_card_width(self) -> None:
        if not hasattr(self, "table_card_host") or not hasattr(self, "table_card"):
            return
        try:
            host_w = float(self.table_card_host.width or 0)
        except Exception:
            host_w = 0.0
        if host_w <= 1:
            return
        avail_w = max(1.0, host_w - float(dp(16)))
        target_w = min(float(self._table_card_max_width), avail_w)
        target_w = max(float(self._table_card_min_width), target_w)
        self.table_card.width = min(target_w, avail_w)
        self._table_reflow_trigger()

    def _fmt_dt(self, dt: datetime) -> str:
        try:
            return dt.strftime("%d.%m.%Y %H:%M:%S")
        except Exception:
            return str(dt)

    def _format_study_label(self, s: Dict) -> str:
        sid = s.get("study_id") or s.get("session_id") or s.get("worklist_id") or s.get("id")
        study_numb = s.get("study_numb") or s.get("study_number") or s.get("numb")
        patient_id = s.get("patient_id")
        bed_name = (s.get("bed_name") or "").strip()
        bed_id = s.get("bed_id")
        bdt = s.get("begin_dt")
        edt = s.get("end_dt")
        descr = (s.get("descr") or s.get("description") or "").strip()

        parts = [f"#{sid}"]
        if study_numb:
            parts.append(str(study_numb))
        if patient_id:
            parts.append(f"Пациент {patient_id}")
        if bed_name:
            parts.append(f"Кровать {bed_name}")
        elif bed_id is not None:
            parts.append(f"Кровать {bed_id}")
        if bdt:
            parts.append(self._fmt_dt(bdt))
        if descr:
            parts.append(descr)
        return " | ".join(parts)

    def _get_cell_value(self, s: Dict, key: str):
        if key == "study_id":
            return s.get("study_id") or s.get("session_id") or s.get("worklist_id") or s.get("id")
        if key == "study_numb":
            return s.get("study_numb") or s.get("study_number") or s.get("numb")
        if key == "patient_name":
            # Если ФИО не пришло из БД, оставим пусто (будет поискаться по ID в соседней колонке).
            return s.get("patient_name") or ""
        if key == "bed_name":
            return s.get("bed_name") or s.get("bed_id")
        if key == "begin_dt":
            return s.get("begin_dt")
        if key == "descr":
            return (s.get("descr") or s.get("description") or "").strip()
        return s.get(key)

    def _format_cell_value(self, key: str, val) -> str:
        if val is None:
            return ""
        if key == "begin_dt":
            if isinstance(val, datetime):
                if getattr(self, "_table_layout_mode", "wide") == "ultra":
                    try:
                        return val.strftime("%d.%m %H:%M")
                    except Exception:
                        return str(val)
                return self._fmt_dt(val)
            return str(val)
        return str(val)

    def _build_table_header_and_filters(self):
        self.header_grid.clear_widgets()
        self.filter_grid.clear_widgets()
        self.column_filter_inputs: Dict[str, TextInput] = {}
        self.header_grid.height = self._header_row_height
        self.header_shell.height = self._header_row_height
        self.filter_shell.height = self._filter_row_height
        self.filter_grid.height = self._filter_row_height - self._filter_shell_pad_y * 2
        self._layout_header_stack()

        last_idx = len(self._table_columns) - 1
        for idx, (key, title, col_w) in enumerate(self._table_columns):
            h = Label(
                text=title,
                size_hint=(None, None),
                width=col_w,
                height=self._header_row_height,
                font_size=dp(13),
                bold=True,
                color=UI_TEXT_STRONG,
                halign="left",
                valign="middle",
                shorten=True,
                shorten_from="right",
                text_size=(col_w - dp(16), self._header_row_height),
            )
            self._style_vertical_divider(h, show_right_divider=(idx < last_idx), inset_y=dp(8), alpha=0.08)
            self.header_grid.add_widget(h)

            inp = TextInput(
                multiline=False,
                hint_text="Поиск",
                size_hint=(None, None),
                width=col_w,
                height=self._filter_row_height - self._filter_shell_pad_y * 2,
                font_size=dp(13),
            )
            style_text_input_dark(inp)
            inp.background_normal = ""
            inp.background_active = ""
            inp.background_color = (0, 0, 0, 0)
            inp.foreground_color = UI_TEXT_STRONG
            inp.hint_text_color = UI_TEXT_MUTED
            inp.cursor_color = UI_CURSOR_NEUTRAL
            inp.font_size = dp(13)
            # TextInput рисует одну строку у верха внутренней области; симметричный
            # padding по вертикали центрирует текст и hint относительно высоты ячейки.
            _inner_h = float(self._filter_row_height - self._filter_shell_pad_y * 2)
            _line_est = float(dp(13)) * 1.32
            _pad_y = max(float(dp(4)), (_inner_h - _line_est) * 0.5)
            inp.padding = (dp(10), _pad_y, dp(10), _pad_y)
            inp._pm_default_hint = "Поиск"
            self._style_vertical_divider(inp, show_right_divider=(idx < last_idx), inset_y=dp(8), alpha=0.06)
            inp.bind(focus=self._on_filter_input_focus)
            inp.bind(text=lambda *_: self._on_filter_input_changed())
            self.column_filter_inputs[key] = inp
            self.filter_grid.add_widget(inp)

    def _style_vertical_divider(self, widget, *, show_right_divider: bool, inset_y: float, alpha: float) -> None:
        if not show_right_divider:
            return

        with widget.canvas.after:
            widget._pm_filter_divider_color = Color(1, 1, 1, alpha)
            widget._pm_filter_divider = Line(points=[0, 0, 0, 0], width=dp(1))

        def _update_divider(*_args):
            x = widget.right
            top = widget.top - inset_y
            bottom = widget.y + inset_y
            widget._pm_filter_divider.points = [x, bottom, x, top]

        widget.bind(pos=_update_divider, size=_update_divider)
        _update_divider()

    def _sync_table_scroll_from_header(self, _inst, value: float) -> None:
        if self._syncing_table_scroll_x:
            return
        self._syncing_table_scroll_x = True
        try:
            self.table_rows_scroll.scroll_x = value
        finally:
            self._syncing_table_scroll_x = False

    def _sync_table_scroll_from_rows(self, _inst, value: float) -> None:
        if self._syncing_table_scroll_x:
            return
        self._syncing_table_scroll_x = True
        try:
            self.table_header_scroll.scroll_x = value
        finally:
            self._syncing_table_scroll_x = False

    def _on_filter_input_focus(self, inp: TextInput, focused: bool):
        default_hint = getattr(inp, "_pm_default_hint", "Поиск")
        if focused:
            inp.hint_text = ""
        elif not (inp.text or "").strip():
            inp.hint_text = default_hint

    def _get_column_filters(self) -> Dict[str, str]:
        column_filters: Dict[str, str] = {}
        if hasattr(self, "column_filter_inputs"):
            for key, inp in self.column_filter_inputs.items():
                txt = (inp.text or "").strip().lower()
                if txt:
                    column_filters[key] = txt
        return column_filters

    def _on_filter_input_changed(self):
        if self.on_search_studies:
            self._search_trigger()
        else:
            self._apply_filter()

    def _refresh_recent_studies(self):
        if not self.on_refresh:
            self.filtered_studies = list(self.studies)
            self._update_studies_list()
            return
        self._table_status_mode = "loading"
        self._table_status_message = "Загрузка исследований…"
        self._update_studies_list()
        try:
            studies = self.on_refresh()
            if isinstance(studies, list):
                self.set_studies(studies)
                if not studies:
                    self.set_table_status("empty", "Нет доступных исследований")
            else:
                self.set_table_status("error", "Не удалось загрузить исследования")
        except Exception as exc:
            self.set_table_status(
                "error",
                f"Не удалось загрузить данные · проверьте подключение к БД ({exc})",
            )

    def _run_debounced_search(self, *_args):
        if not self.on_search_studies:
            self._apply_filter()
            return

        column_filters = self._get_column_filters()
        if not column_filters:
            self._refresh_recent_studies()
            return

        self._table_status_mode = "loading"
        self._table_status_message = "Поиск исследований…"
        self._update_studies_list()
        try:
            studies = self.on_search_studies(column_filters)
            if isinstance(studies, list):
                self.set_studies(studies)
                if not studies:
                    self.set_table_status("empty", "Нет исследований по выбранным фильтрам")
            else:
                self.set_table_status("error", "Не удалось выполнить поиск")
        except Exception as exc:
            self.set_table_status(
                "error",
                f"Ошибка поиска · проверьте подключение к БД ({exc})",
            )

    def _sync_date_filter_ui(self):
        def fmt(d: datetime | None, prefix: str) -> str:
            if not d:
                return f"{prefix}: не задано"
            try:
                return f"{prefix}: {d.strftime('%d.%m.%Y')}"
            except Exception:
                return f"{prefix}: {d}"

        if hasattr(self, "date_from_btn"):
            self.date_from_btn.text = fmt(self.date_filter_from, "С")
        if hasattr(self, "date_to_btn"):
            self.date_to_btn.text = fmt(self.date_filter_to, "По")

    def _apply_filter(self):
        column_filters = self._get_column_filters()

        out: List[Dict] = []
        for s in self.studies:
            bad_col = False
            for key, needle in column_filters.items():
                val_txt = self._format_cell_value(key, self._get_cell_value(s, key)).lower()
                if key == "study_id":
                    # Для study ID оставляем точное совпадение.
                    if val_txt != needle:
                        bad_col = True
                        break
                else:
                    # Для остальных колонок — поиск по вхождению.
                    if needle not in val_txt:
                        bad_col = True
                        break
            if bad_col:
                continue

            out.append(s)

        self.filtered_studies = out
        self._update_studies_list()

    def _clear_date_filter(self, *args):
        self.date_filter_from = None
        self.date_filter_to = None
        self._sync_date_filter_ui()
        self._apply_filter()

    def _open_date_picker(self, target: str):
        """
        Открыть календарь для выбора даты без клавиатуры.
        target: "from" | "to"
        """
        if self.manager is not None:
            try:
                from components.calendar_picker_screen import CalendarPickerScreen

                current_dt = self.date_filter_from if target == "from" else self.date_filter_to
                picker = CalendarPickerScreen(
                    name=f"{self.name}_{target}_date_picker",
                    title_text="Дата начала фильтра" if target == "from" else "Дата конца фильтра",
                    subtitle_text="Выберите дату для фильтра исследований",
                    previous_screen=self.name,
                    initial_date=current_dt.date() if isinstance(current_dt, datetime) else date.today(),
                    range_start=self.date_filter_from.date() if isinstance(self.date_filter_from, datetime) else None,
                    range_end=self.date_filter_to.date() if isinstance(self.date_filter_to, datetime) else None,
                    on_select=lambda picked_date, tgt=target: self._apply_date_filter_target(tgt, picked_date),
                    on_clear=lambda tgt=target: self._clear_date_filter_target(tgt),
                )
                if self._replace_managed_screen(picker):
                    return
            except Exception:
                pass

        import calendar as _cal
        from kivy.uix.anchorlayout import AnchorLayout

        cal = _cal.Calendar(firstweekday=_cal.MONDAY)
        month_names = [
            "Январь",
            "Февраль",
            "Март",
            "Апрель",
            "Май",
            "Июнь",
            "Июль",
            "Август",
            "Сентябрь",
            "Октябрь",
            "Ноябрь",
            "Декабрь",
        ]
        week_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

        base_dt = self.date_filter_from if target == "from" else self.date_filter_to
        base_d = base_dt.date() if isinstance(base_dt, datetime) else date.today()
        state = {"year": int(base_d.year), "month": int(base_d.month)}

        # Центрируем календарь внутри попапа и ограничиваем максимальную ширину,
        # чтобы на больших разрешениях верстка не "разъезжалась".
        root = AnchorLayout(anchor_x="center", anchor_y="center")
        content = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(14),
            size_hint=(None, None),
        )
        content.bind(minimum_height=content.setter("height"))
        apply_rounded_panel(content, base_rgba=(0.11, 0.11, 0.12, 1), radius_px=dp(12), border_alpha=0.12)
        root.add_widget(content)

        # Header (месяц + навигация)
        header = BoxLayout(
            orientation="horizontal",
            spacing=dp(8),
            size_hint_y=None,
            height=dp(52),
        )
        btn_prev = Button(
            text="<",
            size_hint_x=None,
            width=dp(56),
            font_size=dp(20),
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
        )
        btn_prev.color = UI_TEXT_PRIMARY
        apply_rounded_button(btn_prev, base_rgba=(0.22, 0.22, 0.24, 1))
        btn_next = Button(
            text=">",
            size_hint_x=None,
            width=dp(56),
            font_size=dp(20),
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
        )
        btn_next.color = UI_TEXT_PRIMARY
        apply_rounded_button(btn_next, base_rgba=(0.22, 0.22, 0.24, 1))
        title = Label(
            text="",
            font_size=dp(16),
            bold=True,
            color=UI_TEXT_STRONG,
            halign="center",
            valign="middle",
            text_size=(0, 0),
        )
        title.bind(size=lambda inst, s: setattr(inst, "text_size", s))
        header.add_widget(btn_prev)
        header.add_widget(title)  # растягивается, кнопки остаются фиксированными
        header.add_widget(btn_next)
        content.add_widget(header)

        # Grid
        grid = GridLayout(
            cols=7,
            spacing=dp(6),
            padding=(dp(6), dp(6)),
            size_hint_y=None,
            size_hint_x=1,
            row_default_height=dp(40),
            row_force_default=True,
        )
        content.add_widget(grid)

        # Footer
        footer = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(44))

        def _foot_btn(txt, rgba):
            b = Button(
                text=txt,
                background_color=(0, 0, 0, 0),
                background_normal="",
                background_down="",
                size_hint_x=1,
            )
            b.color = UI_TEXT_STRONG
            apply_rounded_button(b, base_rgba=rgba)
            return b

        btn_today = _foot_btn("Сегодня", (0.22, 0.48, 0.40, 1))
        btn_clear = _foot_btn("Очистить", (0.52, 0.30, 0.28, 1))
        btn_close = _foot_btn("Закрыть", (0.22, 0.22, 0.24, 1))
        footer.add_widget(btn_today)
        footer.add_widget(btn_clear)
        footer.add_widget(btn_close)
        content.add_widget(footer)

        # Убираем встроенную шапку Popup: она мешает верстке и "съедает" место сверху.
        popup = Popup(
            title="",
            separator_height=0,
            content=root,
            size_hint=(0.92, 0.84),
        )
        apply_popup_theme(popup)

        def _sync_width(*_args):
            # ограничиваем ширину календаря, чтобы не растягивался "на весь экран"
            avail = max(1.0, float(root.width) - float(dp(40)))
            content.width = min(avail, float(dp(900)))

        root.bind(size=_sync_width)

        def _get_selected_date(dt: datetime | None) -> date | None:
            if not isinstance(dt, datetime):
                return None
            try:
                return dt.date()
            except Exception:
                return None

        def refresh():
            grid.clear_widgets()
            title.text = f"{month_names[state['month'] - 1]} {state['year']}"

            # weekday header
            for wn in week_names:
                grid.add_widget(
                    Label(
                        text=wn,
                        font_size=dp(12),
                        color=UI_TEXT_MUTED,
                        bold=True,
                    )
                )

            # compute range highlights (if both set)
            d_from = _get_selected_date(self.date_filter_from)
            d_to = _get_selected_date(self.date_filter_to)
            if d_from and d_to and d_from > d_to:
                d_from, d_to = d_to, d_from

            weeks = cal.monthdayscalendar(state["year"], state["month"])
            while len(weeks) < 6:
                weeks.append([0] * 7)

            for week in weeks:
                for day in week:
                    if day == 0:
                        grid.add_widget(
                            Button(
                                text="",
                                disabled=True,
                                background_normal="",
                                background_down="",
                                background_color=(0, 0, 0, 0),
                            )
                        )
                        continue

                    d = date(state["year"], state["month"], int(day))
                    is_sel_from = d_from is not None and d == d_from
                    is_sel_to = d_to is not None and d == d_to
                    in_range = False
                    if d_from and d_to:
                        in_range = d_from <= d <= d_to

                    bg = (0.25, 0.25, 0.27, 1)
                    if in_range:
                        bg = (0.30, 0.30, 0.34, 1)
                    if is_sel_from or is_sel_to:
                        bg = (0.2, 0.7, 0.2, 1)

                    b = Button(
                        text=str(day),
                        background_normal="",
                        background_down="",
                        background_color=(0, 0, 0, 0),
                        font_size=dp(14),
                    )
                    b.color = UI_TEXT_PRIMARY
                    apply_rounded_button(b, base_rgba=bg)

                    def select_day(_inst, dd=d):
                        if target == "from":
                            self.date_filter_from = datetime(dd.year, dd.month, dd.day, 0, 0, 0)
                        else:
                            self.date_filter_to = datetime(dd.year, dd.month, dd.day, 23, 59, 59)
                        self._sync_date_filter_ui()
                        self._apply_filter()
                        popup.dismiss()

                    b.bind(on_press=select_day)
                    grid.add_widget(b)

            # 7 строк (заголовок + 6 недель)
            rows = 7
            grid.height = rows * dp(40) + (rows - 1) * dp(6) + dp(12)

        def change_month(delta: int):
            m = state["month"] + delta
            y = state["year"]
            if m < 1:
                m = 12
                y -= 1
            elif m > 12:
                m = 1
                y += 1
            state["month"] = m
            state["year"] = y
            refresh()

        btn_prev.bind(on_press=lambda *_: change_month(-1))
        btn_next.bind(on_press=lambda *_: change_month(1))
        btn_today.bind(on_press=lambda *_: (popup.dismiss(), self._set_date_filter_today(target)))
        btn_clear.bind(on_press=lambda *_: (popup.dismiss(), self._clear_date_filter_target(target)))
        btn_close.bind(on_press=lambda *_: popup.dismiss())

        refresh()
        _sync_width()
        popup.open()

    def _apply_date_filter_target(self, target: str, picked_date: date):
        if target == "from":
            self.date_filter_from = datetime(picked_date.year, picked_date.month, picked_date.day, 0, 0, 0)
        else:
            self.date_filter_to = datetime(picked_date.year, picked_date.month, picked_date.day, 23, 59, 59)
        self._sync_date_filter_ui()
        self._apply_filter()

    def _set_date_filter_today(self, target: str):
        d = date.today()
        if target == "from":
            self.date_filter_from = datetime(d.year, d.month, d.day, 0, 0, 0)
        else:
            self.date_filter_to = datetime(d.year, d.month, d.day, 23, 59, 59)
        self._sync_date_filter_ui()
        self._apply_filter()

    def _clear_date_filter_target(self, target: str):
        if target == "from":
            self.date_filter_from = None
        else:
            self.date_filter_to = None
        self._sync_date_filter_ui()
        self._apply_filter()

    def _update_studies_list(self):
        self.rows_grid.clear_widgets()
        studies = self.filtered_studies if hasattr(self, "filtered_studies") else self.studies
        if self.results_count_badge is not None:
            if self._table_status_mode == "loading":
                self.results_count_badge.text = "…"
            else:
                self.results_count_badge.text = str(len(studies))
        if self._table_status_mode in {"loading", "error", "empty"} or not studies:
            if self._table_status_mode == "loading":
                empty_text = self._table_status_message or "Загрузка исследований…"
            elif self._table_status_mode == "error":
                empty_text = self._table_status_message or "Не удалось загрузить данные"
            elif self._table_status_mode == "empty":
                empty_text = self._table_status_message or "Нет доступных исследований"
            else:
                empty_text = "Нет доступных исследований"
            lbl = Label(
                text=empty_text,
                size_hint_y=None,
                size_hint_x=None,
                width=self._table_total_width,
                height=dp(72),
                font_size=dp(15),
                color=UI_TEXT_MUTED,
                halign="center",
                valign="middle",
                text_size=(self._table_total_width - dp(24), dp(72)),
            )
            self.rows_grid.add_widget(lbl)
            self.rows_grid.height = dp(72)
            return

        row_h = self._row_height
        total_h = 0
        for row_idx, s in enumerate(studies):
            sid = s.get("study_id") or s.get("session_id") or s.get("worklist_id") or s.get("id")
            is_current = self.current_study_id is not None and str(sid) == str(self.current_study_id)
            base_rgba = (0.22, 0.33, 0.27, 1) if is_current else ((0.135, 0.135, 0.145, 1) if row_idx % 2 == 0 else (0.155, 0.155, 0.165, 1))

            row = GridLayout(
                cols=len(self._table_columns),
                size_hint=(None, None),
                width=self._table_total_width,
                height=row_h,
                row_default_height=row_h,
                row_force_default=True,
                spacing=dp(1),
            )

            for key, _title, col_w in self._table_columns:
                txt = self._format_cell_value(key, self._get_cell_value(s, key))
                cell = Button(
                    text=txt,
                    size_hint=(None, None),
                    width=col_w,
                    height=row_h,
                    font_size=dp(13),
                    halign="left",
                    valign="middle",
                    shorten=True,
                    shorten_from="right",
                    text_size=(col_w - dp(14), row_h),
                    background_color=base_rgba,
                    background_normal="",
                    background_down="",
                )
                cell.color = UI_TEXT_STRONG if is_current else UI_TEXT_PRIMARY
                cell.bind(on_press=lambda _inst, ss=s: self._on_study_clicked(ss))
                row.add_widget(cell)

            self.rows_grid.add_widget(row)
            total_h += row_h + dp(1)
        self.rows_grid.height = total_h

    def _on_refresh_clicked(self, *args):
        if self.on_search_studies and self._get_column_filters():
            self._run_debounced_search()
            return
        self._refresh_recent_studies()

    def _on_open_by_id_clicked(self, *args):
        raw = (self.id_input.text or "").strip()
        if not raw:
            return
        try:
            sid = int(raw)
        except Exception:
            return

        # 1) Пытаемся найти в текущем списке
        for s in self.studies or []:
            cur = s.get("study_id") or s.get("session_id") or s.get("worklist_id") or s.get("id")
            try:
                if int(cur) == sid:
                    self._on_study_clicked(s)
                    return
            except Exception:
                continue

        # 2) Запрашиваем точечно (если поддерживается)
        if self.on_open_study_id:
            try:
                s = self.on_open_study_id(sid)
                if isinstance(s, dict):
                    # Добавим в список (в начало)
                    self.studies = [s] + [x for x in self.studies if str((x.get("study_id") or x.get("id"))) != str(sid)]
                    self._apply_filter()
                    self._on_study_clicked(s)
                    return
            except Exception:
                pass

    def _on_study_clicked(self, study: Dict):
        sid = study.get("study_id") or study.get("session_id") or study.get("worklist_id") or study.get("id")
        try:
            self.current_study_id = int(sid) if sid is not None else None
        except Exception:
            self.current_study_id = None

        if self.on_study_selected:
            try:
                self.on_study_selected(study)
            except Exception:
                pass

        # Navigate
        if self.manager and self.next_screen_on_select and self.manager.has_screen(self.next_screen_on_select):
            self.manager.current = self.next_screen_on_select
            return
        self._on_back_clicked()

    def _on_back_clicked(self, *args):
        # Если задан previous_screen — это приоритетнее (не закрываем приложение).
        if self.manager and self.previous_screen and self.manager.has_screen(self.previous_screen):
            self.manager.current = self.previous_screen
            return

        # Иначе можно выполнить внешний обработчик (например, закрыть приложение).
        if self.on_back:
            self.on_back()
            return

        # Fallback: перейти на первый экран
        if self.manager and self.manager.screens:
            self.manager.current = self.manager.screens[0].name

