"""
Главный файл приложения монитора пациента
Мультиоконное приложение с поддержкой раскладок
"""
from kivy.config import Config

Config.set("input", "mouse", "mouse,disable_multitouch")
Config.set("kivy", "exit_on_escape", "0")
from utils.kivy_windows_titlebar import configure_config_for_native_titlebar

configure_config_for_native_titlebar()

from kivy.app import App
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager
from kivy.metrics import dp
from pathlib import Path
import os
import sys
from components.app_menu_bar import AppMenuBar
from components.custom_title_bar import CustomTitleBar
from components.main_window_manager_screen import MainWindowManagerScreen
from components.bed_selection_screen import BedSelectionScreen
from components.parameter_selection_screen import ParameterSelectionScreen
from components.time_range_selection_screen import TimeRangeSelectionScreen
from components.message_screen import MessageScreen
from components.settings_screen import SettingsScreen
from utils.config_loader import ConfigLoader
from utils.shared_db_pool import SharedDatabasePool
from utils.ui_style import UI_APP_SHELL_PADDING, UI_TOPBAR_CONTENT_GAP
from utils.database_source import DatabaseDataSource
from utils.kivy_windows_titlebar import apply_runtime_custom_titlebar_workarounds

apply_runtime_custom_titlebar_workarounds()


class PatientMonitorApp(App):
    """Главное приложение монитора пациента"""

    SETTINGS_SCREEN_NAME = "app_settings_screen"
    MESSAGE_SCREEN_NAME = "app_message_screen"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config_loader = ConfigLoader()
        self._screen_manager = None
        self._main_window_manager = None
    
    def build(self):
        """Создание главного экрана приложения"""
        # Установка темной темы по умолчанию
        Window.clearcolor = (0.1, 0.1, 0.1, 1)
        
        # Создаем менеджер экранов
        sm = ScreenManager()
        
        # Главный экран управления окнами
        main_window_manager = MainWindowManagerScreen()
        sm.add_widget(main_window_manager)
        
        # Экран выбора кровати (используется из окон мониторов)
        bed_selection_screen = BedSelectionScreen()
        sm.add_widget(bed_selection_screen)
        
        # Экран выбора параметров (используется из окон мониторов)
        parameter_selection_screen = ParameterSelectionScreen()
        sm.add_widget(parameter_selection_screen)
        
        # Экран выбора временного диапазона (используется из окон мониторов)
        time_range_selection_screen = TimeRangeSelectionScreen()
        sm.add_widget(time_range_selection_screen)
        
        self._screen_manager = sm
        self._main_window_manager = main_window_manager

        # Устанавливаем главный экран как текущий
        sm.current = 'main_window_manager'

        root = BoxLayout(orientation="vertical", spacing=UI_TOPBAR_CONTENT_GAP, padding=UI_APP_SHELL_PADDING)
        root.add_widget(self._build_top_bar())
        root.add_widget(sm)
        return root

    def _get_main_menu_spec(self):
        return {
            "Файл": [
                ("Открыть папку экспорта", self._menu_open_exports_folder),
            ],
            "Настройки": self._menu_open_settings,
            "Сервис": [
                ("Проверить подключение к БД", self._menu_check_db_connection),
                ("Перезагрузить config.ini и применить", self._menu_reload_config_and_notify),
            ],
            "Справка": [
                ("Показать текущий config", self._menu_show_current_config),
            ],
        }

    def _build_top_bar(self):
        """Одна верхняя строка: меню слева, заголовок справа (как в окнах с CustomTitleBar)."""
        menu = AppMenuBar(
            menu_spec=self._get_main_menu_spec(),
            compact=True,
            embedded=True,
        )
        use_native = sys.platform == "win32"
        show_custom_window_controls = sys.platform in ("win32", "linux")
        return CustomTitleBar(
            title="Монитор пациента",
            menu_widget=menu,
            show_window_controls=show_custom_window_controls,
            on_close=self.stop,
            register_native_frame=use_native,
        )

    def _menu_open_settings(self):
        previous_screen = self._screen_manager.current if self._screen_manager else None
        screen = SettingsScreen(
            name=self.SETTINGS_SCREEN_NAME,
            settings_data=self.config_loader.to_settings_dict(),
            on_save=self._on_settings_saved,
            previous_screen=previous_screen,
        )
        self._open_temporary_screen(screen)

    def _menu_reload_config(self):
        self.config_loader.reload()

    def _menu_reload_config_and_notify(self):
        self._menu_reload_config()
        self._show_message(
            "Config обновлен",
            f"Перечитан файл:\n{self.config_loader.get_config_path()}",
        )

    def _on_settings_saved(self, data: dict) -> bool:
        ok = self.config_loader.apply_settings_dict(data)
        if ok:
            self.config_loader.reload()
        return ok

    def _menu_show_config_path(self):
        self._show_message("Путь к config.ini", self.config_loader.get_config_path())

    def _menu_open_exports_folder(self):
        exports_dir = Path(__file__).resolve().parent / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(exports_dir))
            else:
                self._show_message("Папка экспорта", str(exports_dir))
        except Exception as e:
            self._show_message("Ошибка", f"Не удалось открыть папку:\n{exports_dir}\n\n{e}")

    def _menu_check_db_connection(self):
        try:
            db = DatabaseDataSource(
                host=self.config_loader.get_db_host(),
                port=self.config_loader.get_db_port(),
                database=self.config_loader.get_db_name(),
                user=self.config_loader.get_db_user(),
                password=self.config_loader.get_db_password(),
                signal_ids=self.config_loader.get_signal_ids(),
            )
            ok = db.is_available()
            try:
                db.close()
            except Exception:
                pass
            if ok:
                self._show_message(
                    "Проверка БД",
                    (
                        "Подключение успешно.\n\n"
                        f"host={self.config_loader.get_db_host()}\n"
                        f"port={self.config_loader.get_db_port()}\n"
                        f"database={self.config_loader.get_db_name()}\n"
                        f"user={self.config_loader.get_db_user()}"
                    ),
                )
            else:
                self._show_message("Проверка БД", "Подключение не удалось. Проверьте параметры и доступность сервера.")
        except Exception as e:
            self._show_message("Проверка БД", f"Ошибка проверки подключения:\n{e}")

    def _menu_switch_mode(self, mode: str):
        self.config_loader.set_mode(mode)
        ok = self.config_loader.save()
        if ok:
            self.config_loader.reload()
            self._show_message("Режим обновлен", f"Установлен режим: {self.config_loader.get_mode()}")
        else:
            self._show_message("Ошибка", "Не удалось сохранить режим в config.ini")

    def _menu_show_current_config(self):
        text = (
            f"path: {self.config_loader.get_config_path()}\n"
            f"mode: {self.config_loader.get_mode()}\n"
            f"host: {self.config_loader.get_db_host()}\n"
            f"port: {self.config_loader.get_db_port()}\n"
            f"database: {self.config_loader.get_db_name()}\n"
            f"user: {self.config_loader.get_db_user()}"
        )
        self._show_message("Текущий config", text)

    def _show_message(self, title: str, text: str):
        previous_screen = self._screen_manager.current if self._screen_manager else None
        screen = MessageScreen(
            name=self.MESSAGE_SCREEN_NAME,
            title_text=title,
            message_text=text,
            previous_screen=previous_screen,
        )
        self._open_temporary_screen(screen)

    def _open_temporary_screen(self, screen):
        if not self._screen_manager:
            return
        if self._screen_manager.has_screen(screen.name):
            existing = self._screen_manager.get_screen(screen.name)
            self._screen_manager.remove_widget(existing)
        self._screen_manager.add_widget(screen)
        self._screen_manager.current = screen.name

    def on_stop(self):
        """Закрыть общий пул после остановки всех экранов процесса."""
        SharedDatabasePool().close_all()


if __name__ == '__main__':
    PatientMonitorApp().run()

