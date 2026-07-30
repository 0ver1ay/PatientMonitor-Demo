from __future__ import annotations

from typing import Callable, Optional

from kivy.core.window import Window
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from components.esc_back_navigation import EscBackNavigationMixin
from utils.config_loader import ConfigLoader
from utils.popup_style import style_scrollview_popup
from utils.ui_style import (
    UI_BTN_DANGER,
    UI_BTN_SUCCESS,
    UI_CONTENT_PADDING_UNDER_TITLEBAR,
    UI_CURSOR_NEUTRAL,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    UI_TEXT_STRONG,
    apply_rounded_button,
    apply_rounded_panel,
)


class SettingsScreen(EscBackNavigationMixin, Screen):
    """Полноэкранные настройки приложения вместо popup."""

    def __init__(
        self,
        settings_data: dict,
        on_save: Callable[[dict], bool] | None = None,
        previous_screen: Optional[str] = None,
        title_text: str = "Настройки приложения",
        **kwargs,
    ):
        super().__init__(**kwargs)
        if "name" not in kwargs:
            self.name = "settings_screen"
        self._init_esc_back_navigation()
        self.previous_screen = previous_screen
        self._on_save = on_save
        self._title_text = title_text
        self._settings_data = settings_data or {}
        self._inputs: dict[str, TextInput | Button] = {}
        self._status_label: Label | None = None
        self._password_input: TextInput | None = None
        self._page_host: BoxLayout | None = None
        self._page_scroll: ScrollView | None = None
        self._tab_buttons: dict[str, Button] = {}
        self._pages: dict[str, BoxLayout] = {}
        self._active_tab = "database"
        self._compact_ui = Window.height <= dp(820)
        self._tabs_scroll: ScrollView | None = None
        self._tabs_row: BoxLayout | None = None
        self._build()

    def on_pre_enter(self, *args):
        self._bind_escape_handler()
        return super().on_pre_enter(*args)

    def on_pre_leave(self, *args):
        self._unbind_escape_handler()
        return super().on_pre_leave(*args)

    def _build(self):
        root = BoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=UI_CONTENT_PADDING_UNDER_TITLEBAR,
        )

        header_card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(8),
            padding=(dp(14), dp(12), dp(14), dp(12)),
        )
        header_card.bind(minimum_height=header_card.setter("height"))
        apply_rounded_panel(header_card, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(12), border_alpha=0.06)

        title_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(36),
            spacing=dp(10),
        )
        title = Label(
            text=self._title_text,
            font_size=dp(18),
            bold=True,
            color=UI_TEXT_STRONG,
            halign="left",
            valign="middle",
            size_hint=(1, None),
            height=dp(36),
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
        back_button.bind(on_press=self._on_back_clicked)
        title_row.add_widget(back_button)
        header_card.add_widget(title_row)

        sub = Label(
            text="Запись в config.ini. После смены БД перезапустите окна мониторов.",
            font_size=dp(10) if self._compact_ui else dp(11),
            color=UI_TEXT_MUTED,
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(18) if self._compact_ui else dp(22),
            text_size=(0, None),
        )
        sub.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        header_card.add_widget(sub)
        root.add_widget(header_card)

        tabs_scroll = ScrollView(
            size_hint_y=None,
            height=dp(38) if self._compact_ui else dp(42),
            do_scroll_x=True,
            do_scroll_y=False,
            bar_width=dp(6),
            scroll_type=["bars", "content"],
        )
        style_scrollview_popup(tabs_scroll)
        self._tabs_scroll = tabs_scroll

        tabs = BoxLayout(
            orientation="horizontal",
            size_hint=(None, 1),
            spacing=dp(8) if self._compact_ui else dp(12),
            padding=(dp(2), 0, dp(2), 0),
        )
        tabs.bind(minimum_width=tabs.setter("width"))
        self._tabs_row = tabs
        tabs_scroll.add_widget(tabs)
        root.add_widget(tabs_scroll)

        db = self._settings_data.get("database", {})
        viewer = self._settings_data.get("viewer_auto_periods", {})
        layout_grid = self._settings_data.get("layout_grid", {})

        pane_db = self._pane_shell()
        self._add_title_line(pane_db, "PostgreSQL")
        self._add_h_field(pane_db, "Хост", "database.host", str(db.get("host", "")), hint_text="localhost")
        self._add_h_field(pane_db, "Порт", "database.port", str(db.get("port", 6000)), hint_text="5432")
        self._add_h_field(pane_db, "База", "database.database", str(db.get("database", "")))
        self._add_h_field(pane_db, "Пользователь", "database.user", str(db.get("user", "")))
        self._add_password_compact(pane_db, str(db.get("password", "")))
        apply_rounded_panel(pane_db, base_rgba=(0.15, 0.15, 0.18, 1), radius_px=dp(10), border_alpha=0.06)
        self._pages["database"] = pane_db

        pane_ui = self._pane_shell()
        self._add_title_line(pane_ui, "Показатели и камера по умолчанию")
        self._add_h_field(
            pane_ui,
            "Показатель 1",
            "database.display_value_1",
            str(db.get("display_value_1", "spo2")),
            hint_text="spo2",
        )
        self._add_h_field(
            pane_ui,
            "Показатель 2",
            "database.display_value_2",
            str(db.get("display_value_2", "pulse")),
            hint_text="pulse",
        )
        self._add_h_field(
            pane_ui,
            "Камера",
            "database.camera_image_path",
            str(db.get("camera_image_path", "")),
            hint_text="файл или URL",
        )
        apply_rounded_panel(pane_ui, base_rgba=(0.15, 0.15, 0.18, 1), radius_px=dp(10), border_alpha=0.06)
        self._pages["interface"] = pane_ui

        pane_v = self._pane_shell(spacing=dp(6))
        self._add_title_line(pane_v, "Шаг агрегации, сек")
        hint = Label(
            text="Для каждой длительности окна истории",
            font_size=dp(10),
            color=(0.58, 0.58, 0.64, 1),
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(16),
            text_size=(0, None),
        )
        hint.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        pane_v.add_widget(hint)

        viewer_labels = [
            ("range_1m", "≤1 мин"),
            ("range_5m", "≤5 мин"),
            ("range_15m", "≤15 м"),
            ("range_30m", "≤30 м"),
            ("range_1h", "≤1 ч"),
            ("range_2h", "≤2 ч"),
            ("range_4h", "≤4 ч"),
            ("range_1d", "≤1 д"),
            ("range_over_1d", ">1 д"),
        ]
        grid = GridLayout(cols=3, spacing=(dp(8), dp(6)), size_hint_y=None)
        cell_h = dp(50)
        grid.height = 3 * cell_h + 2 * dp(6)
        for key, short_title in viewer_labels:
            cell = BoxLayout(orientation="vertical", size_hint_y=None, height=cell_h, spacing=dp(2))
            lbl = Label(
                text=short_title,
                font_size=dp(10),
                color=(0.68, 0.68, 0.74, 1),
                halign="left",
                valign="bottom",
                size_hint_y=None,
                height=dp(14),
                text_size=(0, None),
            )
            lbl.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
            inp = TextInput(
                text=str(viewer.get(key, "")),
                multiline=False,
                size_hint_y=None,
                height=dp(32),
                hint_text="сек",
                font_size=dp(13),
            )
            self._style_input(inp, compact=True)
            self._inputs[f"viewer_auto_periods.{key}"] = inp
            cell.add_widget(lbl)
            cell.add_widget(inp)
            grid.add_widget(cell)
        pane_v.add_widget(grid)
        apply_rounded_panel(pane_v, base_rgba=(0.15, 0.15, 0.18, 1), radius_px=dp(10), border_alpha=0.06)
        self._pages["viewer"] = pane_v

        pane_g = self._pane_shell(spacing=dp(6))
        self._add_title_line(pane_g, "Сетки раскладок 2-8")
        grid_hint = Label(
            text="Для каждого количества мониторов выберите общий вариант сетки.",
            font_size=dp(10),
            color=(0.58, 0.58, 0.64, 1),
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(16),
            text_size=(0, None),
        )
        grid_hint.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        pane_g.add_widget(grid_hint)
        for monitor_count in range(2, 9):
            key = f"layout_{monitor_count}"
            options = list(ConfigLoader.get_layout_grid_options(monitor_count))
            value = str(layout_grid.get(key, ConfigLoader.get_default_layout_grid(monitor_count)))
            self._add_grid_selector_row(
                pane_g,
                label_text=f"{monitor_count} монитор{'а' if 2 <= monitor_count <= 4 else 'ов'}",
                key=f"layout_grid.{key}",
                value=value,
                options=options,
            )
        apply_rounded_panel(pane_g, base_rgba=(0.15, 0.15, 0.18, 1), radius_px=dp(10), border_alpha=0.06)
        self._pages["layout_grid"] = pane_g

        self._add_tab_button(tabs, "database", "База данных")
        self._add_tab_button(tabs, "interface", "Интерфейс")
        self._add_tab_button(tabs, "viewer", "Просмотрщик")
        self._add_tab_button(tabs, "layout_grid", "Сетки")

        self._page_host = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=(0, dp(4), 0, 0),
        )
        self._page_host.bind(minimum_height=self._page_host.setter("height"))
        self._page_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True)
        self._page_scroll.add_widget(self._page_host)
        apply_rounded_panel(self._page_scroll, base_rgba=(0.12, 0.12, 0.14, 1), radius_px=dp(10), border_alpha=0.0)
        root.add_widget(self._page_scroll)
        self._switch_tab("database")

        footer = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(6),
            padding=(dp(12), dp(8), dp(12), dp(10)),
        )
        footer.bind(minimum_height=footer.setter("height"))
        apply_rounded_panel(footer, base_rgba=(0.12, 0.12, 0.14, 1), radius_px=dp(12), border_alpha=0.06)

        self._status_label = Label(
            text="",
            size_hint_y=None,
            height=dp(18),
            font_size=dp(11),
            color=(0.92, 0.65, 0.50, 1),
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        self._status_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        footer.add_widget(self._status_label)

        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))
        row.add_widget(Widget())

        btn_save = Button(
            text="Сохранить",
            size_hint_x=None,
            width=dp(168),
            font_size=dp(15),
            bold=True,
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
        )
        btn_save.color = (0.98, 0.98, 1, 1)
        apply_rounded_button(btn_save, base_rgba=UI_BTN_SUCCESS, border_alpha=0.06)
        btn_save.bind(on_press=lambda *_: self._save())
        row.add_widget(btn_save)
        footer.add_widget(row)
        root.add_widget(footer)

        self.add_widget(root)

    def _pane_shell(self, spacing: float | None = None) -> BoxLayout:
        sp = (dp(4) if self._compact_ui else dp(6)) if spacing is None else spacing
        pane = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=(dp(10), dp(10), dp(10), dp(8)) if self._compact_ui else (dp(12), dp(12), dp(12), dp(10)),
            spacing=sp,
        )
        pane.bind(minimum_height=pane.setter("height"))
        return pane

    def _add_tab_button(self, parent: BoxLayout, tab_key: str, caption: str):
        btn = Button(
            text=caption,
            size_hint=(None, 1),
            width=max(dp(122), self._measure_text_w(caption, dp(12) if self._compact_ui else dp(13), padding=dp(28) if self._compact_ui else dp(38))),
            font_size=dp(12) if self._compact_ui else dp(13),
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
        )
        btn.color = UI_TEXT_PRIMARY
        btn.bind(on_release=lambda *_: self._switch_tab(tab_key))
        self._tab_buttons[tab_key] = btn
        parent.add_widget(btn)

    def _switch_tab(self, tab_key: str):
        self._active_tab = tab_key
        if self._page_host is not None:
            self._page_host.clear_widgets()
            page = self._pages.get(tab_key)
            if page is not None:
                self._page_host.add_widget(page)
            self._page_host.height = self._page_host.minimum_height
        if self._page_scroll is not None:
            self._page_scroll.scroll_y = 1.0

        for key, btn in self._tab_buttons.items():
            active = key == tab_key
            apply_rounded_button(
                btn,
                base_rgba=(0.32, 0.33, 0.38, 1) if active else (0.20, 0.20, 0.24, 1),
                border_alpha=0.06,
            )
            btn.color = UI_TEXT_STRONG if active else UI_TEXT_PRIMARY

    def _measure_text_w(self, text: str, font_size: float, padding: float = 0.0) -> float:
        try:
            from kivy.core.text import Label as CoreLabel

            cl = CoreLabel(text=text, font_size=font_size, bold=False)
            cl.refresh()
            return float(cl.texture.size[0]) + float(padding)
        except Exception:
            return float(dp(120))

    def _add_title_line(self, pane: BoxLayout, text: str):
        t = Label(
            text=text,
            font_size=dp(14) if self._compact_ui else dp(15),
            bold=True,
            color=(0.94, 0.94, 0.98, 1),
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(22) if self._compact_ui else dp(26),
            text_size=(0, None),
        )
        t.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        pane.add_widget(t)

    def _style_input(self, ti: TextInput, compact: bool = False):
        ti.background_color = (0.18, 0.18, 0.22, 1)
        ti.foreground_color = UI_TEXT_STRONG
        ti.cursor_color = UI_CURSOR_NEUTRAL
        pad = dp(7) if (compact or self._compact_ui) else dp(10)
        ti.padding = (pad, dp(7), pad, dp(7))
        ti.font_size = dp(12) if (compact or self._compact_ui) else dp(14)

    def _add_grid_selector_row(self, pane: BoxLayout, label_text: str, key: str, value: str, options: list[str]):
        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(36) if self._compact_ui else dp(40),
            spacing=dp(8) if self._compact_ui else dp(10),
        )
        lab = Label(
            text=label_text,
            font_size=dp(11) if self._compact_ui else dp(12),
            color=(0.70, 0.70, 0.76, 1),
            halign="left",
            valign="middle",
            size_hint_x=None,
            width=dp(98) if self._compact_ui else dp(112),
            text_size=(0, None),
        )
        lab.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))

        current_value = value if value in options else (options[0] if options else value)
        btn = Button(
            text=current_value,
            size_hint_x=None,
            width=dp(84),
            font_size=dp(12) if self._compact_ui else dp(13),
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
        )
        btn.color = UI_TEXT_STRONG
        apply_rounded_button(btn, base_rgba=(0.20, 0.20, 0.24, 1), border_alpha=0.06)

        def cycle_option(*_args):
            if not options:
                return
            try:
                idx = options.index(btn.text)
            except ValueError:
                idx = -1
            btn.text = options[(idx + 1) % len(options)]

        btn.bind(on_release=cycle_option)

        options_label = Label(
            text=", ".join(options),
            font_size=dp(10),
            color=(0.58, 0.58, 0.64, 1),
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        options_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        self._inputs[key] = btn
        row.add_widget(lab)
        row.add_widget(btn)
        row.add_widget(options_label)
        pane.add_widget(row)

    def _add_h_field(self, pane: BoxLayout, label_text: str, key: str, value: str, hint_text: str | None = None):
        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(34) if self._compact_ui else dp(38),
            spacing=dp(8) if self._compact_ui else dp(10),
        )
        lab = Label(
            text=label_text,
            font_size=dp(11) if self._compact_ui else dp(12),
            color=(0.70, 0.70, 0.76, 1),
            halign="left",
            valign="middle",
            size_hint_x=None,
            width=dp(98) if self._compact_ui else dp(112),
            text_size=(0, None),
        )
        lab.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        inp = TextInput(
            text=value,
            multiline=False,
            size_hint_x=1,
            hint_text=hint_text or "",
        )
        self._style_input(inp)
        self._inputs[key] = inp
        row.add_widget(lab)
        row.add_widget(inp)
        pane.add_widget(row)

    def _add_password_compact(self, pane: BoxLayout, password: str):
        row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(34) if self._compact_ui else dp(38),
            spacing=dp(8) if self._compact_ui else dp(10),
        )
        lab = Label(
            text="Пароль",
            font_size=dp(11) if self._compact_ui else dp(12),
            color=(0.68, 0.68, 0.74, 1),
            halign="left",
            valign="middle",
            size_hint_x=None,
            width=dp(98) if self._compact_ui else dp(112),
            text_size=(0, None),
        )
        lab.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        inp = TextInput(text=password, multiline=False, password=True, size_hint_x=1)
        self._style_input(inp)
        self._inputs["database.password"] = inp
        self._password_input = inp
        row.add_widget(lab)
        row.add_widget(inp)
        pane.add_widget(row)

        toggle = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(24) if self._compact_ui else dp(28),
            spacing=dp(6),
            padding=(dp(106), 0, 0, 0) if self._compact_ui else (dp(122), 0, 0, 0),
        )
        cb = CheckBox(size_hint=(None, None), size=(dp(22), dp(22)), active=False)
        cb_label = Label(
            text="Показать пароль",
            font_size=dp(10) if self._compact_ui else dp(11),
            color=(0.60, 0.60, 0.66, 1),
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        cb_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))

        def on_active(_inst, active: bool):
            inp.password = not active

        cb.bind(active=on_active)
        toggle.add_widget(cb)
        toggle.add_widget(cb_label)
        pane.add_widget(toggle)

    def _collect_data(self) -> dict:
        data = {
            "database": {},
            "viewer_auto_periods": {},
            "layout_grid": {},
        }
        for key, field in self._inputs.items():
            value = field.text.strip()
            if key.startswith("database."):
                data["database"][key.split(".", 1)[1]] = value
            elif key.startswith("viewer_auto_periods."):
                k = key.split(".", 1)[1]
                data["viewer_auto_periods"][k] = value
            elif key.startswith("layout_grid."):
                k = key.split(".", 1)[1]
                data["layout_grid"][k] = value
        data["database"]["mode"] = "database"
        return data

    def _save(self):
        if self._status_label:
            self._status_label.text = ""
        payload = self._collect_data()
        ok = False
        if self._on_save:
            ok = bool(self._on_save(payload))
        if ok:
            self._on_back_clicked()
            return
        if self._status_label:
            self._status_label.text = "Не удалось сохранить. Проверьте права на файл и значения."

    def _on_back_clicked(self, *_args):
        manager = getattr(self, "manager", None)
        if not manager:
            return

        target = None
        if self.previous_screen and manager.has_screen(self.previous_screen):
            target = self.previous_screen
        elif manager.screens:
            target = manager.screens[0].name

        if not target:
            return

        # Переход делаем через следующий тиковый цикл, чтобы не зависеть
        # от текущего состояния on_press/on_release и активных эффектов кнопки.
        def _go_back(_dt):
            try:
                if manager.current != target:
                    manager.current = target
            except Exception:
                pass

        Clock.schedule_once(_go_back, 0)
