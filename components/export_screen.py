from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.widget import Widget

from components.esc_back_navigation import EscBackNavigationMixin
from utils.ui_style import (
    UI_BTN_DANGER,
    UI_BTN_MUTED,
    UI_BTN_SECONDARY,
    UI_CONTENT_PADDING_UNDER_TITLEBAR,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    UI_TEXT_STRONG,
    apply_rounded_button,
    apply_rounded_panel,
)


class ExportScreen(EscBackNavigationMixin, Screen):
    """Полноэкранный экспорт вместо popup."""

    def __init__(
        self,
        export_dir: str | Path,
        aggregation_options: list[tuple[int, str]],
        has_reportlab: bool,
        on_choose_dir: Optional[Callable[[], str | None]] = None,
        on_export: Optional[Callable[[str, int | None, bool], None]] = None,
        previous_screen: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if "name" not in kwargs:
            self.name = "export_screen"
        self._init_esc_back_navigation()
        self.previous_screen = previous_screen
        self._export_dir = str(export_dir)
        self._aggregation_options = aggregation_options or []
        self._has_reportlab = bool(has_reportlab)
        self._on_choose_dir = on_choose_dir
        self._on_export = on_export
        self._agg_enabled = False
        self._agg_index = 1 if len(self._aggregation_options) > 1 else 0
        self._include_images = False
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
        title_label = Label(
            text="Экспорт истории",
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
            text="Экспорт параметров и кадров за выбранный период",
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

        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True, bar_width=dp(10))
        content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(10),
            padding=(0, 0, 0, dp(6)),
        )
        content.bind(minimum_height=content.setter("height"))
        scroll.add_widget(content)

        content.add_widget(self._build_export_dir_panel())
        content.add_widget(self._build_aggregation_panel())
        content.add_widget(self._build_images_panel())
        content.add_widget(self._build_format_panel())
        root.add_widget(scroll)

        status_card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(6),
            padding=(dp(12), dp(10), dp(12), dp(10)),
        )
        status_card.bind(minimum_height=status_card.setter("height"))
        apply_rounded_panel(status_card, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(12), border_alpha=0.06)
        self.status_label = Label(
            text="",
            size_hint_y=None,
            height=dp(18),
            font_size=dp(11),
            color=(0.92, 0.65, 0.50, 1),
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        self.status_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        status_card.add_widget(self.status_label)
        root.add_widget(status_card)

        self.add_widget(root)
        self._sync_agg_controls()

    def _build_export_dir_panel(self):
        panel = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(8),
            padding=(dp(12), dp(10), dp(12), dp(10)),
        )
        panel.bind(minimum_height=panel.setter("height"))
        apply_rounded_panel(panel, base_rgba=(0.13, 0.13, 0.15, 1), radius_px=dp(10), border_alpha=0.06)

        title = Label(
            text="Папка экспорта",
            size_hint_y=None,
            height=dp(20),
            font_size=dp(13),
            bold=True,
            color=UI_TEXT_STRONG,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        title.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        panel.add_widget(title)

        self.export_dir_label = Label(
            text=self._export_dir,
            size_hint_y=None,
            height=dp(34),
            font_size=dp(12),
            color=UI_TEXT_MUTED,
            halign="left",
            valign="middle",
            text_size=(0, None),
            shorten=True,
            shorten_from="left",
        )
        self.export_dir_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        panel.add_widget(self.export_dir_label)

        row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(40))
        choose_btn = Button(
            text="Папка…",
            size_hint_x=None,
            width=dp(140),
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
        )
        choose_btn.color = UI_TEXT_PRIMARY
        apply_rounded_button(choose_btn, base_rgba=UI_BTN_SECONDARY)
        choose_btn.bind(on_press=self._on_choose_dir_clicked)
        row.add_widget(choose_btn)
        row.add_widget(Widget())
        panel.add_widget(row)
        return panel

    def _build_aggregation_panel(self):
        panel = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(8),
            padding=(dp(12), dp(10), dp(12), dp(10)),
        )
        panel.bind(minimum_height=panel.setter("height"))
        apply_rounded_panel(panel, base_rgba=(0.13, 0.13, 0.15, 1), radius_px=dp(10), border_alpha=0.06)

        title = Label(
            text="Агрегация",
            size_hint_y=None,
            height=dp(22),
            font_size=dp(13),
            bold=True,
            color=UI_TEXT_STRONG,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        title.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        panel.add_widget(title)

        toggle_row = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(30))
        self.agg_checkbox = CheckBox(size_hint=(None, None), size=(dp(22), dp(22)), active=False)
        self.agg_checkbox.bind(active=self._on_agg_toggle)
        toggle_row.add_widget(self.agg_checkbox)
        toggle_label = Label(
            text="Включить агрегацию по периодам",
            font_size=dp(12),
            color=UI_TEXT_PRIMARY,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        toggle_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        toggle_row.add_widget(toggle_label)
        panel.add_widget(toggle_row)

        help_label = Label(
            text="При включении экспорт считает средние значения и может отбирать один кадр на период.",
            size_hint_y=None,
            height=dp(34),
            font_size=dp(11),
            color=UI_TEXT_MUTED,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        help_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        panel.add_widget(help_label)

        slider_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(36))
        slider_caption = Label(
            text="Период:",
            size_hint_x=None,
            width=dp(64),
            font_size=dp(12),
            color=UI_TEXT_PRIMARY,
            halign="left",
            valign="middle",
            text_size=(dp(64), None),
        )
        slider_row.add_widget(slider_caption)
        self.agg_slider = Slider(
            min=0,
            max=max(0, len(self._aggregation_options) - 1),
            step=1,
            value=self._agg_index,
        )
        self.agg_slider.bind(value=self._on_slider_value)
        slider_row.add_widget(self.agg_slider)
        self.agg_value_label = Label(
            text=self._current_aggregation_label(),
            size_hint_x=None,
            width=dp(76),
            font_size=dp(12),
            color=UI_TEXT_STRONG,
            halign="right",
            valign="middle",
            text_size=(dp(76), None),
        )
        slider_row.add_widget(self.agg_value_label)
        panel.add_widget(slider_row)
        return panel

    def _build_images_panel(self):
        panel = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(8),
            padding=(dp(12), dp(10), dp(12), dp(10)),
        )
        panel.bind(minimum_height=panel.setter("height"))
        apply_rounded_panel(panel, base_rgba=(0.13, 0.13, 0.15, 1), radius_px=dp(10), border_alpha=0.06)

        title = Label(
            text="Изображения",
            size_hint_y=None,
            height=dp(22),
            font_size=dp(13),
            bold=True,
            color=UI_TEXT_STRONG,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        title.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        panel.add_widget(title)

        row = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(30))
        include_images_checkbox = CheckBox(size_hint=(None, None), size=(dp(22), dp(22)), active=False)
        include_images_checkbox.bind(active=lambda _inst, active: setattr(self, "_include_images", bool(active)))
        row.add_widget(include_images_checkbox)
        label = Label(
            text="Включить изображения в экспорт",
            font_size=dp(12),
            color=UI_TEXT_PRIMARY,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        row.add_widget(label)
        panel.add_widget(row)

        help_label = Label(
            text="Фотографии сохраняются в отдельную папку рядом с итоговым файлом.",
            size_hint_y=None,
            height=dp(30),
            font_size=dp(11),
            color=UI_TEXT_MUTED,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        help_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        panel.add_widget(help_label)
        return panel

    def _build_format_panel(self):
        panel = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(8),
            padding=(dp(12), dp(10), dp(12), dp(10)),
        )
        panel.bind(minimum_height=panel.setter("height"))
        apply_rounded_panel(panel, base_rgba=(0.13, 0.13, 0.15, 1), radius_px=dp(10), border_alpha=0.06)

        title = Label(
            text="Формат",
            size_hint_y=None,
            height=dp(22),
            font_size=dp(13),
            bold=True,
            color=UI_TEXT_STRONG,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        title.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        panel.add_widget(title)

        row = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(42))
        for fmt in ("csv", "xls", "pdf"):
            btn = Button(
                text=fmt.upper(),
                background_color=(0, 0, 0, 0),
                background_normal="",
                background_down="",
            )
            btn.color = UI_TEXT_STRONG
            apply_rounded_button(btn, base_rgba=UI_BTN_MUTED)
            if fmt == "pdf" and not self._has_reportlab:
                btn.disabled = True
                btn.opacity = 0.5
            btn.bind(on_press=lambda _inst, fmt_name=fmt: self._on_export_clicked(fmt_name))
            row.add_widget(btn)
        panel.add_widget(row)

        if not self._has_reportlab:
            warn = Label(
                text="PDF недоступен: установите пакет reportlab в текущее окружение.",
                size_hint_y=None,
                height=dp(24),
                font_size=dp(11),
                color=(1, 0.75, 0.4, 1),
                halign="left",
                valign="middle",
                text_size=(0, None),
            )
            warn.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
            panel.add_widget(warn)
        return panel

    def _current_aggregation_label(self) -> str:
        if not self._aggregation_options:
            return "—"
        idx = max(0, min(int(self._agg_index), len(self._aggregation_options) - 1))
        return str(self._aggregation_options[idx][1])

    def _selected_aggregation_seconds(self) -> int | None:
        if not self._agg_enabled or not self._aggregation_options:
            return None
        idx = max(0, min(int(self._agg_index), len(self._aggregation_options) - 1))
        return int(self._aggregation_options[idx][0])

    def _sync_agg_controls(self):
        enabled = bool(self._agg_enabled)
        self.agg_slider.disabled = not enabled
        self.agg_slider.opacity = 1.0 if enabled else 0.45
        self.agg_value_label.color = UI_TEXT_STRONG if enabled else UI_TEXT_MUTED

    def _on_agg_toggle(self, _inst, active: bool):
        self._agg_enabled = bool(active)
        self._sync_agg_controls()

    def _on_slider_value(self, _inst, value: float):
        self._agg_index = int(round(value))
        self.agg_value_label.text = self._current_aggregation_label()

    def _on_choose_dir_clicked(self, *_args):
        if self._on_choose_dir is None:
            return
        try:
            selected = self._on_choose_dir()
        except Exception as e:
            self.status_label.text = str(e)
            return
        if selected:
            self._export_dir = str(selected)
            self.export_dir_label.text = self._export_dir
            self.status_label.text = ""

    def _on_export_clicked(self, fmt: str):
        if self._on_export is None:
            return
        self.status_label.text = ""
        try:
            self._on_export(fmt, self._selected_aggregation_seconds(), bool(self._include_images))
        except Exception as e:
            self.status_label.text = str(e)

    def _on_back_clicked(self, *_args):
        if self.manager:
            if self.previous_screen and self.manager.has_screen(self.previous_screen):
                self.manager.current = self.previous_screen
            elif self.manager.screens:
                self.manager.current = self.manager.screens[0].name
