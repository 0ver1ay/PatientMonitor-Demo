from __future__ import annotations

from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.floatlayout import FloatLayout


class DashboardGridLayout(FloatLayout):
    """Размещает именованные виджеты по сетке с поддержкой colspan/rowspan."""

    def __init__(self, cols: int = 5, rows: int = 4, spacing=None, **kwargs):
        super().__init__(**kwargs)
        self.cols = max(1, int(cols or 1))
        self.rows = max(1, int(rows or 1))
        self.spacing = spacing if spacing is not None else dp(6)
        self._items: dict[str, dict] = {}
        self._widgets: dict[str, object] = {}
        self._tile_rects: dict[str, tuple[float, float, float, float]] = {}
        self._selected_item_id: str | None = None
        self._hover_item_id: str | None = None
        self._edit_mode = False
        self._drag_state: dict | None = None
        self._drag_front_item_id: str | None = None
        self.on_config_changed = None
        self.on_context_menu = None
        self.bind(pos=lambda *_: self._layout_items(), size=lambda *_: self._layout_items())
        try:
            Window.bind(mouse_pos=self._on_mouse_pos)
        except Exception:
            pass

    def set_config(self, config: dict, widgets: dict[str, object]) -> None:
        config = config or {}
        self.cols = max(1, int(config.get("cols", self.cols) or self.cols))
        self.rows = max(1, int(config.get("rows", self.rows) or self.rows))
        self._items = dict(config.get("items", {}) or {})
        self._widgets = dict(widgets or {})
        if self._selected_item_id not in self._items:
            self._selected_item_id = None

        self.clear_widgets()
        for item_id, item_cfg in self._items.items():
            if not bool(item_cfg.get("visible", True)):
                continue
            widget = self._widgets.get(item_id)
            if widget is None:
                continue
            parent = getattr(widget, "parent", None)
            if parent is not None and parent is not self:
                try:
                    parent.remove_widget(widget)
                except Exception:
                    pass
            widget.size_hint = (None, None)
            self.add_widget(widget)
        self._layout_items()

    def set_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = bool(enabled)
        self._restore_dragged_widget_order()
        self._drag_state = None
        if not self._edit_mode:
            self._selected_item_id = None
            self._hover_item_id = None
        self._redraw_tile_frames()

    def clear_hover_state(self, redraw: bool = True) -> None:
        """Сбросить hover, когда курсор фактически уходит через меню/экран."""
        if self._hover_item_id is None:
            return
        self._hover_item_id = None
        if redraw:
            self._redraw_tile_frames()

    def get_config(self) -> dict:
        return {
            "cols": int(self.cols),
            "rows": int(self.rows),
            "items": {item_id: dict(item) for item_id, item in self._items.items()},
        }

    def _layout_items(self, *_args) -> None:
        if self.cols <= 0 or self.rows <= 0:
            return
        total_w = float(self.width or 0)
        total_h = float(self.height or 0)
        if total_w <= 1 or total_h <= 1:
            return

        spacing = float(self.spacing or 0)
        cell_w = (total_w - spacing * max(0, self.cols - 1)) / float(self.cols)
        cell_h = (total_h - spacing * max(0, self.rows - 1)) / float(self.rows)
        if cell_w <= 1 or cell_h <= 1:
            return

        self._tile_rects = {}
        for item_id, item_cfg in self._items.items():
            widget = self._widgets.get(item_id)
            if widget is None or widget.parent is not self:
                continue
            col = max(0, min(self.cols - 1, int(item_cfg.get("col", 0) or 0)))
            row = max(0, min(self.rows - 1, int(item_cfg.get("row", 0) or 0)))
            colspan = max(1, min(self.cols - col, int(item_cfg.get("colspan", 1) or 1)))
            rowspan = max(1, min(self.rows - row, int(item_cfg.get("rowspan", 1) or 1)))

            x = self.x + col * (cell_w + spacing)
            # row=0 is top row.
            y = self.y + (self.rows - row - rowspan) * (cell_h + spacing)
            w = cell_w * colspan + spacing * max(0, colspan - 1)
            h = cell_h * rowspan + spacing * max(0, rowspan - 1)
            widget.pos = (x, y)
            widget.size = (max(1, w), max(1, h))
            self._tile_rects[item_id] = (x, y, max(1, w), max(1, h))
        self._redraw_tile_frames()

    def _redraw_tile_frames(self) -> None:
        self.canvas.after.clear()
        with self.canvas.after:
            for item_id, rect in self._tile_rects.items():
                x, y, w, h = rect
                selected = item_id == self._selected_item_id
                hovered = item_id == self._hover_item_id
                if selected:
                    Color(0.50, 0.70, 1.0, 0.95)
                    width = dp(2)
                elif hovered:
                    Color(0.82, 0.86, 0.95, 0.58)
                    width = dp(1.5)
                else:
                    Color(1, 1, 1, 0.08)
                    width = dp(1)
                radius = min(float(dp(10)), max(0.0, min(w, h) * 0.5))
                Line(rounded_rectangle=[x, y, w, h, radius], width=width)
                if self._edit_mode:
                    handle = min(float(dp(22)), max(float(dp(12)), min(w, h) * 0.24))
                    handle_radius = min(float(dp(5)), max(0.0, handle * 0.5))
                    hx = x + w - handle
                    hy = y
                    Color(0.16, 0.19, 0.26, 0.62 if selected else 0.32)
                    RoundedRectangle(pos=(hx, hy), size=(handle, handle), radius=[handle_radius])
                    Color(0.95, 0.95, 1.0, 0.78 if selected else 0.48)
                    Line(rounded_rectangle=[hx, hy, handle, handle, handle_radius], width=dp(1.1))
                    grip_pad = max(float(dp(4)), handle * 0.24)
                    Color(0.95, 0.95, 1.0, 0.58 if selected else 0.34)
                    Line(points=[hx + handle - grip_pad * 1.9, hy + grip_pad, hx + handle - grip_pad, hy + grip_pad * 1.9], width=dp(0.9))
                    Line(points=[hx + handle - grip_pad * 2.9, hy + grip_pad, hx + handle - grip_pad, hy + grip_pad * 2.9], width=dp(0.9))

    def _item_at_pos(self, x: float, y: float) -> str | None:
        for item_id in reversed(list(self._tile_rects.keys())):
            rx, ry, rw, rh = self._tile_rects.get(item_id, (0, 0, 0, 0))
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                return item_id
        return None

    def _on_mouse_pos(self, _window, pos) -> None:
        if not self.get_root_window():
            return
        try:
            local = self.to_widget(float(pos[0]), float(pos[1]), relative=False)
        except Exception:
            self.clear_hover_state()
            return
        if not self.collide_point(*local):
            if self._hover_item_id is not None:
                self.clear_hover_state()
            return
        item_id = self._item_at_pos(float(local[0]), float(local[1]))
        if item_id == self._hover_item_id:
            return
        self._hover_item_id = item_id
        self._redraw_tile_frames()

    def _cell_metrics(self) -> tuple[float, float, float, float]:
        spacing = float(self.spacing or 0)
        cell_w = (float(self.width or 1) - spacing * max(0, self.cols - 1)) / float(max(1, self.cols))
        cell_h = (float(self.height or 1) - spacing * max(0, self.rows - 1)) / float(max(1, self.rows))
        return max(1.0, cell_w), max(1.0, cell_h), spacing, spacing

    def _handle_hit(self, item_id: str, x: float, y: float) -> bool:
        rx, ry, rw, rh = self._tile_rects.get(item_id, (0, 0, 0, 0))
        handle = min(float(dp(24)), max(float(dp(12)), min(rw, rh) * 0.25))
        return (rx + rw - handle) <= x <= (rx + rw) and ry <= y <= (ry + handle)

    def _bring_dragged_widget_to_front(self, item_id: str) -> int | None:
        widget = self._widgets.get(item_id)
        if widget is None or getattr(widget, "parent", None) is not self:
            return None
        try:
            child_index = self.children.index(widget)
        except ValueError:
            child_index = None
        try:
            self.remove_widget(widget)
            self.add_widget(widget)
            self._drag_front_item_id = item_id
        except Exception:
            return child_index
        return child_index

    def _restore_dragged_widget_order(self) -> None:
        state = self._drag_state or {}
        item_id = state.get("item_id") or self._drag_front_item_id
        child_index = state.get("child_index")
        self._drag_front_item_id = None
        if item_id is None or child_index is None:
            return
        widget = self._widgets.get(item_id)
        if widget is None or getattr(widget, "parent", None) is not self:
            return
        try:
            self.remove_widget(widget)
            self.add_widget(widget, index=min(int(child_index), len(self.children)))
        except Exception:
            pass

    def _clamp_item(self, item: dict) -> dict:
        out = dict(item)
        out["col"] = max(0, min(self.cols - 1, int(out.get("col", 0) or 0)))
        out["row"] = max(0, min(self.rows - 1, int(out.get("row", 0) or 0)))
        out["colspan"] = max(1, min(self.cols - out["col"], int(out.get("colspan", 1) or 1)))
        out["rowspan"] = max(1, min(self.rows - out["row"], int(out.get("rowspan", 1) or 1)))
        out["visible"] = bool(out.get("visible", True))
        return out

    def _apply_drag(self, touch) -> None:
        state = self._drag_state
        if not state:
            return
        item_id = state["item_id"]
        start = dict(state["item"])
        cell_w, cell_h, spacing_x, spacing_y = self._cell_metrics()
        dx_cells = int(round((float(touch.x) - float(state["x"])) / max(1.0, cell_w + spacing_x)))
        dy_cells = int(round((float(touch.y) - float(state["y"])) / max(1.0, cell_h + spacing_y)))
        next_item = dict(start)
        if state["mode"] == "resize":
            next_item["colspan"] = int(start.get("colspan", 1)) + dx_cells
            next_item["rowspan"] = int(start.get("rowspan", 1)) - dy_cells
        else:
            next_item["col"] = int(start.get("col", 0)) + dx_cells
            next_item["row"] = int(start.get("row", 0)) - dy_cells
        next_item = self._clamp_item(next_item)
        if next_item == self._items.get(item_id):
            return
        self._items[item_id] = next_item
        self._layout_items()
        callback = self.on_config_changed
        if callable(callback):
            callback(self.get_config())

    def _dispatch_touch_to_children(self, touch) -> bool:
        """Сначала дочерние виджеты (кнопки «Готово», шестерёнка), затем логика сетки."""
        if not self.collide_point(*touch.pos):
            return False
        for child in self.children[:]:
            if child.dispatch("on_touch_down", touch):
                return True
        return False

    def on_touch_down(self, touch):
        if self._dispatch_touch_to_children(touch):
            return True
        if self._edit_mode and self.collide_point(*touch.pos) and getattr(touch, "button", None) in (None, "left"):
            item_id = self._item_at_pos(float(touch.x), float(touch.y))
            if item_id is None:
                return super().on_touch_down(touch)
            self._selected_item_id = item_id
            self._hover_item_id = None
            child_index = self._bring_dragged_widget_to_front(item_id)
            self._drag_state = {
                "item_id": item_id,
                "mode": "resize" if self._handle_hit(item_id, float(touch.x), float(touch.y)) else "move",
                "x": float(touch.x),
                "y": float(touch.y),
                "item": dict(self._items.get(item_id, {})),
                "child_index": child_index,
            }
            self._redraw_tile_frames()
            try:
                touch.grab(self)
            except Exception:
                pass
            return True
        if self.collide_point(*touch.pos) and getattr(touch, "button", None) in (None, "left"):
            item_id = self._item_at_pos(float(touch.x), float(touch.y))
            if item_id is not None:
                self._hover_item_id = None
                if item_id != self._selected_item_id:
                    self._selected_item_id = item_id
                self._redraw_tile_frames()
        if self.collide_point(*touch.pos) and getattr(touch, "button", None) == "right":
            callback = self.on_context_menu
            if callable(callback):
                self.clear_hover_state()
                callback()
                return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self._edit_mode and getattr(touch, "grab_current", None) is self:
            self._apply_drag(touch)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self._edit_mode and getattr(touch, "grab_current", None) is self:
            self._apply_drag(touch)
            self._restore_dragged_widget_order()
            self._drag_state = None
            try:
                touch.ungrab(self)
            except Exception:
                pass
            return True
        return super().on_touch_up(touch)
