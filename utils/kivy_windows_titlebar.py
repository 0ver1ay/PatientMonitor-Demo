"""Настройка Kivy под кастомный title bar на Windows (SDL2).

Практические workaround'и для Kivy 2.3.1 / SDL2 / Windows:
- при необходимости отключить per-monitor DPI awareness до инициализации SDL
  (`PATIENTMONITOR_DISABLE_DPI_AWARENESS=1` -> `SetProcessDpiAwareness(0)`)
- monkeypatch `WindowSDL.create_window()` без проблемного `SetWindowPos(...SWP_FRAMECHANGED)`
  в ветке `custom_titlebar`, см. issue #8524 / #7976 / #8607.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any

from ctypes import Structure, byref, sizeof, windll
from ctypes.wintypes import DWORD, POINT, RECT, UINT

_SW_SHOWNORMAL = 1
_SW_SHOWMINIMIZED = 2
_SW_MINIMIZE = 6
_SW_FORCEMINIMIZE = 11

_HWND_TOPMOST = -1
_HWND_NOTOPMOST = -2
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_SHOWWINDOW = 0x0040

WM_NCLBUTTONDOWN = 0x00A1
WM_SYSCOMMAND = 0x0112
HTCAPTION = 2
SC_MINIMIZE = 0xF020

MONITOR_DEFAULTTONEAREST = 2
_WPF_RESTORETOMAXIMIZED = 0x0002

logger = logging.getLogger(__name__)


def kivy_window_pos_size() -> tuple[int, int, int, int] | None:
    """Текущие x, y, w, h в терминах Kivy: pos в screen coords, size как `system_size`."""
    try:
        from kivy.core.window import Window

        wobj = getattr(Window, "_win", None)
        if wobj is None:
            logger.debug("kivy_window_pos_size: no Window._win")
            return None
        x, y = Window.left, Window.top
        w, h = Window.system_size
        return int(x), int(y), int(w), int(h)
    except Exception:
        logger.exception("kivy_window_pos_size")
        return None


def kivy_move_resize_window(left: int, top: int, width: int, height: int) -> bool:
    """Двигает окно через штатные свойства Kivy; `width/height` здесь в `Window.system_size`."""
    try:
        from kivy.core.window import Window

        width = max(1, int(width))
        height = max(1, int(height))
        left = int(left)
        top = int(top)
        logger.info(
            "kivy_move_resize_window: pos=(%s,%s) system_size=%sx%s before left/top=(%s,%s) system_size=%s density=%s",
            left,
            top,
            width,
            height,
            getattr(Window, "left", None),
            getattr(Window, "top", None),
            getattr(Window, "system_size", None),
            getattr(Window, "_density", None),
        )
        # left/top идут напрямую в SDL, а system_size через trigger_create_window запускает
        # обычный жизненный цикл create_window()/resize_window() Kivy.
        Window.left = left
        Window.top = top
        Window.system_size = (width, height)
        try:
            Window.trigger_create_window()
        except Exception:
            logger.debug("Window.trigger_create_window()", exc_info=True)
        return True
    except Exception:
        logger.exception("kivy_move_resize_window")
        return False


class _MONITORINFO(Structure):
    _fields_ = [
        ("cbSize", DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", DWORD),
    ]


class _WINDOWPLACEMENT(Structure):
    _fields_ = [
        ("length", UINT),
        ("flags", UINT),
        ("showCmd", UINT),
        ("ptMinPosition", POINT),
        ("ptMaxPosition", POINT),
        ("rcNormalPosition", RECT),
    ]


def win32_monitor_work_area(hwnd: int | None = None) -> tuple[int, int, int, int] | None:
    """Рабочая область монитора для окна: left, top, right, bottom в screen pixels."""
    hnd = int(hwnd) if hwnd else 0
    if not hnd or not windll.user32.IsWindow(hnd):
        cur = kivy_sdl_hwnd()
        hnd = int(cur) if cur else 0
    if not hnd or not windll.user32.IsWindow(hnd):
        logger.debug("win32_monitor_work_area: invalid hwnd %s", hnd)
        return None
    hmon = windll.user32.MonitorFromWindow(hnd, MONITOR_DEFAULTTONEAREST)
    if not hmon:
        logger.debug("win32_monitor_work_area: MonitorFromWindow failed hwnd=%s", hnd)
        return None
    mi = _MONITORINFO()
    mi.cbSize = sizeof(_MONITORINFO)
    if not windll.user32.GetMonitorInfoW(hmon, byref(mi)):
        logger.debug("win32_monitor_work_area: GetMonitorInfoW failed")
        return None
    work = mi.rcWork
    return int(work.left), int(work.top), int(work.right), int(work.bottom)


def win32_window_matches_work_area(hwnd: int | None = None, tolerance_px: int = 2) -> bool:
    """Сравнить текущий outer rect окна с рабочей областью монитора."""
    hnd = int(hwnd) if hwnd else 0
    if not hnd:
        cur = kivy_sdl_hwnd()
        hnd = int(cur) if cur else 0
    if not hnd:
        return False
    rr = win32_get_window_rect(hnd)
    wa = win32_monitor_work_area(hnd)
    if rr is None or wa is None:
        logger.debug("win32_window_matches_work_area: rect=%s work_area=%s", rr, wa)
        return False
    ok = all(abs(a - b) <= tolerance_px for a, b in zip(rr, wa))
    logger.info("win32_window_matches_work_area: rect=%s work_area=%s tol=%s ok=%s", rr, wa, tolerance_px, ok)
    return ok


def configure_config_for_native_titlebar() -> None:
    """Вызывать до `from kivy.core.window import Window` (после `kivy.config.Config`).

    Безрамочное окно нужно для кастомной полосы; `custom_titlebar` в Config не трогаем —
    включаем `Window.custom_titlebar` в коде перед `set_custom_titlebar`.
    """
    try:
        from utils.titlebar_logging import setup_titlebar_trace_from_env

        setup_titlebar_trace_from_env()
    except Exception:
        pass
    if sys.platform != "win32":
        logger.debug("configure_config_for_native_titlebar: skip (not win32)")
        return
    try:
        os.environ.setdefault("KIVY_GL_BACKEND", "angle_sdl2")
        logger.info("configure_config_for_native_titlebar: KIVY_GL_BACKEND=%s", os.environ.get("KIVY_GL_BACKEND"))
    except Exception:
        logger.debug("configure_config_for_native_titlebar: KIVY_GL_BACKEND setup skipped", exc_info=True)
    try:
        # DPI-unaware даёт рабочий custom_titlebar, но делает всё окно мыльным на HiDPI.
        # Поэтому по умолчанию НЕ включаем; оставляем как ручной fallback.
        raw = os.environ.get("PATIENTMONITOR_DISABLE_DPI_AWARENESS", "").strip().lower()
        if raw in ("1", "true", "yes", "on"):
            windll.shcore.SetProcessDpiAwareness(0)
            logger.info("configure_config_for_native_titlebar: SetProcessDpiAwareness(0)")
        else:
            logger.info("configure_config_for_native_titlebar: keep DPI awareness enabled")
    except Exception:
        logger.debug("configure_config_for_native_titlebar: SetProcessDpiAwareness(0) skipped", exc_info=True)
    try:
        from kivy.config import Config

        Config.set("graphics", "borderless", "1")
        logger.info("configure_config_for_native_titlebar: graphics.borderless=1")
    except Exception:
        logger.exception("configure_config_for_native_titlebar: Config set failed")


def apply_runtime_custom_titlebar_workarounds() -> None:
    """Monkeypatch Kivy WindowSDL.create_window() для стабильнее custom_titlebar на Win/SDL2."""
    if sys.platform != "win32":
        return
    try:
        from kivy.core.window.window_sdl2 import WindowSDL
        from kivy.utils import platform as kivy_platform

        if getattr(WindowSDL, "_pm_custom_titlebar_patched", False):
            return
        original_create_window = WindowSDL.create_window

        def patched_create_window(self, *largs):
            # Холодный старт оставляем оригиналу; баг в повторных re-create / resize с custom_titlebar.
            if not self.initialized:
                return original_create_window(self, *largs)

            w, h = self.system_size
            self._win.resize_window(w, h)
            if kivy_platform == "win":
                if self.custom_titlebar:
                    # Workaround из issue #8524:
                    # вместо set_border_state(False)+SetWindowPos(...SWP_FRAMECHANGED)
                    # используем простой border_state, без принудительного framechanged.
                    self._win.set_border_state(self.borderless or self.custom_titlebar)
                else:
                    self._win.set_border_state(self.borderless)
            else:
                self._win.set_border_state(self.borderless or self.custom_titlebar)
            self._win.set_fullscreen_mode(self.fullscreen)

            super(WindowSDL, self).create_window()
            self._set_cursor_state(self.show_cursor)
            return

        WindowSDL.create_window = patched_create_window
        WindowSDL._pm_custom_titlebar_patched = True
        logger.info("apply_runtime_custom_titlebar_workarounds: WindowSDL.create_window patched")
    except Exception:
        logger.exception("apply_runtime_custom_titlebar_workarounds")


def kivy_sdl_hwnd() -> Any | None:
    """HWND окна Kivy (SDL), иначе None."""
    if sys.platform != "win32":
        logger.debug("kivy_sdl_hwnd: not win32")
        return None
    try:
        from kivy.core.window import Window

        info = Window.get_window_info()
        if info is None:
            logger.debug("kivy_sdl_hwnd: get_window_info() is None")
            return None
        hwnd = getattr(info, "window", None)
        if hwnd and windll.user32.IsWindow(int(hwnd)):
            return hwnd
        logger.debug("kivy_sdl_hwnd: info.window is falsy/invalid: %r", info)
    except Exception:
        logger.exception("kivy_sdl_hwnd: exception")
    try:
        hwnd = windll.user32.GetActiveWindow()
        if hwnd and windll.user32.IsWindow(int(hwnd)):
            logger.info("kivy_sdl_hwnd: fallback GetActiveWindow -> %s", int(hwnd))
            return hwnd
    except Exception:
        logger.debug("kivy_sdl_hwnd: GetActiveWindow failed", exc_info=True)
    try:
        hwnd = windll.user32.GetForegroundWindow()
        if hwnd and windll.user32.IsWindow(int(hwnd)):
            logger.info("kivy_sdl_hwnd: fallback GetForegroundWindow -> %s", int(hwnd))
            return hwnd
    except Exception:
        logger.debug("kivy_sdl_hwnd: GetForegroundWindow failed", exc_info=True)
    return None


def win32_get_window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """Внешний прямоугольник окна (экранные координаты)."""
    h = int(hwnd)
    if not windll.user32.IsWindow(h):
        logger.debug("win32_get_window_rect: IsWindow(%s) is false", h)
        return None
    rect = RECT()
    if not windll.user32.GetWindowRect(h, byref(rect)):
        logger.debug("win32_get_window_rect: GetWindowRect failed hwnd=%s", h)
        return None
    return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))


def _win32_get_window_placement(hwnd: int) -> _WINDOWPLACEMENT | None:
    placement = _WINDOWPLACEMENT()
    placement.length = sizeof(_WINDOWPLACEMENT)
    if not windll.user32.GetWindowPlacement(int(hwnd), byref(placement)):
        logger.debug("_win32_get_window_placement: GetWindowPlacement failed hwnd=%s", hwnd)
        return None
    return placement


def win32_set_restore_rect(
    left: int,
    top: int,
    width: int,
    height: int,
    *,
    show_cmd: int | None = None,
) -> bool:
    """Обновить normal/restored rect окна через WINDOWPLACEMENT."""
    if sys.platform != "win32":
        return False
    h = kivy_sdl_hwnd()
    if not h:
        return False
    try:
        placement = _win32_get_window_placement(int(h))
        if placement is None:
            return False
        width = max(1, int(width))
        height = max(1, int(height))
        left = int(left)
        top = int(top)
        placement.flags = int(placement.flags) & ~_WPF_RESTORETOMAXIMIZED
        placement.rcNormalPosition.left = left
        placement.rcNormalPosition.top = top
        placement.rcNormalPosition.right = left + width
        placement.rcNormalPosition.bottom = top + height
        if show_cmd is not None:
            placement.showCmd = int(show_cmd)
        ok = bool(windll.user32.SetWindowPlacement(int(h), byref(placement)))
        logger.info(
            "win32_set_restore_rect: hwnd=%s rect=(%s,%s,%s,%s) show_cmd=%s ok=%s",
            int(h),
            left,
            top,
            width,
            height,
            show_cmd,
            ok,
        )
        return ok
    except Exception:
        logger.exception("win32_set_restore_rect")
        return False


def win32_minimize_to_rect(left: int, top: int, width: int, height: int) -> bool:
    """Свернуть окно так, чтобы восстановление шло в заданный normal-rect."""
    if not win32_set_restore_rect(left, top, width, height, show_cmd=_SW_SHOWNORMAL):
        return False
    h = kivy_sdl_hwnd()
    ok = win32_show_window_async(_SW_MINIMIZE)
    minimized = win32_is_minimized(int(h)) if h else False
    logger.info("win32_minimize_to_rect: ShowWindowAsync fallback ok=%s minimized=%s", ok, minimized)
    return bool(ok or minimized)


def win32_fill_monitor_work_area(hwnd: int | None = None) -> bool:
    """Развернуть на рабочую область монитора (учёт панели задач) через SDL/Kivy resize+move."""
    hnd = int(hwnd) if hwnd else 0
    if not hnd:
        cur = kivy_sdl_hwnd()
        hnd = int(cur) if cur else 0
    wa = win32_monitor_work_area(hnd)
    if wa is None:
        logger.debug("win32_fill_monitor_work_area: no work area")
        return False
    left, top, right, bottom = wa
    logger.info(
        "win32_fill_monitor_work_area: hwnd=%s work_area LTRB=(%s,%s,%s,%s)",
        hnd,
        left,
        top,
        right,
        bottom,
    )
    try:
        from kivy.core.window import Window

        density = float(getattr(Window, "_density", 1.0) or 1.0)
    except Exception:
        density = 1.0
    sys_w = max(1, int(round((right - left) / density)))
    sys_h = max(1, int(round((bottom - top) / density)))
    logger.info(
        "win32_fill_monitor_work_area: density=%s -> system_size=%sx%s",
        density,
        sys_w,
        sys_h,
    )
    return kivy_move_resize_window(left, top, sys_w, sys_h)


def win32_show_window(cmd: int) -> bool:
    """ShowWindow — запасной путь; для borderless см. win32_fill_monitor_work_area."""
    if sys.platform != "win32":
        return False
    h = kivy_sdl_hwnd()
    if not h:
        return False
    try:
        windll.user32.ShowWindow(int(h), int(cmd))
        logger.info("win32_show_window: hwnd=%s cmd=%s", h, cmd)
        return True
    except Exception:
        logger.exception("win32_show_window: cmd=%s", cmd)
        return False


def win32_show_window_async(cmd: int) -> bool:
    """Асинхронный ShowWindow для случаев, когда sync-вызов игнорируется SDL/Win32."""
    if sys.platform != "win32":
        return False
    h = kivy_sdl_hwnd()
    if not h:
        return False
    try:
        ok = bool(windll.user32.ShowWindowAsync(int(h), int(cmd)))
        logger.info("win32_show_window_async: hwnd=%s cmd=%s ok=%s", h, cmd, ok)
        return ok
    except Exception:
        logger.exception("win32_show_window_async: cmd=%s", cmd)
        return False


def win32_post_syscommand(cmd: int) -> bool:
    """PostMessage WM_SYSCOMMAND — иногда срабатывает, когда ShowWindow нет."""
    h = kivy_sdl_hwnd()
    if not h:
        return False
    try:
        windll.user32.PostMessageW(int(h), WM_SYSCOMMAND, int(cmd), 0)
        logger.info("win32_post_syscommand: hwnd=%s cmd=0x%x", h, int(cmd) & 0xFFFF)
        return True
    except Exception:
        logger.exception("win32_post_syscommand: cmd=0x%x", int(cmd) & 0xFFFF)
        return False


def win32_send_syscommand(cmd: int) -> bool:
    """SendMessage WM_SYSCOMMAND (синхронно)."""
    h = kivy_sdl_hwnd()
    if not h:
        return False
    try:
        windll.user32.SendMessageW(int(h), WM_SYSCOMMAND, int(cmd), 0)
        logger.info("win32_send_syscommand: hwnd=%s cmd=0x%x", h, int(cmd) & 0xFFFF)
        return True
    except Exception:
        logger.exception("win32_send_syscommand: cmd=0x%x", int(cmd) & 0xFFFF)
        return False


def win32_is_minimized(hwnd: int | None = None) -> bool:
    """Проверка, что окно уже свернуто."""
    if sys.platform != "win32":
        return False
    h = int(hwnd) if hwnd else 0
    if not h:
        cur = kivy_sdl_hwnd()
        h = int(cur) if cur else 0
    if not h or not windll.user32.IsWindow(h):
        return False
    try:
        ok = bool(windll.user32.IsIconic(h))
        logger.debug("win32_is_minimized: hwnd=%s ok=%s", h, ok)
        return ok
    except Exception:
        logger.exception("win32_is_minimized")
        return False


def win32_minimize() -> bool:
    h = kivy_sdl_hwnd()
    if h and win32_is_minimized(int(h)):
        logger.info("win32_minimize: already minimized hwnd=%s", int(h))
        return True

    attempts = (
        ("ShowWindowAsync(SW_MINIMIZE)", lambda: win32_show_window_async(_SW_MINIMIZE)),
        ("ShowWindow(SW_MINIMIZE)", lambda: win32_show_window(_SW_MINIMIZE)),
        ("ShowWindowAsync(SW_SHOWMINIMIZED)", lambda: win32_show_window_async(_SW_SHOWMINIMIZED)),
        ("PostMessage(SC_MINIMIZE)", lambda: win32_post_syscommand(SC_MINIMIZE)),
        ("SendMessage(SC_MINIMIZE)", lambda: win32_send_syscommand(SC_MINIMIZE)),
        ("ShowWindowAsync(SW_FORCEMINIMIZE)", lambda: win32_show_window_async(_SW_FORCEMINIMIZE)),
    )
    for label, func in attempts:
        ok = bool(func())
        minimized = win32_is_minimized(int(h)) if h else False
        logger.info("win32_minimize: %s ok=%s minimized=%s", label, ok, minimized)
        if minimized or ok:
            return True
    return False


def win32_begin_move_drag() -> bool:
    """Запустить нативный системный drag окна через non-client caption."""
    if sys.platform != "win32":
        return False
    h = kivy_sdl_hwnd()
    if not h:
        return False
    try:
        windll.user32.ReleaseCapture()
        windll.user32.SendMessageW(int(h), WM_NCLBUTTONDOWN, HTCAPTION, 0)
        logger.info("win32_begin_move_drag: hwnd=%s", h)
        return True
    except Exception:
        logger.exception("win32_begin_move_drag")
        return False


def win32_allow_set_foreground_window(process_id: int | None) -> bool:
    """Разрешить другому процессу сделать своё окно foreground (Windows focus rules)."""
    if sys.platform != "win32":
        return False
    if process_id is None:
        return False
    try:
        pid = int(process_id)
    except Exception:
        return False
    try:
        ok = bool(windll.user32.AllowSetForegroundWindow(pid))
        logger.info("win32_allow_set_foreground_window: pid=%s ok=%s", pid, ok)
        return ok
    except Exception:
        logger.exception("win32_allow_set_foreground_window: pid=%s", pid)
        return False


def win32_bring_window_to_front(hwnd: int | None = None) -> bool:
    """Попытаться поднять окно на передний план (restore + bring-to-top + foreground)."""
    if sys.platform != "win32":
        return False
    h = int(hwnd) if hwnd else 0
    if not h:
        cur = kivy_sdl_hwnd()
        h = int(cur) if cur else 0
    if not h or not windll.user32.IsWindow(int(h)):
        return False

    try:
        # Restore/Show first: иначе SetForegroundWindow может игнорироваться.
        windll.user32.ShowWindow(int(h), int(_SW_SHOWNORMAL))
    except Exception:
        logger.debug("win32_bring_window_to_front: ShowWindow failed", exc_info=True)

    ok_any = False
    # Частый трюк: временно сделать TOPMOST и сразу вернуть обратно — помогает поднять окно поверх.
    try:
        windll.user32.SetWindowPos(
            int(h),
            int(_HWND_TOPMOST),
            0,
            0,
            0,
            0,
            int(_SWP_NOMOVE | _SWP_NOSIZE | _SWP_SHOWWINDOW),
        )
        windll.user32.SetWindowPos(
            int(h),
            int(_HWND_NOTOPMOST),
            0,
            0,
            0,
            0,
            int(_SWP_NOMOVE | _SWP_NOSIZE | _SWP_SHOWWINDOW),
        )
        ok_any = True
    except Exception:
        logger.debug("win32_bring_window_to_front: SetWindowPos trick failed", exc_info=True)
    try:
        ok_any = bool(windll.user32.BringWindowToTop(int(h))) or ok_any
    except Exception:
        logger.debug("win32_bring_window_to_front: BringWindowToTop failed", exc_info=True)
    try:
        ok_any = bool(windll.user32.SetForegroundWindow(int(h))) or ok_any
    except Exception:
        logger.debug("win32_bring_window_to_front: SetForegroundWindow failed", exc_info=True)
    try:
        ok_any = bool(windll.user32.SetActiveWindow(int(h))) or ok_any
    except Exception:
        logger.debug("win32_bring_window_to_front: SetActiveWindow failed", exc_info=True)
    try:
        ok_any = bool(windll.user32.SetFocus(int(h))) or ok_any
    except Exception:
        logger.debug("win32_bring_window_to_front: SetFocus failed", exc_info=True)

    logger.info("win32_bring_window_to_front: hwnd=%s ok=%s", int(h), bool(ok_any))
    return bool(ok_any)


try:
    from utils.titlebar_logging import setup_titlebar_trace_from_env

    setup_titlebar_trace_from_env()
except Exception:
    pass
