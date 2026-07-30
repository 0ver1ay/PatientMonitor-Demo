"""
Скрипт для запуска отдельного окна с несколькими мониторами
Запускается как отдельный процесс для раскладки мониторов
"""
import sys
import os

# Добавляем путь к проекту и устанавливаем рабочую директорию
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)
os.chdir(project_dir)  # Устанавливаем рабочую директорию для поиска config.ini
print(f"[MonitorWindow] Рабочая директория: {os.getcwd()}")
print(f"[MonitorWindow] Путь к проекту: {project_dir}")

from kivy.config import Config

Config.set("input", "mouse", "mouse,disable_multitouch")
Config.set("kivy", "exit_on_escape", "0")
from utils.kivy_windows_titlebar import configure_config_for_native_titlebar

configure_config_for_native_titlebar()

from kivy.app import App
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import ScreenManager
from kivy.metrics import dp
from components.monitor_screen import MonitorScreen
from components.bed_selection_screen import BedSelectionScreen
from components.parameter_selection_screen import ParameterSelectionScreen
from components.time_range_selection_screen import TimeRangeSelectionScreen
from components.custom_title_bar import CustomTitleBar
from utils.config_loader import ConfigLoader
from utils.layout_config import LayoutConfig
from utils.shared_db_pool import SharedDatabasePool
from utils.kivy_windows_titlebar import apply_runtime_custom_titlebar_workarounds
from utils.ui_style import UI_APP_SHELL_PADDING, UI_TOPBAR_CONTENT_GAP, apply_rounded_panel

apply_runtime_custom_titlebar_workarounds()


class MonitorLayoutWindowApp(App):
    """Отдельное приложение для окна с раскладкой мониторов"""

    def __init__(self, window_id: str, monitor_count: int = 1, config_id: str = None, **kwargs):
        super().__init__(**kwargs)
        self.window_id = window_id
        self.monitor_count = max(1, min(8, int(monitor_count)))
        self.config_id = config_id
        self.monitor_screens = []
        self.layout_config = None
        self.title_bar: CustomTitleBar | None = None
        self._primary_sm: ScreenManager | None = None
        self._primary_monitor_screen_name: str | None = None
        self._config_loader = ConfigLoader()
        self._shutdown_complete = False

        # Загружаем конфигурацию, если указан config_id
        if config_id:
            self.layout_config = LayoutConfig.get_config(config_id)

    def build(self):
        """Создание интерфейса окна"""
        Window.clearcolor = (0.1, 0.1, 0.1, 1)

        main_container = BoxLayout(
            orientation="vertical",
            spacing=UI_TOPBAR_CONTENT_GAP,
            padding=UI_APP_SHELL_PADDING,
        )

        title_text = f'Раскладка: {self.monitor_count} монитор{"ов" if self.monitor_count > 1 else ""}'
        self.title = title_text

        use_native = sys.platform == "win32"
        show_custom_window_controls = sys.platform in ("win32", "linux")
        self.title_bar = CustomTitleBar(
            title=title_text,
            show_window_controls=show_custom_window_controls,
            on_close=self._request_close,
            show_bed_range=False,
            on_bed_press=self._on_title_bed,
            on_range_press=self._on_title_range,
            register_native_frame=use_native,
        )
        main_container.add_widget(self.title_bar)

        monitors_container = self._create_monitors_container()
        main_container.add_widget(monitors_container)

        if self.monitor_count == 1 and self.monitor_screens and self.title_bar:
            self._sync_title_bar_for_screen(self._primary_monitor_screen_name)

        return main_container

    def on_start(self):
        # Для 2+ мониторов на узком экране поднимаем разумный размер окна.
        try:
            if self.monitor_count > 1 and float(getattr(Window, "width", 0) or 0) < 1280:
                Window.size = (1280, 720)
        except Exception:
            pass
        # Важно: при запуске из главного окна новое окно иногда оказывается "под" текущим.
        # Пробуем несколько раз поднять его на передний план.
        def _raise(_dt):
            try:
                if hasattr(Window, "raise_window"):
                    Window.raise_window()
            except Exception:
                pass
            try:
                from utils.kivy_windows_titlebar import win32_bring_window_to_front

                win32_bring_window_to_front()
            except Exception:
                pass

        try:
            Clock.schedule_once(_raise, 0)
            Clock.schedule_once(_raise, 0.05)
            Clock.schedule_once(_raise, 0.2)
        except Exception:
            pass

    def _request_close(self) -> None:
        self.stop()

    def _on_title_bed(self) -> None:
        if self.monitor_screens:
            self.monitor_screens[0]._show_bed_selection_menu(None)

    def _on_title_range(self) -> None:
        if self.monitor_screens:
            self.monitor_screens[0]._show_time_range_menu(None)

    def _on_primary_screen_changed(self, sm, _value) -> None:
        self._sync_title_bar_for_screen(sm.current)

    def _sync_title_bar_for_screen(self, current_name: str | None) -> None:
        tb = self.title_bar
        if tb is None:
            return
        current_name = str(current_name or "")
        on_pick_screen = ("bed_selection" in current_name) or ("time_range_selection" in current_name)
        tb.set_bed_range_visible(not on_pick_screen)

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

    def _create_monitors_container(self):
        """Создание контейнера с мониторами в зависимости от количества"""
        # Создаем ScreenManager для каждого монитора, чтобы они могли переключаться на экраны выбора
        monitor_widgets = []

        for i in range(self.monitor_count):
            # Создаем ScreenManager для каждого монитора
            sm = ScreenManager()

            # Получаем конфигурацию для этого монитора
            monitor_config = None
            if self.layout_config and i < len(self.layout_config.get("monitors", [])):
                monitor_config = self.layout_config["monitors"][i]

            # Создаем монитор с конфигурацией
            monitor_screen = MonitorScreen(
                name=f"{self.window_id}_monitor_{i}",
                layout_config_id=self.config_id,
                monitor_index=i,
                monitor_config=monitor_config,
                external_status_bar=False,
                show_menu_bar=False,
                grid_tile_layout=True,
                align_content_to_host_titlebar=True,
            )
            self.monitor_screens.append(monitor_screen)
            sm.add_widget(monitor_screen)
            if i == 0:
                self._primary_sm = sm
                self._primary_monitor_screen_name = monitor_screen.name

            # Добавляем экраны выбора в ScreenManager с уникальными именами для каждого монитора
            bed_selection_screen = BedSelectionScreen(
                name=f"{self.window_id}_bed_selection_{i}",
                show_header_nav=False,
            )
            sm.add_widget(bed_selection_screen)

            parameter_selection_screen = ParameterSelectionScreen(name=f"{self.window_id}_parameter_selection_{i}")
            sm.add_widget(parameter_selection_screen)

            time_range_selection_screen = TimeRangeSelectionScreen(
                name=f"{self.window_id}_time_range_selection_{i}",
                show_header_nav=False,
            )
            sm.add_widget(time_range_selection_screen)

            # Устанавливаем монитор как текущий экран
            sm.current = monitor_screen.name
            if i == 0:
                sm.bind(current=self._on_primary_screen_changed)

            monitor_widgets.append(sm)

        # Создаем контейнер в зависимости от количества мониторов
        if self.monitor_count == 1:
            # 1 монитор - на весь экран
            container = BoxLayout(orientation="vertical", spacing=0, padding=0)
            container.add_widget(self._wrap_monitor_tile(monitor_widgets[0]))
            return container

        cols, rows = self._config_loader.get_layout_grid_dimensions(self.monitor_count)
        container = GridLayout(cols=cols, rows=rows, spacing=dp(15), padding=dp(6))
        self._apply_flat_fill(container)
        for widget in monitor_widgets:
            container.add_widget(self._wrap_monitor_tile(widget))
        for _ in range(max(0, cols * rows - self.monitor_count)):
            container.add_widget(BoxLayout())
        return container

    def on_stop(self):
        """Остановка приложения"""
        if self._shutdown_complete:
            return
        self._shutdown_complete = True
        # Останавливаем все мониторы
        for monitor_screen in self.monitor_screens:
            if hasattr(monitor_screen, "on_stop"):
                monitor_screen.on_stop()
        SharedDatabasePool().close_all()


if __name__ == "__main__":
    # Получаем параметры из аргументов командной строки
    window_id = sys.argv[1] if len(sys.argv) > 1 else "layout_1"
    try:
        monitor_count = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    except (TypeError, ValueError):
        print(f"[run_monitor_window] invalid monitor_count={sys.argv[2]!r}, fallback to 1")
        monitor_count = 1
    monitor_count = max(1, min(8, monitor_count))
    config_id = sys.argv[3] if len(sys.argv) > 3 else None

    app = MonitorLayoutWindowApp(window_id, monitor_count, config_id)
    app.run()
