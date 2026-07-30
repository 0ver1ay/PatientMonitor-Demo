from __future__ import annotations

from kivy.core.window import Window


def has_open_modal_or_dropdown(window=None) -> bool:
    try:
        from kivy.uix.modalview import ModalView
        try:
            from kivy.uix.dropdown import DropDown  # type: ignore
        except Exception:
            DropDown = None  # type: ignore
    except Exception:
        return False

    try:
        active_window = window or Window
        children = list(getattr(active_window, "children", []) or [])
    except Exception:
        return False

    for child in children:
        try:
            if isinstance(child, ModalView):
                return True
            if DropDown is not None and isinstance(child, DropDown):  # type: ignore[arg-type]
                return True
        except Exception:
            continue
    return False


class EscBackNavigationMixin:
    """Добавляет поведение Esc -> _on_back_clicked() для Screen."""

    def _init_esc_back_navigation(self) -> None:
        self._esc_handler_bound = False

    def _bind_escape_handler(self) -> None:
        if getattr(self, "_esc_handler_bound", False):
            return
        try:
            Window.bind(on_keyboard=self._on_window_keyboard)
            self._esc_handler_bound = True
        except Exception:
            self._esc_handler_bound = False

    def _unbind_escape_handler(self) -> None:
        if not getattr(self, "_esc_handler_bound", False):
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

        if not getattr(self, "manager", None) or self.manager.current != getattr(self, "name", None):
            return False

        on_back = getattr(self, "_on_back_clicked", None)
        if callable(on_back):
            on_back()
            return True
        return False
