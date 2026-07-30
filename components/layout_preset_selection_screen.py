"""
Экран выбора количества мониторов для новой раскладки.
Открывается с главного экрана управления окнами и содержит кнопку "Назад".
"""
from __future__ import annotations

from typing import Callable, Iterable, Optional

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from components.esc_back_navigation import EscBackNavigationMixin
from utils.popup_style import style_scrollview_popup
from utils.ui_style import (
    UI_BTN_DANGER,
    UI_BTN_SECONDARY,
    UI_CONTENT_PADDING_UNDER_TITLEBAR,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    UI_TEXT_STRONG,
    apply_rounded_button,
    apply_rounded_panel,
)


class LayoutPresetSelectionScreen(EscBackNavigationMixin, Screen):
    """Отдельная страница со списком вариантов количества мониторов."""

    _MIN_OPTION_HEIGHT = dp(44)
    _MAX_OPTION_HEIGHT = dp(60)
    _OPTION_SPACING = dp(8)

    def __init__(
        self,
        presets: Iterable[tuple[int, str]],
        on_select: Optional[Callable[[int], None]] = None,
        previous_screen: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if "name" not in kwargs:
            self.name = "layout_preset_selection_screen"
        self._init_esc_back_navigation()
        self._presets: list[tuple[int, str]] = [
            (int(count), str(label)) for count, label in presets
        ]
        self._on_select = on_select
        self.previous_screen = previous_screen
        self._option_buttons: list[Button] = []
        self._scroll: Optional[ScrollView] = None
        self._options_box: Optional[BoxLayout] = None
        self._selectors_card: Optional[BoxLayout] = None
        self._relayout_trigger = Clock.create_trigger(lambda *_: self._relayout_options(), 0)
        self._create_ui()

    def on_pre_enter(self, *args):
        self._bind_escape_handler()
        self._relayout_trigger()
        return super().on_pre_enter(*args)

    def on_pre_leave(self, *args):
        self._unbind_escape_handler()
        return super().on_pre_leave(*args)

    def set_on_select(self, callback: Optional[Callable[[int], None]]) -> None:
        self._on_select = callback

    @staticmethod
    def _clamp(value: float, vmin: float, vmax: float) -> float:
        return max(vmin, min(vmax, value))

    def _create_ui(self) -> None:
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

        title_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(36),
            spacing=dp(10),
        )
        title = Label(
            text="Новая раскладка",
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
            text="Выберите количество мониторов в новой раскладке.",
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

        body_scroll = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=dp(8),
            scroll_type=["bars", "content"],
        )
        style_scrollview_popup(body_scroll)
        self._scroll = body_scroll

        body = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(10),
            padding=(0, 0, 0, dp(6)),
        )

        selectors_card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(8),
            padding=(dp(14), dp(12), dp(14), dp(12)),
        )
        selectors_card.bind(minimum_height=selectors_card.setter("height"))
        apply_rounded_panel(selectors_card, base_rgba=(0.13, 0.13, 0.15, 1), radius_px=dp(10), border_alpha=0.06)
        self._selectors_card = selectors_card

        selectors_title = Label(
            text="Количество мониторов",
            size_hint_y=None,
            height=dp(20),
            font_size=dp(13),
            bold=True,
            color=UI_TEXT_STRONG,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        selectors_title.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        selectors_card.add_widget(selectors_title)

        options = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=self._OPTION_SPACING,
            padding=(0, dp(2), 0, dp(2)),
        )
        options.bind(minimum_height=options.setter("height"))
        self._options_box = options

        for count, label_text in self._presets:
            option_btn = Button(
                text=label_text,
                size_hint_y=None,
                height=self._MIN_OPTION_HEIGHT,
                font_size=dp(14),
                bold=True,
                halign="left",
                valign="middle",
                background_color=(0, 0, 0, 0),
                background_normal="",
                background_down="",
                shorten=True,
                shorten_from="right",
            )
            option_btn.padding = (dp(16), 0)
            option_btn.bind(
                size=lambda inst, s: setattr(inst, "text_size", (max(1, s[0] - dp(28)), s[1]))
            )
            option_btn.color = UI_TEXT_PRIMARY
            apply_rounded_button(option_btn, base_rgba=UI_BTN_SECONDARY, radius_px=dp(9), border_alpha=0.06)
            option_btn.bind(
                on_release=lambda _btn, monitor_count=count: self._handle_select(monitor_count)
            )
            options.add_widget(option_btn)
            self._option_buttons.append(option_btn)
        selectors_card.add_widget(options)

        hint = Label(
            text="Нажмите на вариант, чтобы перейти к настройке раскладки.",
            size_hint_y=None,
            height=dp(18),
            font_size=dp(11),
            color=UI_TEXT_MUTED,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        hint.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        selectors_card.add_widget(hint)

        body.add_widget(selectors_card)
        body.bind(minimum_height=body.setter("height"))
        body_scroll.add_widget(body)
        root.add_widget(body_scroll)

        self.add_widget(root)

        body_scroll.bind(height=lambda *_: self._relayout_trigger())
        body_scroll.bind(width=lambda *_: self._relayout_trigger())
        self.bind(size=lambda *_: self._relayout_trigger())
        Clock.schedule_once(lambda *_: self._relayout_options(), 0)

    def _relayout_options(self) -> None:
        scroll = self._scroll
        options = self._options_box
        card = self._selectors_card
        if scroll is None or options is None or card is None or not self._option_buttons:
            return

        viewport_h = float(getattr(scroll, "height", 0) or 0)
        if viewport_h <= 0:
            return

        n = len(self._option_buttons)
        spacing_total = self._OPTION_SPACING * max(0, n - 1)
        opt_padding = options.padding
        if isinstance(opt_padding, (tuple, list)) and len(opt_padding) >= 4:
            opt_pad_v = float(opt_padding[1] or 0) + float(opt_padding[3] or 0)
        elif isinstance(opt_padding, (tuple, list)) and len(opt_padding) == 2:
            opt_pad_v = float(opt_padding[1] or 0) * 2.0
        else:
            opt_pad_v = float(opt_padding or 0) * 2.0

        card_padding = card.padding
        if isinstance(card_padding, (tuple, list)) and len(card_padding) >= 4:
            card_pad_v = float(card_padding[1] or 0) + float(card_padding[3] or 0)
        elif isinstance(card_padding, (tuple, list)) and len(card_padding) == 2:
            card_pad_v = float(card_padding[1] or 0) * 2.0
        else:
            card_pad_v = float(card_padding or 0) * 2.0

        card_spacing = float(getattr(card, "spacing", 0) or 0)
        non_options_h = card_pad_v + card_spacing * 2.0
        for child in card.children:
            if child is options:
                continue
            non_options_h += float(getattr(child, "height", 0) or 0)

        available = max(0.0, viewport_h - non_options_h - spacing_total - opt_pad_v)
        per_button = self._clamp(
            available / max(1, n),
            float(self._MIN_OPTION_HEIGHT),
            float(self._MAX_OPTION_HEIGHT),
        )

        for btn in self._option_buttons:
            btn.height = per_button

        if per_button <= float(self._MIN_OPTION_HEIGHT) + 0.5:
            try:
                scroll.scroll_y = 1.0
            except Exception:
                pass

    def _handle_select(self, monitor_count: int) -> None:
        callback = self._on_select
        if callable(callback):
            callback(int(monitor_count))
            return
        self._on_back_clicked()

    def _on_back_clicked(self, *_args) -> None:
        if not self.manager:
            return
        if self.previous_screen and self.manager.has_screen(self.previous_screen):
            self.manager.current = self.previous_screen
        elif self.manager.screens:
            self.manager.current = self.manager.screens[0].name
