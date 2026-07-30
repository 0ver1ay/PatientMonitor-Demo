"""
Кроссплатформенная верхняя панель в стиле title bar (внутри клиентской области окна).
Для отдельных окон приложения можно включить кнопки свернуть/развернуть/закрыть.
На Windows при register_native_frame вызывается Window.set_custom_titlebar (SDL hit-test), без ручного Window.left/top.
"""
from __future__ import annotations

import logging
import sys
import time
from typing import Any, Callable

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, InstructionGroup, Line
from kivy.metrics import dp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from utils.ui_style import UI_TEXT_PRIMARY, UI_TEXT_STRONG, apply_rounded_button, apply_rounded_panel

logger = logging.getLogger(__name__)

# Throttle in_drag_area logs (SDL вызывает очень часто при движении мыши)
_DRAG_LOG_INTERVAL_S = 0.12
_last_drag_log_mono: float = 0.0


def _titlebar_hittest_window_xy(x: float, y: float) -> tuple[float, float]:
    """Координаты для `collide_point` / `to_widget` в режиме custom titlebar.

    В `kivy/core/window/_window_sdl2.pyx` callback `custom_titlebar_handler_callback` уже
    передаёт в Python **(pts.x, h - pts.y)** — то есть Y из SDL (сверху вниз) переведён в
    оконную систему Kivy (снизу вверх), как для `widget.collide_point(pts.x, h - pts.y)`.

    Нельзя снова делать `(h-1-y)*density` от сырых SDL — получится двойной flip и «клик не там».

    На части конфигураций координаты C и разметка виджетов совпадают с `* Window._density`
    относительно сырого SDL; сам callback вызывается с теми же числами, что и collide в C.
    Если аргументы уже в том же масштабе, что и `Widget.pos`/`Window` для детей — достаточно
    float-приведения. При рассинхроне DPI оставляем опциональный масштаб (см. env ниже).
    """
    fx, fy = float(x), float(y)
    try:
        import os

        mode = os.environ.get("PATIENTMONITOR_TITLEBAR_HIT_SCALE", "").strip().lower()
        if mode in ("density", "1", "true", "yes"):
            d = float(getattr(Window, "_density", 1.0) or 1.0)
            return (fx * d, fy * d)
    except Exception:
        pass
    return (fx, fy)


def _chrome_line_w() -> float:
    return float(dp(0.9))


# Базовый масштаб иконок: держим знаки управления маленькими и спокойными.
def _chrome_unit(w: float, h: float) -> float:
    return min(w, h) * 0.105


def _draw_chrome_minimize(grp: InstructionGroup, x0: float, y0: float, w: float, h: float) -> None:
    lw = _chrome_line_w()
    unit = _chrome_unit(w, h)
    mx = x0 + w * 0.5
    my = y0 + h * 0.5
    grp.add(Color(*UI_TEXT_PRIMARY))
    grp.add(Line(points=[mx - 2.2 * unit, my, mx + 2.2 * unit, my], width=lw))


def _draw_chrome_close(grp: InstructionGroup, x0: float, y0: float, w: float, h: float) -> None:
    lw = _chrome_line_w()
    unit = _chrome_unit(w, h)
    mx = x0 + w * 0.5
    my = y0 + h * 0.5
    d = 2.35 * unit
    grp.add(Color(0.95, 0.86, 0.86, 1))
    grp.add(Line(points=[mx - d, my - d, mx + d, my + d], width=lw))
    grp.add(Line(points=[mx + d, my - d, mx - d, my + d], width=lw))


def _draw_chrome_maximize(grp: InstructionGroup, x0: float, y0: float, w: float, h: float, expanded: bool) -> None:
    lw = _chrome_line_w()
    unit = _chrome_unit(w, h)
    mx = x0 + w * 0.5
    my = y0 + h * 0.5
    grp.add(Color(*UI_TEXT_PRIMARY))
    if expanded:
        s = 2.2 * unit
        grp.add(Line(rectangle=(mx - 1.85 * unit, my - 0.3 * unit, s, s), width=lw))
        grp.add(Line(rectangle=(mx - 0.3 * unit, my - 1.85 * unit, s, s), width=lw))
    else:
        s = 3.5 * unit
        grp.add(Line(rectangle=(mx - s * 0.5, my - s * 0.5, s, s), width=lw))


class CustomTitleBar(BoxLayout):
    """
    Заголовок по центру полосы; кнопки действий слева, системные _, □, × справа.
    on_back: если задан — слева кнопка «Назад».
    show_window_controls: кнопки _, □, ×.
    show_bed_range: две компактные кнопки (текст задаётся через bind_monitor_actions).
    menu_widget: опционально виджет меню (например AppMenuBar в режиме embedded) в левой группе.
    extra_toolbar: опциональный виджет (например ряд кнопок) в левой группе; видимость — set_extra_toolbar_visible.
    register_native_frame: на Windows попытаться зарегистрировать эту полосу через Window.set_custom_titlebar.
    """

    def __init__(
        self,
        title: str,
        *,
        on_back: Callable[[], Any] | None = None,
        back_label: str | None = None,
        back_width: float | None = None,
        menu_widget: Widget | None = None,
        show_window_controls: bool = False,
        on_close: Callable[[], Any] | None = None,
        show_bed_range: bool = False,
        on_bed_press: Callable[[], Any] | None = None,
        on_range_press: Callable[[], Any] | None = None,
        extra_toolbar: Widget | None = None,
        register_native_frame: bool = False,
        height_px: float | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = height_px or dp(36)
        self.spacing = dp(6)
        self.padding = (dp(8), dp(3), dp(8), dp(3))
        apply_rounded_panel(self, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(9), border_alpha=0.05)

        try:
            from utils.titlebar_logging import setup_titlebar_trace_from_env

            setup_titlebar_trace_from_env()
        except Exception:
            pass

        self._original_title = title
        self._show_window_controls = show_window_controls
        self._register_native_frame = bool(register_native_frame)
        self._native_frame_active = False
        self._on_close = on_close
        self._win_maximized = False
        self._manual_workarea_maximized = False
        self._minimize_in_progress = False
        # Win32: x, y, w, h до ручного maximize через SDL/Kivy, для восстановления.
        self._saved_win_rect: tuple[int, int, int, int] | None = None
        # Win32 outer rect в реальных screen pixels для восстановления из taskbar после minimize.
        self._saved_restore_rect: tuple[int, int, int, int] | None = None
        self._manual_drag_touch = None
        self._manual_drag_start_pos: tuple[float, float] | None = None
        self._manual_drag_start_window: tuple[int, int] | None = None
        self._chrome_removed = False
        self._chrome_min_btn: Button | None = None
        self._chrome_close_btn: Button | None = None
        self._back_btn: Button | None = None
        self._extra_toolbar: Widget | None = None
        self._extra_toolbar_nominal_width: float = 0.0
        self._extra_toolbar_child_min_widths: dict[int, float] = {}
        self._bed_btn_nominal_width: float = 0.0
        self._range_btn_nominal_width: float = 0.0
        self._bed_range_visible: bool = True
        self._bed_value_text: str = "—"
        self._range_value_text: str = "—"
        self._left_strip: BoxLayout
        self._left_host: AnchorLayout
        self._right_host: AnchorLayout | None = None
        self._right_strip: BoxLayout | None = None
        self._back_callback: Callable[[], Any] | None = None
        self._refresh_layout_trigger = Clock.create_trigger(self._refresh_titlebar_layout, 0)

        chrome = (0.155, 0.155, 0.165, 1)
        close_bg = (0.30, 0.15, 0.15, 1)

        self._strip_v_pad = dp(2)
        self._title_slot_gutter = dp(5)
        self._chrome_inner_v_pad = dp(2)
        self._edge_h_pad = dp(3)
        self._left_strip = BoxLayout(
            orientation="horizontal",
            spacing=dp(9),
            padding=(self._edge_h_pad, self._strip_v_pad, 0, self._strip_v_pad),
            size_hint=(None, 1),
        )
        self._left_host = AnchorLayout(anchor_x="left", anchor_y="center", size_hint=(None, 1))

        self._back_btn_nominal_width: float = 0.0
        if on_back:
            self._back_callback = on_back
            bl = back_label or "Вернуться в менеджер окон"
            bw = back_width or dp(250)
            self._back_btn_nominal_width = float(bw)
            back_btn = Button(
                text=bl,
                size_hint=(None, 1),
                width=bw,
                font_size=dp(12),
                background_color=(0, 0, 0, 0),
                background_normal="",
                background_down="",
                halign="center",
                valign="middle",
                shorten=True,
                shorten_from="right",
            )
            back_btn.color = UI_TEXT_PRIMARY
            back_btn.bind(size=lambda inst, s: setattr(inst, "text_size", (max(0, s[0] - dp(12)), None)))
            apply_rounded_button(back_btn, base_rgba=chrome, border_alpha=0.06)
            back_btn.bind(on_release=lambda *_a: self._on_back_button_pressed())
            self._left_strip.add_widget(back_btn)
            self._back_btn = back_btn

        self.menu_widget: Widget | None = None
        if menu_widget is not None:
            self.menu_widget = menu_widget
            menu_widget.size_hint_y = 1
            self._left_strip.add_widget(menu_widget)

        _compact_title = bool(
            show_window_controls or menu_widget or extra_toolbar or show_bed_range
        )
        self._title_base_font_size = float(dp(13) if _compact_title else dp(14))
        self._title_min_font_size = float(dp(10))
        self.title_label = Label(
            text=title,
            size_hint=(None, 1),
            width=0,
            font_size=self._title_base_font_size,
            color=UI_TEXT_PRIMARY if _compact_title else UI_TEXT_STRONG,
            halign="center",
            valign="middle",
        )
        self.title_label.bind(
            size=lambda *_a: self._fit_title_text(),
            text=lambda *_a: self._fit_title_text(),
        )
        # На первом кадре не рисуем title, пока не посчитана фактическая геометрия левой/правой зон.
        self.title_label.opacity = 0.0
        self.bind(size=lambda *_a: self._refresh_layout_trigger())
        self.bind(pos=lambda *_a: self._refresh_layout_trigger())

        self.bed_btn: Button | None = None
        self.range_btn: Button | None = None
        if show_bed_range:
            self.bed_btn = Button(
                text="Кровать: —",
                size_hint=(None, 1),
                width=dp(220),
                font_size=dp(12),
                background_color=(0, 0, 0, 0),
                background_normal="",
                background_down="",
                halign="center",
                valign="middle",
                shorten=True,
                shorten_from="right",
            )
            self.bed_btn.color = UI_TEXT_PRIMARY
            self.bed_btn.bind(size=lambda inst, s: setattr(inst, "text_size", (max(0, s[0] - dp(16)), None)))
            apply_rounded_button(self.bed_btn, base_rgba=(0.22, 0.22, 0.24, 1), border_alpha=0.06)
            self._bed_btn_nominal_width = float(dp(220))
            if on_bed_press:
                self.bed_btn.bind(on_release=lambda *_a: on_bed_press())

            self.range_btn = Button(
                text="Диапазон: —",
                size_hint=(None, 1),
                width=dp(160),
                font_size=dp(12),
                background_color=(0, 0, 0, 0),
                background_normal="",
                background_down="",
                halign="center",
                valign="middle",
                shorten=True,
                shorten_from="right",
            )
            self.range_btn.color = UI_TEXT_PRIMARY
            self.range_btn.bind(size=lambda inst, s: setattr(inst, "text_size", (max(0, s[0] - dp(16)), None)))
            apply_rounded_button(self.range_btn, base_rgba=(0.22, 0.22, 0.24, 1), border_alpha=0.06)
            self._range_btn_nominal_width = float(dp(160))
            if on_range_press:
                self.range_btn.bind(on_release=lambda *_a: on_range_press())

            self._left_strip.add_widget(self.bed_btn)
            self._left_strip.add_widget(self.range_btn)

        if extra_toolbar is not None:
            self._extra_toolbar = extra_toolbar
            extra_toolbar.size_hint_y = 1
            try:
                self._extra_toolbar_nominal_width = float(extra_toolbar.width)
            except Exception:
                self._extra_toolbar_nominal_width = float(dp(480))
            for ch in getattr(extra_toolbar, "children", ()) or ():
                try:
                    ch._pm_nominal_width = float(ch.width)
                    self._extra_toolbar_child_min_widths[id(ch)] = max(float(dp(64)), float(ch.width) * 0.45)
                except Exception:
                    pass
            self._left_strip.add_widget(extra_toolbar)
            self.set_extra_toolbar_visible(False)

        self._left_strip.bind(minimum_width=self._sync_left_strip_width)
        self._left_strip.bind(
            children=lambda *_a: Clock.schedule_once(self._sync_left_strip_width, 0),
        )
        Clock.schedule_once(self._sync_left_strip_width, 0)

        self._left_host.add_widget(self._left_strip)
        self.add_widget(self._left_host)
        self.add_widget(self.title_label)

        if show_window_controls:
            self._right_host = AnchorLayout(anchor_x="right", anchor_y="center", size_hint=(None, 1))
            self._right_strip = BoxLayout(
                orientation="horizontal",
                spacing=dp(5),
                size_hint=(None, 1),
                padding=(
                    0,
                    self._strip_v_pad + self._chrome_inner_v_pad,
                    self._edge_h_pad,
                    self._strip_v_pad + self._chrome_inner_v_pad,
                ),
            )

            def _chrome_btn_empty(base_rgba, on_press):
                # Кнопка заполняет внутреннюю высоту полосы, чтобы сверху/снизу был одинаковый отступ.
                _v = float(self._strip_v_pad + self._chrome_inner_v_pad)
                _s = max(float(dp(28)), float(self.height) - 2.0 * _v)
                b = Button(
                    text="",
                    size_hint=(None, 1),
                    width=_s,
                    font_size=dp(1),
                    background_color=(0, 0, 0, 0),
                    background_normal="",
                    background_down="",
                )
                apply_rounded_button(b, base_rgba=base_rgba, radius_px=dp(8), border_alpha=0.035)
                # on_press: при SDL hit-test release иногда не доходит; для chrome важен первый клик.
                b.bind(on_press=on_press)
                return b

            def _attach_chrome(btn: Button, grp: InstructionGroup, kind: str):
                def _draw(*_a):
                    grp.clear()
                    x0, y0 = btn.pos
                    bw, bh = btn.size
                    if bw < 2 or bh < 2:
                        return
                    if kind == "min":
                        _draw_chrome_minimize(grp, x0, y0, bw, bh)
                    elif kind == "close":
                        _draw_chrome_close(grp, x0, y0, bw, bh)
                    else:
                        _draw_chrome_maximize(grp, x0, y0, bw, bh, self._window_is_expanded())

                btn.bind(pos=_draw, size=_draw)
                _draw()
                return _draw

            self._chrome_min_btn = _chrome_btn_empty(chrome, self._on_minimize)
            self._chrome_min_grp = InstructionGroup()
            self._chrome_min_btn.canvas.after.add(self._chrome_min_grp)
            self._chrome_redraw_min = _attach_chrome(self._chrome_min_btn, self._chrome_min_grp, "min")
            self._right_strip.add_widget(self._chrome_min_btn)

            self.max_btn = _chrome_btn_empty(chrome, self._on_maximize_toggle)
            self._chrome_max_grp = InstructionGroup()
            self.max_btn.canvas.after.add(self._chrome_max_grp)
            self._chrome_redraw_max = _attach_chrome(self.max_btn, self._chrome_max_grp, "max")
            self._right_strip.add_widget(self.max_btn)

            self._chrome_close_btn = _chrome_btn_empty(close_bg, self._on_close_chrome)
            self._chrome_close_grp = InstructionGroup()
            self._chrome_close_btn.canvas.after.add(self._chrome_close_grp)
            _attach_chrome(self._chrome_close_btn, self._chrome_close_grp, "close")
            self._right_strip.add_widget(self._chrome_close_btn)

            self._right_strip.bind(minimum_width=self._sync_right_strip_width)
            self._right_strip.bind(
                children=lambda *_a: Clock.schedule_once(self._sync_right_strip_width, 0),
            )
            Clock.schedule_once(self._sync_right_strip_width, 0)
            self._right_host.add_widget(self._right_strip)
            self.add_widget(self._right_host)

            try:
                Window.bind(
                    on_maximize=self._sync_max_from_window,
                    on_restore=self._sync_restore_from_window,
                )
            except Exception:
                pass
            try:
                Window.bind(fullscreen=self._on_fullscreen_changed)
            except Exception:
                pass

            Clock.schedule_once(lambda _dt: self._refresh_maximize_icon(), 0)
            if self._register_native_frame and sys.platform == "win32":
                Clock.schedule_once(self._try_register_native_titlebar, 0.15)
            else:
                Clock.schedule_once(self._apply_borderless_or_strip_chrome, 0)
                Clock.schedule_once(self._apply_borderless_or_strip_chrome, 0.12)
                Clock.schedule_once(self._apply_borderless_or_strip_chrome, 0.35)

        logger.info(
            "CustomTitleBar init: title=%r register_native=%s show_controls=%s bed_range=%s",
            title,
            self._register_native_frame,
            self._show_window_controls,
            show_bed_range,
        )
        Clock.schedule_once(self._refresh_titlebar_layout, 0)
        Clock.schedule_once(self._refresh_titlebar_layout, 0.03)

    def do_layout(self, *args, **kwargs):
        self._sync_chrome_square_layout()
        self._adapt_bed_range_compact_mode()
        self._fit_left_toolbar_widths()
        self._fit_extra_toolbar_width()
        self._sync_side_host_widths()
        lh = getattr(self, "_left_host", None)
        if lh is not None:
            lh.x = self.x
            lh.y = self.y
            lh.height = self.height
        rh = getattr(self, "_right_host", None)
        if rh is not None:
            rh.x = self.right - rh.width
            rh.y = self.y
            rh.height = self.height
        tl = getattr(self, "title_label", None)
        if tl is not None:
            tl.y = self.y
            tl.height = self.height
        self._update_title_slot_geometry()

    def _refresh_titlebar_layout(self, _dt=None) -> None:
        """Обновить геометрию шапки после смены состояния окна/видимости элементов."""
        try:
            self._sync_chrome_square_layout()
            self._sync_left_strip_width()
            self._sync_right_strip_width()
            self._adapt_bed_range_compact_mode()
            self._fit_left_toolbar_widths()
            self._fit_extra_toolbar_width()
            self._sync_left_strip_width()
            self._sync_side_host_widths()
            self._update_title_slot_geometry()
            self.do_layout()
            self.canvas.ask_update()
        except Exception:
            logger.exception("_refresh_titlebar_layout")

    def _sync_chrome_square_layout(self) -> None:
        """Кнопки _, □, × — квадраты со стороной по внутренней высоте шапки."""
        if getattr(self, "_chrome_removed", False):
            return
        v = float(self._strip_v_pad + self._chrome_inner_v_pad)
        side = max(float(dp(28)), float(self.height) - 2.0 * v)
        for b in (
            self._chrome_min_btn,
            getattr(self, "max_btn", None),
            self._chrome_close_btn,
        ):
            if b is None:
                continue
            b.size_hint = (None, 1)
            b.width = side
        rs = getattr(self, "_right_strip", None)
        if rs is not None:
            pl, _pt, pr, _pb = (float(x) for x in rs.padding)
            sp = float(rs.spacing)
            rs.width = max(1.0, pl + pr + 3.0 * side + 2.0 * sp)

    def _update_title_slot_geometry(self) -> None:
        tl = getattr(self, "title_label", None)
        if tl is None:
            return
        left_w = float(getattr(getattr(self, "_left_host", None), "width", 0.0) or 0.0)
        right_w = float(getattr(getattr(self, "_right_host", None), "width", 0.0) or 0.0)
        gutter = float(self._title_slot_gutter)
        center_x = float(self.center_x)
        left_bound = float(self.x) + left_w + gutter
        right_bound = float(self.right) - right_w - gutter
        half_w = max(0.0, min(center_x - left_bound, right_bound - center_x))
        tl.width = max(0.0, half_w * 2.0)
        tl.center_x = center_x
        self._fit_title_text()

    def _fit_title_text(self, *_args) -> None:
        """Подобрать font_size так, чтобы title влезал в одну строку без ... на узких экранах."""
        tl = getattr(self, "title_label", None)
        if tl is None:
            return
        try:
            avail_w = max(1.0, float(tl.width) - float(dp(8)))
            avail_h = max(1.0, float(tl.height))
            if avail_w < float(dp(120)):
                tl.opacity = 0.0
                tl.text_size = (avail_w, avail_h)
                return
            text = str(tl.text or "")
            size = float(self._title_base_font_size)
            min_size = float(self._title_min_font_size)
            fits = False
            while size > min_size:
                probe = CoreLabel(
                    text=text,
                    font_size=size,
                    font_name=getattr(tl, "font_name", None),
                    bold=bool(getattr(tl, "bold", False)),
                )
                probe.refresh()
                tex = probe.texture
                tw, th = (tex.size if tex is not None else (0, 0))
                if float(tw) <= avail_w and float(th) <= avail_h:
                    fits = True
                    break
                size -= 1.0
            if not fits:
                probe = CoreLabel(
                    text=text,
                    font_size=min_size,
                    font_name=getattr(tl, "font_name", None),
                    bold=bool(getattr(tl, "bold", False)),
                )
                probe.refresh()
                tex = probe.texture
                tw, th = (tex.size if tex is not None else (0, 0))
                fits = float(tw) <= avail_w and float(th) <= avail_h
            tl.opacity = 1.0 if fits else 0.0
            tl.font_size = max(min_size, size)
            tl.text_size = (avail_w, avail_h)
        except Exception:
            logger.exception("_fit_title_text")

    def _fit_left_toolbar_widths(self) -> None:
        """Поджать bed/range-кнопки в левой части, чтобы они не съедали место у _, □, ×."""
        ls = getattr(self, "_left_strip", None)
        if ls is None:
            return
        try:
            adjustable = []
            if self.bed_btn is not None and self.bed_btn.parent is ls and self.bed_btn.opacity > 0 and self.bed_btn.width > 0:
                adjustable.append((self.bed_btn, float(self._bed_btn_nominal_width or self.bed_btn.width), float(dp(96))))
            if self.range_btn is not None and self.range_btn.parent is ls and self.range_btn.opacity > 0 and self.range_btn.width > 0:
                adjustable.append((self.range_btn, float(self._range_btn_nominal_width or self.range_btn.width), float(dp(88))))
            if not adjustable:
                return

            visible_children = [
                ch for ch in ls.children
                if float(getattr(ch, "opacity", 1.0) or 0.0) > 0 and float(getattr(ch, "width", 0.0) or 0.0) > 0
            ]
            total_current = sum(float(getattr(ch, "width", 0.0) or 0.0) for ch in visible_children)
            pl, _pt, pr, _pb = (float(x) for x in ls.padding)
            total_current += pl + pr + float(ls.spacing) * max(0, len(visible_children) - 1)
            adjustable_current = sum(float(getattr(ch, "width", 0.0) or 0.0) for ch, _base, _min_w in adjustable)
            fixed_left = total_current - adjustable_current

            rs = getattr(self, "_right_strip", None)
            right_w = float(getattr(rs, "width", 0.0) or 0.0) if rs is not None else 0.0
            reserve_title = float(dp(120))
            avail_for_adjustable = float(self.width) - right_w - reserve_title - float(self.spacing) * 2.0 - fixed_left
            base_total = sum(base for _ch, base, _min_w in adjustable)
            if base_total <= 1.0:
                return
            scale = min(1.0, max(0.0, avail_for_adjustable) / base_total)
            for ch, base, min_w in adjustable:
                ch.width = max(min_w, base * scale)
        except Exception:
            logger.exception("_fit_left_toolbar_widths")

    def _adapt_bed_range_compact_mode(self) -> None:
        """На очень узких окнах сокращать подписи и при необходимости прятать range."""
        ls = getattr(self, "_left_strip", None)
        rs = getattr(self, "_right_strip", None)
        if ls is None or rs is None:
            return
        bed = self.bed_btn
        rng = self.range_btn
        if bed is None and rng is None:
            return
        if not self._bed_range_visible:
            return
        try:
            right_w = float(getattr(rs, "width", 0.0) or 0.0)
            avail_left = float(self.width) - right_w - float(self.spacing) * 2.0 - float(dp(12))

            compact_level = 0
            if avail_left < float(dp(310)):
                compact_level = 1
            if avail_left < float(dp(230)):
                compact_level = 2

            if bed is not None:
                if compact_level == 0:
                    bed.text = f"Кровать: {self._bed_value_text or '—'}"
                elif compact_level == 1:
                    bed.text = str(self._bed_value_text or "—")
                else:
                    bed.text = "Кровать"

            if rng is not None:
                if compact_level == 0:
                    rng.text = f"Диапазон: {self._range_value_text or '—'}"
                    rng.disabled = False
                    rng.opacity = 1.0
                elif compact_level == 1:
                    rng.text = str(self._range_value_text or "—")
                    rng.disabled = False
                    rng.opacity = 1.0
                else:
                    rng.disabled = True
                    rng.opacity = 0.0
                    rng.width = 0.0

            if rng is not None and compact_level < 2 and rng.width <= 0:
                rng.disabled = False
                rng.opacity = 1.0
                rng.width = float(self._range_btn_nominal_width or dp(160))
        except Exception:
            logger.exception("_adapt_bed_range_compact_mode")

    def _sync_left_strip_width(self, *_args) -> None:
        ls = getattr(self, "_left_strip", None)
        if ls is None:
            return
        ls.width = max(float(ls.minimum_width), 1.0)

    def _sync_right_strip_width(self, *_args) -> None:
        rs = getattr(self, "_right_strip", None)
        if rs is None:
            return
        rs.width = max(float(rs.minimum_width), 1.0)

    def _fit_extra_toolbar_width(self) -> None:
        """Сжать левый toolbar, чтобы справа всегда оставалось место под _, □, ×."""
        tb = getattr(self, "_extra_toolbar", None)
        ls = getattr(self, "_left_strip", None)
        if tb is None or ls is None:
            return
        try:
            rs = getattr(self, "_right_strip", None)
            right_w = float(getattr(rs, "width", 0.0) or 0.0) if rs is not None else 0.0

            left_base = 0.0
            visible_count = 0
            for ch in ls.children:
                if ch is tb:
                    continue
                w = float(getattr(ch, "width", 0.0) or 0.0)
                op = float(getattr(ch, "opacity", 1.0) or 0.0)
                if w > 0 and op > 0:
                    left_base += w
                    visible_count += 1
            pl, _pt, pr, _pb = (float(x) for x in ls.padding)
            left_base += pl + pr + float(ls.spacing) * max(0, visible_count)

            reserve_title = float(dp(110))
            reserve_gaps = float(self.spacing) * 2.0 + float(dp(8))
            avail = float(self.width) - right_w - reserve_title - reserve_gaps - left_base
            target_w = max(0.0, min(float(self._extra_toolbar_nominal_width or 0.0), avail))
            tb.width = target_w

            nominal = float(self._extra_toolbar_nominal_width or 0.0)
            ratio = 1.0 if nominal <= 1.0 else max(0.32, min(1.0, target_w / nominal))
            for ch in getattr(tb, "children", ()) or ():
                base_w = float(getattr(ch, "_pm_nominal_width", getattr(ch, "width", 0.0)) or 0.0)
                min_w = float(self._extra_toolbar_child_min_widths.get(id(ch), dp(64)))
                if base_w > 0:
                    ch.width = max(min_w, base_w * ratio)
                try:
                    ch.font_size = max(float(dp(8)), float(dp(11)) * ratio)
                except Exception:
                    pass
        except Exception:
            logger.exception("_fit_extra_toolbar_width")

    def _sync_side_host_widths(self, *_args) -> None:
        lh = getattr(self, "_left_host", None)
        ls = getattr(self, "_left_strip", None)
        if lh is None or ls is None:
            return
        left_w = max(float(getattr(ls, "width", 0.0) or 0.0), 1.0)
        rs = getattr(self, "_right_strip", None)
        right_w = max(float(getattr(rs, "width", 0.0) or 0.0), 1.0) if rs is not None else 1.0
        rh = getattr(self, "_right_host", None)
        reserve_title = float(dp(120))
        total_needed_for_centered = max(left_w, right_w) * 2.0 + reserve_title + float(self.spacing) * 2.0
        if total_needed_for_centered <= float(self.width):
            host_w = max(left_w, right_w)
            lh.width = host_w
            if rh is not None:
                rh.width = host_w
            return

        # На узких окнах приоритет у фактической ширины правого chrome-блока.
        # Не растягиваем правую сторону до ширины левой, иначе _, □, × выталкиваются за край.
        if rh is not None:
            rh.width = right_w

        max_left = max(1.0, float(self.width) - right_w - float(self.spacing) * 2.0 - float(dp(16)))
        lh.width = min(left_w, max_left)

    def _drag_candidate_at_window_xy(self, wx: float, wy: float) -> bool:
        """Пустая часть шапки, по которой можно запустить системный drag."""
        if not self.collide_point(*self.to_widget(wx, wy, relative=False)):
            return False
        lx, ly = self.to_widget(wx, wy, relative=False)
        cr = self._chrome_controls_rect_local()
        if cr is not None:
            cx0, cy0, cx1, cy1 = cr
            pad = dp(8)
            if cx0 - pad <= lx <= cx1 + pad and cy0 - pad <= ly <= cy1 + pad:
                return False
        for strip in (
            getattr(self, "_left_strip", None),
            getattr(self, "_right_strip", None),
        ):
            if strip is not None and strip.collide_point(*strip.to_widget(wx, wy, relative=False)):
                return False
        return True

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            logger.debug(
                "titlebar on_touch_down: pos=%s uid=%s button=%s grab_current=%s",
                touch.pos,
                getattr(touch, "uid", None),
                getattr(touch, "button", None),
                touch.grab_current,
            )
        if (
            self._native_frame_active
            and not self._window_is_expanded()
            and getattr(touch, "button", "left") == "left"
            and self._drag_candidate_at_window_xy(*touch.pos)
        ):
            try:
                from utils.kivy_windows_titlebar import win32_begin_move_drag

                if win32_begin_move_drag():
                    logger.info(
                        "native drag start: touch=%s pos=%s",
                        getattr(touch, "uid", None),
                        touch.pos,
                    )
                    return True
            except Exception:
                logger.exception("native drag start")
        if (
            sys.platform.startswith("linux")
            and not self._native_frame_active
            and not self._window_is_expanded()
            and getattr(touch, "button", "left") == "left"
            and self._drag_candidate_at_window_xy(*touch.pos)
        ):
            self._manual_drag_touch = touch
            self._manual_drag_start_pos = (float(touch.x), float(touch.y))
            self._manual_drag_start_window = (int(Window.left), int(Window.top))
            touch.grab(self)
            logger.info(
                "linux manual drag start: touch=%s pos=%s win=(%s,%s)",
                getattr(touch, "uid", None),
                self._manual_drag_start_pos,
                Window.left,
                Window.top,
            )
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self and touch is self._manual_drag_touch:
            if self._manual_drag_start_pos is None or self._manual_drag_start_window is None:
                return True
            sx, sy = self._manual_drag_start_pos
            wl, wt = self._manual_drag_start_window
            dx = float(touch.x) - sx
            dy = float(touch.y) - sy
            Window.left = int(round(wl + dx))
            Window.top = int(round(wt - dy))
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self and touch is self._manual_drag_touch:
            touch.ungrab(self)
            logger.info(
                "linux manual drag stop: touch=%s final_win=(%s,%s)",
                getattr(touch, "uid", None),
                Window.left,
                Window.top,
            )
            self._manual_drag_touch = None
            self._manual_drag_start_pos = None
            self._manual_drag_start_window = None
            return True
        return super().on_touch_up(touch)

    def _try_register_native_titlebar(self, _dt) -> None:
        """SDL custom title bar: перетаскивание и Aero snap без дублирования с системной рамкой."""
        if not self._show_window_controls or self._chrome_removed:
            logger.info("_try_register_native_titlebar: skip (no controls or chrome_removed)")
            return
        if sys.platform != "win32":
            logger.debug("_try_register_native_titlebar: skip (not win32)")
            return
        ok = False
        result = None
        try:
            Window.custom_titlebar = True
            result = Window.set_custom_titlebar(self)
            ok = bool(result)
            logger.info(
                "set_custom_titlebar: result=%r ok=%s size=%sx%s",
                result,
                ok,
                self.width,
                self.height,
            )
        except Exception:
            logger.exception("set_custom_titlebar raised")
            ok = False
        if ok:
            self._native_frame_active = True
            self._apply_interactive_draggable_hints()
            logger.info("native titlebar ACTIVE (SDL hit-test + in_drag_area)")
        else:
            logger.warning("native titlebar FAILED -> fallback_system_titlebar")
            self._fallback_system_titlebar()

    def _apply_interactive_draggable_hints(self) -> None:
        """Дочерние элементы должны получать тач; область drag — остальное (см. in_drag_area)."""
        for w in (
            self._back_btn,
            self.menu_widget,
            self.bed_btn,
            self.range_btn,
            self._extra_toolbar,
            self._chrome_min_btn,
            getattr(self, "max_btn", None),
            self._chrome_close_btn,
        ):
            if w is not None:
                try:
                    w.draggable = False
                except Exception as e:
                    logger.debug("draggable=False failed for %s: %s", w, e)
        tb = self._extra_toolbar
        if tb is not None:
            for ch in getattr(tb, "children", ()) or ():
                try:
                    ch.draggable = False
                except Exception as e:
                    logger.debug("draggable=False failed for %s: %s", ch, e)
        logger.debug("_apply_interactive_draggable_hints: done")

    def _reapply_native_titlebar(self, _dt=None) -> None:
        """После maximize/restore заново навесить SDL hit-test на текущий widget."""
        if not self._register_native_frame or sys.platform != "win32" or self._chrome_removed:
            return
        try:
            from utils.kivy_windows_titlebar import win32_is_minimized

            if win32_is_minimized():
                logger.info("_reapply_native_titlebar: skip while minimized")
                return
        except Exception:
            logger.exception("_reapply_native_titlebar: win32_is_minimized")
        try:
            Window.custom_titlebar = True
            result = Window.set_custom_titlebar(self)
            self._native_frame_active = bool(result)
            self._apply_interactive_draggable_hints()
            Clock.schedule_once(self._refresh_titlebar_layout, 0)
            logger.info("_reapply_native_titlebar: result=%r active=%s", result, self._native_frame_active)
        except Exception:
            logger.exception("_reapply_native_titlebar")

    def _chrome_controls_rect_local(self) -> tuple[float, float, float, float] | None:
        """Объединённый прямоугольник кнопок _, □, × в координатах self (надёжнее collide при SDL hit-test)."""
        rs = getattr(self, "_right_strip", None)
        btns = [
            b
            for b in (
                self._chrome_min_btn,
                getattr(self, "max_btn", None),
                self._chrome_close_btn,
            )
            if b is not None and rs is not None and b.parent is rs
        ]
        if not btns or rs is None:
            return None
        x0 = rs.x + min(b.x for b in btns)
        x1 = rs.x + max(b.right for b in btns)
        y0 = rs.y + min(b.y for b in btns)
        y1 = rs.y + max(b.top for b in btns)
        return (x0, y0, x1, y1)

    def in_drag_area(self, x: float, y: float) -> bool:
        """x, y — как из Kivy C: (sdl_x, h - sdl_y), см. _titlebar_hittest_window_xy."""
        global _last_drag_log_mono
        wx, wy = _titlebar_hittest_window_xy(x, y)
        if not self.collide_point(*self.to_widget(wx, wy, relative=False)):
            return False
        lx, ly = self.to_widget(wx, wy, relative=False)
        cr = self._chrome_controls_rect_local()
        chrome_hit = False
        if cr is not None:
            cx0, cy0, cx1, cy1 = cr
            pad = dp(8)
            if cx0 - pad <= lx <= cx1 + pad and cy0 - pad <= ly <= cy1 + pad:
                chrome_hit = True
        interactive = None
        for strip in (getattr(self, "_left_strip", None), getattr(self, "_right_strip", None)):
            if strip is not None and strip.collide_point(*strip.to_widget(wx, wy, relative=False)):
                interactive = "strip"
                break
        is_drag = not chrome_hit and interactive is None
        if logger.isEnabledFor(logging.DEBUG):
            now = time.monotonic()
            if now - _last_drag_log_mono >= _DRAG_LOG_INTERVAL_S:
                _last_drag_log_mono = now
                logger.debug(
                    "in_drag_area: from_C=(%.1f,%.1f) use_win=(%.1f,%.1f) local=(%.1f,%.1f) "
                    "chrome_rect=%s chrome_pad_hit=%s widget_hit=%s -> is_drag(caption)=%s",
                    x,
                    y,
                    wx,
                    wy,
                    lx,
                    ly,
                    cr,
                    chrome_hit,
                    interactive,
                    is_drag,
                )
        # Caption drag через SDL hit-test нестабилен в Kivy 2.3.1/Windows.
        # Всегда отдаём point в клиентскую область и двигаем окно вручную из on_touch_*.
        return False

    def _fallback_system_titlebar(self) -> None:
        """Системная рамка + без кастомных _, □, × (без дублирования)."""
        logger.warning("_fallback_system_titlebar: switching to system frame + removing custom chrome")
        try:
            Window.custom_titlebar = False
        except Exception:
            logger.exception("Window.custom_titlebar = False")
        try:
            Window.borderless = False
        except Exception:
            logger.exception("Window.borderless = False")
        self._native_frame_active = False
        self._remove_duplicate_window_chrome()
        if self.title_label:
            self.title_label.opacity = 1.0

    def _apply_borderless_or_strip_chrome(self, *_args) -> None:
        """Если не используем set_custom_titlebar: повторно borderless или снять дублирующий chrome."""
        if not self._show_window_controls or self._chrome_removed or self._register_native_frame:
            return
        try:
            Window.borderless = True
        except Exception:
            logger.exception("_apply_borderless_or_strip_chrome: borderless=True")
        try:
            borderless = bool(Window.borderless)
        except Exception:
            borderless = False
        logger.debug("_apply_borderless_or_strip_chrome: borderless=%s", borderless)
        if borderless:
            return
        logger.info("_apply_borderless_or_strip_chrome: borderless unavailable -> strip duplicate chrome")
        self._remove_duplicate_window_chrome()

    def _remove_duplicate_window_chrome(self) -> None:
        if self._chrome_removed:
            return
        logger.info("_remove_duplicate_window_chrome: removing min/max/close widgets")
        self._chrome_removed = True
        for w in (self._chrome_min_btn, getattr(self, "max_btn", None), self._chrome_close_btn):
            if w and w.parent is not None:
                w.parent.remove_widget(w)
        rs = getattr(self, "_right_strip", None)
        if rs is not None and rs.parent is self:
            self.remove_widget(rs)
        self._right_strip = None
        if self.title_label and self.title_label.parent:
            self.title_label.opacity = 0
        try:
            Window.unbind(
                on_maximize=self._sync_max_from_window,
                on_restore=self._sync_restore_from_window,
            )
        except Exception:
            logger.debug("Window unbind on_maximize/on_restore", exc_info=True)
        try:
            Window.unbind(fullscreen=self._on_fullscreen_changed)
        except Exception:
            logger.debug("Window unbind fullscreen", exc_info=True)

    def _window_is_expanded(self) -> bool:
        """Состояние «развернуто» для иконки maximize/restore."""
        if self._native_frame_active:
            # С set_custom_titlebar() нельзя опираться на fullscreen — он ломает окно на Windows/SDL.
            return self._win_maximized
        fs = getattr(Window, "fullscreen", False)
        if fs in (True, "auto", "fake", "1", 1):
            return True
        if fs in (False, "0", 0, None, ""):
            return self._win_maximized
        if isinstance(fs, str) and fs.lower() in ("false", "no", "0"):
            return self._win_maximized
        return self._win_maximized

    def _refresh_maximize_icon(self) -> None:
        if not hasattr(self, "max_btn"):
            return
        redraw = getattr(self, "_chrome_redraw_max", None)
        if redraw:
            redraw()

    def _on_fullscreen_changed(self, _instance, _value) -> None:
        self._refresh_maximize_icon()

    def _sync_max_from_window(self, *args):
        logger.info("Window on_maximize event: args=%s", args)
        self._win_maximized = True
        self._refresh_maximize_icon()
        Clock.schedule_once(self._reapply_native_titlebar, 0.02)

    def _sync_restore_from_window(self, *args):
        logger.info("Window on_restore event: args=%s", args)
        if sys.platform == "win32":
            try:
                from utils.kivy_windows_titlebar import win32_is_minimized

                if win32_is_minimized():
                    logger.info("_sync_restore_from_window: ignore while window still minimized")
                    return
            except Exception:
                logger.exception("_sync_restore_from_window: win32_is_minimized")
            if self._minimize_in_progress:
                self._minimize_in_progress = False
                self._win_maximized = False
                self._manual_workarea_maximized = False
                self._refresh_maximize_icon()
                Clock.schedule_once(self._finalize_restore_from_minimize, 0.03)
                return
            self._minimize_in_progress = False
        self._win_maximized = False
        self._refresh_maximize_icon()
        Clock.schedule_once(self._reapply_native_titlebar, 0.02)

    def _finalize_restore_from_minimize(self, _dt=None) -> None:
        """После restore из taskbar синхронизировать SDL/Kivy с normal rect."""
        if sys.platform != "win32":
            Clock.schedule_once(self._refresh_titlebar_layout, 0)
            Clock.schedule_once(self._reapply_native_titlebar, 0.02)
            return
        try:
            from utils.kivy_windows_titlebar import kivy_move_resize_window, win32_is_minimized

            if win32_is_minimized():
                logger.info("_finalize_restore_from_minimize: still minimized, retry")
                Clock.schedule_once(self._finalize_restore_from_minimize, 0.05)
                return
            if self._saved_win_rect:
                l, t, w, h = self._saved_win_rect
                ok = kivy_move_resize_window(l, t, w, h)
                logger.info("_finalize_restore_from_minimize: rect=%s ok=%s", self._saved_win_rect, ok)
        except Exception:
            logger.exception("_finalize_restore_from_minimize")
        self._refresh_maximize_icon()
        Clock.schedule_once(self._refresh_titlebar_layout, 0.02)
        Clock.schedule_once(self._reapply_native_titlebar, 0.05)

    def _on_minimize(self, *args):
        logger.info(
            "_on_minimize: native=%s _win_maximized=%s args=%s",
            self._native_frame_active,
            self._win_maximized,
            args,
        )
        self._minimize_in_progress = True
        # Borderless/custom titlebar на Windows часто игнорирует Window.minimize(),
        # поэтому всегда сначала пробуем прямой Win32 путь.
        if sys.platform == "win32":
            from utils.kivy_windows_titlebar import win32_minimize, win32_minimize_to_rect

            if self._window_is_expanded() and self._saved_restore_rect:
                l, t, w, h = self._saved_restore_rect
                if win32_minimize_to_rect(l, t, w, h):
                    self._win_maximized = False
                    self._manual_workarea_maximized = False
                    Clock.schedule_once(lambda _dt: self._refresh_maximize_icon(), 0.05)
                    return
            if win32_minimize():
                return
        self._minimize_in_progress = False
        try:
            Window.minimize()
        except Exception:
            logger.exception("Window.minimize()")

    def _ensure_manual_workarea_maximized(self, _dt=None) -> None:
        """Если `Window.maximize()` не сработал визуально, докручиваем до work area вручную."""
        if sys.platform != "win32" or not self._native_frame_active or not self._win_maximized:
            return
        try:
            from utils.kivy_windows_titlebar import (
                kivy_window_pos_size,
                win32_fill_monitor_work_area,
                win32_window_matches_work_area,
            )

            if win32_window_matches_work_area():
                logger.info("_ensure_manual_workarea_maximized: OS maximize already applied")
                self._manual_workarea_maximized = False
                return
            if not self._saved_win_rect:
                ps = kivy_window_pos_size()
                if ps:
                    self._saved_win_rect = ps
                    logger.info("_ensure_manual_workarea_maximized: saved rect %s", ps)
            ok = win32_fill_monitor_work_area()
            self._manual_workarea_maximized = bool(ok)
            logger.warning("_ensure_manual_workarea_maximized: manual fallback ok=%s", ok)
        except Exception:
            logger.exception("_ensure_manual_workarea_maximized")

    def _restore_from_manual_workarea(self) -> bool:
        """Вернуть геометрию после manual maximize на рабочую область."""
        if not self._manual_workarea_maximized or not self._saved_win_rect:
            return False
        try:
            from utils.kivy_windows_titlebar import kivy_move_resize_window

            l, t, w, h = self._saved_win_rect
            ok = kivy_move_resize_window(l, t, w, h)
            logger.info("_restore_from_manual_workarea: rect=%s ok=%s", self._saved_win_rect, ok)
            if ok:
                self._manual_workarea_maximized = False
                self._saved_win_rect = None
            return bool(ok)
        except Exception:
            logger.exception("_restore_from_manual_workarea")
            return False

    def apply_win32_start_maximized(self, _dt=None) -> None:
        """Старт развёрнутым на Win32 через штатный maximize SDL/Kivy."""
        logger.info(
            "apply_win32_start_maximized: controls=%s chrome_removed=%s native=%s",
            self._show_window_controls,
            self._chrome_removed,
            self._native_frame_active,
        )
        if not self._show_window_controls or self._chrome_removed:
            return
        if sys.platform != "win32":
            try:
                Window.maximize()
            except Exception:
                logger.exception("apply_win32_start_maximized: Window.maximize (non-win32)")
            return
        if not self._native_frame_active:
            try:
                Window.maximize()
            except Exception:
                logger.exception("apply_win32_start_maximized: Window.maximize (native inactive)")
            return
        try:
            from utils.kivy_windows_titlebar import kivy_sdl_hwnd, kivy_window_pos_size, win32_get_window_rect

            ps = kivy_window_pos_size()
            if ps:
                self._saved_win_rect = ps
            hwnd = kivy_sdl_hwnd()
            if hwnd:
                rr = win32_get_window_rect(int(hwnd))
                if rr:
                    l, t, r, b = rr
                    self._saved_restore_rect = (l, t, r - l, b - t)
            Window.maximize()
            self._win_maximized = True
            self._manual_workarea_maximized = False
            logger.info("apply_win32_start_maximized: Window.maximize() called")
        except Exception:
            logger.exception("apply_win32_start_maximized: Window.maximize()")
        Clock.schedule_once(lambda _dt: self._refresh_maximize_icon(), 0.05)
        Clock.schedule_once(self._ensure_manual_workarea_maximized, 0.08)

    def _on_maximize_toggle(self, *args):
        expanded = self._window_is_expanded()
        logger.info(
            "_on_maximize_toggle: expanded=%s native=%s saved_rect=%s args=%s",
            expanded,
            self._native_frame_active,
            self._saved_win_rect,
            args,
        )
        if self._native_frame_active:
            try:
                if expanded:
                    if not self._restore_from_manual_workarea():
                        Window.restore()
                    self._win_maximized = False
                    logger.info("_on_maximize_toggle: native Window.restore()")
                else:
                    from utils.kivy_windows_titlebar import kivy_sdl_hwnd, kivy_window_pos_size, win32_get_window_rect

                    ps = kivy_window_pos_size()
                    if ps:
                        self._saved_win_rect = ps
                    hwnd = kivy_sdl_hwnd()
                    if hwnd:
                        rr = win32_get_window_rect(int(hwnd))
                        if rr:
                            l, t, r, b = rr
                            self._saved_restore_rect = (l, t, r - l, b - t)
                    Window.maximize()
                    self._win_maximized = True
                    self._manual_workarea_maximized = False
                    logger.info("_on_maximize_toggle: native Window.maximize()")
                    Clock.schedule_once(self._ensure_manual_workarea_maximized, 0.08)
            except Exception:
                logger.exception("_on_maximize_toggle: native Window maximize/restore")
        else:
            if expanded:
                try:
                    Window.fullscreen = False
                except Exception:
                    pass
                try:
                    Window.restore()
                except Exception:
                    pass
                self._win_maximized = False
            else:
                try:
                    Window.fullscreen = "auto"
                except Exception:
                    try:
                        Window.fullscreen = True
                    except Exception:
                        pass
                if not self._window_is_expanded():
                    try:
                        Window.maximize()
                        self._win_maximized = True
                    except Exception:
                        pass
                else:
                    self._win_maximized = True

        Clock.schedule_once(lambda _dt: self._refresh_maximize_icon(), 0.05)

    def _on_close_chrome(self, *args):
        logger.info("_on_close_chrome: args=%s", args)
        if self._on_close:
            self._on_close()

    def set_title(self, text: str) -> None:
        self._original_title = text
        self.title_label.text = text
        Clock.schedule_once(lambda _dt: self._sync_side_host_widths(), 0)
        Clock.schedule_once(self._refresh_titlebar_layout, 0)

    def _on_back_button_pressed(self) -> None:
        cb = self._back_callback
        if cb is not None:
            cb()

    def set_back_nav(
        self,
        *,
        text: str,
        visible: bool,
        callback: Callable[[], Any] | None = None,
        width: float | None = None,
    ) -> None:
        """Текст, видимость и действие левой навигационной кнопки (как «Назад» / «Выбор кровати»)."""
        b = self._back_btn
        if b is None:
            return
        if callback is not None:
            self._back_callback = callback
        b.text = text
        w_show = float(width) if width is not None else (self._back_btn_nominal_width or float(dp(160)))
        if visible:
            b.disabled = False
            b.opacity = 1.0
            b.width = w_show
        else:
            b.disabled = True
            b.opacity = 0.0
            b.width = 0
        Clock.schedule_once(lambda _dt: self._sync_left_strip_width(), 0)
        Clock.schedule_once(lambda _dt: self._sync_side_host_widths(), 0)

    def set_back_button_visible(self, visible: bool) -> None:
        """Показать/скрыть левую кнопку (ширина 0 + opacity), текст и callback не меняются."""
        b = self._back_btn
        if b is None:
            return
        w = self._back_btn_nominal_width or float(b.width) or float(dp(160))
        if visible:
            b.disabled = False
            b.opacity = 1.0
            b.width = w
        else:
            b.disabled = True
            b.opacity = 0.0
            b.width = 0
        Clock.schedule_once(lambda _dt: self._sync_left_strip_width(), 0)
        Clock.schedule_once(lambda _dt: self._sync_side_host_widths(), 0)

    def set_bed_range_visible(self, visible: bool) -> None:
        """Показать/скрыть кнопки `Кровать` и `Диапазон` в левой части шапки."""
        self._bed_range_visible = bool(visible)
        for btn, nominal in (
            (self.bed_btn, self._bed_btn_nominal_width),
            (self.range_btn, self._range_btn_nominal_width),
        ):
            if btn is None:
                continue
            if visible:
                btn.disabled = False
                btn.opacity = 1.0
                btn.width = float(nominal or btn.width or dp(120))
            else:
                btn.disabled = True
                btn.opacity = 0.0
                btn.width = 0.0
        Clock.schedule_once(lambda _dt: self._sync_left_strip_width(), 0)
        Clock.schedule_once(lambda _dt: self._sync_side_host_widths(), 0)
        Clock.schedule_once(self._refresh_titlebar_layout, 0)

    def set_extra_toolbar_visible(self, visible: bool) -> None:
        """Показать/скрыть блок кнопок просмотрщика (исследование / период / экспорт)."""
        tb = self._extra_toolbar
        if tb is None:
            return
        w = self._extra_toolbar_nominal_width or float(tb.width) or float(dp(480))
        if visible:
            tb.disabled = False
            tb.opacity = 1.0
            tb.width = w
            for ch in getattr(tb, "children", ()) or ():
                try:
                    ch.disabled = False
                except Exception:
                    pass
        else:
            tb.disabled = True
            tb.opacity = 0.0
            tb.width = 0
            for ch in getattr(tb, "children", ()) or ():
                try:
                    ch.disabled = True
                except Exception:
                    pass
        Clock.schedule_once(lambda _dt: self._sync_left_strip_width(), 0)
        Clock.schedule_once(lambda _dt: self._fit_extra_toolbar_width(), 0)
        Clock.schedule_once(lambda _dt: self._sync_side_host_widths(), 0)

    def bind_monitor_actions(self, monitor_screen: Any) -> None:
        """Синхронизировать подписи с MonitorScreen.bed_button / time_range_button."""

        def _bed_prefix(text: str | None) -> str:
            return f"Кровать: {text or '—'}"

        def _range_prefix(text: str | None) -> str:
            return f"Диапазон: {text or '—'}"

        bb = getattr(monitor_screen, "bed_button", None)
        if self.bed_btn and bb is not None:
            self._bed_value_text = str(bb.text or "—")
            self.bed_btn.text = _bed_prefix(self._bed_value_text)
            bb.bind(
                text=lambda _i, v: self._on_bound_bed_text(v),
            )

        if self.range_btn and hasattr(monitor_screen, "time_range_button"):
            self._range_value_text = str(monitor_screen.time_range_button.text or "—")
            self.range_btn.text = _range_prefix(self._range_value_text)
            monitor_screen.time_range_button.bind(
                text=lambda _i, v: self._on_bound_range_text(v),
            )
        Clock.schedule_once(self._refresh_titlebar_layout, 0)
        Clock.schedule_once(self._refresh_titlebar_layout, 0.03)

    def _on_bound_bed_text(self, value: str | None) -> None:
        self._bed_value_text = str(value or "—")
        self._adapt_bed_range_compact_mode()
        Clock.schedule_once(self._refresh_titlebar_layout, 0)

    def _on_bound_range_text(self, value: str | None) -> None:
        self._range_value_text = str(value or "—")
        self._adapt_bed_range_compact_mode()
        Clock.schedule_once(self._refresh_titlebar_layout, 0)


try:
    from utils.titlebar_logging import setup_titlebar_trace_from_env

    setup_titlebar_trace_from_env()
except Exception:
    pass
