from __future__ import annotations

from typing import Callable, Optional

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget
from kivy.uix.anchorlayout import AnchorLayout

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


class ConfirmActionScreen(EscBackNavigationMixin, Screen):
    """Простая страница подтверждения действия."""

    def __init__(
        self,
        title_text: str,
        message_text: str,
        action_text: str = "Подтвердить",
        on_confirm: Optional[Callable[[], None]] = None,
        previous_screen: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if "name" not in kwargs:
            self.name = "confirm_action_screen"
        self._init_esc_back_navigation()
        self.previous_screen = previous_screen
        self._title_text = title_text
        self._message_text = message_text
        self._action_text = action_text
        self._on_confirm = on_confirm
        self._create_ui()

    def on_pre_enter(self, *args):
        self._bind_escape_handler()
        return super().on_pre_enter(*args)

    def on_pre_leave(self, *args):
        self._unbind_escape_handler()
        return super().on_pre_leave(*args)

    def _create_ui(self):
        # Важно: вертикальный BoxLayout кладёт "короткий" контент к нижнему краю.
        # Нам нужно, чтобы карточка подтверждения начиналась сразу под верхней строкой.
        root = AnchorLayout(
            anchor_x="center",
            anchor_y="top",
            padding=UI_CONTENT_PADDING_UNDER_TITLEBAR,
        )

        card = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=(dp(14), dp(12), dp(14), dp(12)),
        )
        # Важно: если оставить size_hint_y=1 и добавить "спейсер" в root,
        # карточка может разъезжаться вниз на некоторых размерах окна.
        card.size_hint_y = None
        card.bind(minimum_height=card.setter("height"))
        apply_rounded_panel(card, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(12), border_alpha=0.06)

        title_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(36),
            spacing=dp(10),
        )
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
        card.add_widget(title_row)

        message = Label(
            text=self._message_text,
            size_hint_y=None,
            height=dp(54),
            font_size=dp(13),
            color=UI_TEXT_MUTED,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        message.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        card.add_widget(message)

        buttons = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(44),
            spacing=dp(10),
        )
        buttons.add_widget(Widget())

        confirm_btn = Button(
            text=self._action_text,
            size_hint_x=None,
            width=dp(160),
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
        )
        confirm_btn.color = UI_TEXT_PRIMARY
        apply_rounded_button(confirm_btn, base_rgba=UI_BTN_DANGER)
        confirm_btn.bind(on_release=self._confirm)
        buttons.add_widget(confirm_btn)
        card.add_widget(buttons)

        # Карточка должна начинаться сразу под верхней панелью (padding уже учтён).
        card.size_hint_x = 1
        root.add_widget(card)
        self.add_widget(root)

    def _confirm(self, *_args):
        if self._on_confirm is not None:
            self._on_confirm()
        self._on_back_clicked()

    def _on_back_clicked(self, *_args):
        if self.manager:
            if self.previous_screen and self.manager.has_screen(self.previous_screen):
                self.manager.current = self.previous_screen
            elif self.manager.screens:
                self.manager.current = self.manager.screens[0].name
