from __future__ import annotations

import calendar as _cal
from datetime import date
from typing import Callable, Optional

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget

from components.esc_back_navigation import EscBackNavigationMixin
from utils.ui_style import (
    UI_BTN_DANGER,
    UI_BTN_MUTED,
    UI_BTN_SECONDARY,
    UI_BTN_WARNING,
    UI_CONTENT_PADDING_UNDER_TITLEBAR,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    UI_TEXT_STRONG,
    apply_rounded_button,
    apply_rounded_panel,
)


class CalendarPickerScreen(EscBackNavigationMixin, Screen):
    """Полноэкранный календарь выбора даты."""

    MONTH_NAMES = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
    ]
    WEEK_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    def __init__(
        self,
        title_text: str,
        on_select: Callable[[date], None],
        previous_screen: Optional[str] = None,
        initial_date: Optional[date] = None,
        subtitle_text: str = "",
        range_start: Optional[date] = None,
        range_end: Optional[date] = None,
        on_clear: Optional[Callable[[], None]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if "name" not in kwargs:
            self.name = "calendar_picker_screen"
        self._init_esc_back_navigation()
        self.previous_screen = previous_screen
        self._title_text = title_text
        self._subtitle_text = subtitle_text
        self._on_select = on_select
        self._on_clear = on_clear
        self._range_start = range_start
        self._range_end = range_end
        base_date = initial_date or date.today()
        self._state = {"year": int(base_date.year), "month": int(base_date.month)}
        self._calendar = _cal.Calendar(firstweekday=_cal.MONDAY)
        self._create_ui()
        self._refresh_calendar()

    def on_pre_enter(self, *args):
        self._bind_escape_handler()
        return super().on_pre_enter(*args)

    def on_pre_leave(self, *args):
        self._unbind_escape_handler()
        return super().on_pre_leave(*args)

    def _create_ui(self):
        root = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=UI_CONTENT_PADDING_UNDER_TITLEBAR,
        )

        header = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(8),
            padding=(dp(14), dp(12), dp(14), dp(12)),
        )
        header.bind(minimum_height=header.setter("height"))
        apply_rounded_panel(header, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(12), border_alpha=0.06)

        title_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(10))
        title = Label(
            text=self._title_text,
            size_hint=(1, None),
            height=dp(36),
            font_size=dp(18),
            bold=True,
            color=UI_TEXT_STRONG,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        title.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        title_row.add_widget(title)

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
        back_button.color = UI_TEXT_PRIMARY
        apply_rounded_button(back_button, base_rgba=UI_BTN_DANGER, radius_px=dp(9))
        back_button.bind(on_release=self._on_back_clicked)
        title_row.add_widget(back_button)
        header.add_widget(title_row)

        subtitle = Label(
            text=self._subtitle_text or "Выберите дату",
            size_hint_y=None,
            height=dp(20),
            font_size=dp(12),
            color=UI_TEXT_MUTED,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        subtitle.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        header.add_widget(subtitle)
        root.add_widget(header)

        body = BoxLayout(
            orientation="vertical",
            size_hint=(1, 1),
            spacing=dp(10),
            padding=(dp(12), dp(12), dp(12), dp(12)),
        )
        apply_rounded_panel(body, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(12), border_alpha=0.06)

        nav = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(52), spacing=dp(8))
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
        apply_rounded_button(btn_prev, base_rgba=UI_BTN_MUTED)
        btn_prev.bind(on_release=lambda *_: self._change_month(-1))
        nav.add_widget(btn_prev)

        self.month_title = Label(
            text="",
            font_size=dp(16),
            bold=True,
            color=UI_TEXT_STRONG,
            halign="center",
            valign="middle",
            text_size=(0, None),
        )
        self.month_title.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        nav.add_widget(self.month_title)

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
        apply_rounded_button(btn_next, base_rgba=UI_BTN_MUTED)
        btn_next.bind(on_release=lambda *_: self._change_month(1))
        nav.add_widget(btn_next)
        body.add_widget(nav)

        self.grid = GridLayout(
            cols=7,
            spacing=dp(6),
            padding=(dp(6), dp(6)),
            size_hint=(1, None),
            row_default_height=dp(40),
            row_force_default=True,
        )
        body.add_widget(self.grid)

        footer = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(8))
        today_btn = Button(
            text="Сегодня",
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
        )
        today_btn.color = UI_TEXT_PRIMARY
        apply_rounded_button(today_btn, base_rgba=UI_BTN_WARNING)
        today_btn.bind(on_release=lambda *_: self._select_day(date.today()))
        footer.add_widget(today_btn)

        if self._on_clear is not None:
            clear_btn = Button(
                text="Очистить",
                background_color=(0, 0, 0, 0),
                background_normal="",
                background_down="",
            )
            clear_btn.color = UI_TEXT_PRIMARY
            apply_rounded_button(clear_btn, base_rgba=UI_BTN_SECONDARY)
            clear_btn.bind(on_release=self._clear_value)
            footer.add_widget(clear_btn)

        footer.add_widget(Widget())
        body.add_widget(footer)
        root.add_widget(body)

        self.add_widget(root)

    def _change_month(self, delta: int):
        month = self._state["month"] + int(delta)
        year = self._state["year"]
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1
        self._state["month"] = month
        self._state["year"] = year
        self._refresh_calendar()

    def _refresh_calendar(self):
        self.grid.clear_widgets()
        self.month_title.text = f"{self.MONTH_NAMES[self._state['month'] - 1]} {self._state['year']}"

        for wn in self.WEEK_NAMES:
            self.grid.add_widget(Label(text=wn, font_size=dp(12), color=UI_TEXT_MUTED, bold=True))

        d_from = self._range_start
        d_to = self._range_end
        if d_from and d_to and d_from > d_to:
            d_from, d_to = d_to, d_from

        weeks = self._calendar.monthdayscalendar(self._state["year"], self._state["month"])
        while len(weeks) < 6:
            weeks.append([0] * 7)

        for week in weeks:
            for day in week:
                if day == 0:
                    self.grid.add_widget(
                        Button(
                            text="",
                            disabled=True,
                            background_normal="",
                            background_down="",
                            background_color=(0, 0, 0, 0),
                        )
                    )
                    continue

                picked = date(self._state["year"], self._state["month"], int(day))
                in_range = bool(d_from and d_to and d_from <= picked <= d_to)
                is_edge = (d_from is not None and picked == d_from) or (d_to is not None and picked == d_to)
                rgba = UI_BTN_MUTED
                if in_range:
                    rgba = (0.30, 0.30, 0.34, 1)
                if is_edge:
                    rgba = UI_BTN_SUCCESS

                btn = Button(
                    text=str(day),
                    background_normal="",
                    background_down="",
                    background_color=(0, 0, 0, 0),
                    font_size=dp(14),
                )
                btn.color = UI_TEXT_PRIMARY
                apply_rounded_button(btn, base_rgba=rgba)
                btn.bind(on_release=lambda _inst, picked_date=picked: self._select_day(picked_date))
                self.grid.add_widget(btn)

        rows = 7
        self.grid.height = rows * dp(40) + (rows - 1) * dp(6) + dp(12)

    def _select_day(self, picked_date: date):
        if self._on_select is not None:
            self._on_select(picked_date)
        self._on_back_clicked()

    def _clear_value(self, *_args):
        if self._on_clear is not None:
            self._on_clear()
        self._on_back_clicked()

    def _on_back_clicked(self, *_args):
        if self.manager:
            if self.previous_screen and self.manager.has_screen(self.previous_screen):
                self.manager.current = self.previous_screen
            elif self.manager.screens:
                self.manager.current = self.manager.screens[0].name
