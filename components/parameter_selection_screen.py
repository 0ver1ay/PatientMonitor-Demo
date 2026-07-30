"""
Экран выбора параметра для графика / цифрового блока.
Адаптивная вёрстка под узкие и широкие экраны.
"""
from typing import Callable, Dict, Optional

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from components.esc_back_navigation import has_open_modal_or_dropdown
from utils.popup_style import style_scrollview_popup
from utils.ui_style import (
    UI_BTN_DANGER,
    UI_BTN_MUTED,
    UI_BTN_SECONDARY,
    UI_BTN_SUCCESS,
    UI_CONTENT_PADDING_UNDER_TITLEBAR,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    UI_TEXT_STRONG,
    apply_rounded_button,
    apply_rounded_panel,
)


class ParameterSelectionScreen(Screen):
    """Экран для выбора параметра графика / цифрового блока."""

    _ULTRA_NARROW_PX = dp(520)
    _NARROW_PX = dp(720)
    _ULTRA_SHORT_PX = dp(420)
    _COMPACT_SHORT_PX = dp(540)

    def __init__(
        self,
        param_info: Dict = None,
        current_param_key: Optional[str] = None,
        on_parameter_selected: Optional[Callable] = None,
        previous_screen: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if "name" not in kwargs:
            self.name = "parameter_selection"
        self.param_info = param_info or {}
        self.available_param_keys: set = set()
        self.filter_available_only = False
        self.current_param_key = current_param_key
        self.on_parameter_selected = on_parameter_selected
        self.previous_screen = previous_screen
        self.selection_title_text = "Выбор параметра для показа"
        self.current_label_prefix = "Текущий параметр"
        self._esc_handler_bound = False
        self._relayout_trigger = Clock.create_trigger(lambda *_: self._apply_responsive_layout(), 0)
        self._refresh_list_trigger = Clock.create_trigger(lambda *_: self._update_parameters_list(), 0)
        self._create_ui()
        self.bind(width=lambda *_: self._relayout_trigger())
        self.bind(height=lambda *_: self._relayout_trigger())
        Clock.schedule_once(lambda *_: self._apply_responsive_layout(), 0)

    def on_pre_enter(self, *args):
        self._bind_escape_handler()
        self._relayout_trigger()
        return super().on_pre_enter(*args)

    def on_pre_leave(self, *args):
        self._unbind_escape_handler()
        return super().on_pre_leave(*args)

    def set_param_info(self, param_info: Dict):
        self.param_info = param_info
        self._refresh_list_trigger()

    def set_available_param_keys(self, param_keys):
        self.available_param_keys = set(param_keys or [])
        self._refresh_list_trigger()

    def set_current_param_key(self, param_key: Optional[str]):
        self.current_param_key = param_key
        self._refresh_list_trigger()

    def set_on_parameter_selected(self, callback: Callable):
        self.on_parameter_selected = callback

    def set_selection_title(self, title: str, current_label_prefix: Optional[str] = None):
        self.selection_title_text = str(title or "Выбор параметра для показа")
        if current_label_prefix is not None:
            self.current_label_prefix = str(current_label_prefix or "Текущий параметр")
        if hasattr(self, "title_label"):
            self.title_label.text = self.selection_title_text
        self._update_summary_label()

    def _create_ui(self):
        self._btn_base = UI_BTN_SECONDARY
        self._btn_current = UI_BTN_SUCCESS
        self._btn_text = UI_TEXT_PRIMARY
        self._card_h = dp(56)

        main_container = BoxLayout(
            orientation="vertical",
            spacing=dp(8),
            padding=UI_CONTENT_PADDING_UNDER_TITLEBAR,
        )
        self._main_container = main_container

        header_card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(6),
            padding=(dp(12), dp(10), dp(12), dp(10)),
        )
        header_card.bind(minimum_height=header_card.setter("height"))
        apply_rounded_panel(header_card, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(12), border_alpha=0.06)
        self._header_card = header_card

        title_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(32),
            spacing=dp(8),
        )
        self._title_row = title_row

        self.title_label = Label(
            text=self.selection_title_text,
            size_hint=(1, None),
            height=dp(32),
            font_size=dp(16),
            bold=True,
            color=UI_TEXT_STRONG,
            halign="left",
            valign="middle",
            shorten=True,
            shorten_from="right",
            text_size=(0, None),
        )
        self.title_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], s[1])))
        title_row.add_widget(self.title_label)

        self.back_button = Button(
            text="Назад",
            size_hint_x=None,
            width=dp(92),
            height=dp(32),
            font_size=dp(13),
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
        )
        self.back_button.color = self._btn_text
        apply_rounded_button(self.back_button, base_rgba=UI_BTN_DANGER, radius_px=dp(9))
        self.back_button.bind(on_press=self._on_back_clicked)
        title_row.add_widget(self.back_button)
        header_card.add_widget(title_row)

        self.subtitle_label = Label(
            text="Выберите параметр из списка ниже.",
            size_hint_y=None,
            height=dp(16),
            font_size=dp(11),
            color=UI_TEXT_MUTED,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        self.subtitle_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        header_card.add_widget(self.subtitle_label)

        self.summary_label = Label(
            text="",
            size_hint_y=None,
            height=dp(28),
            font_size=dp(12),
            halign="left",
            valign="middle",
            color=UI_TEXT_PRIMARY,
            shorten=True,
            shorten_from="right",
            padding=(dp(10), 0),
            text_size=(0, None),
        )
        self.summary_label.bind(size=lambda inst, s: setattr(inst, "text_size", (max(1, s[0] - dp(20)), s[1])))
        apply_rounded_panel(self.summary_label, base_rgba=(0.16, 0.16, 0.18, 1), radius_px=dp(8), border_alpha=0.05)
        header_card.add_widget(self.summary_label)
        main_container.add_widget(header_card)

        list_card = BoxLayout(
            orientation="vertical",
            size_hint=(1, 1),
            spacing=dp(6),
            padding=(dp(8), dp(8), dp(8), dp(8)),
        )
        apply_rounded_panel(list_card, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(12), border_alpha=0.06)
        self._list_card = list_card

        list_header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(22),
            spacing=dp(8),
        )
        self.list_title = Label(
            text="Доступные параметры",
            size_hint=(1, None),
            height=dp(22),
            font_size=dp(13),
            bold=True,
            color=UI_TEXT_STRONG,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        self.list_title.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        list_header.add_widget(self.list_title)

        self.list_count_badge = Label(
            text="0",
            size_hint=(None, None),
            width=dp(36),
            height=dp(22),
            font_size=dp(11),
            color=UI_TEXT_PRIMARY,
            halign="center",
            valign="middle",
        )
        self.list_count_badge.bind(size=lambda inst, s: setattr(inst, "text_size", s))
        apply_rounded_panel(self.list_count_badge, base_rgba=(0.18, 0.18, 0.19, 1), radius_px=dp(7), border_alpha=0.05)
        list_header.add_widget(self.list_count_badge)
        list_card.add_widget(list_header)

        self.scroll = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=dp(8),
            scroll_type=["bars", "content"],
        )
        style_scrollview_popup(self.scroll)

        self.params_grid = GridLayout(
            cols=2,
            spacing=dp(6),
            size_hint_y=None,
            padding=(0, dp(2), 0, dp(2)),
        )
        self.params_grid.bind(minimum_height=self.params_grid.setter("height"))
        self.scroll.bind(width=lambda *_: self._refresh_list_trigger())

        self.scroll.add_widget(self.params_grid)
        list_card.add_widget(self.scroll)
        main_container.add_widget(list_card)

        self.add_widget(main_container)
        self._update_parameters_list()

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

    def _is_ultra_narrow(self) -> bool:
        return float(getattr(self, "width", 0) or 0) <= self._ULTRA_NARROW_PX

    def _is_narrow(self) -> bool:
        return float(getattr(self, "width", 0) or 0) <= self._NARROW_PX

    def _is_ultra_short(self) -> bool:
        return float(getattr(self, "height", 0) or 0) <= float(self._ULTRA_SHORT_PX)

    def _is_compact_short(self) -> bool:
        return float(getattr(self, "height", 0) or 0) <= float(self._COMPACT_SHORT_PX)

    def _layout_tier(self) -> int:
        """0 = normal, 1 = compact, 2 = ultra (узкий экран или мало высоты)."""
        if self._is_ultra_narrow() or self._is_ultra_short():
            return 2
        if self._is_narrow() or self._is_compact_short():
            return 1
        return 0

    def _apply_responsive_layout(self) -> None:
        tier = self._layout_tier()

        if tier == 2:
            title_fs, title_h = dp(14), dp(28)
            back_w, back_fs = dp(72), dp(12)
            subtitle_h = 0
            subtitle_opacity = 0
            summary_fs, summary_h = dp(11), dp(26)
            self._main_container.spacing = dp(6)
            self._header_card.padding = (dp(10), dp(8), dp(10), dp(8))
            self._header_card.spacing = dp(5)
            self._list_card.padding = (dp(6), dp(6), dp(6), dp(6))
            self._card_h = dp(44)
        elif tier == 1:
            title_fs, title_h = dp(15), dp(30)
            back_w, back_fs = dp(84), dp(13)
            subtitle_h = dp(16)
            subtitle_opacity = 1
            summary_fs, summary_h = dp(12), dp(28)
            self._main_container.spacing = dp(7)
            self._header_card.padding = (dp(11), dp(9), dp(11), dp(9))
            self._header_card.spacing = dp(6)
            self._list_card.padding = (dp(7), dp(7), dp(7), dp(7))
            self._card_h = dp(50)
        else:
            title_fs, title_h = dp(16), dp(32)
            back_w, back_fs = dp(96), dp(13)
            subtitle_h = dp(16)
            subtitle_opacity = 1
            summary_fs, summary_h = dp(12), dp(28)
            self._main_container.spacing = dp(8)
            self._header_card.padding = (dp(12), dp(10), dp(12), dp(10))
            self._header_card.spacing = dp(6)
            self._list_card.padding = (dp(8), dp(8), dp(8), dp(8))
            self._card_h = dp(56)

        self.title_label.font_size = title_fs
        self.title_label.height = title_h
        self._title_row.height = title_h
        self.back_button.width = back_w
        self.back_button.height = title_h
        self.back_button.font_size = back_fs

        self.subtitle_label.height = subtitle_h
        self.subtitle_label.opacity = subtitle_opacity
        self.subtitle_label.disabled = subtitle_opacity == 0

        self.summary_label.font_size = summary_fs
        self.summary_label.height = summary_h

        self._refresh_list_trigger()

    def _update_summary_label(self) -> None:
        if not hasattr(self, "summary_label"):
            return
        total_count = len(self.param_info or {})
        current_name = ""
        if self.current_param_key and self.current_param_key in (self.param_info or {}):
            current_name = str(self.param_info[self.current_param_key].get("name") or "")

        if current_name:
            current_part = f"{self.current_label_prefix}: {current_name}"
        else:
            current_part = "Параметр не выбран"

        if total_count > 0:
            self.summary_label.text = f"{current_part}  ·  всего сигналов: {total_count}"
        else:
            self.summary_label.text = current_part

    def _update_parameters_list(self) -> None:
        self.params_grid.clear_widgets()

        visible_param_info = self._get_visible_param_info()
        self.params_grid.cols = self._get_grid_cols()
        self._update_summary_label()

        visible_count = len(visible_param_info)
        self.list_count_badge.text = str(visible_count)

        if not visible_param_info:
            no_params_label = Label(
                text="Нет доступных параметров",
                size_hint_y=None,
                height=dp(80),
                font_size=dp(14),
                color=(0.8, 0.8, 0.8, 1),
                halign="center",
                valign="middle",
            )
            no_params_label.bind(size=lambda inst, size: setattr(inst, "text_size", size))
            self.params_grid.add_widget(no_params_label)
            self.params_grid.height = dp(80)
            return

        cols = max(1, int(self.params_grid.cols or 1))
        num_rows = (visible_count + cols - 1) // cols
        self.params_grid.height = num_rows * (self._card_h + dp(6)) + dp(2)

        for param_key, param_data in visible_param_info.items():
            is_current = param_key == self.current_param_key
            has_data = (not self.available_param_keys) or (param_key in self.available_param_keys)

            rgb_color = self._hex_to_rgb(param_data["color"])
            param_button = Button(
                text=("Текущий: " if is_current else "") + param_data["name"],
                size_hint_y=None,
                height=self._card_h,
                font_size=dp(11) if self._layout_tier() == 2 else dp(12),
                background_color=(0, 0, 0, 0),
                background_normal="",
                background_down="",
                shorten=True,
                shorten_from="right",
                halign="center",
                valign="middle",
                text_size=(0, 0),
            )
            param_button.bind(
                size=lambda inst, s: setattr(inst, "text_size", (max(1, s[0] - dp(10)), max(1, s[1] - dp(6))))
            )
            try:
                param_button.color = rgb_color
            except Exception:
                param_button.color = self._btn_text

            if is_current:
                param_button.color = (1, 1, 1, 1)
                base_rgba = self._btn_current
            elif not has_data:
                param_button.color = UI_TEXT_MUTED
                base_rgba = UI_BTN_MUTED
            else:
                base_rgba = self._btn_base
            apply_rounded_button(param_button, base_rgba=base_rgba, radius_px=dp(8))

            param_button.bind(
                on_press=lambda instance, key=param_key, data=param_data: self._on_parameter_clicked(key, data)
            )

            self.params_grid.add_widget(param_button)

    def _get_grid_cols(self) -> int:
        width = float(getattr(self, "width", 0) or 0)
        height = float(getattr(self, "height", 0) or 0)
        if height <= float(dp(400)):
            return 1
        if width <= dp(520):
            return 1
        if width <= dp(820):
            return 2
        if height <= float(dp(520)) and width <= dp(1100):
            return 2
        if width <= dp(1200):
            return 3
        return 4

    def _get_visible_param_info(self) -> Dict:
        if not self.filter_available_only:
            return self.param_info
        if not self.available_param_keys:
            return {}
        return {
            key: value
            for key, value in self.param_info.items()
            if key in self.available_param_keys
        }

    def _hex_to_rgb(self, hex_color):
        if isinstance(hex_color, str):
            hex_color = hex_color.lstrip("#")
            if len(hex_color) == 6:
                return tuple(int(hex_color[i:i + 2], 16) / 255.0 for i in (0, 2, 4)) + (1,)
        return (1, 1, 1, 1)

    def _on_parameter_clicked(self, param_key: str, param_data: Dict):
        if self.on_parameter_selected:
            self.on_parameter_selected(param_key, param_data)
        self._on_back_clicked()

    def _on_back_clicked(self, *args):
        if not self.manager:
            return
        if self.previous_screen and self.manager.has_screen(self.previous_screen):
            self.manager.current = self.previous_screen
            return
        if self.manager.has_screen("main_window_manager"):
            self.manager.current = "main_window_manager"
            return
        for screen in self.manager.screens:
            if screen.name.startswith("monitor_window_"):
                self.manager.current = screen.name
                break
