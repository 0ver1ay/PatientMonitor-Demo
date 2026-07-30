"""
Экран окна монитора пациента
Обертка над MonitorScreen с возможностью возврата в менеджер окон
"""
from kivy.core.window import Window
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.metrics import dp

from components.esc_back_navigation import EscBackNavigationMixin
from components.monitor_screen import MonitorScreen
from components.custom_title_bar import CustomTitleBar
from utils.ui_style import UI_APP_SHELL_PADDING, UI_TOPBAR_CONTENT_GAP


class MonitorWindowScreen(EscBackNavigationMixin, Screen):
    """Экран окна монитора пациента"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_esc_back_navigation()
        # name должен быть установлен при создании

        main_container = BoxLayout(
            orientation="vertical",
            spacing=UI_TOPBAR_CONTENT_GAP,
            padding=UI_APP_SHELL_PADDING,
        )

        title_text = f"Окно монитора: {self.name}"
        self.title_bar = CustomTitleBar(
            title=title_text,
            on_back=self._on_back_clicked,
            show_window_controls=False,
            show_bed_range=True,
            on_bed_press=self._on_title_bed,
            on_range_press=self._on_title_range,
        )
        main_container.add_widget(self.title_bar)

        monitor_screen_name = f"{self.name}_monitor"
        self.monitor_screen = MonitorScreen(
            name=monitor_screen_name,
            show_menu_bar=False,
            external_status_bar=True,
            align_content_to_host_titlebar=True,
        )
        main_container.add_widget(self.monitor_screen)

        self.title_bar.bind_monitor_actions(self.monitor_screen)

        self.add_widget(main_container)

    def _on_title_bed(self) -> None:
        if self.monitor_screen:
            self.monitor_screen._show_bed_selection_menu(None)

    def _on_title_range(self) -> None:
        if self.monitor_screen:
            self.monitor_screen._show_time_range_menu(None)

    def _sync_monitor_context(self):
        """Прокинуть embedded MonitorScreen реальный ScreenManager-контекст."""
        if hasattr(self, "monitor_screen"):
            self.monitor_screen.manager = self.manager
            self.monitor_screen.navigation_screen_name = self.name

    def on_pre_enter(self, *args):
        self._bind_escape_handler()
        self._sync_monitor_context()
        return super().on_pre_enter(*args)

    def _on_back_clicked(self, *args):
        """Обработчик кнопки возврата - переход в менеджер окон"""
        if self.manager:
            if self.manager.has_screen("main_window_manager"):
                self.manager.current = "main_window_manager"

    def on_pre_leave(self, *args):
        """Вызывается перед уходом с экрана"""
        self._unbind_escape_handler()
        if hasattr(self.monitor_screen, "on_stop"):
            self.monitor_screen.on_stop()
        return super().on_pre_leave(*args)
