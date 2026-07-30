"""
Отдельная программа: просмотрщик для одной кровати

Поток:
1) Выбор исследования (и при необходимости кровати)
2) Выбор диапазона дат/времени (start/end)
3) Просмотр (визуально как монитор пациента)
"""
import os
import sys

# Добавляем путь к проекту и устанавливаем рабочую директорию
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)
os.chdir(project_dir)

from kivy.config import Config
Config.set("input", "mouse", "mouse,disable_multitouch")
Config.set("kivy", "exit_on_escape", "0")
from utils.kivy_windows_titlebar import configure_config_for_native_titlebar

configure_config_for_native_titlebar()

from kivy.app import App
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager

from components.esc_back_navigation import has_open_modal_or_dropdown

from components.bed_selection_screen import BedSelectionScreen
from components.custom_title_bar import CustomTitleBar
from components.date_time_range_selection_screen import DateTimeRangeSelectionScreen
from components.parameter_selection_screen import ParameterSelectionScreen
from components.monitor_screen import MonitorScreen
from components.study_selection_screen import StudySelectionScreen
from components.time_range_selection_screen import TimeRangeSelectionScreen
from utils.database_source import DatabaseDataSource
from utils.kivy_windows_titlebar import apply_runtime_custom_titlebar_workarounds
from utils.shared_db_pool import SharedDatabasePool
from utils.ui_style import UI_APP_SHELL_PADDING, UI_TOPBAR_CONTENT_GAP

apply_runtime_custom_titlebar_workarounds()


class BedViewerApp(App):
    """Просмотрщик данных для одной кровати."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._start_screen_name = None
        self._sm = None
        self._monitor_screen: MonitorScreen | None = None
        self._title_bar: CustomTitleBar | None = None
        self._shutdown_complete = False

    def build(self):
        Window.clearcolor = (0.1, 0.1, 0.1, 1)

        sm = ScreenManager()

        self._monitor_screen = MonitorScreen(
            name="viewer_monitor",
            viewer_mode=True,
            auto_start=False,
            show_menu_bar=False,
            viewer_toolbar_in_titlebar=False,
            grid_tile_layout=True,
        )

        def stop_app():
            self.stop()

        study_screen = StudySelectionScreen(
            name="viewer_study_selection",
            beds_screen="viewer_bed_selection",
            next_screen_on_select="viewer_monitor",
            on_back=stop_app,
        )

        bed_screen = BedSelectionScreen(
            name="viewer_bed_selection",
            previous_screen="viewer_study_selection",
            next_screen_on_select="viewer_date_time_range",
            show_header_nav=False,
        )

        range_screen = DateTimeRangeSelectionScreen(
            name="viewer_date_time_range",
            previous_screen="viewer_bed_selection",
            next_screen_on_apply="viewer_monitor",
            show_header_nav=False,
        )

        # Экран выбора параметра (для кликов по графикам/цифрам)
        param_screen = ParameterSelectionScreen(name="viewer_parameter_selection")
        # Экран выбора "разрешения" (используем существующий выбор диапазона)
        resolution_screen = TimeRangeSelectionScreen(name="viewer_time_range_selection")

        # Callbacks
        def on_bed_selected(bed_id: int, bed_name: str):
            # Устанавливаем кровать на источнике данных монитора
            if self._monitor_screen is not None and isinstance(self._monitor_screen.data_source, DatabaseDataSource):
                self._monitor_screen.data_source.set_bed_id(bed_id)
                # обновим кнопку на самом мониторе (если UI уже создан)
                if hasattr(self._monitor_screen, "bed_button"):
                    if hasattr(self._monitor_screen, "_set_bed_button_text"):
                        self._monitor_screen._set_bed_button_text(bed_name, int(bed_id))
                    else:
                        self._monitor_screen.bed_button.text = bed_name

        def on_range_selected(start_dt, end_dt):
            if self._monitor_screen is None:
                return
            self._monitor_screen.set_history_range(start_dt, end_dt)
            self._monitor_screen.reload_historical_data()

        def on_study_selected(study: dict):
            # Study -> bed + абсолютный диапазон
            if self._monitor_screen is None or not isinstance(self._monitor_screen.data_source, DatabaseDataSource):
                return
            # Сохраним выбранное исследование для UI монитора
            try:
                self._monitor_screen.current_study = study
                if hasattr(self._monitor_screen, "_set_study_button_text"):
                    self._monitor_screen._set_study_button_text(study)
            except Exception:
                pass
            try:
                bed_id = study.get("bed_id")
                bed_name = None
                if bed_id is not None:
                    try:
                        bed = self._monitor_screen.data_source.get_bed_info(int(bed_id))
                        if bed:
                            bed_name = bed.get("bed_name") or bed.get("name")
                    except Exception:
                        pass
                if bed_id is not None:
                    self._monitor_screen.data_source.set_bed_id(int(bed_id))
                    if hasattr(self._monitor_screen, "bed_button"):
                        if hasattr(self._monitor_screen, "_set_bed_button_text"):
                            self._monitor_screen._set_bed_button_text(bed_name, int(bed_id))
                        else:
                            self._monitor_screen.bed_button.text = bed_name or f"Кровать {bed_id}"
            except Exception:
                pass

            start_dt = study.get("begin_dt")
            end_dt = study.get("end_dt")
            if start_dt and end_dt:
                self._monitor_screen.set_history_range(start_dt, end_dt)
                self._monitor_screen.reload_historical_data()

        bed_screen.set_on_bed_selected(on_bed_selected)
        range_screen.set_on_range_selected(on_range_selected)
        study_screen.set_on_study_selected(on_study_selected)

        # Подгружаем кровати/study только при реальном online-подключении.
        if self._monitor_screen is not None and isinstance(self._monitor_screen.data_source, DatabaseDataSource):
            db_online = True
            if hasattr(self._monitor_screen, "_is_database_online"):
                db_online = bool(self._monitor_screen._is_database_online())
            elif hasattr(self._monitor_screen.data_source, "is_available"):
                db_online = bool(self._monitor_screen.data_source.is_available())

            if not db_online:
                study_screen.set_table_status(
                    "error",
                    "База данных недоступна · запустите PostgreSQL и нажмите «Обновить»",
                )
                bed_screen.set_beds([])
            else:
                beds = self._monitor_screen.data_source.get_available_beds()
                bed_screen.set_beds(beds)
                bed_screen.set_current_bed_id(self._monitor_screen.data_source.get_current_bed_id())
                try:
                    studies = self._monitor_screen.data_source.get_recent_studies(limit=200)
                    if studies:
                        study_screen.set_studies(studies)
                    else:
                        study_screen.set_table_status("empty", "Нет доступных исследований")
                except Exception as exc:
                    study_screen.set_table_status(
                        "error",
                        f"Не удалось загрузить исследования · {exc}",
                    )

            study_screen.set_on_refresh(lambda: self._monitor_screen.data_source.get_recent_studies(limit=200))
            study_screen.set_on_search_studies(
                lambda filters: self._monitor_screen.data_source.search_studies(filters, limit=200)
            )
            study_screen.set_on_open_study_id(lambda sid: self._monitor_screen.data_source.get_study_by_id(sid))
        else:
            study_screen.set_table_status(
                "error",
                "Источник данных недоступен · проверьте config.ini и подключение к БД",
            )

        # Позволяем с экрана study перейти в режим выбора кровати
        study_screen.set_beds_screen(bed_screen.name)

        # ВАЖНО: посадочный экран должен быть study без "мигания" monitor.
        # Добавляем study первым и сразу делаем его current, затем остальные экраны.
        sm.add_widget(study_screen)
        sm.current = study_screen.name
        sm.add_widget(self._monitor_screen)
        sm.add_widget(bed_screen)
        sm.add_widget(range_screen)
        sm.add_widget(param_screen)
        sm.add_widget(resolution_screen)

        # Стартуем с выбора study
        sm.current = study_screen.name
        self._start_screen_name = study_screen.name
        self._sm = sm
        sm.bind(current=self._on_viewer_screen_changed)

        root = BoxLayout(orientation="vertical", spacing=UI_TOPBAR_CONTENT_GAP, padding=UI_APP_SHELL_PADDING)
        root.add_widget(self._build_top_bar(stop_app))
        root.add_widget(sm)
        Clock.schedule_once(lambda _dt: self._on_viewer_screen_changed(sm, None), 0)
        return root

    def on_start(self):
        # Защитно фиксируем стартовый экран после инициализации всех виджетов.
        def _force_start(_dt):
            try:
                if self._sm and self._start_screen_name and self._sm.has_screen(self._start_screen_name):
                    self._sm.current = self._start_screen_name
            except Exception:
                pass

        Clock.schedule_once(_force_start, 0)
        Clock.schedule_once(_force_start, 0.1)
        try:
            Window.bind(on_keyboard=self._on_viewer_keyboard)
        except Exception:
            pass

    def _on_viewer_keyboard(self, window, key, _scancode, _codepoint, _modifiers):
        try:
            if int(key) != 27:
                return False
        except Exception:
            return False
        if has_open_modal_or_dropdown(window):
            return False
        if not self._sm:
            return False
        current = self._sm.current
        if current == "viewer_monitor":
            self._nav_to_study_selection()
            return True
        return False

    def on_stop(self):
        if self._shutdown_complete:
            return
        self._shutdown_complete = True
        try:
            Window.unbind(on_keyboard=self._on_viewer_keyboard)
        except Exception:
            pass
        if self._monitor_screen is not None:
            self._monitor_screen.on_stop()
        SharedDatabasePool().close_all()

    def _build_top_bar(self, on_close):
        use_native = sys.platform == "win32"
        show_custom_window_controls = sys.platform in ("win32", "linux")
        self._title_bar = CustomTitleBar(
            title="",
            on_back=self._open_bed_selection,
            back_label="Выбор кровати",
            back_width=160,
            show_window_controls=show_custom_window_controls,
            on_close=on_close,
            register_native_frame=use_native,
        )
        return self._title_bar

    def _open_bed_selection(self):
        if self._sm and self._sm.has_screen("viewer_bed_selection"):
            self._sm.current = "viewer_bed_selection"

    def _nav_to_study_selection(self):
        if self._sm and self._sm.has_screen("viewer_study_selection"):
            self._sm.current = "viewer_study_selection"

    def _nav_to_bed_selection(self):
        if self._sm and self._sm.has_screen("viewer_bed_selection"):
            self._sm.current = "viewer_bed_selection"

    def _nav_to_current_previous_screen(self):
        if not self._sm:
            return
        try:
            current_screen = self._sm.current_screen
        except Exception:
            current_screen = None
        if current_screen is None:
            return
        target = getattr(current_screen, "previous_screen", None)
        if target and self._sm.has_screen(target):
            self._sm.current = target

    def _on_viewer_screen_changed(self, sm, _value):
        """Навигация слева в шапке; заголовок по шагу; тулбар просмотрщика только на графиках."""
        if self._title_bar is None:
            return
        try:
            cur = sm.current
            self._title_bar.set_title("")

            if cur == "viewer_study_selection":
                self._title_bar.set_back_nav(text="Назад", visible=False)
            elif cur == "viewer_bed_selection":
                self._title_bar.set_back_nav(
                    text="Назад",
                    visible=True,
                    callback=self._nav_to_study_selection,
                    width=dp(118),
                )
            elif cur == "viewer_date_time_range":
                self._title_bar.set_back_nav(
                    text="Назад",
                    visible=True,
                    callback=self._nav_to_bed_selection,
                    width=dp(118),
                )
            elif cur == "viewer_monitor":
                self._title_bar.set_back_nav(
                    text="К исследованиям",
                    visible=True,
                    callback=self._nav_to_study_selection,
                    width=dp(150),
                )
            else:
                self._title_bar.set_back_nav(text="Назад", visible=False)
        except Exception:
            pass


if __name__ == "__main__":
    BedViewerApp().run()

