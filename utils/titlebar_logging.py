"""Включение подробного лога шапки (SDL hit-test, Win32) без правки кода.

Установите перед запуском:
  PATIENTMONITOR_TITLEBAR_DEBUG=1

Если hit-test снова «не там» на экранах с масштабом Windows, попробуйте:
  PATIENTMONITOR_TITLEBAR_HIT_SCALE=density

Сообщения идут в stderr в формате:
  %(asctime)s [logger] LEVEL message
"""
from __future__ import annotations

import logging
import os
import sys

_SETUP_DONE = False

# Логгеры шапки (имена модулей — как в getLogger(__name__))
TITLEBAR_LOGGER_NAMES = (
    "components.custom_title_bar",
    "utils.kivy_windows_titlebar",
)


def setup_titlebar_trace_from_env() -> None:
    """Один раз: если PATIENTMONITOR_TITLEBAR_DEBUG=1 — DEBUG + StreamHandler на stderr."""
    global _SETUP_DONE
    if _SETUP_DONE:
        return
    _SETUP_DONE = True
    raw = os.environ.get("PATIENTMONITOR_TITLEBAR_DEBUG", "").strip().lower()
    if raw not in ("1", "true", "yes", "on"):
        return
    fmt = "%(asctime)s [%(name)s] %(levelname)s %(message)s"
    formatter = logging.Formatter(fmt)
    for name in TITLEBAR_LOGGER_NAMES:
        lg = logging.getLogger(name)
        lg.setLevel(logging.DEBUG)
        if not lg.handlers:
            h = logging.StreamHandler(sys.stderr)
            h.setLevel(logging.DEBUG)
            h.setFormatter(formatter)
            lg.addHandler(h)
        lg.propagate = False
