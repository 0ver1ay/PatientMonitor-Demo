from __future__ import annotations

from typing import Optional

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from components.esc_back_navigation import EscBackNavigationMixin
from utils.ui_style import (
    UI_BTN_DANGER,
    UI_CONTENT_PADDING_UNDER_TITLEBAR,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    UI_TEXT_STRONG,
    apply_rounded_button,
    apply_rounded_panel,
)


class MessageScreen(EscBackNavigationMixin, Screen):
    """Полноэкранное информационное сообщение вместо popup."""

    def __init__(
        self,
        title_text: str = "Информация",
        message_text: str = "",
        previous_screen: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if "name" not in kwargs:
            self.name = "message_screen"
        self._init_esc_back_navigation()
        self.previous_screen = previous_screen
        self._title_text = title_text
        self._message_text = message_text
        self._create_ui()

    def on_pre_enter(self, *args):
        self._bind_escape_handler()
        return super().on_pre_enter(*args)

    def on_pre_leave(self, *args):
        self._unbind_escape_handler()
        return super().on_pre_leave(*args)

    def set_content(self, title_text: str, message_text: str):
        self._title_text = str(title_text or "Информация")
        self._message_text = str(message_text or "")
        if hasattr(self, "title_label"):
            self.title_label.text = self._title_text
        if hasattr(self, "message_label"):
            self.message_label.text = self._message_text

    def _create_ui(self):
        root = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=UI_CONTENT_PADDING_UNDER_TITLEBAR,
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
        self.title_label = Label(
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
        self.title_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        title_row.add_widget(self.title_label)

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
        back_button.bind(on_press=self._on_back_clicked)
        title_row.add_widget(back_button)
        summary_card.add_widget(title_row)

        subtitle = Label(
            text="Сообщение приложения",
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
        root.add_widget(summary_card)

        body_card = BoxLayout(
            orientation="vertical",
            size_hint=(1, 1),
            padding=(dp(14), dp(14), dp(14), dp(14)),
        )
        apply_rounded_panel(body_card, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(12), border_alpha=0.06)

        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True, bar_width=dp(10))
        self.message_label = Label(
            text=self._message_text,
            size_hint_y=None,
            font_size=dp(14),
            color=UI_TEXT_PRIMARY,
            halign="left",
            valign="top",
            text_size=(0, None),
        )
        self.message_label.bind(size=self._update_message_text_size)
        self.message_label.bind(texture_size=lambda inst, _size: setattr(inst, "height", max(dp(32), inst.texture_size[1])))
        scroll.add_widget(self.message_label)
        body_card.add_widget(scroll)
        root.add_widget(body_card)

        self.add_widget(root)

    def _update_message_text_size(self, inst, size):
        inst.text_size = (max(1, size[0] - dp(6)), None)

    def _on_back_clicked(self, *_args):
        if self.manager:
            if self.previous_screen and self.manager.has_screen(self.previous_screen):
                self.manager.current = self.previous_screen
            elif self.manager.screens:
                self.manager.current = self.manager.screens[0].name
