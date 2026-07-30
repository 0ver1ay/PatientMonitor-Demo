from __future__ import annotations

from typing import Callable, Optional

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from components.esc_back_navigation import EscBackNavigationMixin
from utils.ui_style import (
    UI_BTN_DANGER,
    UI_BTN_MUTED,
    UI_CONTENT_PADDING_UNDER_TITLEBAR,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    UI_TEXT_STRONG,
    apply_rounded_button,
    apply_rounded_panel,
)


class ActionListScreen(EscBackNavigationMixin, Screen):
    """Полноэкранный список действий вместо popup-меню."""

    # Пороги: ~1/4–1/6 от 1920x1080 и плитки в сетке мониторов
    _ULTRA_W = dp(520)
    _ULTRA_H = dp(420)
    _COMPACT_W = dp(640)
    _COMPACT_H = dp(540)

    def __init__(
        self,
        title_text: str,
        previous_screen: Optional[str] = None,
        subtitle_text: str = "",
        **kwargs,
    ):
        super().__init__(**kwargs)
        if "name" not in kwargs:
            self.name = "action_list_screen"
        self._init_esc_back_navigation()
        self.previous_screen = previous_screen
        self._title_text = title_text
        self._subtitle_text = subtitle_text
        self._sections: list[tuple[str, list[dict]]] = []
        self._last_layout_mode: int | None = None
        self._relayout_trigger = Clock.create_trigger(self._apply_responsive_layout, 0)
        self._create_ui()
        self.bind(width=lambda *_: self._relayout_trigger())
        self.bind(height=lambda *_: self._relayout_trigger())

    def on_pre_enter(self, *args):
        self._bind_escape_handler()
        self._last_layout_mode = None
        Clock.schedule_once(lambda *_: self._apply_responsive_layout(), 0)
        return super().on_pre_enter(*args)

    def on_pre_leave(self, *args):
        self._unbind_escape_handler()
        return super().on_pre_leave(*args)

    def set_sections(self, sections: list[tuple[str, list[dict]]]):
        self._sections = sections or []
        self._render_sections()
        self._relayout_trigger()

    def _layout_mode(self) -> int:
        """0 = normal, 1 = compact, 2 = ultra."""
        w = float(self.width or 0)
        h = float(self.height or 0)
        if w <= float(self._ULTRA_W) or h <= float(self._ULTRA_H):
            return 2
        if w <= float(self._COMPACT_W) or h <= float(self._COMPACT_H):
            return 1
        return 0

    def _create_ui(self):
        self._root = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=UI_CONTENT_PADDING_UNDER_TITLEBAR,
        )

        self._header = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(8),
            padding=(dp(14), dp(12), dp(14), dp(12)),
        )
        self._header.bind(minimum_height=self._header.setter("height"))
        apply_rounded_panel(self._header, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(12), border_alpha=0.06)

        self._title_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(10))
        self._title = Label(
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
        self._title.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        self._title_row.add_widget(self._title)

        self._back_button = Button(
            text="Назад",
            size_hint_x=None,
            width=dp(104),
            height=dp(36),
            font_size=dp(14),
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
        )
        self._back_button.color = UI_TEXT_PRIMARY
        apply_rounded_button(self._back_button, base_rgba=UI_BTN_DANGER, radius_px=dp(9))
        self._back_button.bind(on_release=self._on_back_clicked)
        self._title_row.add_widget(self._back_button)
        self._header.add_widget(self._title_row)

        self._subtitle = Label(
            text=self._subtitle_text or "Выберите действие",
            size_hint_y=None,
            height=dp(20),
            font_size=dp(12),
            color=UI_TEXT_MUTED,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        self._subtitle.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        self._header.add_widget(self._subtitle)
        self._root.add_widget(self._header)

        self._body = BoxLayout(
            orientation="vertical",
            size_hint=(1, 1),
            padding=(dp(12), dp(12), dp(12), dp(12)),
        )
        apply_rounded_panel(self._body, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(12), border_alpha=0.06)

        self._scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True, bar_width=dp(10))
        self.content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(10),
            padding=(0, 0, 0, dp(4)),
        )
        self.content.bind(minimum_height=self.content.setter("height"))
        self._scroll.add_widget(self.content)
        self._body.add_widget(self._scroll)
        self._root.add_widget(self._body)
        self.add_widget(self._root)

        # Дефолты для кнопок секций (обновляются в _apply_responsive_layout)
        self._action_btn_height = dp(42)
        self._section_spacing = dp(8)
        self._section_padding = (dp(10), dp(10), dp(10), dp(10))
        self._section_label_h = dp(20)
        self._section_label_fs = dp(12)
        self._action_font_size = dp(13)

    def _apply_responsive_layout(self, *_args) -> None:
        mode = self._layout_mode()
        if mode == self._last_layout_mode:
            return
        self._last_layout_mode = mode

        if mode == 2:
            self._root.spacing = dp(6)
            self._root.padding = (0, dp(6), 0, dp(8))
            self._header.spacing = dp(5)
            self._header.padding = (dp(10), dp(8), dp(10), dp(8))
            tr_h, title_fs = dp(28), dp(14)
            back_w, back_fs = dp(72), dp(12)
            sub_h, sub_op = 0, 0.0
            body_pad = (dp(8), dp(8), dp(8), dp(8))
            scroll_bar = dp(8)
            content_spacing = dp(6)
            self._action_btn_height = dp(36)
            self._section_spacing = dp(5)
            self._section_padding = (dp(8), dp(8), dp(8), dp(8))
            self._section_label_h = dp(18)
            self._section_label_fs = dp(11)
            self._action_font_size = dp(12)
        elif mode == 1:
            self._root.spacing = dp(8)
            self._root.padding = (0, dp(7), 0, dp(9))
            self._header.spacing = dp(6)
            self._header.padding = (dp(12), dp(10), dp(12), dp(10))
            tr_h, title_fs = dp(32), dp(16)
            back_w, back_fs = dp(92), dp(13)
            sub_h, sub_op = dp(18), 1.0
            body_pad = (dp(10), dp(10), dp(10), dp(10))
            scroll_bar = dp(9)
            content_spacing = dp(8)
            self._action_btn_height = dp(40)
            self._section_spacing = dp(6)
            self._section_padding = (dp(9), dp(9), dp(9), dp(9))
            self._section_label_h = dp(19)
            self._section_label_fs = dp(11)
            self._action_font_size = dp(12)
        else:
            self._root.spacing = dp(10)
            self._root.padding = UI_CONTENT_PADDING_UNDER_TITLEBAR
            self._header.spacing = dp(8)
            self._header.padding = (dp(14), dp(12), dp(14), dp(12))
            tr_h, title_fs = dp(36), dp(18)
            back_w, back_fs = dp(104), dp(14)
            sub_h, sub_op = dp(20), 1.0
            body_pad = (dp(12), dp(12), dp(12), dp(12))
            scroll_bar = dp(10)
            content_spacing = dp(10)
            self._action_btn_height = dp(42)
            self._section_spacing = dp(8)
            self._section_padding = (dp(10), dp(10), dp(10), dp(10))
            self._section_label_h = dp(20)
            self._section_label_fs = dp(12)
            self._action_font_size = dp(13)

        self._title_row.height = tr_h
        self._title.height = tr_h
        self._title.font_size = title_fs
        self._back_button.width = back_w
        self._back_button.height = tr_h
        self._back_button.font_size = back_fs

        self._subtitle.height = sub_h
        self._subtitle.opacity = sub_op
        self._subtitle.disabled = sub_op == 0

        self._body.padding = body_pad
        self._scroll.bar_width = scroll_bar
        self.content.spacing = content_spacing

        self._render_sections()

    def _render_sections(self):
        self.content.clear_widgets()
        btn_h = getattr(self, "_action_btn_height", dp(42))
        sec_sp = getattr(self, "_section_spacing", dp(8))
        sec_pad = getattr(self, "_section_padding", (dp(10),) * 4)
        lbl_h = getattr(self, "_section_label_h", dp(20))
        lbl_fs = getattr(self, "_section_label_fs", dp(12))
        act_fs = getattr(self, "_action_font_size", dp(13))

        for section_title, actions in self._sections:
            section = BoxLayout(
                orientation="vertical",
                size_hint_y=None,
                spacing=sec_sp,
                padding=sec_pad,
            )
            section.bind(minimum_height=section.setter("height"))
            apply_rounded_panel(section, base_rgba=(0.13, 0.13, 0.15, 1), radius_px=dp(10), border_alpha=0.06)

            label = Label(
                text=section_title,
                size_hint_y=None,
                height=lbl_h,
                font_size=lbl_fs,
                color=UI_TEXT_MUTED,
                halign="left",
                valign="middle",
                text_size=(0, None),
            )
            label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
            section.add_widget(label)

            for action in actions or []:
                btn = Button(
                    text=str(action.get("text") or ""),
                    size_hint_y=None,
                    height=btn_h,
                    font_size=act_fs,
                    background_color=(0, 0, 0, 0),
                    background_normal="",
                    background_down="",
                )
                btn.color = UI_TEXT_PRIMARY
                apply_rounded_button(btn, base_rgba=tuple(action.get("base_rgba") or UI_BTN_MUTED))
                btn.bind(on_release=lambda _inst, act=action: self._run_action(act))
                section.add_widget(btn)

            self.content.add_widget(section)

    def _run_action(self, action: dict):
        callback = action.get("on_press")
        if callable(callback):
            callback()
        if bool(action.get("return_back", False)):
            self._on_back_clicked()

    def _on_back_clicked(self, *_args):
        if self.manager:
            if self.previous_screen and self.manager.has_screen(self.previous_screen):
                self.manager.current = self.previous_screen
            elif self.manager.screens:
                self.manager.current = self.manager.screens[0].name
