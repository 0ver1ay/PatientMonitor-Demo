from __future__ import annotations

from typing import Callable, Optional

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from components.bed_selection_screen import BedSelectionScreen
from components.esc_back_navigation import EscBackNavigationMixin
from utils.ui_style import (
    UI_BTN_DANGER,
    UI_BTN_SUCCESS,
    UI_CONTENT_PADDING_UNDER_TITLEBAR,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    UI_TEXT_STRONG,
    apply_rounded_button,
    apply_rounded_panel,
)


class LayoutCreationScreen(EscBackNavigationMixin, Screen):
    """Создание раскладки как отдельная страница."""

    def __init__(
        self,
        monitor_count: int,
        beds: list[dict],
        on_create: Optional[Callable[[str, list[dict]], tuple[bool, str]]] = None,
        previous_screen: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if "name" not in kwargs:
            self.name = "layout_creation_screen"
        self._init_esc_back_navigation()
        self.monitor_count = int(monitor_count)
        self.previous_screen = previous_screen
        self._beds = list(beds or [])
        self._on_create = on_create
        self._selector_buttons: list[Button] = []
        self._selector_index: list[int] = []
        self._bed_picker_screen_name = f"{self.name}_bed_picker"
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

        title_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(36),
            spacing=dp(10),
        )
        title = Label(
            text=f"Новая раскладка: {self.monitor_count} {self._monitor_word()}",
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
            text="Задайте имя раскладки и выберите кровать для каждого монитора.",
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

        body_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True, bar_width=dp(10))
        body = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(10),
            padding=(0, 0, 0, dp(6)),
        )
        body.bind(minimum_height=body.setter("height"))
        body_scroll.add_widget(body)

        name_card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(6),
            padding=(dp(14), dp(12), dp(14), dp(12)),
        )
        name_card.bind(minimum_height=name_card.setter("height"))
        apply_rounded_panel(name_card, base_rgba=(0.13, 0.13, 0.15, 1), radius_px=dp(10), border_alpha=0.06)
        name_label = Label(
            text="Название раскладки",
            size_hint_y=None,
            height=dp(20),
            font_size=dp(13),
            bold=True,
            color=UI_TEXT_STRONG,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        name_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        name_card.add_widget(name_label)
        self.name_input = TextInput(
            text=f"Раскладка {self.monitor_count} {self._monitor_word()}",
            multiline=False,
            size_hint_y=None,
            height=dp(40),
            font_size=dp(14),
            padding=(dp(10), dp(10), dp(10), dp(10)),
        )
        name_card.add_widget(self.name_input)
        body.add_widget(name_card)

        selectors_card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(8),
            padding=(dp(14), dp(12), dp(14), dp(12)),
        )
        selectors_card.bind(minimum_height=selectors_card.setter("height"))
        apply_rounded_panel(selectors_card, base_rgba=(0.13, 0.13, 0.15, 1), radius_px=dp(10), border_alpha=0.06)

        selectors_title = Label(
            text="Койко-места по мониторам",
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

        for idx in range(self.monitor_count):
            row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(42),
                spacing=dp(8),
            )
            label = Label(
                text=f"Монитор {idx + 1}",
                size_hint_x=None,
                width=dp(104),
                font_size=dp(12),
                color=UI_TEXT_MUTED,
                halign="left",
                valign="middle",
                text_size=(dp(104), None),
            )
            row.add_widget(label)
            btn = Button(
                text=self._button_text_for_index(0),
                size_hint=(1, 1),
                font_size=dp(13),
                background_color=(0, 0, 0, 0),
                background_normal="",
                background_down="",
                halign="left",
                valign="middle",
                shorten=True,
                shorten_from="right",
                text_size=(0, None),
            )
            btn.bind(size=lambda inst, s: setattr(inst, "text_size", (max(1, s[0] - dp(16)), None)))
            btn.color = UI_TEXT_PRIMARY
            apply_rounded_button(btn, base_rgba=(0.19, 0.19, 0.20, 1), border_alpha=0.06)
            btn.bind(on_release=lambda _inst, row_index=idx: self._open_bed_picker(row_index))
            row.add_widget(btn)
            selectors_card.add_widget(row)
            self._selector_buttons.append(btn)
            self._selector_index.append(0)

        hint = Label(
            text="Нажмите на строку монитора, чтобы открыть выбор койко-места.",
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
        root.add_widget(body_scroll)

        footer = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(6),
            padding=(dp(12), dp(10), dp(12), dp(10)),
        )
        footer.bind(minimum_height=footer.setter("height"))
        apply_rounded_panel(footer, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(12), border_alpha=0.06)
        self.error_label = Label(
            text="",
            size_hint_y=None,
            height=dp(18),
            font_size=dp(11),
            color=(0.95, 0.55, 0.45, 1),
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        self.error_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        footer.add_widget(self.error_label)

        buttons = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(10))
        buttons.add_widget(Widget())
        create_btn = Button(
            text="Создать",
            size_hint_x=None,
            width=dp(168),
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
            font_size=dp(14),
        )
        create_btn.color = UI_TEXT_PRIMARY
        apply_rounded_button(create_btn, base_rgba=UI_BTN_SUCCESS)
        create_btn.bind(on_release=self._create_layout)
        buttons.add_widget(create_btn)
        footer.add_widget(buttons)
        root.add_widget(footer)

        self.add_widget(root)

    def _monitor_word(self) -> str:
        if self.monitor_count == 1:
            return "монитор"
        if 2 <= self.monitor_count <= 4:
            return "монитора"
        return "мониторов"

    def _button_text_for_index(self, idx: int) -> str:
        if not self._beds:
            return "Нет доступных кроватей"
        idx = max(0, min(idx, len(self._beds) - 1))
        bed = self._beds[idx]
        bed_name = str(bed.get("name") or bed.get("bed_name") or f"Кровать {bed.get('id')}")
        return bed_name

    def _cycle_bed(self, row_index: int):
        if not self._beds:
            return
        next_idx = (self._selector_index[row_index] + 1) % len(self._beds)
        self._selector_index[row_index] = next_idx
        self._selector_buttons[row_index].text = self._button_text_for_index(next_idx)

    def _open_bed_picker(self, row_index: int):
        if not self._beds or not self.manager:
            return
        if row_index < 0 or row_index >= len(self._selector_index):
            return

        selected_idx = self._selector_index[row_index]
        current_bed_id = self._beds[selected_idx].get("id") if 0 <= selected_idx < len(self._beds) else None

        def _on_selected(bed_id, _bed_name, target_row=row_index):
            self._select_bed_for_row(target_row, bed_id)

        if self.manager.has_screen(self._bed_picker_screen_name):
            bed_screen = self.manager.get_screen(self._bed_picker_screen_name)
            if hasattr(bed_screen, "set_beds"):
                bed_screen.set_beds(self._beds)
            if hasattr(bed_screen, "set_current_bed_id"):
                bed_screen.set_current_bed_id(current_bed_id)
            if hasattr(bed_screen, "set_on_bed_selected"):
                bed_screen.set_on_bed_selected(_on_selected)
            bed_screen.previous_screen = self.name
            bed_screen.next_screen_on_select = None
            bed_screen.on_back = None
        else:
            bed_screen = BedSelectionScreen(
                name=self._bed_picker_screen_name,
                beds=self._beds,
                current_bed_id=current_bed_id,
                on_bed_selected=_on_selected,
                previous_screen=self.name,
                next_screen_on_select=None,
                show_header_nav=True,
            )
            self.manager.add_widget(bed_screen)

        self.manager.current = self._bed_picker_screen_name

    def _select_bed_for_row(self, row_index: int, bed_id):
        if row_index < 0 or row_index >= len(self._selector_index):
            return
        for idx, bed in enumerate(self._beds):
            if str(bed.get("id")) == str(bed_id):
                self._selector_index[row_index] = idx
                self._selector_buttons[row_index].text = self._button_text_for_index(idx)
                return

    def _selected_beds(self) -> list[dict]:
        result = []
        for idx in self._selector_index:
            if not self._beds:
                continue
            result.append(self._beds[idx])
        return result

    def _create_layout(self, *_args):
        name = self.name_input.text.strip()
        if not name:
            self.error_label.text = "Введите имя раскладки"
            return
        selected_beds = self._selected_beds()
        if len(selected_beds) != self.monitor_count:
            self.error_label.text = "Нет доступных кроватей для всех мониторов"
            return
        if self._on_create is None:
            self._on_back_clicked()
            return
        ok, message = self._on_create(name, selected_beds)
        self.error_label.text = "" if ok else str(message or "Не удалось создать раскладку")
        if ok:
            self._on_back_clicked()

    def _on_back_clicked(self, *_args):
        if self.manager:
            if self.previous_screen and self.manager.has_screen(self.previous_screen):
                self.manager.current = self.previous_screen
            elif self.manager.screens:
                self.manager.current = self.manager.screens[0].name
