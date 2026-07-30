"""
Отдельное приложение для окна монитора
Создает независимое окно для каждого монитора
"""
import sys

from kivy.config import Config

Config.set("input", "mouse", "mouse,disable_multitouch")
Config.set("kivy", "exit_on_escape", "0")
from utils.kivy_windows_titlebar import configure_config_for_native_titlebar

configure_config_for_native_titlebar()

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.metrics import dp

from components.monitor_screen import MonitorScreen
from components.custom_title_bar import CustomTitleBar
from utils.kivy_windows_titlebar import apply_runtime_custom_titlebar_workarounds
from utils.shared_db_pool import SharedDatabasePool
from utils.ui_style import UI_APP_SHELL_PADDING, UI_TOPBAR_CONTENT_GAP

apply_runtime_custom_titlebar_workarounds()


class MonitorWindowApp(App):
    """Отдельное приложение для окна монитора"""

    def __init__(self, window_id: str, **kwargs):
        super().__init__(**kwargs)
        self.window_id = window_id
        self.monitor_screen = None
        self.title_bar: CustomTitleBar | None = None
        self._shutdown_complete = False

    def build(self):
        """Создание интерфейса окна"""
        Window.clearcolor = (0.1, 0.1, 0.1, 1)

        main_container = BoxLayout(
            orientation="vertical",
            spacing=UI_TOPBAR_CONTENT_GAP,
            padding=UI_APP_SHELL_PADDING,
        )

        title_text = f"Монитор: {self.window_id}"
        self.title = title_text

        use_native = sys.platform == "win32"
        show_custom_window_controls = sys.platform in ("win32", "linux")
        self.title_bar = CustomTitleBar(
            title=title_text,
            show_window_controls=show_custom_window_controls,
            on_close=self._on_close_clicked,
            show_bed_range=True,
            on_bed_press=self._on_title_bed,
            on_range_press=self._on_title_range,
            register_native_frame=use_native,
        )
        main_container.add_widget(self.title_bar)

        self.monitor_screen = MonitorScreen(
            name=f"{self.window_id}_monitor",
            show_menu_bar=False,
            external_status_bar=True,
            align_content_to_host_titlebar=True,
        )
        main_container.add_widget(self.monitor_screen)

        if self.title_bar:
            self.title_bar.bind_monitor_actions(self.monitor_screen)

        return main_container

    def on_start(self):
        Clock.schedule_once(self._apply_start_maximized, 0.28)

    def _apply_start_maximized(self, _dt):
        if self.title_bar:
            self.title_bar.apply_win32_start_maximized(_dt)
            return
        try:
            Window.maximize()
        except Exception:
            pass

    def _on_title_bed(self) -> None:
        if self.monitor_screen:
            self.monitor_screen._show_bed_selection_menu(None)

    def _on_title_range(self) -> None:
        if self.monitor_screen:
            self.monitor_screen._show_time_range_menu(None)

    def _on_close_clicked(self, *args):
        """Обработчик кнопки закрытия"""
        self.stop()

    def on_stop(self):
        """Остановка приложения"""
        if self._shutdown_complete:
            return
        self._shutdown_complete = True
        if self.monitor_screen and hasattr(self.monitor_screen, "on_stop"):
            self.monitor_screen.on_stop()
        SharedDatabasePool().close_all()
