"""
Экран выбора абсолютного диапазона даты/времени (start/end)

Формат ввода по умолчанию: YYYY-MM-DD HH:MM
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable, Optional, Tuple

from kivy.core.window import Window
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.metrics import dp

from components.esc_back_navigation import has_open_modal_or_dropdown
from utils.popup_style import apply_popup_theme, style_scrollview_popup
from utils.ui_style import (
    UI_BTN_DANGER,
    UI_BTN_SECONDARY,
    UI_BTN_SUCCESS,
    UI_BTN_WARNING,
    UI_CONTENT_PADDING_UNDER_TITLEBAR,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    UI_TEXT_STRONG,
    apply_rounded_button,
    apply_rounded_panel,
)


class DateTimeRangeSelectionScreen(Screen):
    """Экран для выбора абсолютного временного диапазона."""

    INPUT_FORMAT = "%Y-%m-%d %H:%M"

    def __init__(
        self,
        current_range: Optional[Tuple[datetime, datetime]] = None,
        on_range_selected: Optional[Callable[[datetime, datetime], None]] = None,
        previous_screen: Optional[str] = None,
        next_screen_on_apply: Optional[str] = None,
        on_back: Optional[Callable[[], None]] = None,
        show_header_nav: bool = True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if "name" not in kwargs:
            self.name = "date_time_range_selection"

        self.on_range_selected = on_range_selected
        self.previous_screen = previous_screen
        self.next_screen_on_apply = next_screen_on_apply
        self.on_back = on_back
        self.show_header_nav = show_header_nav
        self._esc_handler_bound = False

        if current_range:
            start_dt, end_dt = current_range
        else:
            end_dt = datetime.now().replace(second=0, microsecond=0)
            start_dt = end_dt - timedelta(hours=6)

        self._start_dt = start_dt
        self._end_dt = end_dt
        self._btn_base = UI_BTN_SECONDARY
        self._btn_text = UI_TEXT_PRIMARY

        self._create_ui()
        self.set_current_range(self._start_dt, self._end_dt)

    def on_pre_enter(self, *args):
        self._bind_escape_handler()
        return super().on_pre_enter(*args)

    def on_pre_leave(self, *args):
        self._unbind_escape_handler()
        return super().on_pre_leave(*args)

    def set_on_range_selected(self, callback: Callable[[datetime, datetime], None]):
        self.on_range_selected = callback

    def set_current_range(self, start_dt: datetime, end_dt: datetime):
        self._start_dt = start_dt
        self._end_dt = end_dt
        self._sync_ui_from_state()
        self._update_current_label()
        self._set_error("")

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
        main_container = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=dp(16) if self.show_header_nav else UI_CONTENT_PADDING_UNDER_TITLEBAR,
        )
        summary_card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(8),
            padding=(dp(14), dp(12), dp(14), dp(12)),
        )
        summary_card.bind(minimum_height=summary_card.setter("height"))
        apply_rounded_panel(summary_card, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(12), border_alpha=0.06)

        title_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(36),
            spacing=dp(10),
        )
        if self.show_header_nav:
            title_label = Label(
                text="Выбор диапазона дат/времени",
                size_hint=(1, None),
                height=dp(36),
                font_size=dp(18),
                bold=True,
                color=UI_TEXT_STRONG,
                halign="left",
                valign="middle",
                text_size=(0, None),
            )
            title_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
            title_row.add_widget(title_label)
        else:
            title_row.add_widget(Widget())

        back_button = Button(
            text="Назад",
            size_hint_x=None,
            width=dp(104),
            height=dp(36),
            font_size=dp(14),
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
        )
        back_button.color = self._btn_text
        apply_rounded_button(back_button, base_rgba=UI_BTN_DANGER, radius_px=dp(9))
        back_button.bind(on_press=self._on_back_clicked)
        title_row.add_widget(back_button)
        summary_card.add_widget(title_row)

        subtitle = Label(
            text="Выберите абсолютный диапазон даты и времени",
            size_hint_y=None,
            height=dp(20),
            font_size=dp(12),
            color=UI_TEXT_MUTED,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        subtitle.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        summary_card.add_widget(subtitle)

        self.current_label = Label(
            text="",
            size_hint_y=None,
            height=dp(34),
            font_size=dp(13),
            color=UI_TEXT_PRIMARY,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        self.current_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        apply_rounded_panel(self.current_label, base_rgba=(0.18, 0.18, 0.19, 1), radius_px=dp(8), border_alpha=0.05)
        summary_card.add_widget(self.current_label)
        main_container.add_widget(summary_card)

        controls_card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(10),
            padding=(dp(12), dp(12), dp(12), dp(12)),
        )
        controls_card.bind(minimum_height=controls_card.setter("height"))
        apply_rounded_panel(controls_card, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(12), border_alpha=0.06)

        section_hint = Label(
            text="Выберите дату и время (без клавиатуры)",
            size_hint_y=None,
            height=dp(22),
            font_size=dp(12),
            color=UI_TEXT_MUTED,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        section_hint.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        controls_card.add_widget(section_hint)

        inputs = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None, height=dp(126))

        start_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(58))
        start_row.add_widget(
            Label(
                text="Начало:",
                size_hint_x=None,
                width=dp(76),
                font_size=dp(14),
                color=UI_TEXT_STRONG,
                halign="left",
                valign="middle",
                text_size=(dp(76), None),
            )
        )
        self.start_date_btn = Button(
            text="Дата…",
            font_size=dp(14),
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
            shorten=True,
            shorten_from="right",
            text_size=(0, 0),
        )
        self.start_date_btn.color = self._btn_text
        apply_rounded_button(self.start_date_btn, base_rgba=self._btn_base)
        self.start_date_btn.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0] - dp(10), None)))
        self.start_date_btn.bind(on_press=lambda *_: self._open_date_picker("start"))
        start_row.add_widget(self.start_date_btn)

        def _time_btn(**kw):
            b = Button(
                background_color=(0, 0, 0, 0),
                background_normal="",
                background_down="",
                font_size=dp(14),
                color=self._btn_text,
                **kw,
            )
            apply_rounded_button(b, base_rgba=self._btn_base)
            return b

        self.start_hour_btn = _time_btn(
            text="00",
            size_hint_x=None,
            width=dp(52),
        )
        self.start_min_btn = _time_btn(
            text="00",
            size_hint_x=None,
            width=dp(52),
        )
        start_row.add_widget(self.start_hour_btn)
        start_row.add_widget(Label(text=":", size_hint_x=None, width=dp(12), color=UI_TEXT_PRIMARY, font_size=dp(16)))
        start_row.add_widget(self.start_min_btn)
        self.start_hour_btn.bind(on_press=lambda *_: self._open_time_picker("start", "hour"))
        self.start_min_btn.bind(on_press=lambda *_: self._open_time_picker("start", "min"))
        inputs.add_widget(start_row)

        end_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(58))
        end_row.add_widget(
            Label(
                text="Конец:",
                size_hint_x=None,
                width=dp(76),
                font_size=dp(14),
                color=UI_TEXT_STRONG,
                halign="left",
                valign="middle",
                text_size=(dp(76), None),
            )
        )
        self.end_date_btn = Button(
            text="Дата…",
            font_size=dp(14),
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
            shorten=True,
            shorten_from="right",
            text_size=(0, 0),
        )
        self.end_date_btn.color = self._btn_text
        apply_rounded_button(self.end_date_btn, base_rgba=self._btn_base)
        self.end_date_btn.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0] - dp(10), None)))
        self.end_date_btn.bind(on_press=lambda *_: self._open_date_picker("end"))
        end_row.add_widget(self.end_date_btn)

        self.end_hour_btn = _time_btn(
            text="00",
            size_hint_x=None,
            width=dp(52),
        )
        self.end_min_btn = _time_btn(
            text="00",
            size_hint_x=None,
            width=dp(52),
        )
        end_row.add_widget(self.end_hour_btn)
        end_row.add_widget(Label(text=":", size_hint_x=None, width=dp(12), color=UI_TEXT_PRIMARY, font_size=dp(16)))
        end_row.add_widget(self.end_min_btn)
        self.end_hour_btn.bind(on_press=lambda *_: self._open_time_picker("end", "hour"))
        self.end_min_btn.bind(on_press=lambda *_: self._open_time_picker("end", "min"))
        inputs.add_widget(end_row)
        controls_card.add_widget(inputs)

        presets = GridLayout(
            cols=4,
            spacing=dp(8),
            size_hint_y=None,
            height=dp(42),
        )
        for hours, label in [(1, "1ч"), (6, "6ч"), (12, "12ч"), (24, "24ч")]:
            btn = Button(
                text=f"Последние {label}",
                font_size=dp(13),
                background_color=(0, 0, 0, 0),
                background_normal="",
                background_down="",
                color=self._btn_text,
            )
            apply_rounded_button(btn, base_rgba=self._btn_base)
            btn.bind(on_press=lambda instance, h=hours: self._apply_last_hours(h))
            presets.add_widget(btn)
        controls_card.add_widget(presets)

        self.error_label = Label(
            text="",
            size_hint_y=None,
            height=dp(0),
            font_size=dp(12),
            color=(1, 0.4, 0.4, 1),
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        self.error_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        controls_card.add_widget(self.error_label)

        apply_btn = Button(
            text="Применить",
            size_hint_y=None,
            height=dp(46),
            font_size=dp(16),
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
            color=self._btn_text,
        )
        apply_rounded_button(apply_btn, base_rgba=UI_BTN_SUCCESS)
        apply_btn.bind(on_press=self._on_apply_clicked)
        controls_card.add_widget(apply_btn)
        main_container.add_widget(controls_card)
        main_container.add_widget(Label(text="", size_hint=(1, 1)))
        self.add_widget(main_container)
        self._update_current_label()

    def _set_error(self, msg: str):
        txt = msg or ""
        self.error_label.text = txt
        self.error_label.height = dp(26) if txt else dp(0)

    def _update_current_label(self):
        try:
            self.current_label.text = (
                f"Текущий диапазон: {self._start_dt.strftime(self.INPUT_FORMAT)}  до  {self._end_dt.strftime(self.INPUT_FORMAT)}"
            )
        except Exception:
            self.current_label.text = "Текущий диапазон: (не задан)"

    def _sync_ui_from_state(self):
        """Обновить кнопки/спиннеры из self._start_dt/self._end_dt."""
        try:
            if hasattr(self, "start_date_btn"):
                self.start_date_btn.text = self._start_dt.strftime("%d.%m.%Y")
            if hasattr(self, "end_date_btn"):
                self.end_date_btn.text = self._end_dt.strftime("%d.%m.%Y")
            if hasattr(self, "start_hour_btn"):
                self.start_hour_btn.text = f"{int(self._start_dt.hour):02d}"
            if hasattr(self, "start_min_btn"):
                self.start_min_btn.text = f"{int(self._start_dt.minute):02d}"
            if hasattr(self, "end_hour_btn"):
                self.end_hour_btn.text = f"{int(self._end_dt.hour):02d}"
            if hasattr(self, "end_min_btn"):
                self.end_min_btn.text = f"{int(self._end_dt.minute):02d}"
        except Exception:
            pass

    def _set_time_part(self, target: str, hour: int | None = None, minute: int | None = None):
        """Установить часы/минуты для start|end."""
        try:
            if target == "start":
                dt = self._start_dt
                self._start_dt = dt.replace(
                    hour=dt.hour if hour is None else int(hour),
                    minute=dt.minute if minute is None else int(minute),
                    second=0,
                    microsecond=0,
                )
            else:
                dt = self._end_dt
                self._end_dt = dt.replace(
                    hour=dt.hour if hour is None else int(hour),
                    minute=dt.minute if minute is None else int(minute),
                    second=0,
                    microsecond=0,
                )
            self._sync_ui_from_state()
            self._update_current_label()
        except Exception:
            return

    def _open_time_picker(self, target: str, part: str):
        """Открыть удобный попап выбора часов/минут (без длинного dropdown)."""
        if part not in ("hour", "min"):
            return

        if self.manager is not None:
            try:
                from components.value_picker_screen import ValuePickerScreen

                is_hour = part == "hour"
                cur = self._start_dt if target == "start" else self._end_dt
                cur_val = int(cur.hour) if is_hour else int(cur.minute)
                values = list(range(24)) if is_hour else list(range(60))
                picker = ValuePickerScreen(
                    name=f"{self.name}_{target}_{part}_picker",
                    title_text="Выбор часа" if is_hour else "Выбор минут",
                    subtitle_text="Выберите значение",
                    values=values,
                    selected_value=cur_val,
                    previous_screen=self.name,
                    on_select=lambda picked, tgt=target, hour=is_hour: (
                        self._set_time_part(tgt, hour=picked) if hour else self._set_time_part(tgt, minute=picked)
                    ),
                )
                if self._replace_managed_screen(picker):
                    return
            except Exception:
                pass

        is_hour = part == "hour"
        cur = self._start_dt if target == "start" else self._end_dt
        cur_val = int(cur.hour) if is_hour else int(cur.minute)
        values = list(range(24)) if is_hour else list(range(60))

        root = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))
        apply_rounded_panel(root, base_rgba=(0.11, 0.12, 0.15, 1), radius_px=dp(12), border_alpha=0.12)
        title = Label(
            text=("Выбор часа" if is_hour else "Выбор минут"),
            size_hint_y=None,
            height=dp(28),
            font_size=dp(16),
            bold=True,
            color=(0.94, 0.94, 0.98, 1),
        )
        root.add_widget(title)

        grid = GridLayout(
            cols=6,
            spacing=dp(6),
            padding=(dp(6), dp(6)),
            size_hint_y=None,
            row_default_height=dp(44),
            row_force_default=True,
        )
        grid.bind(minimum_height=grid.setter("height"))

        def mk_btn(v: int):
            txt = f"{v:02d}"
            selected = v == cur_val
            bg = (0.2, 0.7, 0.2, 1) if selected else (0.22, 0.23, 0.28, 1)
            b = Button(
                text=txt,
                background_normal="",
                background_down="",
                background_color=(0, 0, 0, 0),
                font_size=dp(16),
            )
            b.color = UI_TEXT_PRIMARY
            apply_rounded_button(b, base_rgba=bg)

            def on_pick(*_):
                if is_hour:
                    self._set_time_part(target, hour=v)
                else:
                    self._set_time_part(target, minute=v)
                popup.dismiss()

            b.bind(on_press=on_pick)
            return b

        for v in values:
            grid.add_widget(mk_btn(int(v)))

        sc = ScrollView(do_scroll_x=False, do_scroll_y=True, bar_width=dp(10))
        style_scrollview_popup(sc)
        sc.add_widget(grid)
        root.add_widget(sc)

        footer = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(44))
        btn_close = Button(
            text="Закрыть",
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
        )
        btn_close.color = UI_TEXT_PRIMARY
        apply_rounded_button(btn_close, base_rgba=(0.22, 0.23, 0.28, 1))
        footer.add_widget(btn_close)
        root.add_widget(footer)

        popup = Popup(title="", separator_height=0, content=root, size_hint=(0.58, 0.68))
        apply_popup_theme(popup)
        btn_close.bind(on_press=lambda *_: popup.dismiss())
        popup.open()

    def _open_date_picker(self, target: str):
        """Календарь выбора даты (без клавиатуры). target: start|end."""
        if self.manager is not None:
            try:
                from components.calendar_picker_screen import CalendarPickerScreen

                picker = CalendarPickerScreen(
                    name=f"{self.name}_{target}_date_picker",
                    title_text="Выбор даты начала" if target == "start" else "Выбор даты окончания",
                    subtitle_text="Выберите день в календаре",
                    previous_screen=self.name,
                    initial_date=(self._start_dt if target == "start" else self._end_dt).date(),
                    range_start=self._start_dt.date(),
                    range_end=self._end_dt.date(),
                    on_select=lambda picked_date, tgt=target: self._apply_picked_date(tgt, picked_date),
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

        base_dt = self._start_dt if target == "start" else self._end_dt
        base_d = base_dt.date()
        state = {"year": int(base_d.year), "month": int(base_d.month)}

        root = AnchorLayout(anchor_x="center", anchor_y="center")
        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14), size_hint=(None, None))
        content.bind(minimum_height=content.setter("height"))
        apply_rounded_panel(content, base_rgba=(0.11, 0.12, 0.15, 1), radius_px=dp(12), border_alpha=0.12)
        root.add_widget(content)

        header = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(52))
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
        apply_rounded_button(btn_prev, base_rgba=(0.22, 0.23, 0.28, 1))
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
        apply_rounded_button(btn_next, base_rgba=(0.22, 0.23, 0.28, 1))
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
        header.add_widget(title)
        header.add_widget(btn_next)
        content.add_widget(header)

        grid = GridLayout(cols=7, spacing=dp(6), padding=(dp(6), dp(6)), size_hint_y=None, size_hint_x=1, row_default_height=dp(40), row_force_default=True)
        content.add_widget(grid)

        footer = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(44))
        btn_today = Button(text="Сегодня", background_color=(0, 0, 0, 0), background_normal="", background_down="", size_hint_x=1)
        btn_today.color = UI_TEXT_PRIMARY
        apply_rounded_button(btn_today, base_rgba=UI_BTN_WARNING)
        btn_close = Button(text="Закрыть", background_color=(0, 0, 0, 0), background_normal="", background_down="", size_hint_x=1)
        btn_close.color = UI_TEXT_PRIMARY
        apply_rounded_button(btn_close, base_rgba=UI_BTN_SECONDARY)
        footer.add_widget(btn_today)
        footer.add_widget(btn_close)
        content.add_widget(footer)

        popup = Popup(title="", separator_height=0, content=root, size_hint=(0.92, 0.84))
        apply_popup_theme(popup)

        def _sync_width(*_args):
            avail = max(1.0, float(root.width) - float(dp(40)))
            content.width = min(avail, float(dp(900)))

        root.bind(size=_sync_width)

        def refresh():
            grid.clear_widgets()
            title.text = f"{month_names[state['month'] - 1]} {state['year']}"

            for wn in week_names:
                grid.add_widget(Label(text=wn, font_size=dp(12), color=(0.85, 0.85, 0.9, 1), bold=True))

            weeks = cal.monthdayscalendar(state["year"], state["month"])
            while len(weeks) < 6:
                weeks.append([0] * 7)

            # Подсветка диапазона start..end по датам
            d_from = self._start_dt.date()
            d_to = self._end_dt.date()
            if d_from and d_to and d_from > d_to:
                d_from, d_to = d_to, d_from

            for week in weeks:
                for day in week:
                    if day == 0:
                        grid.add_widget(Button(text="", disabled=True, background_normal="", background_down="", background_color=(0, 0, 0, 0)))
                        continue
                    d = date(state["year"], state["month"], int(day))
                    is_range = d_from <= d <= d_to
                    is_edge = d == self._start_dt.date() or d == self._end_dt.date()
                    bg = (0.25, 0.25, 0.35, 1)
                    if is_range:
                        bg = (0.2, 0.35, 0.55, 1)
                    if is_edge:
                        bg = (0.2, 0.7, 0.2, 1)

                    b = Button(text=str(day), background_normal="", background_down="", background_color=(0, 0, 0, 0), font_size=dp(14))
                    b.color = UI_TEXT_PRIMARY
                    apply_rounded_button(b, base_rgba=bg)

                    def select_day(_inst, dd=d):
                        if target == "start":
                            self._start_dt = self._start_dt.replace(year=dd.year, month=dd.month, day=dd.day)
                        else:
                            self._end_dt = self._end_dt.replace(year=dd.year, month=dd.month, day=dd.day)
                        self._sync_ui_from_state()
                        self._update_current_label()
                        popup.dismiss()

                    b.bind(on_press=select_day)
                    grid.add_widget(b)

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

        def set_today(*_):
            dd = date.today()
            if target == "start":
                self._start_dt = self._start_dt.replace(year=dd.year, month=dd.month, day=dd.day)
            else:
                self._end_dt = self._end_dt.replace(year=dd.year, month=dd.month, day=dd.day)
            self._sync_ui_from_state()
            self._update_current_label()
            popup.dismiss()

        btn_today.bind(on_press=set_today)
        btn_close.bind(on_press=lambda *_: popup.dismiss())

        refresh()
        _sync_width()
        popup.open()

    def _apply_picked_date(self, target: str, picked_date: date):
        if target == "start":
            self._start_dt = self._start_dt.replace(
                year=picked_date.year,
                month=picked_date.month,
                day=picked_date.day,
            )
        else:
            self._end_dt = self._end_dt.replace(
                year=picked_date.year,
                month=picked_date.month,
                day=picked_date.day,
            )
        self._sync_ui_from_state()
        self._update_current_label()

    def _apply_last_hours(self, hours: int):
        end_dt = datetime.now().replace(second=0, microsecond=0)
        start_dt = end_dt - timedelta(hours=hours)
        self.set_current_range(start_dt, end_dt)

    def _on_apply_clicked(self, *args):
        start_dt, end_dt = self._start_dt, self._end_dt
        if end_dt <= start_dt:
            self._set_error("Конец должен быть позже начала.")
            return

        self._set_error("")
        if self.on_range_selected:
            self.on_range_selected(start_dt, end_dt)

        # Navigate forward if requested, otherwise back
        if self.manager and self.next_screen_on_apply:
            if self.manager.has_screen(self.next_screen_on_apply):
                self.manager.current = self.next_screen_on_apply
                return
        self._on_back_clicked()

    def _on_back_clicked(self, *args):
        if self.on_back:
            self.on_back()
            return

        if self.manager:
            if self.previous_screen:
                self.manager.current = self.previous_screen
            else:
                # fallback: go to first screen
                if self.manager.screens:
                    self.manager.current = self.manager.screens[0].name

