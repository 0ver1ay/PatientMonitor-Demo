from __future__ import annotations

from copy import deepcopy
from typing import Callable, Optional

from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from components.esc_back_navigation import EscBackNavigationMixin
from utils.ui_style import (
    UI_BTN_DANGER,
    UI_BTN_MUTED,
    UI_BTN_SUCCESS,
    UI_CONTENT_PADDING_UNDER_TITLEBAR,
    UI_CURSOR_NEUTRAL,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    UI_TEXT_STRONG,
    apply_rounded_button,
    apply_rounded_panel,
)


class _DashboardGridVisualEditor(Widget):
    """Интерактивная схема сетки для редактора."""

    def __init__(
        self,
        on_select: Callable[[str], None],
        on_change: Callable[[str, dict], None],
        label_for: Callable[[str], str],
        short_label: Callable[[str], str],
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._config: dict = {"cols": 1, "rows": 1, "items": {}}
        self._selected_id = ""
        self._on_select = on_select
        self._on_change = on_change
        self._label_for = label_for
        self._short_label = short_label
        self._labels: dict[str, Label] = {}
        self._rects: dict[str, tuple[float, float, float, float]] = {}
        self._drag: dict | None = None
        self._spacing = dp(4)
        self._pad = dp(8)
        self.bind(pos=lambda *_: self._redraw(), size=lambda *_: self._redraw())

    def set_config(self, config: dict, selected_id: str) -> None:
        self._config = config or {"cols": 1, "rows": 1, "items": {}}
        self._selected_id = selected_id or ""
        self._sync_labels()
        self._redraw()

    def _visible_item_ids(self) -> list[str]:
        items = self._config.get("items", {}) if isinstance(self._config, dict) else {}
        return [item_id for item_id, item in items.items() if bool((item or {}).get("visible", True))]

    def _sync_labels(self) -> None:
        visible_ids = set(self._visible_item_ids())
        for item_id in list(self._labels):
            if item_id in visible_ids:
                continue
            label = self._labels.pop(item_id)
            if label.parent is self:
                self.remove_widget(label)
        for item_id in visible_ids:
            if item_id in self._labels:
                continue
            label = Label(
                text="",
                size_hint=(None, None),
                color=UI_TEXT_STRONG,
                bold=True,
                halign="center",
                valign="middle",
                shorten=True,
                shorten_from="right",
            )
            label.bind(size=lambda inst, s: setattr(inst, "text_size", (max(1, s[0] - dp(8)), max(1, s[1] - dp(6)))))
            self._labels[item_id] = label
            self.add_widget(label)

    def _metrics(self) -> tuple[float, float, float, float, float, float, float]:
        cols = max(1, int(self._config.get("cols", 1) or 1))
        rows = max(1, int(self._config.get("rows", 1) or 1))
        pad = float(self._pad)
        spacing = float(self._spacing)
        x0 = float(self.x) + pad
        y0 = float(self.y) + pad
        w = max(1.0, float(self.width) - pad * 2.0)
        h = max(1.0, float(self.height) - pad * 2.0)
        cell_w = max(1.0, (w - spacing * max(0, cols - 1)) / float(cols))
        cell_h = max(1.0, (h - spacing * max(0, rows - 1)) / float(rows))
        return x0, y0, cell_w, cell_h, spacing, float(cols), float(rows)

    def _item_rect(self, item: dict) -> tuple[float, float, float, float]:
        x0, y0, cell_w, cell_h, spacing, _cols, rows = self._metrics()
        col = int(item.get("col", 0) or 0)
        row = int(item.get("row", 0) or 0)
        colspan = int(item.get("colspan", 1) or 1)
        rowspan = int(item.get("rowspan", 1) or 1)
        x = x0 + col * (cell_w + spacing)
        y = y0 + (rows - row - rowspan) * (cell_h + spacing)
        w = cell_w * colspan + spacing * max(0, colspan - 1)
        h = cell_h * rowspan + spacing * max(0, rowspan - 1)
        return x, y, max(1.0, w), max(1.0, h)

    def _overlaps(self) -> tuple[set[tuple[int, int]], set[str]]:
        cols = max(1, int(self._config.get("cols", 1) or 1))
        rows = max(1, int(self._config.get("rows", 1) or 1))
        cells: dict[tuple[int, int], str] = {}
        overlap_cells: set[tuple[int, int]] = set()
        overlap_items: set[str] = set()
        for item_id, item in (self._config.get("items", {}) or {}).items():
            if not bool((item or {}).get("visible", True)):
                continue
            for row in range(int(item["row"]), int(item["row"]) + int(item["rowspan"])):
                for col in range(int(item["col"]), int(item["col"]) + int(item["colspan"])):
                    if not (0 <= row < rows and 0 <= col < cols):
                        continue
                    key = (row, col)
                    other = cells.get(key)
                    if other is not None:
                        overlap_cells.add(key)
                        overlap_items.add(other)
                        overlap_items.add(item_id)
                    else:
                        cells[key] = item_id
        return overlap_cells, overlap_items

    def _redraw(self) -> None:
        self.canvas.before.clear()
        self._rects = {}
        if float(self.width or 0) <= 1 or float(self.height or 0) <= 1:
            return
        x0, y0, cell_w, cell_h, spacing, cols_f, rows_f = self._metrics()
        cols = int(cols_f)
        rows = int(rows_f)
        overlap_cells, overlap_items = self._overlaps()
        with self.canvas.before:
            Color(0.075, 0.075, 0.09, 1)
            Rectangle(pos=(self.x, self.y), size=(self.width, self.height))
            for row in range(rows):
                for col in range(cols):
                    x = x0 + col * (cell_w + spacing)
                    y = y0 + (rows - row - 1) * (cell_h + spacing)
                    if (row, col) in overlap_cells:
                        Color(0.42, 0.12, 0.12, 0.52)
                    else:
                        Color(0.12, 0.12, 0.145, 1)
                    Rectangle(pos=(x, y), size=(cell_w, cell_h))
                    Color(0.35, 0.35, 0.40, 0.18)
                    Line(rectangle=(x, y, cell_w, cell_h), width=dp(0.8))

            active_id = (self._drag or {}).get("id") or self._selected_id
            visible_items = [
                (item_id, item)
                for item_id, item in (self._config.get("items", {}) or {}).items()
                if bool((item or {}).get("visible", True))
            ]
            visible_items.sort(key=lambda pair: 1 if pair[0] == active_id else 0)

            for item_id, item in visible_items:
                x, y, w, h = self._item_rect(item)
                self._rects[item_id] = (x, y, w, h)
                selected = item_id == self._selected_id
                overlapped = item_id in overlap_items
                radius = min(float(dp(10)), max(0.0, min(w, h) * 0.5))
                if overlapped:
                    Color(0.72, 0.20, 0.16, 0.72)
                elif selected:
                    Color(0.22, 0.40, 0.70, 0.78)
                else:
                    Color(0.18, 0.25, 0.34, 0.74)
                RoundedRectangle(pos=(x, y), size=(w, h), radius=[radius])
                Color(1.0, 0.32, 0.26, 0.92) if overlapped else Color(0.54, 0.72, 1.0, 0.98) if selected else Color(0.62, 0.66, 0.72, 0.65)
                Line(rounded_rectangle=[x, y, w, h, radius], width=2 if selected or overlapped else 1.2)
                handle = min(float(dp(18)), max(float(dp(10)), min(w, h) * 0.22))
                handle_radius = min(float(dp(4)), max(0.0, handle * 0.5))
                Color(0.95, 0.95, 1.0, 0.84 if selected else 0.55)
                RoundedRectangle(pos=(x + w - handle, y), size=(handle, handle), radius=[handle_radius])

        for item_id, label in self._labels.items():
            rect = self._rects.get(item_id)
            if rect is None:
                label.opacity = 0
                continue
            x, y, w, h = rect
            label.opacity = 1
            label.pos = (x + dp(4), y + dp(4))
            label.size = (max(1, w - dp(8)), max(1, h - dp(8)))
            label.font_size = max(dp(9), min(dp(15), min(w, h) * 0.16))
            label.text = self._short_label(item_id) if w < dp(92) or h < dp(42) else self._label_for(item_id)
        active_label = self._labels.get((self._drag or {}).get("id") or self._selected_id)
        if active_label is not None and active_label.parent is self:
            try:
                self.remove_widget(active_label)
                self.add_widget(active_label)
            except Exception:
                pass

    def _hit_item(self, x: float, y: float) -> str | None:
        for item_id in reversed(self._visible_item_ids()):
            rx, ry, rw, rh = self._rects.get(item_id, (0, 0, 0, 0))
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                return item_id
        return None

    def _handle_hit(self, item_id: str, x: float, y: float) -> bool:
        rx, ry, rw, rh = self._rects.get(item_id, (0, 0, 0, 0))
        handle = min(float(dp(20)), max(float(dp(12)), min(rw, rh) * 0.25))
        return (rx + rw - handle) <= x <= (rx + rw) and ry <= y <= (ry + handle)

    @staticmethod
    def _clamp_item(item: dict, cols: int, rows: int) -> dict:
        out = dict(item)
        out["col"] = max(0, min(cols - 1, int(out.get("col", 0) or 0)))
        out["row"] = max(0, min(rows - 1, int(out.get("row", 0) or 0)))
        out["colspan"] = max(1, min(cols - out["col"], int(out.get("colspan", 1) or 1)))
        out["rowspan"] = max(1, min(rows - out["row"], int(out.get("rowspan", 1) or 1)))
        out["visible"] = bool(out.get("visible", True))
        return out

    def _apply_drag(self, touch) -> None:
        if not self._drag:
            return
        item_id = self._drag["id"]
        start = dict(self._drag["item"])
        _x0, _y0, cell_w, cell_h, spacing, cols_f, rows_f = self._metrics()
        cols = int(cols_f)
        rows = int(rows_f)
        step_x = max(1.0, cell_w + spacing)
        step_y = max(1.0, cell_h + spacing)
        dx_cells = int(round((float(touch.x) - float(self._drag["x"])) / step_x))
        dy_cells = int(round((float(touch.y) - float(self._drag["y"])) / step_y))
        next_item = dict(start)
        if self._drag["mode"] == "resize":
            next_item["colspan"] = int(start.get("colspan", 1)) + dx_cells
            next_item["rowspan"] = int(start.get("rowspan", 1)) - dy_cells
        else:
            next_item["col"] = int(start.get("col", 0)) + dx_cells
            next_item["row"] = int(start.get("row", 0)) - dy_cells
        next_item = self._clamp_item(next_item, cols, rows)
        self._on_change(item_id, next_item)

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        if getattr(touch, "button", "left") not in (None, "left"):
            return super().on_touch_down(touch)
        item_id = self._hit_item(float(touch.x), float(touch.y))
        if item_id is None:
            return True
        self._on_select(item_id)
        self._drag = {
            "id": item_id,
            "mode": "resize" if self._handle_hit(item_id, float(touch.x), float(touch.y)) else "move",
            "x": float(touch.x),
            "y": float(touch.y),
            "item": dict((self._config.get("items", {}) or {}).get(item_id, {})),
        }
        try:
            touch.grab(self)
        except Exception:
            pass
        return True

    def on_touch_move(self, touch):
        if getattr(touch, "grab_current", None) is not self:
            return super().on_touch_move(touch)
        self._apply_drag(touch)
        return True

    def on_touch_up(self, touch):
        if getattr(touch, "grab_current", None) is not self:
            return super().on_touch_up(touch)
        self._apply_drag(touch)
        self._drag = None
        try:
            touch.ungrab(self)
        except Exception:
            pass
        return True


class DashboardGridEditorScreen(EscBackNavigationMixin, Screen):
    """Формовый редактор внутренней сетки одного монитора."""

    ITEM_LABELS = {
        "graph1": "График 1",
        "graph2": "График 2",
        "graph3": "График 3",
        "graph4": "График 4",
        "value1": "Индикатор 1",
        "value2": "Индикатор 2",
        "value3": "Индикатор 3",
        "value4": "Индикатор 4",
        "value5": "Индикатор 5",
        "value6": "Индикатор 6",
        "camera": "Фото / камера",
        "bed_panel": "Пациент / управление",
        "patient_panel": "Информация пациента",
    }
    DEFAULT_ORDER = (
        "graph1",
        "graph2",
        "graph3",
        "graph4",
        "value1",
        "value2",
        "value3",
        "value4",
        "value5",
        "value6",
        "camera",
        "bed_panel",
        "patient_panel",
    )

    def __init__(
        self,
        grid_config: dict,
        on_save: Optional[Callable[[dict], bool]] = None,
        previous_screen: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if "name" not in kwargs:
            self.name = "dashboard_grid_editor"
        self._init_esc_back_navigation()
        self.previous_screen = previous_screen
        self._on_save = on_save
        self._config = self._normalize_config(grid_config or {})
        self._selected_id = self._first_item_id()
        self._item_buttons: dict[str, Button] = {}
        self._coord_inputs: dict[str, TextInput] = {}
        self._cols_input: TextInput | None = None
        self._rows_input: TextInput | None = None
        self._visible_checkbox: CheckBox | None = None
        self._selected_title: Label | None = None
        self._preview_label: Label | None = None
        self._visual_grid: _DashboardGridVisualEditor | None = None
        self._status_label: Label | None = None
        self._narrow_body_active: bool | None = None
        self._preview_box: BoxLayout | None = None
        self._root: BoxLayout | None = None
        self._body: BoxLayout | None = None
        self._wide_body: BoxLayout | None = None
        self._narrow_scroll: ScrollView | None = None
        self._narrow_inner: BoxLayout | None = None
        self._item_btn_height = dp(40)
        self._build()
        self._refresh_all()
        self.bind(size=lambda *_a: self._on_dashboard_size())
        Clock.schedule_once(lambda _dt: self._on_dashboard_size(), 0)

    def on_pre_enter(self, *args):
        self._bind_escape_handler()
        Clock.schedule_once(lambda _dt: self._on_dashboard_size(), 0)
        return super().on_pre_enter(*args)

    def on_pre_leave(self, *args):
        self._unbind_escape_handler()
        return super().on_pre_leave(*args)

    def set_grid_config(self, grid_config: dict) -> None:
        self._config = self._normalize_config(grid_config or {})
        if self._selected_id not in self._config["items"]:
            self._selected_id = self._first_item_id()
        self._refresh_all()

    def set_on_save(self, callback: Callable[[dict], bool]) -> None:
        self._on_save = callback

    def _on_dashboard_size(self, *_args) -> None:
        self._sync_body_layout()
        self._apply_chrome_compact()

    def _want_narrow_body(self) -> bool:
        w = float(self.width or 0)
        h = float(self.height or 0)
        return w <= float(dp(720)) or h <= float(dp(500))

    def _sync_body_layout(self) -> None:
        if self._body is None or self._item_panel is None or self._editor_panel is None:
            return
        narrow = self._want_narrow_body()
        if self._narrow_body_active is not None and narrow == self._narrow_body_active:
            return
        self._narrow_body_active = narrow

        if self._item_panel.parent is not None:
            self._item_panel.parent.remove_widget(self._item_panel)
        if self._editor_panel.parent is not None:
            self._editor_panel.parent.remove_widget(self._editor_panel)

        self._body.clear_widgets()
        h = float(self.height or 0) or float(dp(400))

        if narrow:
            assert self._narrow_inner is not None and self._narrow_scroll is not None
            self._narrow_inner.clear_widgets()
            self._item_panel.size_hint_x = 1
            self._item_panel.size_hint_y = None
            self._item_panel.height = min(max(dp(120), h * 0.28), dp(220))
            self._editor_panel.size_hint_x = 1
            self._editor_panel.size_hint_y = None
            self._editor_panel.height = max(dp(320), min(dp(520), h * 0.52))
            self._set_preview_stacked(True)
            self._narrow_inner.add_widget(self._item_panel)
            self._narrow_inner.add_widget(self._editor_panel)
            self._body.add_widget(self._narrow_scroll)
        else:
            self._set_preview_stacked(False)
            assert self._wide_body is not None
            self._item_panel.size_hint = (0.34, 1)
            self._editor_panel.size_hint = (0.66, 1)
            self._wide_body.clear_widgets()
            self._wide_body.add_widget(self._item_panel)
            self._wide_body.add_widget(self._editor_panel)
            self._body.add_widget(self._wide_body)

    def _set_preview_stacked(self, narrow: bool) -> None:
        box = getattr(self, "_preview_box", None)
        if box is None or self._visual_grid is None:
            return
        if narrow:
            box.size_hint_y = None
            box.height = dp(220)
            self._visual_grid.size_hint = (1, 1)
        else:
            box.size_hint = (1, 1)
            self._visual_grid.size_hint = (1, 1)

    def _apply_chrome_compact(self) -> None:
        """Компактнее шапка и подвал на малых окнах."""
        if self._root is None or self._header is None:
            return
        w = float(self.width or 0)
        h = float(self.height or 0)
        ultra = w <= float(dp(520)) or h <= float(dp(420))
        compact = w <= float(dp(720)) or h <= float(dp(540))

        if ultra:
            self._root.spacing = dp(6)
            self._root.padding = (0, dp(6), 0, dp(8))
            self._item_btn_height = dp(34)
        elif compact:
            self._root.spacing = dp(8)
            self._root.padding = UI_CONTENT_PADDING_UNDER_TITLEBAR
            self._item_btn_height = dp(38)
        else:
            self._root.spacing = dp(10)
            self._root.padding = UI_CONTENT_PADDING_UNDER_TITLEBAR
            self._item_btn_height = dp(40)

        if getattr(self, "_header_title", None) is not None:
            self._header_title.font_size = dp(14) if ultra else (dp(16) if compact else dp(18))
            self._header_title.height = dp(28) if ultra else (dp(32) if compact else dp(36))
        if getattr(self, "_header_title_row", None) is not None:
            self._header_title_row.height = dp(28) if ultra else (dp(32) if compact else dp(36))
        if getattr(self, "_header_back", None) is not None:
            b = self._header_back
            b.width = dp(72) if ultra else (dp(92) if compact else dp(104))
            b.height = dp(28) if ultra else (dp(32) if compact else dp(36))
            b.font_size = dp(12) if ultra else (dp(12) if compact else dp(13))
        if getattr(self, "_header", None) is not None:
            self._header.spacing = dp(5) if ultra else (dp(6) if compact else dp(8))
            if ultra:
                self._header.padding = (dp(10), dp(8), dp(10), dp(8))
            elif compact:
                self._header.padding = (dp(12), dp(10), dp(12), dp(10))
            else:
                self._header.padding = (dp(14), dp(12), dp(14), dp(12))
        if getattr(self, "_header_grid_row", None) is not None:
            self._header_grid_row.height = dp(30) if ultra else (dp(32) if compact else dp(34))
        if getattr(self, "_grid_hint_label", None) is not None:
            self._grid_hint_label.text = "row0=верх" if ultra else "row=0 - верхняя строка"
        if getattr(self, "_footer", None) is not None:
            self._footer.height = dp(46) if ultra else (dp(50) if compact else dp(54))
            if ultra:
                self._footer.padding = (dp(8), dp(4), dp(8), dp(4))
            elif compact:
                self._footer.padding = (dp(10), dp(5), dp(10), dp(5))
            else:
                self._footer.padding = (dp(12), dp(6), dp(12), dp(6))
        if getattr(self, "_save_button", None) is not None:
            self._save_button.width = dp(140) if ultra else (dp(158) if compact else dp(168))
        self._refresh_item_buttons()

    def _build(self) -> None:
        self._root = BoxLayout(orientation="vertical", spacing=dp(10), padding=UI_CONTENT_PADDING_UNDER_TITLEBAR)
        self._header = self._build_header()
        self._root.add_widget(self._header)

        self._body = BoxLayout(orientation="vertical", size_hint=(1, 1), spacing=dp(10))
        self._item_panel = self._build_item_list_panel()
        self._editor_panel = self._build_editor_panel()

        self._wide_body = BoxLayout(orientation="horizontal", size_hint=(1, 1), spacing=dp(10))
        self._wide_body.add_widget(self._item_panel)
        self._wide_body.add_widget(self._editor_panel)

        self._narrow_scroll = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=dp(8),
        )
        self._narrow_inner = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(8),
            padding=(0, 0, 0, dp(4)),
        )
        self._narrow_inner.bind(minimum_height=self._narrow_inner.setter("height"))
        self._narrow_scroll.add_widget(self._narrow_inner)

        self._body.add_widget(self._wide_body)
        self._root.add_widget(self._body)

        self._footer = self._build_footer()
        self._root.add_widget(self._footer)
        self.add_widget(self._root)

    def _build_header(self):
        header = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8), padding=(dp(14), dp(12), dp(14), dp(12)))
        header.bind(minimum_height=header.setter("height"))
        apply_rounded_panel(header, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(12), border_alpha=0.06)

        title_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(36), spacing=dp(10))
        self._header_title_row = title_row
        title = Label(
            text="Редактор сетки",
            size_hint=(1, None),
            height=dp(36),
            font_size=dp(18),
            bold=True,
            color=UI_TEXT_STRONG,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        self._header_title = title
        title.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        title_row.add_widget(title)

        back_button = self._make_button("Назад", UI_BTN_DANGER, width=dp(104))
        self._header_back = back_button
        back_button.bind(on_release=self._on_back_clicked)
        title_row.add_widget(back_button)
        header.add_widget(title_row)

        grid_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(34), spacing=dp(8))
        self._header_grid_row = grid_row
        grid_row.add_widget(self._make_small_label("Колонки"))
        self._cols_input = self._make_number_input(str(self._config["cols"]), width=dp(64))
        self._cols_input.bind(text=lambda *_: self._apply_grid_size_from_inputs())
        grid_row.add_widget(self._cols_input)
        grid_row.add_widget(self._make_small_label("Строки"))
        self._rows_input = self._make_number_input(str(self._config["rows"]), width=dp(64))
        self._rows_input.bind(text=lambda *_: self._apply_grid_size_from_inputs())
        grid_row.add_widget(self._rows_input)
        hint = self._make_small_label("row=0 - верхняя строка", height=dp(28))
        self._grid_hint_label = hint
        grid_row.add_widget(hint)
        header.add_widget(grid_row)
        return header

    def _build_item_list_panel(self):
        panel = BoxLayout(orientation="vertical", size_hint=(0.34, 1), spacing=dp(8), padding=dp(10))
        apply_rounded_panel(panel, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(12), border_alpha=0.06)
        panel.add_widget(self._make_section_title("Элементы"))

        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True, bar_width=dp(8))
        self._items_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(7))
        self._items_box.bind(minimum_height=self._items_box.setter("height"))
        scroll.add_widget(self._items_box)
        panel.add_widget(scroll)
        return panel

    def _build_editor_panel(self):
        panel = BoxLayout(orientation="vertical", size_hint=(0.66, 1), spacing=dp(10), padding=dp(10))
        apply_rounded_panel(panel, base_rgba=(0.12, 0.12, 0.14, 1), radius_px=dp(12), border_alpha=0.06)

        self._selected_title = self._make_section_title("")
        panel.add_widget(self._selected_title)

        visible_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(32), spacing=dp(8))
        self._visible_checkbox = CheckBox(size_hint=(None, None), size=(dp(24), dp(24)))
        self._visible_checkbox.bind(active=lambda _inst, active: self._set_selected_visible(bool(active)))
        visible_row.add_widget(self._visible_checkbox)
        visible_row.add_widget(self._make_small_label("Показывать элемент в сетке"))
        panel.add_widget(visible_row)

        coord_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(8))
        for key, label in (("col", "Колонка"), ("row", "Строка"), ("colspan", "Ширина"), ("rowspan", "Высота")):
            coord_row.add_widget(self._make_coord_input(key, label))
        panel.add_widget(coord_row)

        move_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(8))
        for text, delta_col, delta_row in (("Влево", -1, 0), ("Вправо", 1, 0), ("Вверх", 0, -1), ("Вниз", 0, 1)):
            btn = self._make_button(text, UI_BTN_MUTED)
            btn.bind(on_release=lambda _inst, dc=delta_col, dr=delta_row: self._move_selected(dc, dr))
            move_row.add_widget(btn)
        panel.add_widget(move_row)

        resize_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(8))
        for text, dcs, drs in (("Уже", -1, 0), ("Шире", 1, 0), ("Ниже", 0, -1), ("Выше", 0, 1)):
            btn = self._make_button(text, UI_BTN_MUTED)
            btn.bind(on_release=lambda _inst, dc=dcs, dr=drs: self._resize_selected(dc, dr))
            resize_row.add_widget(btn)
        panel.add_widget(resize_row)

        preview_panel = BoxLayout(orientation="vertical", size_hint=(1, 1), spacing=dp(6), padding=dp(8))
        apply_rounded_panel(preview_panel, base_rgba=(0.10, 0.10, 0.12, 1), radius_px=dp(10), border_alpha=0.05)
        preview_panel.add_widget(self._make_section_title("Визуальная сетка"))
        self._visual_grid = _DashboardGridVisualEditor(
            on_select=self._select_item,
            on_change=self._apply_visual_grid_change,
            label_for=self._label_for,
            short_label=self._short_label,
            size_hint=(1, 1),
        )
        preview_panel.add_widget(self._visual_grid)
        self._preview_box = preview_panel
        panel.add_widget(preview_panel)
        return panel

    def _build_footer(self):
        footer = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(54), spacing=dp(10), padding=(dp(12), dp(6), dp(12), dp(6)))
        apply_rounded_panel(footer, base_rgba=(0.12, 0.12, 0.14, 1), radius_px=dp(12), border_alpha=0.06)
        self._status_label = Label(text="", size_hint=(1, 1), font_size=dp(11), color=(0.92, 0.65, 0.50, 1), halign="left", valign="middle", text_size=(0, None))
        self._status_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        footer.add_widget(self._status_label)

        save_button = self._make_button("Сохранить", UI_BTN_SUCCESS, width=dp(168))
        self._save_button = save_button
        save_button.bind(on_release=lambda *_: self._save())
        footer.add_widget(save_button)
        return footer

    def _make_coord_input(self, key: str, label: str):
        box = BoxLayout(orientation="vertical", size_hint_x=1, spacing=dp(3))
        box.add_widget(self._make_small_label(label, height=dp(16)))
        inp = self._make_number_input("0")
        inp.bind(text=lambda *_args, k=key: self._apply_selected_inputs(k))
        self._coord_inputs[key] = inp
        box.add_widget(inp)
        return box

    def _make_number_input(self, text: str, width=None):
        inp = TextInput(
            text=str(text),
            multiline=False,
            input_filter="int",
            size_hint=(None, None) if width else (1, None),
            width=width or dp(72),
            height=dp(28),
            font_size=dp(13),
            background_color=(0.16, 0.16, 0.19, 1),
            foreground_color=UI_TEXT_STRONG,
            cursor_color=UI_CURSOR_NEUTRAL,
            padding=(dp(8), dp(4), dp(8), dp(4)),
        )
        return inp

    def _make_button(self, text: str, base_rgba, width=None):
        btn = Button(
            text=text,
            size_hint=(None, 1) if width else (1, 1),
            width=width or dp(80),
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
            font_size=dp(13),
        )
        btn.color = UI_TEXT_PRIMARY
        apply_rounded_button(btn, base_rgba=base_rgba, border_alpha=0.06)
        return btn

    def _make_small_label(self, text: str, height=dp(28)):
        label = Label(
            text=text,
            size_hint=(1, None),
            height=height,
            font_size=dp(11),
            color=UI_TEXT_MUTED,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        return label

    def _make_section_title(self, text: str):
        label = Label(
            text=text,
            size_hint_y=None,
            height=dp(24),
            font_size=dp(13),
            bold=True,
            color=UI_TEXT_STRONG,
            halign="left",
            valign="middle",
            text_size=(0, None),
        )
        label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        return label

    def _refresh_all(self) -> None:
        self._refresh_item_buttons()
        self._refresh_selected_panel()
        self._refresh_preview()

    def _refresh_item_buttons(self) -> None:
        self._items_box.clear_widgets()
        self._item_buttons = {}
        for item_id in self._ordered_item_ids():
            item = self._config["items"][item_id]
            visible = bool(item.get("visible", True))
            prefix = "Выбрано: " if item_id == self._selected_id else ""
            suffix = "" if visible else " (скрыт)"
            label = f"{prefix}{self._label_for(item_id)}{suffix}"
            btn = self._make_button(label, UI_BTN_MUTED)
            btn.size_hint_y = None
            btn.height = getattr(self, "_item_btn_height", dp(40))
            btn.bind(on_release=lambda _inst, sid=item_id: self._select_item(sid))
            self._item_buttons[item_id] = btn
            self._items_box.add_widget(btn)

    def _refresh_selected_panel(self) -> None:
        item = self._selected_item()
        if self._selected_title is not None:
            self._selected_title.text = self._label_for(self._selected_id)
        if self._cols_input is not None:
            self._set_input_text(self._cols_input, str(self._config["cols"]))
        if self._rows_input is not None:
            self._set_input_text(self._rows_input, str(self._config["rows"]))
        if self._visible_checkbox is not None:
            self._visible_checkbox.active = bool(item.get("visible", True))
        for key, inp in self._coord_inputs.items():
            self._set_input_text(inp, str(item.get(key, 0)))

    def _refresh_preview(self) -> None:
        cols = int(self._config["cols"])
        rows = int(self._config["rows"])
        cells = [["." for _ in range(cols)] for _ in range(rows)]
        overlaps: set[tuple[int, int]] = set()
        for item_id, item in self._config["items"].items():
            if not item.get("visible", True):
                continue
            mark = self._short_label(item_id)
            for row in range(int(item["row"]), int(item["row"]) + int(item["rowspan"])):
                for col in range(int(item["col"]), int(item["col"]) + int(item["colspan"])):
                    if 0 <= row < rows and 0 <= col < cols:
                        if cells[row][col] != ".":
                            overlaps.add((row, col))
                        cells[row][col] = mark
        if self._visual_grid is not None:
            self._visual_grid.set_config(self._config, self._selected_id)
        if self._status_label is not None:
            self._status_label.text = "Есть пересечения элементов." if overlaps else ""

    def _select_item(self, item_id: str) -> None:
        self._selected_id = item_id
        self._refresh_all()

    def _apply_visual_grid_change(self, item_id: str, item_config: dict) -> None:
        if item_id not in self._config["items"]:
            return
        if self._config["items"][item_id] == item_config:
            return
        self._config["items"][item_id] = dict(item_config)
        self._clamp_item(self._config["items"][item_id])
        self._refresh_selected_panel()
        self._refresh_preview()

    def _set_selected_visible(self, visible: bool) -> None:
        item = self._selected_item()
        if bool(item.get("visible", True)) == bool(visible):
            return
        item["visible"] = bool(visible)
        self._refresh_item_buttons()
        self._refresh_preview()

    def _apply_grid_size_from_inputs(self) -> None:
        if self._cols_input is None or self._rows_input is None:
            return
        cols = self._parse_int(self._cols_input.text, self._config["cols"])
        rows = self._parse_int(self._rows_input.text, self._config["rows"])
        cols = max(1, min(12, cols))
        rows = max(1, min(12, rows))
        if cols == self._config["cols"] and rows == self._config["rows"]:
            return
        self._config["cols"] = cols
        self._config["rows"] = rows
        self._clamp_all_items()
        self._refresh_selected_panel()
        self._refresh_preview()

    def _apply_selected_inputs(self, changed_key: str) -> None:
        item = self._selected_item()
        old = dict(item)
        for key, inp in self._coord_inputs.items():
            fallback = item.get(key, 0 if key in ("col", "row") else 1)
            value = self._parse_int(inp.text, fallback)
            item[key] = value
        self._clamp_item(item)
        if item != old:
            self._refresh_selected_panel()
            self._refresh_preview()

    def _move_selected(self, delta_col: int, delta_row: int) -> None:
        item = self._selected_item()
        item["col"] = int(item.get("col", 0)) + int(delta_col)
        item["row"] = int(item.get("row", 0)) + int(delta_row)
        self._clamp_item(item)
        self._refresh_selected_panel()
        self._refresh_preview()

    def _resize_selected(self, delta_colspan: int, delta_rowspan: int) -> None:
        item = self._selected_item()
        item["colspan"] = int(item.get("colspan", 1)) + int(delta_colspan)
        item["rowspan"] = int(item.get("rowspan", 1)) + int(delta_rowspan)
        self._clamp_item(item)
        self._refresh_selected_panel()
        self._refresh_preview()

    def _save(self) -> None:
        if self._status_label:
            self._status_label.text = ""
        self._clamp_all_items()
        ok = bool(self._on_save(deepcopy(self._config))) if self._on_save else False
        if ok:
            self._on_back_clicked()
        elif self._status_label:
            self._status_label.text = "Не удалось сохранить сетку."

    def _on_back_clicked(self, *_args):
        if not self.manager:
            return
        if self.previous_screen and self.manager.has_screen(self.previous_screen):
            self.manager.current = self.previous_screen
        elif self.manager.screens:
            self.manager.current = self.manager.screens[0].name

    def _normalize_config(self, raw: dict) -> dict:
        cols = max(1, min(12, self._parse_int(raw.get("cols", 5), 5)))
        rows = max(1, min(12, self._parse_int(raw.get("rows", 4), 4)))
        items = {}
        raw_items = raw.get("items", {}) if isinstance(raw.get("items", {}), dict) else {}
        for item_id in self.DEFAULT_ORDER:
            source = raw_items.get(item_id, {})
            items[item_id] = {
                "col": self._parse_int(source.get("col", 0), 0),
                "row": self._parse_int(source.get("row", 0), 0),
                "colspan": self._parse_int(source.get("colspan", 1), 1),
                "rowspan": self._parse_int(source.get("rowspan", 1), 1),
                "visible": bool(source.get("visible", item_id in raw_items)),
            }
        for item_id, source in raw_items.items():
            if item_id in items or not isinstance(source, dict):
                continue
            items[str(item_id)] = {
                "col": self._parse_int(source.get("col", 0), 0),
                "row": self._parse_int(source.get("row", 0), 0),
                "colspan": self._parse_int(source.get("colspan", 1), 1),
                "rowspan": self._parse_int(source.get("rowspan", 1), 1),
                "visible": bool(source.get("visible", True)),
            }
        config = {"cols": cols, "rows": rows, "items": items}
        self._clamp_all_items(config)
        return config

    def _clamp_all_items(self, config: dict | None = None) -> None:
        config = config or self._config
        for item in config["items"].values():
            self._clamp_item(item, config)

    def _clamp_item(self, item: dict, config: dict | None = None) -> None:
        config = config or self._config
        cols = int(config["cols"])
        rows = int(config["rows"])
        item["col"] = max(0, min(cols - 1, self._parse_int(item.get("col", 0), 0)))
        item["row"] = max(0, min(rows - 1, self._parse_int(item.get("row", 0), 0)))
        item["colspan"] = max(1, min(cols - item["col"], self._parse_int(item.get("colspan", 1), 1)))
        item["rowspan"] = max(1, min(rows - item["row"], self._parse_int(item.get("rowspan", 1), 1)))
        item["visible"] = bool(item.get("visible", True))

    def _selected_item(self) -> dict:
        return self._config["items"][self._selected_id]

    def _first_item_id(self) -> str:
        ordered = self._ordered_item_ids()
        return ordered[0] if ordered else "graph1"

    def _ordered_item_ids(self) -> list[str]:
        item_ids = set((self._config.get("items") or {}).keys())
        ordered = [item_id for item_id in self.DEFAULT_ORDER if item_id in item_ids]
        ordered.extend(sorted(item_ids - set(ordered)))
        return ordered

    def _label_for(self, item_id: str) -> str:
        return self.ITEM_LABELS.get(item_id, item_id)

    def _short_label(self, item_id: str) -> str:
        if item_id.startswith("graph"):
            return "G" + item_id.replace("graph", "")
        if item_id.startswith("value"):
            return "V" + item_id.replace("value", "")
        if item_id == "camera":
            return "CAM"
        if item_id == "bed_panel":
            return "BED"
        if item_id == "patient_panel":
            return "PAT"
        return item_id[:3].upper()

    @staticmethod
    def _parse_int(value, fallback: int) -> int:
        try:
            return int(str(value).strip())
        except Exception:
            return int(fallback)

    @staticmethod
    def _set_input_text(inp: TextInput, value: str) -> None:
        if inp.text != value:
            inp.text = value
