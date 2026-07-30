"""
Переиспользуемая верхняя панель меню приложения.
"""
from __future__ import annotations

from typing import Callable

from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.dropdown import DropDown
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from utils.ui_style import UI_TEXT_MUTED, UI_TEXT_PRIMARY, UI_TEXT_STRONG, apply_rounded_button, apply_rounded_panel


class MenuDropDown(DropDown):
    """DropDown с небольшим зазором от кнопки меню."""

    gap_y = dp(6)

    def _reposition(self, *largs):
        win = self._win
        if not win:
            return
        widget = self.attach_to
        if not widget or not widget.get_parent_window():
            return

        wx, wy = widget.to_window(*widget.pos)
        wright, wtop = widget.to_window(widget.right, widget.top)

        if self.auto_width:
            self.width = wright - wx

        x = wx
        if x + self.width > win.width:
            x = win.width - self.width
        if x < 0:
            x = 0
        self.x = x

        if self.max_height is not None:
            height = min(self.max_height, self.container.minimum_height)
        else:
            height = self.container.minimum_height

        gap = float(self.gap_y)
        h_bottom = wy - height - gap
        h_top = win.height - (wtop + height + gap)
        if h_bottom > 0:
            self.top = wy - gap
            self.height = height
        elif h_top > 0:
            self.y = wtop + gap
            self.height = height
        else:
            if h_top < h_bottom:
                self.top = self.height = max(0, wy - gap)
            else:
                self.y = wtop + gap
                self.height = max(0, win.height - wtop - gap)


class AppMenuBar(BoxLayout):
    """Простая menu bar на кнопках с выпадающими списками."""

    def __init__(
        self,
        menu_spec: dict[str, Callable | list[tuple[str, Callable | None]]],
        app_title: str | None = None,
        status_text: str | None = None,
        *,
        compact: bool = False,
        embedded: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self._compact = compact
        self._embedded = embedded
        if compact:
            self.spacing = dp(8)
            # В шапке (embedded): без левого внутреннего отступа; высота = высота полосы title bar.
            self.padding = (
                (0, dp(2), dp(4), dp(2)) if embedded else (dp(6), dp(2), dp(6), dp(2))
            )
            if embedded:
                self.size_hint_y = 1
            else:
                self.height = dp(48)
        else:
            self.height = dp(48)
            self.spacing = dp(10)
            self.padding = (dp(10), dp(6), dp(10), dp(6))
        if not embedded:
            apply_rounded_panel(
                self,
                base_rgba=(0.12, 0.12, 0.13, 1.0),
                radius_px=dp(8) if compact else dp(10),
                border_alpha=0.06,
            )

        self._menu_spec = menu_spec or {}
        self._app_title = app_title or ""
        self._status_text = status_text or ""
        self._active_dropdown = None
        self._active_menu_button = None
        self._build()
        if embedded:
            self.size_hint_x = None
            if not compact:
                self.size_hint_y = 1

            def _fit_width(*_a):
                try:
                    w = float(self.minimum_size[0])
                except Exception:
                    w = float(dp(200))
                self.width = max(w, 1.0)

            self.bind(minimum_size=_fit_width, children=_fit_width)
            Clock.schedule_once(_fit_width, 0)

    def _build(self):
        self.clear_widgets()

        if self._app_title:
            brand = Label(
                text=self._app_title,
                size_hint=(None, 1),
                width=self._measure_text_w(self._app_title, dp(13), padding=dp(24)),
                font_size=dp(13),
                bold=True,
                color=UI_TEXT_PRIMARY,
                halign="center",
                valign="middle",
            )
            brand.bind(size=lambda inst, s: setattr(inst, "text_size", s))
            apply_rounded_panel(brand, base_rgba=(0.18, 0.18, 0.19, 1), radius_px=dp(8), border_alpha=0.06)
            self.add_widget(brand)

        # Растягиваем только если слева есть бренд — иначе меню прижато к левому краю
        if self._app_title:
            self.add_widget(Widget(size_hint_x=1))

        fs = dp(12) if self._compact else dp(14)
        min_w = dp(80) if self._compact else dp(120)
        cap_pad = dp(22) if self._compact else dp(34)
        for section_name, section_action in self._menu_spec.items():
            section_btn = Button(
                text=section_name,
                size_hint=(None, 1),
                width=max(min_w, self._measure_text_w(section_name, fs, padding=cap_pad)),
                background_color=(0, 0, 0, 0),
                background_normal="",
                background_down="",
                font_size=fs,
            )
            section_btn.color = UI_TEXT_PRIMARY
            if callable(section_action):
                # Прямая action-кнопка (например, "Настройки") выделяется мягким акцентом.
                section_btn._menu_base_rgba = (0.28, 0.28, 0.30, 1)
                section_btn._menu_active_rgba = (0.34, 0.34, 0.36, 1)
                apply_rounded_button(section_btn, base_rgba=section_btn._menu_base_rgba, border_alpha=0.06)
                section_btn.bind(on_release=lambda _btn, cb=section_action: cb())
            else:
                section_btn._menu_base_rgba = (0.18, 0.18, 0.19, 1)
                section_btn._menu_active_rgba = (0.24, 0.24, 0.25, 1)
                apply_rounded_button(section_btn, base_rgba=section_btn._menu_base_rgba, border_alpha=0.06)
                section_btn.bind(on_release=lambda btn, _items=section_action: self._open_dropdown(btn, _items))
            self.add_widget(section_btn)

        if self._status_text:
            self.add_widget(Widget(size_hint_x=1))
            status = Label(
                text=self._status_text,
                size_hint=(None, 1),
                width=self._measure_text_w(self._status_text, dp(11), padding=dp(14)),
                font_size=dp(11),
                color=UI_TEXT_MUTED,
                halign="right",
                valign="middle",
            )
            status.bind(size=lambda inst, s: setattr(inst, "text_size", s))
            self.add_widget(status)

    def _measure_text_w(self, text: str, font_size: float, padding: float = 0.0) -> float:
        try:
            cl = CoreLabel(text=text, font_size=font_size, bold=False)
            cl.refresh()
            return float(cl.texture.size[0]) + float(padding)
        except Exception:
            return dp(120)

    def _open_dropdown(self, source_button: Button, items: list[tuple[str, Callable | None]]):
        if self._active_dropdown is not None:
            try:
                self._active_dropdown.dismiss()
            except Exception:
                pass
            self._active_dropdown = None

        max_caption_w = dp(0)
        for caption, _callback in items:
            max_caption_w = max(max_caption_w, self._measure_text_w(caption, dp(13), padding=dp(30)))
        dropdown_w = max(source_button.width, max_caption_w)
        dropdown = MenuDropDown(
            auto_width=False,
            width=dropdown_w,
            auto_dismiss=True,
            max_height=dp(360),
        )

        panel = BoxLayout(
            orientation="vertical",
            size_hint=(None, None),
            width=dropdown_w,
            spacing=dp(1),
            padding=(0, 0, 0, 0),
        )
        panel.height = (len(items) * dp(44)) + max(0, len(items) - 1) * dp(1)
        apply_rounded_panel(panel, base_rgba=(0.13, 0.13, 0.14, 1), radius_px=dp(0), border_alpha=0.06)

        source_button.color = UI_TEXT_STRONG
        apply_rounded_button(
            source_button,
            base_rgba=getattr(source_button, "_menu_active_rgba", (0.24, 0.24, 0.25, 1)),
            border_alpha=0.06,
        )
        self._active_dropdown = dropdown
        self._active_menu_button = source_button

        def _reset_active(*_args):
            if self._active_menu_button is source_button:
                source_button.color = UI_TEXT_PRIMARY
                apply_rounded_button(
                    source_button,
                    base_rgba=getattr(source_button, "_menu_base_rgba", (0.18, 0.18, 0.19, 1)),
                    border_alpha=0.06,
                )
                self._active_menu_button = None
            if self._active_dropdown is dropdown:
                self._active_dropdown = None

        dropdown.bind(on_dismiss=_reset_active)

        for caption, callback in items:
            item_btn = Button(
                text=caption,
                size_hint_y=None,
                height=dp(44),
                halign="left",
                valign="middle",
                text_size=(dropdown_w - dp(22), None),
                background_color=(0, 0, 0, 0),
                background_normal="",
                background_down="",
                font_size=dp(13),
            )
            item_btn.color = (0.94, 0.94, 0.98, 1)
            apply_rounded_button(item_btn, base_rgba=(0.18, 0.18, 0.19, 1), radius_px=dp(0), border_alpha=0.04)

            def _on_item_press(_instance, cb=callback, dd=dropdown):
                dd.dismiss()
                if cb:
                    cb()

            item_btn.bind(on_release=_on_item_press)
            panel.add_widget(item_btn)

        dropdown.add_widget(panel)
        dropdown.open(source_button)
