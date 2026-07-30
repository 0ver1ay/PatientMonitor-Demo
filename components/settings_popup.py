"""
Popup настроек config.ini: вкладки + компактная вёрстка — один экран без скролла.
"""
from __future__ import annotations

from typing import Callable

from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from utils.config_loader import ConfigLoader
from utils.popup_style import apply_popup_theme, style_scrollview_popup
from utils.ui_style import (
    UI_BTN_DANGER,
    UI_BTN_SUCCESS,
    UI_CURSOR_NEUTRAL,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    UI_TEXT_STRONG,
    apply_rounded_button,
    apply_rounded_panel,
)


class SettingsPopup(Popup):
    """Диалог редактирования глобальных настроек."""

    def __init__(
        self,
        settings_data: dict,
        on_save: Callable[[dict], bool] | None = None,
        title: str = "Настройки приложения",
        **kwargs,
    ):
        content = BoxLayout(orientation="vertical", spacing=0, padding=0)
        super().__init__(
            title="",
            content=content,
            size_hint=(0.96, 0.90) if Window.height <= dp(820) else (0.94, 0.84),
            auto_dismiss=False,
            **kwargs,
        )
        apply_popup_theme(self, frameless=True)
        self.background_color = (0.11, 0.11, 0.13, 0.99)
        self._on_save = on_save
        self._title_text = title
        self._inputs: dict[str, TextInput | Button] = {}
        self._settings_data = settings_data or {}
        self._status_label: Label | None = None
        self._password_input: TextInput | None = None
        self._page_host: BoxLayout | None = None
        self._page_scroll: ScrollView | None = None
        self._tab_buttons: dict[str, Button] = {}
        self._pages: dict[str, BoxLayout] = {}
        self._active_tab = "database"
        self._compact_ui = Window.height <= dp(820)
        self._build(content)

    def _build(self, root: BoxLayout):
        shell = BoxLayout(
            orientation="vertical",
            spacing=dp(8) if self._compact_ui else dp(10),
            padding=(dp(12), dp(12), dp(12), dp(10)) if self._compact_ui else (dp(14), dp(14), dp(14), dp(12)),
        )
        apply_rounded_panel(shell, base_rgba=(0.12, 0.12, 0.14, 1), radius_px=dp(12), border_alpha=0.06)
        root.add_widget(shell)

        header = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(48) if self._compact_ui else dp(58),
            spacing=dp(2) if self._compact_ui else dp(4),
        )
        title = Label(
            text=self._title_text,
            font_size=dp(16) if self._compact_ui else dp(18),
            bold=True,
            color=UI_TEXT_STRONG,
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(24) if self._compact_ui else dp(28),
        )
        title.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        sub = Label(
            text="Запись в config.ini. После смены БД перезапустите окна мониторов.",
            font_size=dp(10) if self._compact_ui else dp(11),
            color=UI_TEXT_MUTED,
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(18) if self._compact_ui else dp(22),
        )
        sub.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        header.add_widget(title)
        header.add_widget(sub)
        shell.add_widget(header)

        tabs = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(38) if self._compact_ui else dp(42),
            spacing=dp(8) if self._compact_ui else dp(12),
            padding=(dp(2), 0, dp(2), 0),
        )
        shell.add_widget(tabs)

        db = self._settings_data.get("database", {})
        viewer = self._settings_data.get("viewer_auto_periods", {})
        layout_grid = self._settings_data.get("layout_grid", {})

        pane_db = self._pane_shell()
        self._add_title_line(pane_db, "PostgreSQL")
        self._add_h_field(
            pane_db, "Хост", "database.host", str(db.get("host", "")),
            hint_text="localhost",
        )
        self._add_h_field(
            pane_db, "Порт", "database.port", str(db.get("port", 6000)),
            hint_text="5432",
        )
        self._add_h_field(
            pane_db, "База", "database.database", str(db.get("database", "")),
        )
        self._add_h_field(
            pane_db, "Пользователь", "database.user", str(db.get("user", "")),
        )
        self._add_password_compact(pane_db, str(db.get("password", "")))
        self._finish_pane(pane_db)
        apply_rounded_panel(pane_db, base_rgba=(0.15, 0.15, 0.18, 1), radius_px=dp(10), border_alpha=0.06)
        self._pages["database"] = pane_db

        pane_ui = self._pane_shell()
        self._add_title_line(pane_ui, "Показатели и камера по умолчанию")
        self._add_h_field(
            pane_ui, "Показатель 1", "database.display_value_1",
            str(db.get("display_value_1", "spo2")), hint_text="spo2",
        )
        self._add_h_field(
            pane_ui, "Показатель 2", "database.display_value_2",
            str(db.get("display_value_2", "pulse")), hint_text="pulse",
        )
        self._add_h_field(
            pane_ui, "Камера", "database.camera_image_path",
            str(db.get("camera_image_path", "")),
            hint_text="файл или URL",
        )
        self._finish_pane(pane_ui)
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
        self._finish_pane(pane_v)
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
        self._finish_pane(pane_g)
        apply_rounded_panel(pane_g, base_rgba=(0.15, 0.15, 0.18, 1), radius_px=dp(10), border_alpha=0.06)
        self._pages["layout_grid"] = pane_g

        self._add_tab_button(tabs, "database", "База данных")
        self._add_tab_button(tabs, "interface", "Интерфейс")
        self._add_tab_button(tabs, "viewer", "Просмотрщик")
        self._add_tab_button(tabs, "layout_grid", "Сетки")
        tabs.add_widget(Widget())

        self._page_host = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=(0, dp(4), 0, 0),
        )
        self._page_host.bind(minimum_height=self._page_host.setter("height"))
        self._page_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True)
        style_scrollview_popup(self._page_scroll)
        self._page_scroll.add_widget(self._page_host)
        apply_rounded_panel(self._page_scroll, base_rgba=(0.12, 0.12, 0.14, 1), radius_px=dp(10), border_alpha=0.0)
        shell.add_widget(self._page_scroll)
        self._switch_tab("database")

        footer = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(6),
            padding=(dp(12), dp(6), dp(12), dp(10)),
        )
        apply_rounded_panel(footer, base_rgba=(0.12, 0.12, 0.14, 1), radius_px=dp(0), border_alpha=0.0)

        self._status_label = Label(
            text="",
            size_hint_y=None,
            height=dp(18),
            font_size=dp(11),
            color=(0.92, 0.65, 0.50, 1),
            halign="left",
            valign="middle",
        )
        self._status_label.bind(size=lambda inst, s: setattr(inst, "text_size", s))
        footer.add_widget(self._status_label)

        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(10))
        row.add_widget(Widget())

        btn_cancel = Button(
            text="Отмена",
            size_hint_x=None,
            width=dp(118),
            font_size=dp(15),
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
        )
        btn_cancel.color = (0.94, 0.95, 0.98, 1)
        apply_rounded_button(btn_cancel, base_rgba=UI_BTN_DANGER, border_alpha=0.06)
        btn_cancel.bind(on_release=lambda *_: self.dismiss())

        btn_save = Button(
            text="Сохранить",
            size_hint_x=None,
            width=dp(158),
            font_size=dp(15),
            bold=True,
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
        )
        btn_save.color = (0.98, 0.98, 1, 1)
        apply_rounded_button(btn_save, base_rgba=UI_BTN_SUCCESS, border_alpha=0.06)
        btn_save.bind(on_release=lambda *_: self._save())

        row.add_widget(btn_save)
        row.add_widget(btn_cancel)
        footer.add_widget(row)
        shell.add_widget(footer)

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

    def _finish_pane(self, pane: BoxLayout):
        return

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
            return dp(120)

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

    def _add_grid_selector_row(
        self,
        pane: BoxLayout,
        label_text: str,
        key: str,
        value: str,
        options: list[str],
    ):
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
        )
        lab.bind(size=lambda inst, s: setattr(inst, "text_size", s))

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
        )
        options_label.bind(size=lambda inst, s: setattr(inst, "text_size", s))
        self._inputs[key] = btn
        row.add_widget(lab)
        row.add_widget(btn)
        row.add_widget(options_label)
        pane.add_widget(row)

    def _add_h_field(
        self,
        pane: BoxLayout,
        label_text: str,
        key: str,
        value: str,
        hint_text: str | None = None,
    ):
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
        )
        lab.bind(size=lambda inst, s: setattr(inst, "text_size", s))
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
        )
        lab.bind(size=lambda inst, s: setattr(inst, "text_size", s))
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
        )
        cb_label.bind(size=lambda inst, s: setattr(inst, "text_size", s))

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
            self.dismiss()
            return
        if self._status_label:
            self._status_label.text = "Не удалось сохранить. Проверьте права на файл и значения."
