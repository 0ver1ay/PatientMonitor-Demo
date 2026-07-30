"""
UI style helpers (rounded panels/buttons) used across screens.

Designed to keep the look consistent between live monitor and bed viewer.
"""

from __future__ import annotations

from kivy.metrics import dp

UI_SURFACE_PANEL = (0.12, 0.12, 0.14, 1.0)
UI_SURFACE_PANEL_ALT = (0.15, 0.15, 0.18, 1.0)
UI_SURFACE_PANEL_STRONG = (0.18, 0.18, 0.19, 1.0)
UI_SURFACE_POPUP = (0.10, 0.10, 0.12, 0.985)
UI_SURFACE_POPUP_OVERLAY = (0.02, 0.02, 0.03, 0.76)
UI_POPUP_SEPARATOR = (0.20, 0.20, 0.24, 1.0)

UI_BTN_SECONDARY = (0.23, 0.23, 0.26, 1.0)
UI_BTN_MUTED = (0.30, 0.30, 0.33, 1.0)
UI_BTN_SUCCESS = (0.24, 0.40, 0.30, 1.0)
UI_BTN_DANGER = (0.42, 0.22, 0.22, 1.0)
UI_BTN_WARNING = (0.48, 0.36, 0.20, 1.0)
UI_TEXT_PRIMARY = (0.91, 0.91, 0.93, 1.0)
UI_TEXT_SECONDARY = (0.78, 0.78, 0.81, 1.0)
UI_TEXT_MUTED = (0.66, 0.66, 0.69, 1.0)
UI_TEXT_STRONG = (0.96, 0.96, 0.97, 1.0)
UI_CURSOR_NEUTRAL = (0.82, 0.82, 0.84, 1.0)
UI_POPUP_TITLE = (0.95, 0.95, 0.96, 1.0)
UI_POPUP_TEXT = (0.89, 0.89, 0.91, 1.0)
UI_POPUP_TEXT_MUTED = (0.64, 0.64, 0.67, 1.0)
UI_TOPBAR_CONTENT_GAP = dp(8)
UI_APP_SHELL_PADDING = (dp(8), dp(8), dp(8), dp(8))
UI_CONTENT_PADDING_UNDER_TITLEBAR = (0, dp(8), 0, dp(10))


def apply_rounded_panel(widget, base_rgba=UI_SURFACE_PANEL, radius_px=None, border_alpha=0.06):
    """Apply dark rounded background + subtle border to any layout widget."""
    try:
        from kivy.graphics import Color, RoundedRectangle, Line
    except Exception:
        return

    if getattr(widget, "_pm_panel_style", False):
        return
    widget._pm_panel_style = True

    r = float(radius_px if radius_px is not None else dp(10))
    with widget.canvas.before:
        widget._pm_panel_bg_c = Color(*base_rgba)
        widget._pm_panel_bg = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[r])
        widget._pm_panel_br_c = Color(1, 1, 1, float(border_alpha))
        widget._pm_panel_br = Line(rounded_rectangle=[widget.x, widget.y, widget.width, widget.height, r], width=dp(1))

    def _upd(*_args):
        widget._pm_panel_bg.pos = widget.pos
        widget._pm_panel_bg.size = widget.size
        widget._pm_panel_br.rounded_rectangle = [widget.x, widget.y, widget.width, widget.height, r]

    widget.bind(pos=_upd, size=_upd)
    _upd()


def apply_rounded_button(
    btn,
    base_rgba=UI_BTN_SECONDARY,
    radius_px=None,
    border_alpha=0.10,
    disabled_rgba=(0.19, 0.19, 0.19, 0.75),
):
    """Rounded button style (dark, subtle border) matching GraphWidget/camera style."""
    try:
        from kivy.graphics import Color, RoundedRectangle, Line
    except Exception:
        return

    if getattr(btn, "_pm_rounded_style", False):
        btn._pm_base_rgba = tuple(base_rgba)
        btn._pm_disabled_rgba = tuple(disabled_rgba)
        btn._pm_border_alpha = float(border_alpha)
        if hasattr(btn, "_pm_border_color"):
            btn._pm_border_color.a = float(border_alpha)
        if hasattr(btn, "_pm_update_style"):
            btn._pm_update_style()
        return
    btn._pm_rounded_style = True
    btn._pm_base_rgba = tuple(base_rgba)
    btn._pm_disabled_rgba = tuple(disabled_rgba)
    btn._pm_border_alpha = float(border_alpha)

    btn.background_normal = ""
    btn.background_down = ""
    btn.background_color = (0, 0, 0, 0)
    btn.color = getattr(btn, "color", UI_TEXT_PRIMARY)

    r = float(radius_px if radius_px is not None else dp(10))
    with btn.canvas.before:
        btn._pm_bg_color = Color(*base_rgba)
        btn._pm_bg_rr = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[r])
        btn._pm_border_color = Color(1, 1, 1, float(border_alpha))
        btn._pm_border = Line(rounded_rectangle=[btn.x, btn.y, btn.width, btn.height, r], width=dp(1))

    def _update_style(*_args):
        btn._pm_bg_rr.pos = btn.pos
        btn._pm_bg_rr.size = btn.size
        btn._pm_border.rounded_rectangle = [btn.x, btn.y, btn.width, btn.height, r]

        base = getattr(btn, "_pm_base_rgba", tuple(base_rgba))
        disabled_color = getattr(btn, "_pm_disabled_rgba", tuple(disabled_rgba))
        btn._pm_border_color.a = float(getattr(btn, "_pm_border_alpha", border_alpha))

        disabled = bool(getattr(btn, "disabled", False))
        pressed = getattr(btn, "state", "") == "down"
        if disabled:
            bg = disabled_color
        elif pressed:
            bg = (base[0] * 0.88, base[1] * 0.88, base[2] * 0.88, base[3])
        else:
            bg = base
        btn._pm_bg_color.rgba = bg

    btn._pm_update_style = _update_style
    btn.bind(pos=_update_style, size=_update_style, state=_update_style, disabled=_update_style)
    _update_style()


def attach_gear_icon(btn, color=UI_TEXT_STRONG, line_width=None) -> None:
    """Нарисовать иконку шестерёнки на кнопке (без Unicode-символа)."""
    try:
        import math

        from kivy.graphics import Color, InstructionGroup, Line
    except Exception:
        return

    base_lw = float(line_width if line_width is not None else dp(1.35))
    grp = InstructionGroup()
    btn.canvas.after.add(grp)
    btn.text = ""

    def _draw(*_args):
        grp.clear()
        x0, y0 = btn.pos
        w, h = btn.size
        if w < 4 or h < 4:
            return
        # На маленьких кнопках фиксированный dp(1.35) слишком толстый и превращает
        # внутренние окружности в "кашу". Поджимаем толщину под фактический размер.
        lw = float(min(base_lw, max(dp(1.0), min(w, h) * 0.055)))
        cx = x0 + w * 0.5
        cy = y0 + h * 0.5
        # Геометрия "как на иконке": мягкий внешний контур с плоскими вершинами зубьев,
        # толстая обводка, внутреннее кольцо + отверстие (без спиц).
        unit = min(w, h) * 0.225
        gear_r_outer = unit * 1.25
        gear_r_root = unit * 0.98
        ring_r = unit * 0.60
        hole_r = unit * 0.34
        teeth = 8

        def _circle_points(r: float, steps: int) -> list[float]:
            pts: list[float] = []
            for i in range(steps + 1):
                a = -math.pi / 2 + math.pi * 2 * i / steps
                pts.extend([cx + r * math.cos(a), cy + r * math.sin(a)])
            return pts

        # Контур шестерёнки: для каждого зуба делаем "площадку" на внешнем радиусе,
        # а между зубьями — корневой радиус. Joint round сглаживает углы.
        outline: list[float] = []
        step = math.pi * 2.0 / float(teeth)
        tooth_half = step * 0.18
        gap_half = step * 0.14
        base = -math.pi / 2
        for i in range(teeth):
            a = base + step * i
            a0 = a - (tooth_half + gap_half)
            a1 = a - tooth_half
            a2 = a + tooth_half
            a3 = a + (tooth_half + gap_half)
            outline.extend([cx + gear_r_root * math.cos(a0), cy + gear_r_root * math.sin(a0)])
            outline.extend([cx + gear_r_outer * math.cos(a1), cy + gear_r_outer * math.sin(a1)])
            outline.extend([cx + gear_r_outer * math.cos(a2), cy + gear_r_outer * math.sin(a2)])
            outline.extend([cx + gear_r_root * math.cos(a3), cy + gear_r_root * math.sin(a3)])
        icon_color = tuple(color) if isinstance(color, (tuple, list)) else UI_TEXT_STRONG
        if bool(getattr(btn, "disabled", False)):
            icon_color = (icon_color[0] * 0.55, icon_color[1] * 0.55, icon_color[2] * 0.55, icon_color[3])
        grp.add(Color(*icon_color))
        # Внешний контур шестерни
        grp.add(Line(points=outline, width=lw, close=True, joint="round", cap="round"))
        # Внутреннее кольцо намеренно убрано: на некоторых размерах/рендерах
        # оно выглядит как "лишний круг" внутри шестерёнки.
        grp.add(Line(points=_circle_points(hole_r, 22), width=lw, close=True, cap="round"))

    def _redraw(*_args):
        _draw()
        if hasattr(btn, "_pm_update_style"):
            btn._pm_update_style()

    btn.bind(pos=_redraw, size=_redraw, state=_redraw, disabled=_redraw)
    _redraw()
    btn._pm_gear_icon_grp = grp

