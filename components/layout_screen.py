"""
Экран с раскладкой нескольких мониторов.
Поддерживает раскладки от 1 до 8 мониторов.
"""
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.metrics import dp

from components.esc_back_navigation import EscBackNavigationMixin
from components.monitor_screen import MonitorScreen
from components.custom_title_bar import CustomTitleBar
from utils.config_loader import ConfigLoader
from utils.ui_style import UI_APP_SHELL_PADDING, UI_TOPBAR_CONTENT_GAP, apply_rounded_panel


class LayoutScreen(EscBackNavigationMixin, Screen):
    """Экран с раскладкой нескольких мониторов"""

    def __init__(self, monitor_count: int = 1, **kwargs):
        """
        Инициализация экрана раскладки

        Args:
            monitor_count: Количество мониторов (1-8)
        """
        super().__init__(**kwargs)
        self._init_esc_back_navigation()
        self.monitor_count = max(1, min(8, int(monitor_count)))
        self.monitor_screens = []
        self.title_bar: CustomTitleBar | None = None
        self._config_loader = ConfigLoader()

        self._create_ui()

    def _create_ui(self):
        """Создание пользовательского интерфейса"""
        main_container = BoxLayout(
            orientation="vertical",
            spacing=UI_TOPBAR_CONTENT_GAP,
            padding=UI_APP_SHELL_PADDING,
        )

        title_text = f'Раскладка: {self.monitor_count} монитор{"ов" if self.monitor_count > 1 else ""}'
        self.title_bar = CustomTitleBar(
            title=title_text,
            on_back=self._on_back_clicked,
            show_window_controls=False,
            show_bed_range=False,
            on_bed_press=self._on_title_bed,
            on_range_press=self._on_title_range,
        )
        main_container.add_widget(self.title_bar)

        monitors_container = self._create_monitors_container()
        main_container.add_widget(monitors_container)

        self.add_widget(main_container)

    def _on_title_bed(self) -> None:
        if self.monitor_count == 1 and self.monitor_screens:
            self.monitor_screens[0]._show_bed_selection_menu(None)

    def _on_title_range(self) -> None:
        if self.monitor_count == 1 and self.monitor_screens:
            self.monitor_screens[0]._show_time_range_menu(None)

    def _sync_monitor_contexts(self):
        """Прокинуть embedded MonitorScreen реальный ScreenManager-контекст."""
        for monitor_screen in self.monitor_screens:
            monitor_screen.manager = self.manager
            monitor_screen.navigation_screen_name = self.name

    def _create_monitors_container(self):
        """Создание контейнера с мониторами в зависимости от количества"""
        for i in range(self.monitor_count):
            monitor_screen = MonitorScreen(
                name=f"{self.name}_monitor_{i}",
                show_menu_bar=False,
                external_status_bar=False,
                grid_tile_layout=True,
                align_content_to_host_titlebar=True,
            )
            self.monitor_screens.append(monitor_screen)

        if self.monitor_count == 1:
            container = BoxLayout(orientation="vertical", spacing=0, padding=0)
            container.add_widget(self._wrap_monitor_tile(self.monitor_screens[0]))
            return container

        cols, rows = self._config_loader.get_layout_grid_dimensions(self.monitor_count)
        container = GridLayout(cols=cols, rows=rows, spacing=dp(15), padding=dp(6))
        self._apply_flat_fill(container)
        for monitor in self.monitor_screens:
            container.add_widget(self._wrap_monitor_tile(monitor))
        for _ in range(max(0, cols * rows - self.monitor_count)):
            container.add_widget(Widget())
        return container

    def _wrap_monitor_tile(self, content_widget):
        tile_shell = BoxLayout(
            orientation="vertical",
            padding=dp(6),
            spacing=0,
            size_hint=(1, 1),
        )
        apply_rounded_panel(
            tile_shell,
            base_rgba=(0.095, 0.098, 0.112, 1),
            radius_px=dp(14),
            border_alpha=0.08,
        )
        tile_shell.add_widget(content_widget)
        return tile_shell

    @staticmethod
    def _apply_flat_fill(widget, rgba=(0.062, 0.066, 0.078, 1)):
        with widget.canvas.before:
            widget._pm_flat_bg_color = Color(*rgba)
            widget._pm_flat_bg_rect = Rectangle(pos=widget.pos, size=widget.size)

        def _upd(*_args):
            widget._pm_flat_bg_rect.pos = widget.pos
            widget._pm_flat_bg_rect.size = widget.size

        widget.bind(pos=_upd, size=_upd)
        _upd()

    def _on_back_clicked(self, *args):
        """Обработчик кнопки возврата - переход в менеджер окон"""
        if self.manager:
            if self.manager.has_screen("main_window_manager"):
                self.manager.current = "main_window_manager"

    def on_pre_enter(self, *args):
        self._bind_escape_handler()
        self._sync_monitor_contexts()
        return super().on_pre_enter(*args)

    def on_pre_leave(self, *args):
        """Вызывается перед уходом с экрана"""
        self._unbind_escape_handler()
        for monitor_screen in self.monitor_screens:
            if hasattr(monitor_screen, "on_stop"):
                monitor_screen.on_stop()
        return super().on_pre_leave(*args)
