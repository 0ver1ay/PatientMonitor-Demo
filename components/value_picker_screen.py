from __future__ import annotations

from typing import Callable, Iterable, Optional

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from components.esc_back_navigation import EscBackNavigationMixin
from utils.ui_style import (
    UI_BTN_DANGER,
    UI_BTN_MUTED,
    UI_BTN_SUCCESS,
    UI_CONTENT_PADDING_UNDER_TITLEBAR,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    UI_TEXT_STRONG,
    apply_rounded_button,
    apply_rounded_panel,
)


class ValuePickerScreen(EscBackNavigationMixin, Screen):
    """Полноэкранный выбор значения из сетки."""

    def __init__(
        self,
        title_text: str,
        values: Iterable[int],
        selected_value: Optional[int] = None,
        on_select: Optional[Callable[[int], None]] = None,
        previous_screen: Optional[str] = None,
        subtitle_text: str = "",
        columns: int = 6,
        formatter: Optional[Callable[[int], str]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if "name" not in kwargs:
            self.name = "value_picker_screen"
        self._init_esc_back_navigation()
        self.previous_screen = previous_screen
        self._title_text = title_text
        self._subtitle_text = subtitle_text
        self._values = list(values)
        self._selected_value = selected_value
        self._on_select = on_select
        self._columns = max(1, int(columns))
        self._formatter = formatter or (lambda value: f"{int(value):02d}")
        self._create_ui()

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
            text=self._subtitle_text or "Выберите значение",
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
            padding=(dp(12), dp(12), dp(12), dp(12)),
        )
        apply_rounded_panel(body, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(12), border_alpha=0.06)

        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True, bar_width=dp(10))
        grid = GridLayout(
            cols=self._columns,
            spacing=dp(8),
            padding=(0, 0, 0, dp(4)),
            size_hint_y=None,
            row_default_height=dp(44),
            row_force_default=True,
        )
        grid.bind(minimum_height=grid.setter("height"))

        for value in self._values:
            selected = value == self._selected_value
            btn = Button(
                text=self._formatter(int(value)),
                background_color=(0, 0, 0, 0),
                background_normal="",
                background_down="",
                font_size=dp(16),
            )
            btn.color = UI_TEXT_PRIMARY
            apply_rounded_button(btn, base_rgba=UI_BTN_SUCCESS if selected else UI_BTN_MUTED)
            btn.bind(on_release=lambda _inst, picked=int(value): self._select_value(picked))
            grid.add_widget(btn)

        scroll.add_widget(grid)
        body.add_widget(scroll)
        root.add_widget(body)
        self.add_widget(root)

    def _select_value(self, value: int):
        if self._on_select is not None:
            self._on_select(int(value))
        self._on_back_clicked()

    def _on_back_clicked(self, *_args):
        if self.manager:
            if self.previous_screen and self.manager.has_screen(self.previous_screen):
                self.manager.current = self.previous_screen
            elif self.manager.screens:
                self.manager.current = self.manager.screens[0].name
