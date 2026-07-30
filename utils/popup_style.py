"""
Единое оформление всех Kivy Popup: фон, затемнение, заголовок, скролл, поля ввода.
Подключайте apply_popup_theme(popup) сразу после создания Popup (перед open).
"""
from __future__ import annotations

from kivy.metrics import dp

from utils.ui_style import (
    UI_CURSOR_NEUTRAL,
    UI_POPUP_SEPARATOR,
    UI_POPUP_TEXT,
    UI_POPUP_TEXT_MUTED,
    UI_POPUP_TITLE,
    UI_SURFACE_PANEL_ALT,
    UI_SURFACE_POPUP,
    UI_SURFACE_POPUP_OVERLAY,
)

# Палитра (согласована с settings_popup и тёмным UI)
POPUP_BG = UI_SURFACE_POPUP
POPUP_TITLE_COLOR = UI_POPUP_TITLE
POPUP_TITLE_SIZE_DP = 19
POPUP_SEPARATOR_COLOR = UI_POPUP_SEPARATOR
POPUP_OVERLAY = UI_SURFACE_POPUP_OVERLAY

POPUP_BODY_TEXT = UI_POPUP_TEXT
POPUP_MUTED_TEXT = UI_POPUP_TEXT_MUTED
POPUP_SCROLLBAR = (0.34, 0.34, 0.36, 0.55)

_ESC_DISMISS_HANDLER_INSTALLED = False


def _ensure_esc_dismiss_handler() -> None:
    """
    Глобальный обработчик: Esc закрывает верхний открытый Popup/ModalView.

    В Kivy Esc/Back по умолчанию часто завязан на auto_dismiss. Нам нужно,
    чтобы закрытие работало и для auto_dismiss=False (например, формы/настройки).
    """
    global _ESC_DISMISS_HANDLER_INSTALLED
    if _ESC_DISMISS_HANDLER_INSTALLED:
        return
    _ESC_DISMISS_HANDLER_INSTALLED = True

    try:
        from kivy.core.window import Window
        from kivy.uix.modalview import ModalView
        try:
            from kivy.uix.dropdown import DropDown  # type: ignore
        except Exception:
            DropDown = None  # type: ignore
    except Exception:
        return

    def _on_keyboard(window, key, _scancode, _codepoint, _modifier):
        # 27 = Escape (также используется как Back на Android).
        if int(key) != 27:
            return False

        try:
            children = list(getattr(window, "children", []) or [])
        except Exception:
            children = []

        for child in children:
            if isinstance(child, ModalView):
                try:
                    child.dismiss()
                except Exception:
                    pass
                return True
            if DropDown is not None and isinstance(child, DropDown):  # type: ignore[arg-type]
                try:
                    child.dismiss()
                except Exception:
                    pass
                return True
        return False

    try:
        Window.bind(on_keyboard=_on_keyboard)
    except Exception:
        pass


def apply_popup_theme(popup, *, frameless: bool | None = None) -> None:
    """
    Общий стиль окна Popup.
    frameless=None: полоса заголовка только если title непустой.
    frameless=True: без separator / без оформления title-bar (контент сам рисует шапку).
    frameless=False: всегда показать title-bar (если задан title).
    """
    _ensure_esc_dismiss_handler()
    try:
        popup.border = [0, 0, 0, 0]
    except Exception:
        pass
    try:
        popup.background = ""
    except Exception:
        pass
    popup.background_color = POPUP_BG
    popup.overlay_color = POPUP_OVERLAY

    title = str(getattr(popup, "title", "") or "").strip()
    if frameless is None:
        show_chrome = bool(title)
    else:
        show_chrome = (not frameless) and bool(title)

    if show_chrome:
        popup.separator_height = dp(1)
        popup.separator_color = POPUP_SEPARATOR_COLOR
        popup.title_color = POPUP_TITLE_COLOR
        popup.title_size = dp(POPUP_TITLE_SIZE_DP)
    else:
        popup.separator_height = 0


def style_scrollview_popup(sv) -> None:
    """Скролл внутри попапов — полоска прокрутки в стиле приложения."""
    try:
        sv.bar_width = max(float(sv.bar_width or 0), float(dp(8)))
    except Exception:
        sv.bar_width = dp(8)
    sv.bar_color = POPUP_SCROLLBAR


def style_text_input_dark(ti) -> None:
    """Текстовое поле в модальных формах."""
    ti.background_color = UI_SURFACE_PANEL_ALT
    ti.foreground_color = UI_POPUP_TITLE
    ti.cursor_color = UI_CURSOR_NEUTRAL
    ti.padding = (dp(10), dp(9), dp(10), dp(9))
    ti.font_size = dp(14)


def style_popup_label_body(lbl) -> None:
    """Основной текст сообщений внутри попапа."""
    lbl.color = POPUP_BODY_TEXT
