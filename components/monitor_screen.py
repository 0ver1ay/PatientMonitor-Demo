"""
Главный экран монитора пациента с 4 графиками
"""
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.graphics.stencil_instructions import (
    StencilPush as _StencilPush,
    StencilPop as _StencilPop,
    StencilUse as _StencilUse,
    StencilUnUse as _StencilUnUse,
)
from kivy.graphics import Rectangle as _StencilRect
from kivy.clock import Clock
from kivy.clock import mainthread
from kivy.metrics import dp
from kivy.core.window import Window
from datetime import datetime, timedelta
from bisect import bisect_left, bisect_right
import threading
import time
from pathlib import Path
from components.graph_widget import GraphWidget
from components.camera_widget import CameraWidget
from components.value_display_widget import ValueDisplayWidget
from components.bed_selection_screen import BedSelectionScreen
from components.parameter_selection_screen import ParameterSelectionScreen
from components.time_range_selection_screen import TimeRangeSelectionScreen
from components.date_time_range_selection_screen import DateTimeRangeSelectionScreen
from components.dashboard_grid_layout import DashboardGridLayout
from components.dashboard_grid_editor_screen import DashboardGridEditorScreen
from components.esc_back_navigation import has_open_modal_or_dropdown
from utils.signal_registry import (
    get_display_range,
    get_signal_meta,
    get_display_range_by_signal_id,
    get_signal_meta_by_signal_id,
)
from components.study_selection_screen import StudySelectionScreen
from components.app_menu_bar import AppMenuBar
from utils.time_range import TimeRange
from utils.data_source import DataSource
from utils.data_storage import DataStorage
from utils.config_loader import ConfigLoader
from utils.data_source_factory import (
    DataSourceCreationResult,
    create_configured_data_source,
    database_retry_delay,
)
from utils.database_source import DatabaseDataSource
from utils.history_load_controller import (
    HistoryLoadController,
    HistoryLoadKey,
    split_signal_rows,
)
from utils.layout_config import LayoutConfig
from utils.popup_style import apply_popup_theme, style_popup_label_body, style_scrollview_popup
from utils.ui_style import (
    UI_BTN_DANGER,
    UI_BTN_MUTED,
    UI_BTN_SECONDARY,
    UI_BTN_SUCCESS,
    UI_TOPBAR_CONTENT_GAP,
    UI_BTN_WARNING,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    UI_TEXT_STRONG,
    apply_rounded_button,
    apply_rounded_panel,
    attach_gear_icon,
)

MONITOR_BACKGROUND_RGBA = (0.10, 0.10, 0.10, 1.0)


def _apply_stencil_clip(widget) -> None:
    """Добавляет жесткий stencil-клиппинг по границам widget,
    чтобы дочерний контент не вылезал за пределы контейнера.
    Безопасно вызывать после apply_rounded_panel: мы добавляем инструкции в самый конец
    canvas.before и в самое начало canvas.after.
    """
    from kivy.graphics import Color as _StencilColor

    rect_before = _StencilRect(pos=widget.pos, size=widget.size)
    rect_after = _StencilRect(pos=widget.pos, size=widget.size)
    canvas_before = widget.canvas.before
    canvas_after = widget.canvas.after
    canvas_before.add(_StencilPush())
    canvas_before.add(rect_before)
    canvas_before.add(_StencilUse())
    canvas_after.add(_StencilUnUse())
    canvas_after.add(rect_after)
    canvas_after.add(_StencilPop())

    def _sync(*_args):
        rect_before.pos = widget.pos
        rect_before.size = widget.size
        rect_after.pos = widget.pos
        rect_after.size = widget.size

    widget.bind(pos=_sync, size=_sync)


class MonitorScreen(Screen):
    """Главный экран монитора пациента"""
    
    def __init__(
        self,
        layout_config_id: str = None,
        monitor_index: int = 0,
        monitor_config: dict = None,
        viewer_mode: bool = False,
        auto_start: bool = True,
        history_range: tuple[datetime, datetime] | None = None,
        **kwargs,
    ):
        self.external_status_bar = bool(kwargs.pop("external_status_bar", False))
        self.show_menu_bar = bool(kwargs.pop("show_menu_bar", True))
        self.viewer_toolbar_in_titlebar = bool(kwargs.pop("viewer_toolbar_in_titlebar", False))
        self.grid_tile_layout = bool(kwargs.pop("grid_tile_layout", False))
        self.align_content_to_host_titlebar = bool(kwargs.pop("align_content_to_host_titlebar", False))
        super().__init__(**kwargs)
        # ВАЖНО: не перетираем name, если его передали при создании
        if not getattr(self, "name", None):
            self.name = "monitor"
        # Если MonitorScreen встроен внутрь другого Screen как обычный виджет,
        # навигация должна возвращать не на его внутреннее имя, а на host-screen.
        self.navigation_screen_name: str | None = None
        
        # Параметры конфигурации раскладки
        self.layout_config_id = layout_config_id
        self.monitor_index = monitor_index
        self.monitor_config = monitor_config or {}

        # Режим "просмотрщик" (история по абсолютному диапазону)
        self.viewer_mode = viewer_mode
        self.auto_start = auto_start
        self.current_study: dict | None = None
        self.history_start: datetime | None = None
        self.history_end: datetime | None = None
        if history_range:
            self.history_start, self.history_end = history_range

        # Hover (viewer_mode): синхронизация тултипов между 2 графиками
        self._hover_bound = False
        self._hover_suspend_until_leave = False
        self._hover_suspend_base_pos = None
        self._last_mouse_pos = None

        # Пациент (viewer_mode): ФИО + timeline на период
        self._patient_name_cache: dict[int, str] = {}
        self._patient_timeline: list[dict] = []  # [{begin_dt,end_dt,patient_id,name}]
        self._patient_starts: list[datetime] = []
        self._patient_multi: bool = False
        self._last_patient_id: int | None = None

        # Viewer zoom/pan: полное окно (выбранный период) и окно просмотра
        self._full_start: datetime | None = self.history_start
        self._full_end: datetime | None = self.history_end
        self._view_start: datetime | None = self.history_start
        self._view_end: datetime | None = self.history_end
        self._viewer_playback_state = 0  # -1 назад, 0 пауза, 1 вперед
        self._viewer_playback_speed = 1
        self._viewer_playback_event = None
        self._viewer_playback_base_rate = 1.0
        self._graph_pan_active = False
        self._graph_pan_touch_uid = None
        self._graph_pan_owner = None
        self._graph_pan_start_x = 0.0
        self._graph_pan_start_view_start: datetime | None = None
        self._graph_pan_start_view_end: datetime | None = None
        self._graph_pan_moved = False
        self._viewer_primary_block_mirror_bound = False
        
        # Основной контейнер для содержимого экрана
        side_pad = dp(0) if (self.align_content_to_host_titlebar and not self.show_menu_bar) else dp(10)
        self.main_container = BoxLayout(
            orientation='vertical',
            spacing=dp(0) if not self.show_menu_bar else dp(10),
            padding=(side_pad, UI_TOPBAR_CONTENT_GAP, side_pad, dp(10)) if not self.show_menu_bar else dp(10)
        )
        self.add_widget(self.main_container)
        
        # Загрузка конфигурации
        self.config = ConfigLoader()

        # Состояние соединения отделено от типа источника: в production
        # недоступная БД никогда не подменяется синтетическими данными.
        self._db_state = "connecting"
        self._db_error: str | None = None
        self._db_retry_attempt = 0
        self._db_retry_event = None
        self._db_reconnect_in_progress = False
        self._stopped = False
        self._history_controller = HistoryLoadController()
        self._history_reload_trigger = Clock.create_trigger(self._run_async_history_reload, 0.15)
        self._pending_history_key: HistoryLoadKey | None = None
        
        # Источник данных (выбирается на основе конфига)
        self.data_source: DataSource = self._create_data_source()
        
        # Хранилище данных
        self.data_storage = DataStorage()
        
        # Текущий временной диапазон (загружаем из конфигурации или используем по умолчанию)
        time_range_str = self.monitor_config.get('time_range', 'MIN_5')
        try:
            self.current_time_range = TimeRange[time_range_str]
        except (KeyError, AttributeError):
            self.current_time_range = TimeRange.get_default()

        # Разрешение графиков (агрегация по времени) — особенно важно в viewer_mode
        resolution_str = self.monitor_config.get("resolution", "MIN_1")
        try:
            self.current_resolution = TimeRange[resolution_str]
        except Exception:
            self.current_resolution = TimeRange.MIN_1
        self._viewer_resolution_seconds = int(getattr(self.current_resolution, "seconds", 60) or 60)
        self._viewer_auto_periods = self.config.get_viewer_auto_periods()
        # В viewer_mode используем авто-разрешение от длины периода
        self._auto_set_resolution_from_history_range()

        # Runtime state, который может понадобиться уже внутри _create_ui()
        self.data_update_event = None
        self.graph_update_event = None
        self.camera_update_event = None
        self._data_thread = None
        self._stop_event = threading.Event()
        self._slots_lock = threading.Lock()
        self._camera_fetch_in_progress = False
        self._last_camera_frame_ts: datetime | None = None
        self._patient_info_cache: dict | None = None
        self._viewer_image_timestamps: list[datetime] = []
        self._viewer_image_bytes_by_ts: dict[datetime, bytes] = {}
        self._viewer_image_current_ts: datetime | None = None
        # Кэш исторических точек для value-слотов, чьи сигналы не отображаются
        # на графиках (нужен для индикаторов в правой колонке viewer-режима).
        self._viewer_value_history: dict[str, list[tuple[float, datetime]]] = {}

        # Слоты отображения (2 графика + набор цифровых значений)
        self.slot_signal_ids = {}
        self._slot_meta_cache = {}
        self._colors_palette = ['#FF4444', '#44FF44', '#4444FF', '#FFFF44', '#FF44FF', '#44FFFF']
        self._value_grid_cols = 2
        self._init_default_slots()
        self.graph_settings = self._load_graph_settings_from_config()
        self.dashboard_grid_config = self._load_dashboard_grid_config()
        self._dashboard_grid_edit_mode = False
        self._dashboard_edit_esc_bound = False

        # Папка экспорта (по умолчанию exports/ в корне проекта)
        self.export_dir = Path(__file__).parent.parent / "exports"
        
        # Создание UI
        self._create_ui()
        Clock.schedule_once(lambda _dt: self._sync_connection_ui(), 0)
        self.bind(size=self._update_responsive_layout)
        Clock.schedule_once(lambda _dt: self._update_responsive_layout(), 0)

        # Если viewer_mode уже получил history_range через __init__, применим абсолютное окно времени к графикам
        if self.viewer_mode and self.history_start and self.history_end:
            for g in getattr(self, "graph_slots", {}).values():
                try:
                    g.set_absolute_time_window(self.history_start, self.history_end)
                except Exception:
                    pass
            self._update_viewer_playback_base_rate()
        
        # Загружаем конфигурацию после создания UI
        self._load_monitor_config()
        
        # Ленивая загрузка исторических данных - загрузим при первом обновлении
        self._historical_data_loaded = False

        # Запуск обновления данных (если нужно)
        if self.auto_start and not self.viewer_mode:
            self.start_updates()

        # (инициализация hover/patient/zoom выполняется до _create_ui)

    def start_updates(self):
        """Запустить периодическое обновление данных/графиков."""
        # Историю грузим один раз; флаг выставляется только после успешного apply.
        if self._is_live_presentation_allowed() and not self._historical_data_loaded:
            Clock.schedule_once(lambda dt: self._schedule_history_reload(), 0.3)

        # Для БД — НЕ дергаем _update_data в UI потоке (он тяжелый), вместо этого поток на монитор.
        if isinstance(self.data_source, DatabaseDataSource):
            if self._data_thread is None or not self._data_thread.is_alive():
                self._stop_event.clear()
                self._data_thread = threading.Thread(target=self._data_worker_loop, daemon=True)
                self._data_thread.start()
        else:
            # Demo mode можно оставлять таймером
            if self.data_update_event is None:
                self.data_update_event = Clock.schedule_interval(self._update_data, 1.0)
        if self.graph_update_event is None:
            # Было слишком часто; при нескольких мониторах превращается в лаги.
            self.graph_update_event = Clock.schedule_interval(self._update_graphs, 0.25)

    def _start_camera_updates(self) -> None:
        if not self._is_database_online():
            return
        if self.camera_update_event is None:
            self.camera_update_event = Clock.schedule_interval(self._schedule_camera_frame_fetch, 1.0)
        self._schedule_camera_frame_fetch(0)

    def _schedule_camera_frame_fetch(self, _dt) -> None:
        if self._camera_fetch_in_progress or self._stop_event.is_set():
            return
        if not self._is_database_online():
            return
        bed_id = self.data_source.get_current_bed_id()
        if bed_id is None:
            self._apply_db_camera_frame(None)
            return

        self._camera_fetch_in_progress = True
        threading.Thread(
            target=self._fetch_latest_camera_frame,
            args=(int(bed_id),),
            daemon=True,
        ).start()

    def _fetch_latest_camera_frame(self, bed_id: int) -> None:
        frame = None
        try:
            if self._is_database_online():
                frame = self.data_source.get_latest_image_frame(bed_id)
        except Exception as e:
            print(f"[MonitorScreen] camera fetch error: {e}")
        finally:
            self._camera_fetch_in_progress = False
        self._apply_db_camera_frame(frame)

    @mainthread
    def _apply_db_camera_frame(self, frame: dict | None) -> None:
        if not hasattr(self, "camera_widget"):
            return
        if not frame:
            self._last_camera_frame_ts = None
            self.camera_widget.set_image_bytes(None)
            return

        frame_ts = frame.get("ts")
        image_bytes = frame.get("image_bytes")
        if frame_ts is not None and self._last_camera_frame_ts == frame_ts:
            return
        self._last_camera_frame_ts = frame_ts
        self.camera_widget.set_image_bytes(image_bytes)

    def _get_viewer_image_default_time(self) -> datetime | None:
        if self._view_start and self._view_end:
            try:
                return self._view_start + (self._view_end - self._view_start) / 2
            except Exception:
                pass
        if self.history_start and self.history_end:
            try:
                return self.history_start + (self.history_end - self.history_start) / 2
            except Exception:
                return self.history_start
        return self.history_start

    def _show_viewer_no_image_placeholder(self, message: str = "Нет изображений за исследование") -> None:
        self._last_camera_frame_ts = None
        if not hasattr(self, "camera_widget"):
            return
        try:
            self.camera_widget.show_placeholder(message)
        except Exception:
            self.camera_widget.set_image_bytes(None)

    def _reload_viewer_images_for_history(self) -> None:
        self._viewer_image_timestamps = []
        self._viewer_image_bytes_by_ts = {}
        self._viewer_image_current_ts = None

        if not self.viewer_mode:
            return
        if not self._is_database_online():
            self._apply_db_camera_frame(None)
            return
        if not (self.history_start and self.history_end):
            self._apply_db_camera_frame(None)
            return

        bed_id = self.data_source.get_current_bed_id()
        if bed_id is None:
            self._apply_db_camera_frame(None)
            return

        try:
            frames = self.data_source.get_image_frames_between(
                int(bed_id),
                self.history_start,
                self.history_end,
            )
        except Exception as e:
            print(f"[MonitorScreen] viewer images load error: {e}")
            frames = []

        for frame in frames or []:
            ts = frame.get("ts")
            image_bytes = frame.get("image_bytes")
            if ts is None or not image_bytes:
                continue
            self._viewer_image_timestamps.append(ts)
            self._viewer_image_bytes_by_ts[ts] = bytes(image_bytes)

        self._viewer_image_timestamps.sort()

        if not self._viewer_image_timestamps:
            self._show_viewer_no_image_placeholder()
            return

        self._update_viewer_image_for_time(self._get_viewer_image_default_time())

    def _find_nearest_viewer_image_timestamp(self, target_time: datetime | None) -> datetime | None:
        if target_time is None or not self._viewer_image_timestamps:
            return None
        if getattr(target_time, "tzinfo", None) is not None:
            target_time = target_time.replace(tzinfo=None)

        timestamps = self._viewer_image_timestamps
        idx = bisect_left(timestamps, target_time)
        if idx <= 0:
            return timestamps[0]
        if idx >= len(timestamps):
            return timestamps[-1]

        prev_ts = timestamps[idx - 1]
        next_ts = timestamps[idx]
        if (target_time - prev_ts) <= (next_ts - target_time):
            return prev_ts
        return next_ts

    def _update_viewer_image_for_time(self, target_time: datetime | None) -> None:
        if not self.viewer_mode:
            return

        nearest_ts = self._find_nearest_viewer_image_timestamp(target_time)
        if nearest_ts is None:
            if self._viewer_image_current_ts is not None:
                self._viewer_image_current_ts = None
                self._show_viewer_no_image_placeholder()
            return

        if nearest_ts == self._viewer_image_current_ts:
            return

        image_bytes = self._viewer_image_bytes_by_ts.get(nearest_ts)
        if not image_bytes:
            return

        self._viewer_image_current_ts = nearest_ts
        self._apply_db_camera_frame({"ts": nearest_ts, "image_bytes": image_bytes})

    def _get_slot_signal_ids_snapshot(self):
        with self._slots_lock:
            return dict(self.slot_signal_ids)

    def _data_worker_loop(self):
        """Фоновый поток: раз в секунду батчем забирает значения и пушит в UI."""
        next_health_check = 0.0
        while not self._stop_event.is_set():
            t0 = time.monotonic()

            try:
                if not self._is_database_online():
                    time.sleep(0.5)
                    continue
                if t0 >= next_health_check:
                    next_health_check = t0 + 10.0
                    if not self.data_source.is_available():
                        self._enter_offline_state("Связь с PostgreSQL потеряна")
                        continue
                bed_id = self.data_source.get_current_bed_id() if isinstance(self.data_source, DatabaseDataSource) else None
                if bed_id is None:
                    time.sleep(0.5)
                    continue

                slots = self._get_slot_signal_ids_snapshot()
                # Берем только реальные signal_id
                wanted = []
                for k in list(getattr(self, "graph_slots", {}).keys()) + list(getattr(self, "value_slots", {}).keys()):
                    sid = slots.get(k)
                    if sid is None:
                        continue
                    try:
                        wanted.append(int(sid))
                    except Exception:
                        continue
                # Уникальные
                wanted = sorted(set(wanted))
                if not wanted:
                    time.sleep(0.5)
                    continue

                values = self.data_source.get_latest_values(int(bed_id), wanted)
                ts = datetime.now()
                self._apply_live_values(values, ts)
            except Exception as e:
                print(f"[MonitorScreen] data worker error: {e}")
                self._enter_offline_state(str(e))

            # держим период ~1 сек
            dt = time.monotonic() - t0
            sleep_for = max(0.05, 1.0 - dt)
            time.sleep(sleep_for)

    @mainthread
    def _apply_live_values(self, values_by_signal_id: dict, ts: datetime):
        """UI-поток: применить полученные значения к цифровым блокам и графикам."""
        if not self._is_database_online():
            return
        # Цифры
        for slot_id, widget in self.value_slots.items():
            sid = self.slot_signal_ids.get(slot_id)
            if sid is None:
                continue
            val = values_by_signal_id.get(int(sid))
            if val is not None:
                widget.set_value(val)

        # Графики (точки + антидубликаты)
        if not hasattr(self, "_last_added_values"):
            self._last_added_values = {}
        for slot_id, graph in self.graph_slots.items():
            sid = self.slot_signal_ids.get(slot_id)
            if sid is None:
                continue
            val = values_by_signal_id.get(int(sid))
            if val is None:
                continue
            last = self._last_added_values.get(slot_id)
            if last is None or abs(last - val) > 0.0001:
                graph.add_data_point(float(val), ts)
                self._last_added_values[slot_id] = float(val)

    def set_history_range(self, start_dt: datetime, end_dt: datetime):
        """Установить абсолютный диапазон истории (для viewer)."""
        self.history_start = start_dt
        self.history_end = end_dt
        # Полное окно и окно просмотра (по умолчанию = полный период)
        self._full_start, self._full_end = start_dt, end_dt
        self._view_start, self._view_end = start_dt, end_dt
        self._apply_view_window_to_graphs()
        # Авто-разрешение по длине периода (viewer_mode)
        self._auto_set_resolution_from_history_range()
        # Обновляем подпись на кнопке (если UI уже создан)
        if hasattr(self, "time_range_button"):
            self.time_range_button.text = self._format_absolute_range()
        # Обновим ФИО/таймлайн пациента под новый период
        self._refresh_patient_context()
        self._update_viewer_playback_base_rate()

    def _update_viewer_playback_base_rate(self) -> None:
        """При x1 скорость play: сколько секунд временной оси проходим за 1 с wall time.

        База привязана к длине **выбранного** абсолютного диапазона (`_full_start`…`_full_end`):
        чем период длиннее, тем выше base_rate, чтобы пройти его за разумное время
        при воспроизведении. Множители x2/x4/x8 накладываются поверх.
        """
        if not getattr(self, "viewer_mode", False):
            self._viewer_playback_base_rate = 1.0
            return
        if not (self._full_start and self._full_end):
            self._viewer_playback_base_rate = 1.0
            return
        try:
            full_span = float((self._full_end - self._full_start).total_seconds())
        except Exception:
            self._viewer_playback_base_rate = 1.0
            return
        full_span = max(1.0, full_span)
        # За это число секунд реального времени при x1 условно проезжаем весь выбранный период.
        ref_wall_sec = 90.0
        self._viewer_playback_base_rate = full_span / ref_wall_sec

    def on_pre_enter(self, *args):
        super().on_pre_enter(*args)
        # Hover для live multi-monitor и viewer. Координаты — только через to_widget,
        # иначе одинаковые плитки раскладки срабатывают на один Window.mouse_pos.
        self._bind_hover()
        if self.viewer_mode:
            try:
                Clock.schedule_once(lambda _dt: self._refresh_hover_now(), 0.05)
                Clock.schedule_once(lambda _dt: self._refresh_hover_now(), 0.25)
            except Exception:
                pass

    def on_pre_leave(self, *args):
        if getattr(self, "_dashboard_grid_edit_mode", False):
            self._finish_dashboard_grid_editing()
        self._unbind_dashboard_edit_escape()
        self._clear_dashboard_grid_hover()
        self._unbind_hover()
        if self.viewer_mode:
            self._set_viewer_playback_state(0)
        super().on_pre_leave(*args)

    @staticmethod
    def _window_pos_hits(widget, window_pos) -> bool:
        """Проверить попадание Window.mouse_pos в виджет в локальных координатах."""
        if widget is None or window_pos is None:
            return False
        try:
            local = widget.to_widget(float(window_pos[0]), float(window_pos[1]), relative=False)
            return bool(widget.collide_point(*local))
        except Exception:
            return False

    def _clear_all_graph_hovers(self) -> None:
        for g in getattr(self, "graph_slots", {}).values():
            try:
                g.clear_hover()
            except Exception:
                pass

    def _bind_hover(self):
        if self._hover_bound:
            return
        try:
            Window.bind(mouse_pos=self._on_mouse_pos)
            self._hover_bound = True
            try:
                Clock.schedule_once(lambda _dt: self._refresh_hover_now(), 0.02)
            except Exception:
                pass
        except Exception:
            self._hover_bound = False

    def _refresh_hover_now(self):
        """Принудительно обновить hover по текущей позиции курсора."""
        if not self._hover_bound:
            return
        try:
            pos = getattr(Window, "mouse_pos", None) or self._last_mouse_pos
            if not pos:
                return
            self._on_mouse_pos(Window, pos)
        except Exception:
            pass

    def _unbind_hover(self):
        if not self._hover_bound:
            return
        try:
            Window.unbind(mouse_pos=self._on_mouse_pos)
        except Exception:
            pass
        self._hover_bound = False
        self._clear_all_graph_hovers()

    def _on_mouse_pos(self, _window, pos):
        """Hover: один курсор только на мониторе под мышью."""
        if self._graph_pan_active:
            return
        graphs = getattr(self, "graph_slots", {}) or {}
        try:
            self._last_mouse_pos = (float(pos[0]), float(pos[1]))
        except Exception:
            self._last_mouse_pos = None

        if self.manager is not None:
            try:
                if self.manager.current != self._get_navigation_screen_name():
                    self._clear_all_graph_hovers()
                    return
            except Exception:
                pass

        # Без to_widget все плитки с одинаковой локальной геометрией «видят» мышь сразу.
        if not self._window_pos_hits(self, pos):
            self._clear_all_graph_hovers()
            return

        if not graphs:
            return

        if self._hover_suspend_until_leave:
            over_any = False
            for g in graphs.values():
                try:
                    target = getattr(g, "graph_container", None) or g
                    if self._window_pos_hits(target, pos):
                        over_any = True
                        break
                except Exception:
                    continue
            if over_any:
                bp = self._hover_suspend_base_pos
                try:
                    if bp is None:
                        self._hover_suspend_until_leave = False
                    else:
                        dx = float(pos[0]) - float(bp[0])
                        dy = float(pos[1]) - float(bp[1])
                        if (dx * dx + dy * dy) >= float(dp(6)) ** 2:
                            self._hover_suspend_until_leave = False
                except Exception:
                    self._hover_suspend_until_leave = False
                if self._hover_suspend_until_leave:
                    return
            else:
                self._hover_suspend_until_leave = False

        hovered_graph = None
        for _slot_id, g in graphs.items():
            try:
                if self._window_pos_hits(g, pos) or self._window_pos_hits(
                    getattr(g, "graph_container", None),
                    pos,
                ):
                    hovered_graph = g
                    break
            except Exception as e:
                print(f"[HOVER-DBG] collide error: {e}")
                continue

        if hovered_graph is None:
            self._clear_all_graph_hovers()
            return

        try:
            # plot_area / x_to_time живут в координатах GraphWidget, не окна.
            local_x, local_y = hovered_graph.to_widget(float(pos[0]), float(pos[1]), relative=False)
        except Exception:
            local_x, local_y = float(pos[0]), float(pos[1])

        try:
            t = hovered_graph.x_to_time(float(local_x))
        except Exception:
            t = None

        if t is None:
            self._clear_all_graph_hovers()
            return

        if self.viewer_mode:
            try:
                self._update_patient_label_for_time(t)
            except Exception:
                pass
            try:
                self._update_viewer_image_for_time(t)
            except Exception:
                pass

        # Собираем значения с отрисованных серий и делаем 1 тултип на активном графике
        hover_rows = []
        # Время индикатора всегда должно соответствовать X-координате курсора,
        # а не "прилипать" к ближайшей точке данных.
        hovered_ts = t
        shared_prefer_upper = None

        # Выбор верхней/нижней границы определяем один раз на активном графике
        # и затем применяем ко всем графикам, чтобы не приходилось двигать мышь
        # отдельно над каждым графиком.
        try:
            hovered_in_window = True
            if hasattr(hovered_graph, "has_time_in_display_window"):
                hovered_in_window = bool(hovered_graph.has_time_in_display_window(t))
            hovered_p = (
                hovered_graph.nearest_point(t, mouse_y=local_y) if hovered_in_window else None
            )
            if hovered_p:
                hovered_idx = hovered_p[0]
                bucket_ranges = getattr(hovered_graph, "_display_bucket_ranges", None) or []
                if 0 <= hovered_idx < len(bucket_ranges):
                    rng = bucket_ranges[hovered_idx]
                    if rng is not None:
                        lo, hi = float(rng[0]), float(rng[1])
                        if lo != hi:
                            hovered_val = float(hovered_p[2])
                            shared_prefer_upper = abs(hovered_val - hi) <= abs(hovered_val - lo)
        except Exception:
            shared_prefer_upper = None

        for g in graphs.values():
            in_window = True
            try:
                if hasattr(g, "has_time_in_display_window"):
                    in_window = bool(g.has_time_in_display_window(t))
            except Exception:
                in_window = True

            try:
                mouse_y = local_y if ((g is hovered_graph) and shared_prefer_upper is None) else None
                p = g.nearest_point(t, mouse_y=mouse_y, prefer_upper=shared_prefer_upper) if in_window else None
            except Exception:
                p = None
            title = getattr(getattr(g, "title_label", None), "text", None) or getattr(g, "title", "")
            if not p:
                hover_rows.append(f"{title}: нет данных")
                continue
            _idx, ts, val, _x, _y = p
            try:
                vtxt = g.format_value(val)
            except Exception:
                vtxt = str(val)
            unit = getattr(g, "unit", "") or ""
            if unit:
                vtxt = f"{vtxt} {unit}"
            hover_rows.append(f"{title}: {vtxt}")

        # Формат времени берем по правилам активного графика
        try:
            time_txt = hovered_graph._format_tooltip_time(hovered_ts)  # внутренний helper, но стабильнее единообразно
        except Exception:
            time_txt = hovered_ts.strftime("%d.%m.%Y %H:%M:%S")

        tooltip_text = "\n".join([time_txt] + hover_rows) if hover_rows else time_txt
        try:
            local_anchor = hovered_graph.to_widget(float(pos[0]), float(pos[1]), relative=False)
        except Exception:
            local_anchor = pos

        for g in graphs.values():
            try:
                g.set_hover_time(
                    t,
                    show_tooltip=(g is hovered_graph),
                    anchor_pos=local_anchor if g is hovered_graph else None,
                    tooltip_text=tooltip_text if g is hovered_graph else None,
                    prefer_upper=shared_prefer_upper,
                )
            except Exception:
                try:
                    g.clear_hover()
                except Exception:
                    pass

        # Синхронизируем 4 индикатора в правой колонке viewer-режима со временем
        # курсора: для value-слотов с графиком берём ближайшую точку графика, для
        # остальных — точку из предзагруженного кэша истории.
        if not self.viewer_mode:
            return
        for slot_id, widget in getattr(self, "value_slots", {}).items():
            try:
                val = self._viewer_value_at_time(slot_id, t)
                widget.set_value(val if val is not None else None)
            except Exception:
                pass
    def _set_bed_button_text(self, bed_name: str | None = None, bed_id: int | None = None):
        """Единая точка для текста кнопки кровати."""
        if bed_name:
            txt = str(bed_name)
        elif bed_id is not None:
            txt = f"Кровать {bed_id}"
        else:
            txt = "Кровать…"
        if self.grid_tile_layout and not self.viewer_mode:
            txt = txt.replace("Койко-место", "Койка").replace("Кровать", "Койка")
        self._current_bed_display_text = txt
        if hasattr(self, "patient_info_panel"):
            try:
                self._apply_patient_info_to_panel(getattr(self, "_patient_info_cache", None) or {})
            except Exception:
                pass
        if not hasattr(self, "bed_button") or self.bed_button is None:
            return
        self.bed_button.text = txt

    def _set_study_button_text(self, study: dict | None):
        """Единая точка для текста кнопки исследования (viewer UI)."""
        if not hasattr(self, "study_button"):
            return
        if not study:
            self.study_button.text = "Выбрать исследование"
            return
        sid = study.get("study_id") or study.get("id")
        numb = study.get("study_numb")
        if sid is None:
            self.study_button.text = "Выбрать исследование"
            return
        try:
            sid_txt = f"№{int(sid)}"
        except Exception:
            sid_txt = f"№{sid}"
        self.study_button.text = f"{sid_txt} · {numb}".rstrip() if numb else f"Исследование {sid_txt}"

    def _auto_set_resolution_from_history_range(self):
        """
        Авто-разрешение графиков по длине выбранного периода.
        """
        if not self.viewer_mode or not (self.history_start and self.history_end):
            return
        try:
            # Если пользователь приблизил график, авто-разрешение считаем по окну просмотра,
            # чтобы можно было "подробно смотреть точки".
            view_start = getattr(self, "_view_start", None)
            view_end = getattr(self, "_view_end", None)
            if view_start and view_end and view_end > view_start:
                seconds = max(0, int((view_end - view_start).total_seconds()))
            else:
                seconds = max(0, int((self.history_end - self.history_start).total_seconds()))
        except Exception:
            return

        self._refresh_viewer_auto_periods()
        chosen_seconds = self._get_auto_resolution_seconds_for_span(seconds)
        self._viewer_resolution_seconds = chosen_seconds
        for g in getattr(self, "graph_slots", {}).values():
            g.set_resolution_seconds(chosen_seconds)
            try:
                g.update_graph()
            except Exception:
                pass

    def _refresh_viewer_auto_periods(self):
        """Подхватить изменения VIEWER_AUTO_PERIODS из config.ini без перезапуска."""
        try:
            self.config.reload_if_changed()
            self._viewer_auto_periods = self.config.get_viewer_auto_periods()
        except Exception:
            pass

    def _get_auto_resolution_seconds_for_span(self, span_seconds: int) -> int:
        """
        Точное соответствие окна просмотра и шага агрегации.

        Для каждого масштаба шаг свой, чтобы соседние масштабы не выглядели одинаково:
        1 мин  -> 5 сек
        5 мин  -> 10 сек
        15 мин -> 30 сек
        30 мин -> 1 мин
        1 час  -> 2 мин
        2 часа -> 5 мин
        4 часа -> 10 мин
        1 день -> 30 мин
        >1 дня -> 60 мин
        """
        periods = getattr(self, "_viewer_auto_periods", None) or {}
        s = max(1, int(span_seconds))
        if s <= 1 * 60:
            return int(periods.get("range_1m", 5))
        if s <= 5 * 60:
            return int(periods.get("range_5m", 10))
        if s <= 15 * 60:
            return int(periods.get("range_15m", 30))
        if s <= 30 * 60:
            return int(periods.get("range_30m", 60))
        if s <= 60 * 60:
            return int(periods.get("range_1h", 120))
        if s <= 2 * 60 * 60:
            return int(periods.get("range_2h", 300))
        if s <= 4 * 60 * 60:
            return int(periods.get("range_4h", 600))
        if s <= 24 * 60 * 60:
            return int(periods.get("range_1d", 1800))
        return int(periods.get("range_over_1d", 3600))

    def _get_resolution_seconds_for_graphs(self) -> int | None:
        """Текущий шаг агрегации для графиков."""
        if self.viewer_mode:
            return int(getattr(self, "_viewer_resolution_seconds", 60) or 60)
        try:
            minutes = int(getattr(getattr(self, "current_time_range", None), "minutes", 5) or 5)
        except Exception:
            minutes = 5
        if minutes <= 5:
            return 1
        if minutes <= 10:
            return 2
        if minutes <= 30:
            return 5
        if minutes <= 60:
            return 10
        if minutes <= 360:
            return 30
        return 60

    def reload_historical_data(self):
        """Перезагрузить исторические данные (очистка + фоновая загрузка)."""
        if isinstance(self.data_source, DatabaseDataSource) and not self._is_database_online():
            for graph in getattr(self, "graph_slots", {}).values():
                graph.clear_data()
                graph.set_empty_message("БД недоступна")
            if self.viewer_mode and hasattr(self, "camera_widget"):
                self._show_viewer_no_image_placeholder("БД недоступна")
            return
        self._schedule_history_reload()

    def _schedule_history_reload(self) -> None:
        """Собрать last-wins запросы смены study/койки/периода."""
        self._auto_set_resolution_from_history_range()
        for graph in getattr(self, "graph_slots", {}).values():
            graph.clear_data()
            graph.set_empty_message("Загрузка…")
        self._historical_data_loaded = False
        self._viewer_value_history = {}
        if self.viewer_mode and hasattr(self, "camera_widget"):
            try:
                self.camera_widget.show_placeholder(
                    "Загрузка изображений…",
                    status_color=(0.70, 0.70, 0.72, 1),
                )
            except Exception:
                pass
        self._history_reload_trigger()

    def _collect_history_signal_ids(self) -> list[int]:
        signal_ids: list[int] = []
        for slot_id in list(self._graph_slot_ids()) + ["value1", "value2", "value3", "value4"]:
            sid = self.slot_signal_ids.get(slot_id)
            if sid is None:
                continue
            try:
                signal_ids.append(int(sid))
            except Exception:
                continue
        return sorted(set(signal_ids))

    def _run_async_history_reload(self, *_args) -> None:
        if self._stopped:
            return
        if not isinstance(self.data_source, DatabaseDataSource):
            self._load_historical_data()
            self._historical_data_loaded = True
            return
        if not self._is_database_online():
            return

        bed_id = self.data_source.get_current_bed_id()
        if bed_id is None:
            for graph in getattr(self, "graph_slots", {}).values():
                graph.set_empty_message("Выберите кровать")
            return

        if self.history_start and self.history_end:
            key = HistoryLoadKey.from_parts(
                int(bed_id),
                self.history_start,
                self.history_end,
                self._collect_history_signal_ids(),
            )
            self._pending_history_key = key
            generation, cancel_event = self._history_controller.begin_request()
            data_source = self.data_source

            def worker():
                try:
                    rows = self._history_controller.fetch_with_retry(
                        lambda: data_source.get_signal_values_between(
                            key.bed_id,
                            list(key.signal_ids),
                            key.start,
                            key.end,
                        ),
                        generation=generation,
                        cancel_event=cancel_event,
                    )
                    if cancel_event.is_set() or not self._history_controller.is_current(generation):
                        return
                    series = split_signal_rows(rows or [])
                    Clock.schedule_once(
                        lambda _dt, gen=generation, load_key=key, payload=series: self._apply_history_series(
                            gen,
                            load_key,
                            payload,
                        ),
                        0,
                    )
                    if self.viewer_mode:
                        frames = self._history_controller.fetch_with_retry(
                            lambda: data_source.get_image_frames_between(
                                key.bed_id,
                                key.start,
                                key.end,
                            ),
                            generation=generation,
                            cancel_event=cancel_event,
                        )
                        if cancel_event.is_set() or not self._history_controller.is_current(generation):
                            return
                        Clock.schedule_once(
                            lambda _dt, gen=generation, load_key=key, payload=frames: self._apply_history_images(
                                gen,
                                load_key,
                                payload or [],
                            ),
                            0,
                        )
                except Exception as exc:
                    if cancel_event.is_set() or not self._history_controller.is_current(generation):
                        return
                    Clock.schedule_once(
                        lambda _dt, gen=generation, err=str(exc): self._apply_history_error(gen, err),
                        0,
                    )

            self._history_controller.run_in_background(worker)
            return

        # Live backfill без absolute history_range — оставляем лёгкий sync path.
        self._load_historical_data()
        self._historical_data_loaded = True

    def _history_key_matches_current(self, key: HistoryLoadKey) -> bool:
        if self._pending_history_key is None:
            return False
        current_bed = None
        try:
            current_bed = self.data_source.get_current_bed_id()
        except Exception:
            current_bed = None
        if current_bed is None or int(current_bed) != int(key.bed_id):
            return False
        if not (self.history_start and self.history_end):
            return False
        return (
            self.history_start == key.start
            and self.history_end == key.end
            and self._pending_history_key == key
        )

    def _apply_history_series(
        self,
        generation: int,
        key: HistoryLoadKey,
        series_by_signal: dict[int, list[tuple[float, datetime]]],
    ) -> None:
        if self._stopped or not self._history_controller.is_current(generation):
            return
        if not self._history_key_matches_current(key):
            return

        graph_signal_ids: set[int] = set()
        for slot_id in self._graph_slot_ids():
            graph = self.graph_slots.get(slot_id)
            sid = self.slot_signal_ids.get(slot_id)
            if graph is None or sid is None:
                continue
            try:
                sid_i = int(sid)
            except Exception:
                continue
            graph_signal_ids.add(sid_i)
            points = series_by_signal.get(sid_i) or []
            if points:
                values, times = zip(*points)
                graph.load_historical_data(list(values), list(times))
                graph.set_empty_message("Нет данных")
            else:
                graph.clear_data()
                graph.set_empty_message("Нет данных")

        self._viewer_value_history = {}
        if self.viewer_mode:
            for slot_id in ("value1", "value2", "value3", "value4"):
                sid = self.slot_signal_ids.get(slot_id)
                if sid is None:
                    continue
                try:
                    sid_i = int(sid)
                except Exception:
                    continue
                if sid_i in graph_signal_ids:
                    continue
                self._viewer_value_history[slot_id] = list(series_by_signal.get(sid_i) or [])
            self._refresh_viewer_value_indicators_to_window_end()
            try:
                Clock.schedule_once(lambda _dt: self._refresh_hover_now(), 0.05)
                Clock.schedule_once(lambda _dt: self._refresh_hover_now(), 0.20)
            except Exception:
                pass

        if not (self.viewer_mode and self.history_start and self.history_end):
            minutes = self.current_time_range.minutes
            for graph in self.graph_slots.values():
                try:
                    graph.filter_data_by_time_range(minutes)
                except Exception:
                    pass

        self._historical_data_loaded = True

    def _apply_history_images(
        self,
        generation: int,
        key: HistoryLoadKey,
        frames: list,
    ) -> None:
        if self._stopped or not self._history_controller.is_current(generation):
            return
        if not self._history_key_matches_current(key):
            return
        self._viewer_image_timestamps = []
        self._viewer_image_bytes_by_ts = {}
        self._viewer_image_current_ts = None
        for frame in frames or []:
            ts = frame.get("ts") if isinstance(frame, dict) else None
            image_bytes = frame.get("image_bytes") if isinstance(frame, dict) else None
            if ts is None or not image_bytes:
                continue
            self._viewer_image_timestamps.append(ts)
            self._viewer_image_bytes_by_ts[ts] = bytes(image_bytes)
        self._viewer_image_timestamps.sort()
        if not self._viewer_image_timestamps:
            self._show_viewer_no_image_placeholder()
            return
        self._update_viewer_image_for_time(self._get_viewer_image_default_time())

    def _apply_history_error(self, generation: int, error: str) -> None:
        if self._stopped or not self._history_controller.is_current(generation):
            return
        for graph in getattr(self, "graph_slots", {}).values():
            graph.clear_data()
            graph.set_empty_message("Ошибка загрузки")
        if self.viewer_mode and hasattr(self, "camera_widget"):
            self._show_viewer_no_image_placeholder(f"Ошибка загрузки · {error}")
        self._historical_data_loaded = False

    def _format_absolute_range(self) -> str:
        if not self.history_start or not self.history_end:
            return "Не выбран"
        # Короткий формат для кнопки (чтобы не ломал UI)
        fmt_date = "%d.%m"
        fmt_time = "%H:%M"
        if self.history_start.date() == self.history_end.date():
            return f"{self.history_start.strftime(fmt_date)} {self.history_start.strftime(fmt_time)}–{self.history_end.strftime(fmt_time)}"
        return (
            f"{self.history_start.strftime(fmt_date)} {self.history_start.strftime(fmt_time)}–"
            f"{self.history_end.strftime(fmt_date)} {self.history_end.strftime(fmt_time)}"
        )
    
    def _create_data_source(self) -> DataSource:
        """Создать источник, не подменяя недоступную БД синтетикой."""
        result = create_configured_data_source(self.config)
        if result.mode == "demo":
            self._db_state = "demo"
            self._db_error = None
            print("[MonitorScreen] Запущен явно разрешенный демонстрационный режим")
        elif result.available:
            self._db_state = "online"
            self._db_error = None
            print("[MonitorScreen] Подключение к базе данных успешно установлено")
        else:
            self._db_state = "offline"
            self._db_error = result.error or "База данных недоступна"
            print(f"[MonitorScreen] OFFLINE: {self._db_error}")
        return result.source

    def _is_database_online(self) -> bool:
        return isinstance(self.data_source, DatabaseDataSource) and self._db_state == "online"

    def _is_live_presentation_allowed(self) -> bool:
        return self._db_state in {"online", "demo"}

    def _build_connection_banner(self) -> BoxLayout:
        banner = BoxLayout(
            orientation="horizontal",
            spacing=dp(8),
            padding=(dp(12), dp(5), dp(6), dp(5)),
            size_hint_y=None,
            height=0,
            opacity=0,
            disabled=True,
        )
        apply_rounded_panel(
            banner,
            base_rgba=UI_BTN_DANGER,
            radius_px=dp(9),
            border_alpha=0.16,
        )
        self._db_status_label = Label(
            text="",
            color=UI_TEXT_STRONG,
            font_size=dp(13),
            halign="left",
            valign="middle",
            shorten=True,
            shorten_from="right",
        )
        self._db_status_label.bind(
            size=lambda inst, size: setattr(inst, "text_size", (max(1, size[0]), max(1, size[1])))
        )
        self._db_retry_button = Button(
            text="Повторить",
            size_hint=(None, 1),
            width=dp(112),
            background_normal="",
            background_down="",
            background_color=(0, 0, 0, 0),
            color=UI_TEXT_STRONG,
            font_size=dp(12),
        )
        self._db_retry_button.bind(on_release=self._attempt_database_reconnect)
        apply_rounded_button(
            self._db_retry_button,
            base_rgba=UI_BTN_DANGER,
            radius_px=dp(8),
            border_alpha=0.24,
        )
        banner.add_widget(self._db_status_label)
        banner.add_widget(self._db_retry_button)
        return banner

    def _set_db_state(self, state: str, error: str | None = None) -> None:
        self._db_state = str(state)
        self._db_error = error
        try:
            Clock.schedule_once(lambda _dt: self._sync_connection_ui(), 0)
        except Exception:
            pass

    def _enter_offline_state(self, error: str) -> None:
        if self._stopped or self._db_state == "demo":
            return
        self._set_db_state("offline", error or "Связь с базой данных потеряна")

    def _sync_connection_ui(self) -> None:
        banner = getattr(self, "_db_status_banner", None)
        if banner is None:
            return

        state = self._db_state
        is_online = state == "online"
        is_demo = state == "demo"
        visible = not is_online
        banner.height = dp(40) if visible else 0
        banner.opacity = 1 if visible else 0
        banner.disabled = not visible

        if is_demo:
            self._db_status_label.text = "ДЕМО-РЕЖИМ · отображаются синтетические данные"
            self._db_retry_button.opacity = 0
            self._db_retry_button.disabled = True
            self._db_retry_button.width = 0
            if hasattr(banner, "_pm_panel_bg_c"):
                banner._pm_panel_bg_c.rgba = UI_BTN_WARNING
        elif state == "reconnecting":
            self._db_status_label.text = "Подключение к PostgreSQL… реальные данные временно недоступны"
            self._db_retry_button.text = "Подключение…"
            self._db_retry_button.opacity = 1
            self._db_retry_button.disabled = True
            self._db_retry_button.width = dp(132)
            if hasattr(banner, "_pm_panel_bg_c"):
                banner._pm_panel_bg_c.rgba = UI_BTN_WARNING
        elif state == "offline":
            self._db_status_label.text = (
                f"БД НЕДОСТУПНА · данные не обновляются · {self._db_error or 'проверьте подключение'}"
            )
            self._db_retry_button.text = "Повторить"
            self._db_retry_button.opacity = 1
            self._db_retry_button.disabled = False
            self._db_retry_button.width = dp(112)
            if hasattr(banner, "_pm_panel_bg_c"):
                banner._pm_panel_bg_c.rgba = UI_BTN_DANGER
        else:
            self._db_status_label.text = ""
            self._db_retry_button.opacity = 0
            self._db_retry_button.disabled = True
            self._db_retry_button.width = 0

        for graph in getattr(self, "graph_slots", {}).values():
            try:
                graph.set_live_time_axis_enabled(is_online or is_demo)
                graph.set_empty_message("Нет данных" if (is_online or is_demo) else "БД недоступна")
                if state in {"offline", "reconnecting"}:
                    graph.clear_data()
            except Exception:
                pass

        if state in {"offline", "reconnecting"}:
            self.available_beds = []
            self._last_added_values = {}
            for widget in getattr(self, "value_slots", {}).values():
                try:
                    widget.set_value(None)
                except Exception:
                    pass
            if getattr(self, "bed_button", None) is not None:
                self.bed_button.text = "БД недоступна"
                self.bed_button.disabled = True
            if hasattr(self, "camera_widget") and self.camera_widget is not None:
                self.camera_widget.show_placeholder(
                    "БД недоступна",
                    status_color=(0.86, 0.48, 0.48, 1),
                )
        elif is_online and getattr(self, "bed_button", None) is not None:
            self.bed_button.disabled = False

        if state == "offline":
            self._schedule_database_retry()

    def _schedule_database_retry(self) -> None:
        if self._stopped or self._db_state != "offline" or self._db_retry_event is not None:
            return
        delay = database_retry_delay(self._db_retry_attempt)
        self._db_retry_attempt += 1
        self._db_retry_event = Clock.schedule_once(self._attempt_database_reconnect, delay)

    def _attempt_database_reconnect(self, *_args) -> None:
        if self._stopped or self._db_state == "demo" or self._db_reconnect_in_progress:
            return
        if self._db_retry_event is not None:
            try:
                self._db_retry_event.cancel()
            except Exception:
                pass
            self._db_retry_event = None

        self._db_reconnect_in_progress = True
        self._set_db_state("reconnecting", self._db_error)
        try:
            bed_id = self.data_source.get_current_bed_id()
        except Exception:
            bed_id = self.monitor_config.get("bed_id")
        config_path = self.config.get_config_path()

        def _reconnect_worker():
            fresh_config = ConfigLoader(config_path)
            result = create_configured_data_source(fresh_config, bed_id=bed_id)
            Clock.schedule_once(
                lambda _dt, reconnect_result=result, cfg=fresh_config: self._finish_database_reconnect(
                    reconnect_result,
                    cfg,
                ),
                0,
            )

        threading.Thread(target=_reconnect_worker, daemon=True).start()

    def _finish_database_reconnect(
        self,
        result: DataSourceCreationResult,
        fresh_config: ConfigLoader,
    ) -> None:
        self._db_reconnect_in_progress = False
        if self._stopped:
            if isinstance(result.source, DatabaseDataSource):
                result.source.close()
            return

        previous = self.data_source
        self.data_source = result.source
        self.config = fresh_config
        if previous is not result.source and isinstance(previous, DatabaseDataSource):
            previous.close()

        if result.available and result.mode == "database":
            self._db_retry_attempt = 0
            self._set_db_state("online")
            self._load_available_signals()
            self._load_beds()
            if self.viewer_mode and self.history_start and self.history_end:
                self.reload_historical_data()
            elif not self.viewer_mode:
                Clock.schedule_once(lambda _dt: self._load_historical_data(), 0)
            self._start_camera_updates()
            self.start_updates()
            return

        self._set_db_state("offline", result.error or "Повторное подключение не удалось")
    
    def _create_ui(self):
        """Создание пользовательского интерфейса"""
        tile_sidebar_layout = self.grid_tile_layout and not self.viewer_mode
        viewer_grid_layout = self.viewer_mode and self.grid_tile_layout
        if self.show_menu_bar:
            self.main_container.add_widget(self._build_monitor_menu())
        self._db_status_banner = self._build_connection_banner()
        self.main_container.add_widget(self._db_status_banner)

        # Верхняя часть (2 строки из 3)
        top_container = BoxLayout(
            orientation='horizontal',
            spacing=dp(10),
            size_hint_y=(0.18 if self.viewer_mode and not self.viewer_toolbar_in_titlebar else (0.11 if self.viewer_mode else (0.16 if self.external_status_bar else 0.21))),
            padding=(0, 0, 0, 0) if self.viewer_mode else (0, 0, 0, 0),
        )
        self.top_container = top_container
        
        # Левая часть - панель выбора кровати
        # Показываем всегда, но активна только в режиме БД
        bed_panel = self._create_bed_selection_panel()
        self._bed_panel = bed_panel
        if not (self.external_status_bar and not self.viewer_mode):
            if not (self.viewer_mode and self.viewer_toolbar_in_titlebar):
                if not tile_sidebar_layout and not (self.viewer_mode and not self.viewer_toolbar_in_titlebar):
                    top_container.add_widget(bed_panel)

        if tile_sidebar_layout or viewer_grid_layout:
            # Важно: в Kivy вертикальный BoxLayout раскладывает детей снизу вверх,
            # поэтому для "текст от левого верхнего" используем AnchorLayout.
            from kivy.uix.anchorlayout import AnchorLayout

            self.patient_info_panel = AnchorLayout(
                anchor_x="left",
                anchor_y="top",
                padding=(dp(7), dp(3), dp(7), dp(3)),
                size_hint_y=None,
                height=dp(82),
            )
            apply_rounded_panel(
                self.patient_info_panel,
                base_rgba=(0.125, 0.125, 0.135, 1),
                radius_px=dp(10),
                border_alpha=0.06,
            )
            self.patient_info_text_col = BoxLayout(
                orientation="vertical",
                spacing=dp(1),
                size_hint=(1, None),
            )
            self.patient_info_text_col.bind(minimum_height=self.patient_info_text_col.setter("height"))
            self.patient_info_name_label = Label(
                text="Пациент: —",
                size_hint_y=None,
                height=dp(18),
                font_size=dp(11),
                bold=True,
                color=UI_TEXT_STRONG,
                halign="left",
                valign="top",
                shorten=True,
                shorten_from="right",
                text_size=(0, 0),
            )
            self.patient_info_history_label = Label(
                text="ИБ: —",
                size_hint_y=None,
                height=dp(16),
                font_size=dp(10),
                color=UI_TEXT_PRIMARY,
                halign="left",
                valign="top",
                shorten=True,
                shorten_from="right",
                text_size=(0, 0),
            )
            self.patient_info_age_label = Label(
                text="Возраст: —",
                size_hint_y=None,
                height=dp(16),
                font_size=dp(10),
                color=UI_TEXT_PRIMARY,
                halign="left",
                valign="top",
                shorten=True,
                shorten_from="right",
                text_size=(0, 0),
            )
            self.patient_info_admitted_label = Label(
                text="Поступил: —",
                size_hint_y=None,
                height=dp(16),
                font_size=dp(10),
                color=UI_TEXT_PRIMARY,
                halign="left",
                valign="top",
                shorten=True,
                shorten_from="right",
                text_size=(0, 0),
            )
            for lbl in (
                self.patient_info_name_label,
                self.patient_info_history_label,
                self.patient_info_age_label,
                self.patient_info_admitted_label,
            ):
                # Для корректного valign нужно задавать высоту в text_size.
                lbl.bind(size=lambda inst, s: setattr(inst, "text_size", (max(1, s[0]), max(1, s[1]))))
                self.patient_info_text_col.add_widget(lbl)
            self.patient_info_panel.add_widget(self.patient_info_text_col)

        # В viewer_mode показываем ФИО пациента: справа от кнопок и слева от камеры
        if self.viewer_mode:
            patient_container = BoxLayout(
                orientation="vertical",
                spacing=dp(4) if not self.viewer_toolbar_in_titlebar else dp(2),
                padding=(dp(6), dp(2), dp(6), dp(2)) if not self.viewer_toolbar_in_titlebar else (dp(4), 0, dp(4), 0),
                size_hint_x=1,
                size_hint_y=None,
            )
            patient_container.bind(minimum_height=patient_container.setter("height"))
            if not self.viewer_toolbar_in_titlebar:
                apply_rounded_panel(
                    patient_container,
                    base_rgba=(0.12, 0.12, 0.13, 1),
                    radius_px=dp(10),
                    border_alpha=0.06,
                )
            self.patient_title_label = Label(
                text="Пациент",
                size_hint_y=None,
                height=dp(22),
                font_size=dp(12),
                color=(0.75, 0.75, 0.75, 1),
                halign="center",
                valign="middle",
                text_size=(0, 0),
            )
            self.patient_title_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
            patient_container.add_widget(self.patient_title_label)

            self.patient_name_label = Label(
                text="—",
                size_hint_y=None,
                height=dp(38),
                font_size=dp(15),
                bold=True,
                color=(1, 1, 1, 1),
                halign="center",
                valign="middle",
                shorten=True,
                shorten_from="right",
                text_size=(0, 0),
            )
            self.patient_name_label.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
            patient_container.add_widget(self.patient_name_label)

            self.patient_container = patient_container
            if self.viewer_toolbar_in_titlebar:
                top_container.add_widget(patient_container)
        
        # Средняя часть - камера (квадратная, больше по размеру)
        from kivy.uix.anchorlayout import AnchorLayout
        camera_container = AnchorLayout(
            anchor_x='center' if self.viewer_mode else 'center',
            anchor_y='center' if self.viewer_mode else ('top' if tile_sidebar_layout else 'center'),
            size_hint_x=None if self.viewer_mode else 0.35,
            width=(dp(190) if self.viewer_mode and not self.viewer_toolbar_in_titlebar else (dp(150) if self.viewer_mode else dp(0))),
        )
        if self.viewer_mode:
            try:
                camera_container.padding = (0, 0, 0, 0)
            except Exception:
                pass
        self.camera_widget = CameraWidget()
        self.camera_widget.set_compact_tile_mode(tile_sidebar_layout)
        camera_container.add_widget(self.camera_widget)
        self.camera_container = camera_container
        if not tile_sidebar_layout and not (self.viewer_mode and not self.viewer_toolbar_in_titlebar):
            top_container.add_widget(camera_container)
        
        # Размер рамки камеры должен повторять пропорции изображения, иначе
        # внутри обертки появляются лишние поля сверху/снизу.
        def make_square(instance, size):
            # В компактной плиточной верстке размер контролирует _update_tile_camera_panel_layout,
            # чтобы камера всегда занимала полную ширину правой колонки. Здесь вмешиваться нельзя,
            # иначе будет цикл: make_square <-> camera_container.size.
            if getattr(self, "_is_live_sidebar_layout", lambda: False)() or getattr(self, "_use_dashboard_grid_layout", lambda: False)():
                return
            if size[0] > 0 and size[1] > 0:
                pad_l = pad_t = pad_r = pad_b = 0
                if self.viewer_mode and hasattr(camera_container, "padding"):
                    try:
                        p = camera_container.padding
                        if isinstance(p, (list, tuple)):
                            if len(p) == 4:
                                pad_l, pad_t, pad_r, pad_b = p
                            elif len(p) == 2:
                                pad_l = pad_r = p[0]
                                pad_t = pad_b = p[1]
                    except Exception:
                        pad_l = pad_t = pad_r = pad_b = 0
                available_w = max(1, size[0] - (pad_l + pad_r))
                available_h = max(1, size[1] - (pad_t + pad_b))
                aspect = 0.75
                try:
                    texture = getattr(getattr(self.camera_widget, "image_widget", None), "texture", None)
                    if texture and texture.size and texture.size[0] > 0:
                        aspect = max(0.2, min(2.0, float(texture.size[1]) / float(texture.size[0])))
                except Exception:
                    aspect = 0.75
                target_w = available_w
                target_h = target_w * aspect
                if target_h > available_h:
                    target_h = available_h
                    target_w = target_h / max(aspect, 0.01)
                self.camera_widget.size_hint = (None, None)
                self.camera_widget.width = max(1, target_w)
                self.camera_widget.height = max(1, target_h)
        camera_container.bind(size=make_square)

        def _on_camera_texture(*_args):
            # При смене текстуры в плиточной верстке нужно пересчитать высоту через
            # _update_tile_camera_panel_layout, в остальных режимах работает make_square.
            if getattr(self, "_is_live_sidebar_layout", lambda: False)():
                try:
                    self._update_tile_camera_panel_layout()
                except Exception:
                    pass
            else:
                make_square(camera_container, camera_container.size)

        try:
            self.camera_widget.image_widget.bind(texture=_on_camera_texture)
        except Exception:
            pass
        if self.viewer_mode and not self.viewer_toolbar_in_titlebar:
            def _sync_viewer_camera_height(*_args):
                try:
                    avail_w = float(camera_container.width or 0)
                except Exception:
                    avail_w = 0.0
                if avail_w > 0:
                    aspect = 0.75
                    try:
                        texture = getattr(getattr(self.camera_widget, "image_widget", None), "texture", None)
                        if texture and texture.size and texture.size[0] > 0:
                            aspect = max(0.2, min(2.0, float(texture.size[1]) / float(texture.size[0])))
                    except Exception:
                        aspect = 0.75
                    camera_container.size_hint_y = None
                    camera_container.height = avail_w * aspect
            camera_container.bind(width=_sync_viewer_camera_height)
        
        # Правая часть - цифровые значения
        values_container = BoxLayout(
            orientation='vertical',
            spacing=dp(10),
            size_hint_x=0.35
        )
        self.values_container = values_container
        
        # Получаем названия параметров из конфига
        param1_name = self.config.get_display_value_1()
        param2_name = self.config.get_display_value_2()
        
        # Получаем названия сигналов из БД или используем значения по умолчанию
        param_info = self._get_param_info()
        
        info1 = param_info.get(param1_name, {'title': 'Параметр 1', 'color': '#FF4444', 'unit': '%'})
        info2 = param_info.get(param2_name, {'title': 'Параметр 2', 'color': '#44FF44', 'unit': 'уд/мин'})
        info3 = param_info.get('breathing', {'title': 'Параметр 3', 'color': '#4444FF', 'unit': 'вдох/мин'})
        info4 = param_info.get('temperature', {'title': 'Параметр 4', 'color': '#FFFF44', 'unit': '°C'})

        self.value_display_1 = self._create_value_display_widget("value1", info1)
        self.display_param_1 = param1_name  # legacy
        self.value_display_2 = self._create_value_display_widget("value2", info2)
        self.display_param_2 = param2_name  # legacy
        self.value_display_3 = self._create_value_display_widget("value3", info3)
        self.value_display_4 = self._create_value_display_widget("value4", info4)
        self.value_display_5 = self._create_value_display_widget("value5", info1)
        self.value_display_6 = self._create_value_display_widget("value6", info2)

        viewer_inline_sidebar = self.viewer_mode and not self.viewer_toolbar_in_titlebar
        if tile_sidebar_layout or (viewer_inline_sidebar and not self._use_dashboard_grid_layout()):
            self.values_grid = GridLayout(cols=2, rows=3, spacing=dp(10), size_hint=(1, 1))
            for widget in (
                self.value_display_1,
                self.value_display_2,
                self.value_display_3,
                self.value_display_4,
                self.value_display_5,
                self.value_display_6,
            ):
                self.values_grid.add_widget(widget)
            values_container.add_widget(self.values_grid)
        else:
            values_container.add_widget(self.value_display_1)
            values_container.add_widget(self.value_display_2)
        
        # В просмотрщике истории пока скрываем правые верхние численные значения:
        # данные туда не попадают (live-обновление отключено), чтобы не вводить в заблуждение.
        if not self.viewer_mode:
            if not tile_sidebar_layout:
                top_container.add_widget(values_container)
        if not tile_sidebar_layout and not (self.viewer_mode and not self.viewer_toolbar_in_titlebar):
            self.main_container.add_widget(top_container)

        # Нижняя часть - графики (2 строки) с кнопками выбора справа
        graphs_main_container = BoxLayout(
            orientation='horizontal',
            spacing=dp(10),
            # live: добавили высоту графикам (0.75 + 0.14)
            size_hint_y=0.85 if self.viewer_mode else 0.89
        )
        self.graphs_main_container = graphs_main_container
        
        # Контейнер для двух графиков (на всю ширину)
        graphs_container = BoxLayout(
            orientation='vertical',
            spacing=dp(4),
            size_hint_x=1.0
        )
        self.graphs_container = graphs_container
        
        # Получаем названия сигналов из БД для графиков
        param_info = self._get_param_info()
        
        # Создаем все графики с названиями из БД
        spo2_info = param_info.get('spo2', {'title': 'SPO2', 'color': '#FF4444', 'unit': '%'})
        pulse_info = param_info.get('pulse', {'title': 'Пульс', 'color': '#44FF44', 'unit': 'уд/мин'})
        breathing_info = param_info.get('breathing', {'title': 'Дыхание', 'color': '#4444FF', 'unit': 'вдох/мин'})
        temperature_info = param_info.get('temperature', {'title': 'Температура', 'color': '#FFFF44', 'unit': '°C'})
        
        spo2_range = get_display_range("spo2")
        pulse_range = get_display_range("pulse")
        breathing_range = get_display_range("breathing")
        temperature_range = get_display_range("temperature")
        self.spo2_graph = GraphWidget(
            title=spo2_info['title'],
            color=spo2_info['color'],
            min_value=spo2_range[0],
            max_value=spo2_range[1],
            unit=spo2_info.get('unit', '')
        )
        self.pulse_graph = GraphWidget(
            title=pulse_info['title'],
            color=pulse_info['color'],
            min_value=pulse_range[0],
            max_value=pulse_range[1],
            unit=pulse_info.get('unit', '')
        )
        self.breathing_graph = GraphWidget(
            title=breathing_info['title'],
            color=breathing_info['color'],
            min_value=breathing_range[0],
            max_value=breathing_range[1],
            unit=breathing_info.get('unit', '')
        )
        self.temperature_graph = GraphWidget(
            title=temperature_info['title'],
            color=temperature_info['color'],
            min_value=temperature_range[0],
            max_value=temperature_range[1],
            unit=temperature_info.get('unit', '')
        )
        if not self.viewer_mode:
            # main.py: одна временная шкала на 2 графика + правый верхний бейдж значений.
            self.spo2_graph.set_header_visible(False)
            self.pulse_graph.set_header_visible(False)
            self.spo2_graph.set_corner_badge_visible(True)
            self.pulse_graph.set_corner_badge_visible(True)
            self.breathing_graph.set_header_visible(False)
            self.temperature_graph.set_header_visible(False)
            self.breathing_graph.set_corner_badge_visible(True)
            self.temperature_graph.set_corner_badge_visible(True)
            self.spo2_graph.set_time_axis_visible(False)
            self.pulse_graph.set_time_axis_visible(True)
            self.breathing_graph.set_time_axis_visible(False)
            self.temperature_graph.set_time_axis_visible(False)
        # Слоты графиков (на экране показываем 2 графика)
        self.graph_slots = {
            "graph1": self.spo2_graph,
            "graph2": self.pulse_graph,
            "graph3": self.breathing_graph,
            "graph4": self.temperature_graph,
        }
        for _slot_id, _graph in self.graph_slots.items():
            self._apply_graph_settings_to_widget(_slot_id, _graph)
        # Клик по графику открывает экран выбора параметра для этого слота
        # (тот же экран, что и для цифровых блоков).
        for _slot_id, _graph in self.graph_slots.items():
            try:
                _graph.set_on_select(
                    lambda sid=_slot_id: self._open_parameter_selection_for_slot(sid)
                )
                _graph.set_on_context_select(
                    lambda sid=_slot_id: self._show_graph_context_menu(sid)
                )
            except Exception:
                pass
        
        # Слоты цифр
        self.value_slots = {
            "value1": self.value_display_1,
            "value2": self.value_display_2,
            "value3": self.value_display_3,
            "value4": self.value_display_4,
            "value5": self.value_display_5,
            "value6": self.value_display_6,
        }
        
        # Словарь для хранения доступных параметров из БД
        self.available_signals = []
        
        # Загружаем доступные сигналы из БД при инициализации
        if isinstance(self.data_source, DatabaseDataSource):
            self._load_available_signals()
        
        # Первая строка - один график
        self.first_row_graph_container = BoxLayout(
            orientation='horizontal',
            size_hint_y=0.5
        )
        self.first_row_graph_container.add_widget(self.spo2_graph)
        graphs_container.add_widget(self.first_row_graph_container)
        
        # Вторая строка - один график
        self.second_row = BoxLayout(
            orientation='horizontal',
            size_hint_y=0.5
        )
        self.second_row.add_widget(self.pulse_graph)
        graphs_container.add_widget(self.second_row)
        graphs_container.bind(size=lambda *_: self._update_graph_row_layout())

        if self._use_dashboard_grid_layout():
            graphs_main_container.padding = dp(0)
            self._setup_dashboard_grid_layout(graphs_main_container)
            if self.viewer_mode:
                Clock.schedule_once(lambda _dt: self._refresh_patient_context(), 0.1)
            else:
                Clock.schedule_once(lambda _dt: self._refresh_patient_info(), 0.1)
        elif tile_sidebar_layout:
            host_side_pad = dp(0) if self.align_content_to_host_titlebar else dp(6)
            self.main_container.padding = (host_side_pad, UI_TOPBAR_CONTENT_GAP, host_side_pad, dp(6))
            graphs_main_container.padding = 0
            block_padding = self._get_primary_block_padding(compact=False, tiny=False)

            self.tile_graphs_panel = BoxLayout(
                orientation="vertical",
                padding=block_padding,
                size_hint_x=0.74,
                size_hint_y=1,
            )
            apply_rounded_panel(
                self.tile_graphs_panel,
                base_rgba=MONITOR_BACKGROUND_RGBA,
                radius_px=dp(12),
                border_alpha=0.0,
            )
            # Жесткий клиппинг по границам левой колонки: контент не вылезает за пределы.
            _apply_stencil_clip(self.tile_graphs_panel)

            self.tile_sidebar_panel = BoxLayout(
                orientation="vertical",
                padding=block_padding,
                size_hint_x=0.26,
                size_hint_y=1,
            )
            apply_rounded_panel(
                self.tile_sidebar_panel,
                base_rgba=MONITOR_BACKGROUND_RGBA,
                radius_px=dp(12),
                border_alpha=0.0,
            )
            # Жесткий клиппинг правой колонки тоже на уровне самой панели.
            _apply_stencil_clip(self.tile_sidebar_panel)

            from kivy.uix.anchorlayout import AnchorLayout as _SBHost
            self.tile_sidebar_host = _SBHost(
                anchor_x="left",
                anchor_y="top",
                size_hint=(1, 1),
            )
            self.tile_sidebar_container = BoxLayout(
                orientation="vertical",
                spacing=0,
                size_hint=(1, 1),
            )

            self.tile_camera_panel = BoxLayout(
                orientation="vertical",
                padding=0,
                size_hint_x=1,
                size_hint_y=None,
                height=dp(120),
            )

            self.tile_values_panel = BoxLayout(
                orientation="vertical",
                spacing=dp(0),
                padding=dp(8),
                size_hint=(1, 1),
            )
            apply_rounded_panel(self.tile_values_panel, base_rgba=(0.10, 0.10, 0.11, 1), radius_px=dp(10), border_alpha=0.0)
            graphs_container.size_hint_x = 1

            self._bed_panel.size_hint_x = 1
            self._bed_panel.width = dp(0)
            self._bed_panel.size_hint_y = None
            self._bed_panel.height = dp(84)
            self._bed_panel.padding = (0, 0, 0, 0)
            self._bed_panel.spacing = dp(4)

            self.camera_container.size_hint_x = 1
            self.camera_container.width = dp(0)
            self.camera_container.size_hint_y = None
            self.camera_container.height = dp(0)

            self.values_container.size_hint_x = 1
            self.values_container.size_hint_y = 1
            self.values_container.spacing = dp(0)
            self.value_display_1.set_compact_tile_mode(True, layout_variant="grid")
            self.value_display_2.set_compact_tile_mode(True, layout_variant="grid")
            self.value_display_3.set_compact_tile_mode(True, layout_variant="grid")
            self.value_display_4.set_compact_tile_mode(True, layout_variant="grid")
            self.value_display_5.set_compact_tile_mode(True, layout_variant="grid")
            self.value_display_6.set_compact_tile_mode(True, layout_variant="grid")
            self.tile_values_panel.add_widget(self.values_container)

            self.tile_camera_panel.add_widget(self.camera_container)
            # Верхний отступ компенсирует внутренний padding=dp(8) у GraphWidget,
            # чтобы верхний край блока пациента был на одной линии с верхом области графика.
            self.tile_gap_top = Widget(size_hint_x=1, size_hint_y=None, height=dp(8))
            self.tile_gap_patient_camera = Widget(size_hint_x=1, size_hint_y=None, height=dp(8))
            self.tile_gap_camera_bed = Widget(size_hint_x=1, size_hint_y=None, height=dp(8))
            self.tile_gap_bed_values = Widget(size_hint_x=1, size_hint_y=None, height=dp(8))
            self.tile_gap_bottom = Widget(size_hint_x=1, size_hint_y=None, height=dp(0))
            # Принудительно фиксируем единую ширину всех элементов правой колонки.
            self.patient_info_panel.size_hint_x = 1
            self.patient_info_panel.width = dp(0)
            self.tile_camera_panel.size_hint_x = 1
            self.tile_camera_panel.width = dp(0)
            self.tile_values_panel.size_hint_x = 1
            self.tile_values_panel.width = dp(0)
            self._bed_panel.size_hint_x = 1
            self._bed_panel.width = dp(0)
            self.tile_sidebar_container.add_widget(self.tile_gap_top)
            self.tile_sidebar_container.add_widget(self.patient_info_panel)
            self.tile_sidebar_container.add_widget(self.tile_gap_patient_camera)
            self.tile_sidebar_container.add_widget(self.tile_camera_panel)
            self.tile_sidebar_container.add_widget(self.tile_gap_camera_bed)
            self.tile_sidebar_container.add_widget(self._bed_panel)
            self.tile_sidebar_container.add_widget(self.tile_gap_bed_values)
            self.tile_sidebar_container.add_widget(self.tile_values_panel)
            self.tile_sidebar_container.add_widget(self.tile_gap_bottom)
            self.tile_sidebar_host.add_widget(self.tile_sidebar_container)
            self.tile_sidebar_panel.add_widget(self.tile_sidebar_host)

            # Камера в плитке должна уметь пересчитываться после layout (когда известна ширина колонки).
            try:
                self.tile_camera_panel.bind(width=lambda *_: self._update_tile_camera_panel_layout())
                self.tile_sidebar_container.bind(height=lambda *_: self._update_tile_camera_panel_layout())
                self.tile_sidebar_container.bind(height=lambda *_: self._redistribute_tile_sidebar_gaps())
                self.tile_sidebar_container.bind(width=lambda *_: self._update_tile_camera_panel_layout())
                self.tile_sidebar_host.bind(size=lambda *_: self._update_tile_camera_panel_layout())
                self.tile_sidebar_panel.bind(size=lambda *_: self._update_value_grid_layout())
                self.tile_sidebar_panel.bind(size=lambda *_: self._update_tile_camera_panel_layout())
            except Exception:
                pass

            self.tile_graphs_panel.add_widget(graphs_container)
            graphs_main_container.add_widget(self.tile_graphs_panel)
            graphs_main_container.add_widget(self.tile_sidebar_panel)
            Clock.schedule_once(lambda _dt: self._refresh_patient_info(), 0.1)
        elif self.viewer_mode and not self.viewer_toolbar_in_titlebar and not self._use_dashboard_grid_layout():
            self.viewer_graphs_panel = BoxLayout(
                orientation="vertical",
                padding=(dp(8), dp(8), dp(8), dp(8)),
                size_hint_x=0.76,
                size_hint_y=1,
            )
            apply_rounded_panel(
                self.viewer_graphs_panel,
                base_rgba=MONITOR_BACKGROUND_RGBA,
                radius_px=dp(12),
                border_alpha=0.06,
            )
            _apply_stencil_clip(self.viewer_graphs_panel)
            self.viewer_graphs_panel.add_widget(graphs_container)

            self.viewer_sidebar_panel = BoxLayout(
                orientation="vertical",
                padding=(dp(8), dp(8), dp(8), dp(8)),
                size_hint_x=0.24,
                size_hint_y=1,
            )
            apply_rounded_panel(
                self.viewer_sidebar_panel,
                base_rgba=MONITOR_BACKGROUND_RGBA,
                radius_px=dp(12),
                border_alpha=0.06,
            )
            _apply_stencil_clip(self.viewer_sidebar_panel)
            # Сайдбар просмотрщика построен по той же логике, что и живой:
            # фиксированные элементы сверху (камера, пациент, кнопки), а 4 индикатора
            # «прижимаются» к низу через гибкий разделитель. Так левая и правая
            # колонки получаются одинаковой высоты и согласованной ширины.
            self.viewer_sidebar_container = BoxLayout(
                orientation="vertical",
                spacing=dp(10),
                size_hint=(1, 1),
            )
            self.viewer_sidebar_container.add_widget(self.camera_container)
            if hasattr(self, "patient_container"):
                self.viewer_sidebar_container.add_widget(self.patient_container)
            self.viewer_sidebar_container.add_widget(self._bed_panel)
            # Гибкий разделитель: занимает свободное пространство между кнопками
            # и блоком индикаторов, чтобы индикаторы стояли у нижней границы.
            self.viewer_sidebar_spacer = BoxLayout(size_hint_y=1)
            self.viewer_sidebar_container.add_widget(self.viewer_sidebar_spacer)
            # Блок 4 индикаторов (использует общий values_container, размещённый
            # в 2x2-сетке выше). Делаем индикаторы компактными — как в живом
            # режиме, чтобы числа крупно читались, а заголовок был выровнен
            # по центру.
            try:
                values_container.size_hint = (1, None)
                values_container.height = dp(168)
                values_container.spacing = dp(0)
                for _vw in (
                    self.value_display_1,
                    self.value_display_2,
                    self.value_display_3,
                    self.value_display_4,
                    self.value_display_5,
                    self.value_display_6,
                ):
                    _vw.set_compact_tile_mode(True, layout_variant="grid")
            except Exception:
                pass
            self.viewer_sidebar_container.add_widget(values_container)
            self.viewer_sidebar_panel.add_widget(self.viewer_sidebar_container)

            graphs_main_container.add_widget(self.viewer_graphs_panel)
            graphs_main_container.add_widget(self.viewer_sidebar_panel)
        else:
            graphs_main_container.add_widget(graphs_container)
        self.main_container.add_widget(graphs_main_container)
        
        # Добавляем обработчики клика на графики
        self._setup_graph_click_handlers()
        
        # Инициализация камеры: для БД берем live-кадры из images, для test/fallback — файл из конфига.
        if isinstance(self.data_source, DatabaseDataSource):
            if self.viewer_mode:
                self._reload_viewer_images_for_history()
            else:
                self._start_camera_updates()
        else:
            camera_path = self.config.get_camera_image_path()
            if camera_path:
                self.camera_widget.start_auto_update(interval=1.0, image_path=camera_path)

        # Инициализация ФИО при старте (viewer_mode)
        if self.viewer_mode:
            self._refresh_patient_context()

            # Инициализация окна просмотра и слайдеров, если диапазон уже задан
            if self.history_start and self.history_end:
                self._full_start, self._full_end = self.history_start, self.history_end
                self._view_start, self._view_end = self.history_start, self.history_end
                self._apply_view_window_to_graphs()

    def _create_value_display_widget(self, slot_id: str, info: dict) -> ValueDisplayWidget:
        widget = ValueDisplayWidget(
            title=info.get("title", "Параметр"),
            color=info.get("color", "#FFFFFF"),
            unit=info.get("unit", ""),
            show_unit=False,
        )
        widget.set_on_select(lambda sid=slot_id: self._open_parameter_selection_for_slot(sid))
        widget.set_on_context_select(lambda sid=slot_id: self._open_parameter_selection_for_slot(sid))
        if info.get("min") is not None and info.get("max") is not None:
            widget.set_normal_range(info.get("min"), info.get("max"))
        return widget

    def _show_value_context_menu(self, slot_id: str):
        """Быстрое меню выбора параметра для цифрового блока по правому клику."""
        self._open_parameter_selection_for_slot(slot_id)

    def _create_dashboard_settings_button(self):
        btn = Button(
            text="",
            size_hint=(None, None),
            size=(dp(48), dp(48)),
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
        )
        btn.bind(on_release=lambda *_: self._show_dashboard_quick_settings_menu())
        apply_rounded_button(btn, base_rgba=(0.24, 0.24, 0.28, 0.98), radius_px=dp(14), border_alpha=0.28)
        attach_gear_icon(btn, color=UI_TEXT_STRONG)
        return btn

    def _create_dashboard_edit_done_button(self):
        btn = Button(
            text="Готово",
            size_hint=(None, None),
            size=(dp(132), dp(40)),
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
            font_size=dp(14),
            bold=True,
        )
        btn.color = UI_TEXT_STRONG
        btn.bind(on_release=lambda *_: self._finish_dashboard_grid_editing())
        apply_rounded_button(btn, base_rgba=UI_BTN_SUCCESS, radius_px=dp(12), border_alpha=0.18)
        return btn

    def _attach_dashboard_settings_button(self, grid=None) -> None:
        grid = grid or getattr(self, "dashboard_grid_layout", None)
        if grid is None:
            return
        if not hasattr(self, "dashboard_settings_button") or self.dashboard_settings_button is None:
            self.dashboard_settings_button = self._create_dashboard_settings_button()
        btn = self.dashboard_settings_button
        parent = getattr(btn, "parent", None)
        if parent is not None and parent is not grid:
            try:
                parent.remove_widget(btn)
            except Exception:
                pass
        if btn.parent is not grid:
            grid.add_widget(btn)
        else:
            grid.remove_widget(btn)
            grid.add_widget(btn)

        def _position(*_args):
            try:
                size = max(float(dp(42)), min(float(dp(52)), min(float(grid.width or 0), float(grid.height or 0)) * 0.08))
                margin = float(dp(10))
                btn.size = (size, size)
                btn.pos = (grid.right - size - margin, grid.top - size - margin)
            except Exception:
                pass

        if getattr(self, "_dashboard_settings_button_bound_grid", None) is not grid:
            grid.bind(pos=_position, size=_position)
            self._dashboard_settings_button_bound_grid = grid
        _position()
        self._sync_dashboard_edit_done_button(grid)

    def _sync_dashboard_edit_done_button(self, grid=None) -> None:
        grid = grid or getattr(self, "dashboard_grid_layout", None)
        if grid is None:
            return
        if not hasattr(self, "dashboard_edit_done_button") or self.dashboard_edit_done_button is None:
            self.dashboard_edit_done_button = self._create_dashboard_edit_done_button()
        btn = self.dashboard_edit_done_button
        editing = bool(getattr(self, "_dashboard_grid_edit_mode", False))
        if not editing:
            if getattr(btn, "parent", None) is not None:
                try:
                    btn.parent.remove_widget(btn)
                except Exception:
                    pass
            return
        parent = getattr(btn, "parent", None)
        if parent is not None and parent is not grid:
            try:
                parent.remove_widget(btn)
            except Exception:
                pass
        if btn.parent is not grid:
            grid.add_widget(btn)
        else:
            grid.remove_widget(btn)
            grid.add_widget(btn)

        def _position(*_args):
            try:
                margin = float(dp(12))
                btn.width = max(float(dp(112)), min(float(dp(152)), float(grid.width or 0) * 0.22))
                btn.height = max(float(dp(36)), min(float(dp(44)), float(grid.height or 0) * 0.07))
                btn.pos = (grid.right - btn.width - margin, grid.y + margin)
            except Exception:
                pass

        if getattr(self, "_dashboard_edit_done_button_bound_grid", None) is not grid:
            grid.bind(pos=_position, size=_position)
            self._dashboard_edit_done_button_bound_grid = grid
        _position()
        if getattr(self, "dashboard_settings_button", None) is not None and self.dashboard_settings_button.parent is grid:
            settings_btn = self.dashboard_settings_button
            grid.remove_widget(settings_btn)
            grid.add_widget(settings_btn)

    def _show_dashboard_quick_settings_menu(self):
        self._clear_dashboard_grid_hover()
        if self.manager is not None:
            try:
                from components.action_list_screen import ActionListScreen

                nav_screen_name = self._get_navigation_screen_name()
                screen = ActionListScreen(
                    name=f"{nav_screen_name}_dashboard_quick_settings",
                    title_text="Настройки монитора",
                    subtitle_text="Диапазон, сетка и кровать",
                    previous_screen=nav_screen_name,
                )
                screen.set_sections(
                    [
                        (
                            "Основное",
                            [
                                {
                                    "text": f"Диапазон: {self.current_time_range.label}",
                                    "on_press": lambda: self._show_time_range_menu(None),
                                    "return_back": False,
                                    "base_rgba": UI_BTN_MUTED,
                                },
                                {
                                    "text": "Завершить редактирование сетки" if getattr(self, "_dashboard_grid_edit_mode", False) else "Настроить сетку",
                                    "on_press": self._finish_dashboard_grid_editing if getattr(self, "_dashboard_grid_edit_mode", False) else self._show_dashboard_grid_menu,
                                    "return_back": False,
                                    "base_rgba": UI_BTN_SUCCESS if getattr(self, "_dashboard_grid_edit_mode", False) else UI_BTN_MUTED,
                                },
                                {
                                    "text": "Выбрать кровать",
                                    "on_press": lambda: self._show_bed_selection_menu(None),
                                    "return_back": False,
                                    "base_rgba": UI_BTN_MUTED,
                                },
                            ],
                        ),
                    ]
                )
                if self._replace_managed_screen(screen):
                    return
            except Exception:
                pass
        self._show_dashboard_grid_menu()

    def _detach_widget(self, widget) -> None:
        parent = getattr(widget, "parent", None)
        if parent is not None:
            try:
                parent.remove_widget(widget)
            except Exception:
                pass

    def _get_dashboard_widget_map(self) -> dict:
        widgets = {}
        widgets.update(getattr(self, "graph_slots", {}) or {})
        widgets.update(getattr(self, "value_slots", {}) or {})
        if hasattr(self, "patient_info_panel"):
            widgets["patient_panel"] = self.patient_info_panel
        elif self.viewer_mode and hasattr(self, "patient_container"):
            widgets["patient_panel"] = self.patient_container
        for name in ("camera_container", "_bed_panel"):
            widget = getattr(self, name, None)
            if widget is not None:
                key = "bed_panel" if name == "_bed_panel" else name.replace("_container", "")
                widgets[key] = widget
        return widgets

    def _setup_dashboard_grid_layout(self, parent_container) -> None:
        for widget in self._get_dashboard_widget_map().values():
            self._detach_widget(widget)
        for graph in getattr(self, "graph_slots", {}).values():
            try:
                graph.padding = 0
                graph.spacing = 0
                graph._update_responsive_metrics()
            except Exception:
                pass
        try:
            self.camera_container.padding = 0
            self.camera_widget.size_hint = (1, 1)
        except Exception:
            pass
        for widget in getattr(self, "value_slots", {}).values():
            try:
                widget.set_compact_tile_mode(True, layout_variant="grid")
            except Exception:
                pass
        if hasattr(self, "patient_info_panel"):
            self.patient_info_panel.bind(size=lambda *_: self._update_dashboard_patient_panel_layout())
            self._update_dashboard_patient_panel_layout()
        grid = DashboardGridLayout(
            cols=int(self.dashboard_grid_config.get("cols", 5) or 5),
            rows=int(self.dashboard_grid_config.get("rows", 4) or 4),
            spacing=dp(6),
            size_hint=(1, 1),
        )
        apply_rounded_panel(grid, base_rgba=MONITOR_BACKGROUND_RGBA, radius_px=dp(12), border_alpha=0.0)
        grid.on_config_changed = self._on_dashboard_grid_live_change
        grid.set_config(self.dashboard_grid_config, self._get_dashboard_widget_map())
        grid.set_edit_mode(bool(getattr(self, "_dashboard_grid_edit_mode", False)))
        self.dashboard_grid_layout = grid
        self._attach_dashboard_settings_button(grid)
        parent_container.add_widget(grid)

    def _update_dashboard_patient_panel_layout(self) -> None:
        if not self._use_dashboard_grid_layout() or not hasattr(self, "patient_info_panel"):
            return
        panel = self.patient_info_panel
        try:
            panel.padding = (dp(8), dp(8), dp(8), dp(8))
            panel.spacing = dp(3)
        except Exception:
            pass
        self._render_dashboard_patient_info_text()
        labels = [
            getattr(self, "patient_info_name_label", None),
            getattr(self, "patient_info_history_label", None),
            getattr(self, "patient_info_age_label", None),
            getattr(self, "patient_info_admitted_label", None),
        ]
        visible = [lbl for lbl in labels if lbl is not None and float(getattr(lbl, "opacity", 1) or 0) > 0]
        if not visible:
            return
        try:
            h = max(float(dp(48)), float(panel.height or 0))
            w = max(float(dp(80)), float(panel.width or 0))
        except Exception:
            h = float(dp(80))
            w = float(dp(160))
        compact = h < float(dp(92)) or w < float(dp(170))
        tiny = h < float(dp(66)) or w < float(dp(130))
        try:
            panel.padding = (dp(10), dp(8), dp(10), dp(6)) if not tiny else (dp(8), dp(6), dp(8), dp(5))
            panel.spacing = dp(4) if not tiny else dp(2)
        except Exception:
            pass

        if tiny:
            heights = [float(dp(22)), float(dp(19))]
            fonts = [float(dp(14)), float(dp(12))]
        elif compact:
            heights = [float(dp(26)), float(dp(22)), float(dp(19))]
            fonts = [float(dp(15)), float(dp(13)), float(dp(11.5))]
        else:
            heights = [float(dp(30)), float(dp(25)), float(dp(21)), float(dp(19))]
            fonts = [float(dp(17)), float(dp(14.5)), float(dp(12.5)), float(dp(11))]

        # На широких карточках текст должен визуально занимать доступную ширину,
        # а не выглядеть как мелкая подпись в углу.
        width_bonus = max(0.0, min(float(dp(3)), (w - float(dp(150))) / 120.0 * float(dp(3))))
        fonts = [f + width_bonus for f in fonts]

        for lbl in labels:
            if lbl not in visible:
                try:
                    lbl.height = 0
                    lbl.size_hint_y = None
                    lbl.text_size = (max(1, float(panel.width or 0) - float(dp(20))), 0)
                except Exception:
                    pass

        for idx, lbl in enumerate(visible):
            try:
                line_h = heights[min(idx, len(heights) - 1)]
                if idx == 0:
                    line_h += width_bonus * 1.4
                lbl.height = line_h
                lbl.size_hint_y = None
                lbl.font_size = fonts[min(idx, len(fonts) - 1)]
                lbl.bold = idx == 0
                lbl.halign = "left"
                lbl.valign = "top"
                lbl.shorten = True
                if idx == 0:
                    lbl.color = UI_TEXT_STRONG
                elif idx == 1:
                    lbl.color = UI_TEXT_PRIMARY
                else:
                    lbl.color = UI_TEXT_MUTED
                lbl.text_size = (max(1, float(panel.width or 0) - float(dp(20))), line_h)
            except Exception:
                pass

    def _render_dashboard_patient_info_text(self) -> None:
        """Пересобрать текст patient_panel под фактический размер ячейки."""
        data = getattr(self, "_dashboard_patient_info_data", None)
        if not isinstance(data, dict):
            return
        labels = [
            getattr(self, "patient_info_name_label", None),
            getattr(self, "patient_info_history_label", None),
            getattr(self, "patient_info_age_label", None),
            getattr(self, "patient_info_admitted_label", None),
        ]
        labels = [lbl for lbl in labels if lbl is not None]
        if not labels:
            return
        panel = getattr(self, "patient_info_panel", None)
        try:
            w = float(getattr(panel, "width", 0) or 0)
            h = float(getattr(panel, "height", 0) or 0)
        except Exception:
            w = h = 0.0

        bed = self._compact_bed_text(data.get("bed"))
        has_patient = bool(data.get("has_patient"))
        name = str(data.get("name") or "Пациент отсутствует").strip()
        history = str(data.get("history") or "—").strip()
        age = str(data.get("age") or "—").strip()
        admitted = str(data.get("admitted_short") or data.get("admitted") or "—").strip()

        if not has_patient:
            if h < float(dp(58)) or w < float(dp(150)):
                lines = [bed, "Нет пациента"]
            else:
                lines = [bed, "Пациент отсутствует", "ИБ: —"]
        elif h < float(dp(58)):
            lines = [bed, name]
        elif h < float(dp(92)) or w < float(dp(170)):
            lines = [bed, name, f"{age} · ИБ {history}"]
        elif h < float(dp(124)) or w < float(dp(220)):
            lines = [bed, name, f"{age} · ИБ {history}"]
        else:
            lines = [bed, name, f"{age} · ИБ {history}", f"Поступил: {admitted}"]

        for idx, lbl in enumerate(labels):
            if idx < len(lines):
                lbl.text = lines[idx]
                lbl.opacity = 1
            else:
                lbl.text = ""
                lbl.opacity = 0

    @staticmethod
    def _compact_bed_text(value) -> str:
        text = str(value or "Койка: —").strip()
        if not text:
            return "Койка: —"
        if text.lower().startswith("койка"):
            return text
        return f"Койка: {text}"

    def _clear_dashboard_grid_hover(self) -> None:
        grid = getattr(self, "dashboard_grid_layout", None)
        if grid is None:
            return
        try:
            grid.clear_hover_state()
        except Exception:
            pass

    def _bind_dashboard_edit_escape(self) -> None:
        if getattr(self, "_dashboard_edit_esc_bound", False):
            return
        try:
            Window.bind(on_keyboard=self._on_dashboard_edit_keyboard)
            self._dashboard_edit_esc_bound = True
        except Exception:
            self._dashboard_edit_esc_bound = False

    def _unbind_dashboard_edit_escape(self) -> None:
        if not getattr(self, "_dashboard_edit_esc_bound", False):
            return
        try:
            Window.unbind(on_keyboard=self._on_dashboard_edit_keyboard)
        except Exception:
            pass
        self._dashboard_edit_esc_bound = False

    def _on_dashboard_edit_keyboard(self, _window, key, _scancode, _codepoint, _modifiers):
        try:
            if int(key) != 27:
                return False
        except Exception:
            return False
        if has_open_modal_or_dropdown(_window):
            return False
        if not getattr(self, "_dashboard_grid_edit_mode", False):
            return False
        if getattr(self, "manager", None) is not None and self.manager.current != self._get_navigation_screen_name():
            return False
        self._finish_dashboard_grid_editing()
        return True

    def _set_dashboard_grid_config(self, config: dict, persist: bool = True) -> None:
        self.dashboard_grid_config = self._normalize_dashboard_grid_config(config)
        self.monitor_config["dashboard_grid"] = self.dashboard_grid_config
        grid = getattr(self, "dashboard_grid_layout", None)
        if grid is not None:
            grid.set_config(self.dashboard_grid_config, self._get_dashboard_widget_map())
            self._attach_dashboard_settings_button(grid)
        if persist:
            self._save_dashboard_grid_config()

    def _save_dashboard_grid_config(self) -> None:
        """Сохранить сетку: в layout_configs для live, в отдельный файл для bed viewer."""
        cfg = self._normalize_dashboard_grid_config(self.dashboard_grid_config)
        self.dashboard_grid_config = cfg
        if self.viewer_mode:
            LayoutConfig.save_viewer_dashboard_grid(cfg)
            return
        self.monitor_config["dashboard_grid"] = cfg
        self._save_monitor_config()

    def _on_dashboard_grid_live_change(self, config: dict) -> None:
        self.dashboard_grid_config = self._normalize_dashboard_grid_config(config)
        self.monitor_config["dashboard_grid"] = self.dashboard_grid_config
        if getattr(self, "_dashboard_grid_edit_mode", False):
            self._sync_dashboard_edit_done_button()

    def _set_dashboard_grid_edit_mode(self, enabled: bool, persist: bool = False) -> None:
        self._dashboard_grid_edit_mode = bool(enabled)
        grid = getattr(self, "dashboard_grid_layout", None)
        if grid is not None:
            if not enabled:
                self._on_dashboard_grid_live_change(grid.get_config())
            grid.set_edit_mode(bool(enabled))
            self._sync_dashboard_edit_done_button(grid)
        if enabled:
            self._bind_dashboard_edit_escape()
        else:
            self._unbind_dashboard_edit_escape()
        if persist:
            self._set_dashboard_grid_config(self.dashboard_grid_config, persist=True)

    def _start_dashboard_grid_editing(self) -> None:
        self._set_dashboard_grid_edit_mode(True, persist=False)

    def _finish_dashboard_grid_editing(self) -> None:
        self._set_dashboard_grid_edit_mode(False, persist=True)

    def _save_dashboard_grid_from_editor(self, config: dict) -> bool:
        try:
            self._set_dashboard_grid_config(config, persist=True)
            return True
        except Exception as exc:
            print(f"Ошибка сохранения сетки: {exc}")
            return False

    def _open_dashboard_grid_editor(self):
        self._clear_dashboard_grid_hover()
        if self.manager is None:
            return
        screen = DashboardGridEditorScreen(
            name=f"{self._get_navigation_screen_name()}_dashboard_grid_editor",
            grid_config=self.dashboard_grid_config,
            on_save=self._save_dashboard_grid_from_editor,
            previous_screen=self._get_navigation_screen_name(),
        )
        self._replace_managed_screen(screen)

    def _show_dashboard_grid_menu(self):
        self._clear_dashboard_grid_hover()
        if self.manager is not None:
            try:
                from components.action_list_screen import ActionListScreen

                nav_screen_name = self._get_navigation_screen_name()
                screen = ActionListScreen(
                    name=f"{nav_screen_name}_dashboard_grid_actions",
                    title_text="Настройка сетки",
                    subtitle_text="Выберите быстрый вариант размещения блоков",
                    previous_screen=nav_screen_name,
                )
                sections = [
                    (
                        "Пресеты: графики + индикаторы + фото + описание",
                        [
                            {
                                "text": "2 графика + 4 индикатора",
                                "on_press": lambda: self._set_dashboard_grid_config(LayoutConfig.create_default_dashboard_grid("graphs_2_values_4")),
                                "return_back": True,
                                "base_rgba": UI_BTN_MUTED,
                            },
                            {
                                "text": "2 графика + 6 индикаторов",
                                "on_press": lambda: self._set_dashboard_grid_config(LayoutConfig.create_default_dashboard_grid("graphs_2_values_6")),
                                "return_back": True,
                                "base_rgba": UI_BTN_MUTED,
                            },
                            {
                                "text": "3 графика + 4 индикатора",
                                "on_press": lambda: self._set_dashboard_grid_config(LayoutConfig.create_default_dashboard_grid("graphs_3_values_4")),
                                "return_back": True,
                                "base_rgba": UI_BTN_MUTED,
                            },
                            {
                                "text": "3 графика + 6 индикаторов",
                                "on_press": lambda: self._set_dashboard_grid_config(LayoutConfig.create_default_dashboard_grid("graphs_3_values_6")),
                                "return_back": True,
                                "base_rgba": UI_BTN_MUTED,
                            },
                            {
                                "text": "4 графика + 4 индикатора",
                                "on_press": lambda: self._set_dashboard_grid_config(LayoutConfig.create_default_dashboard_grid("graphs_4_values_4")),
                                "return_back": True,
                                "base_rgba": UI_BTN_MUTED,
                            },
                            {
                                "text": "4 графика + 6 индикаторов",
                                "on_press": lambda: self._set_dashboard_grid_config(LayoutConfig.create_default_dashboard_grid("graphs_4_values_6")),
                                "return_back": True,
                                "base_rgba": UI_BTN_MUTED,
                            },
                            {
                                "text": "Завершить редактирование на экране" if getattr(self, "_dashboard_grid_edit_mode", False) else "Редактировать сетку на экране",
                                "on_press": self._finish_dashboard_grid_editing if getattr(self, "_dashboard_grid_edit_mode", False) else self._start_dashboard_grid_editing,
                                "return_back": True,
                                "base_rgba": UI_BTN_SUCCESS if getattr(self, "_dashboard_grid_edit_mode", False) else UI_BTN_WARNING,
                            },
                            {
                                "text": "Редактировать элементы сетки",
                                "on_press": self._open_dashboard_grid_editor,
                                "return_back": False,
                                "base_rgba": UI_BTN_MUTED,
                            },
                        ],
                    )
                ]
                screen.set_sections(sections)
                if self._replace_managed_screen(screen):
                    return
            except Exception:
                pass

    def _is_live_sidebar_layout(self) -> bool:
        return (not self.viewer_mode) and not self._use_dashboard_grid_layout()

    def _get_live_layout_profile(self) -> dict:
        try:
            w = float(self.width)
            h = float(self.height)
        except Exception:
            w = h = 0.0

        try:
            sidebar_w = float(getattr(getattr(self, "tile_sidebar_panel", None), "width", 0) or 0)
        except Exception:
            sidebar_w = 0.0
        try:
            sidebar_panel = getattr(self, "tile_sidebar_panel", None)
            sidebar_h = float(getattr(sidebar_panel, "height", 0) or 0)
            pad = getattr(sidebar_panel, "padding", (0, 0, 0, 0))
            if isinstance(pad, (tuple, list)):
                pad_top = float(pad[1] if len(pad) > 1 else pad[0])
                pad_bottom = float(pad[3] if len(pad) > 3 else pad[0])
                sidebar_h = max(0.0, sidebar_h - pad_top - pad_bottom)
            else:
                sidebar_h = max(0.0, sidebar_h - float(pad or 0) * 2.0)
        except Exception:
            sidebar_h = 0.0

        expected_sidebar_w = w * ((0.26 if self.grid_tile_layout else 0.28) if w > 0 else 0.0)
        if w > 0 and (sidebar_w <= 1 or sidebar_w < max(float(dp(140)), expected_sidebar_w * 0.92)):
            sidebar_w = w * (0.26 if self.grid_tile_layout else 0.30)
        if h > 0 and sidebar_h <= 1:
            sidebar_h = h * (0.72 if self.show_menu_bar else 0.78)

        ultra_tiny = h < float(dp(300)) or sidebar_w < float(dp(150)) or w < float(dp(430))
        tiny = ultra_tiny or h < float(dp(380)) or sidebar_w < float(dp(190)) or w < float(dp(620))
        compact = tiny or h < float(dp(470)) or sidebar_w < float(dp(240)) or w < float(dp(860))

        if ultra_tiny:
            name = "ultra_tiny"
        elif tiny:
            name = "tiny"
        elif compact:
            name = "compact"
        else:
            name = "normal"

        sidebar_ratio_map = {
            "normal": 0.26 if self.grid_tile_layout else 0.28,
            "compact": 0.28 if self.grid_tile_layout else 0.30,
            "tiny": 0.30 if self.grid_tile_layout else 0.33,
            "ultra_tiny": 0.32 if self.grid_tile_layout else 0.36,
        }
        sidebar_ratio = sidebar_ratio_map[name]
        graph_ratio = max(0.58, 1.0 - sidebar_ratio)
        value_cols = 2 if (name in {"normal", "compact"} and sidebar_w >= float(dp(225)) and sidebar_h >= float(dp(260))) else 1

        return {
            "name": name,
            "compact": compact,
            "tiny": tiny,
            "ultra_tiny": ultra_tiny,
            "sidebar_width": sidebar_w,
            "sidebar_height": sidebar_h,
            "sidebar_ratio": sidebar_ratio,
            "graph_ratio": graph_ratio,
            "value_cols": value_cols,
            "hide_camera": False,
        }

    def _get_live_sidebar_metrics(self) -> dict:
        profile = self._get_live_layout_profile()
        if not self._is_live_sidebar_layout():
            return profile

        name = profile["name"]
        sidebar_h = max(float(dp(120)), float(profile.get("sidebar_height", 0) or 0))
        sidebar_w = max(float(dp(100)), float(profile.get("sidebar_width", 0) or 0))
        cols = int(profile.get("value_cols", 1) or 1)

        base_gap = {
            "normal": float(dp(12)),
            "compact": float(dp(10)),
            "tiny": float(dp(8)),
            "ultra_tiny": float(dp(6)),
        }.get(name, float(dp(8)))

        bed_height_map = {
            ("normal", 2): float(dp(76)),
            ("compact", 2): float(dp(70)),
            ("tiny", 2): float(dp(62)),
            ("ultra_tiny", 2): float(dp(54)),
            ("normal", 1): float(dp(74)),
            ("compact", 1): float(dp(68)),
            ("tiny", 1): float(dp(60)),
            ("ultra_tiny", 1): float(dp(52)),
        }
        bed_h = bed_height_map.get((name, cols), float(dp(72)))
        patient_info_h_map = {
            "normal": float(dp(86)),
            "compact": float(dp(82)),
            "tiny": float(dp(76)),
            "ultra_tiny": float(dp(70)),
        }
        patient_info_h = patient_info_h_map.get(name, float(dp(70)))
        values_panel_pad_v = float(dp(10)) if cols == 2 else float(dp(6))
        camera_panel_pad_v = float(dp(6))
        gap_camera_bed = base_gap
        gap_bed_values = base_gap

        value_card_height_map = {
            ("normal", 2): float(dp(68)),
            ("compact", 2): float(dp(66)),
            ("tiny", 2): float(dp(64)),
            ("ultra_tiny", 2): float(dp(62)),
            ("normal", 1): float(dp(48)),
            ("compact", 1): float(dp(46)),
            ("tiny", 1): float(dp(44)),
            ("ultra_tiny", 1): float(dp(42)),
        }
        value_card_h = value_card_height_map.get((name, cols), float(dp(42)))
        value_rows = 2 if cols == 2 else 4
        values_spacing = float(dp(7)) if cols == 2 else (float(dp(5)) if name in {"normal", "compact"} else float(dp(4)))

        tall_extra = max(0.0, sidebar_h - float(dp(520)))
        if tall_extra > 0 and name in {"normal", "compact"}:
            if cols == 2:
                patient_info_h += min(float(dp(18)), tall_extra * 0.06)
                bed_h += min(float(dp(28)), tall_extra * 0.10)
                value_card_h += min(float(dp(20)), tall_extra * 0.075)
                values_spacing += min(float(dp(4)), tall_extra * 0.010)
                values_panel_pad_v += min(float(dp(6)), tall_extra * 0.020)
            else:
                patient_info_h += min(float(dp(14)), tall_extra * 0.045)
                bed_h += min(float(dp(24)), tall_extra * 0.08)
                value_card_h += min(float(dp(12)), tall_extra * 0.045)
                values_spacing += min(float(dp(4)), tall_extra * 0.010)

        # Не даем кнопкам уйти из компактного режима: на высоких экранах они должны
        # стать выше, но оставаться ровно двумя крупными кнопками без лишних подписей.
        if cols == 2:
            patient_info_h = min(patient_info_h, float(dp(94)))
            bed_h = min(bed_h, float(dp(104)))
            value_card_h = min(value_card_h, float(dp(78)))
        else:
            patient_info_h = min(patient_info_h, float(dp(80)))
            bed_h = min(bed_h, float(dp(96)))
            value_card_h = min(value_card_h, float(dp(50)))

        desired_values_h = (
            value_card_h * value_rows
            + values_spacing * max(0, value_rows - 1)
            + values_panel_pad_v
        )

        hide_camera = bool(profile.get("hide_camera"))
        hide_bed = False
        min_camera_h_map = {
            "normal": float(dp(76)),
            "compact": float(dp(66)),
            "tiny": float(dp(56)),
            "ultra_tiny": float(dp(48)),
        }
        min_camera_h = min(sidebar_w * 0.75, min_camera_h_map.get(name, float(dp(72))))
        camera_aspect = 0.75
        try:
            texture = getattr(getattr(getattr(self, "camera_widget", None), "image_widget", None), "texture", None)
            if texture and texture.size and texture.size[0] > 0:
                camera_aspect = max(0.2, min(2.0, float(texture.size[1]) / float(texture.size[0])))
        except Exception:
            camera_aspect = 0.75

        min_values_h = (
            float(dp(150))
            if cols == 2
            else (float(dp(190)) if name in {"normal", "compact"} else float(dp(176)))
        )
        values_h = min(
            desired_values_h,
            max(min_values_h, sidebar_h * (0.30 if cols == 2 else 0.36)),
        )
        if hide_camera:
            camera_h = 0.0
        else:
            # Камера должна занимать всю ширину сайдбара; высота следует из aspect ratio.
            camera_h = max(min_camera_h, sidebar_w * camera_aspect)

        # Минимальные допустимые высоты (после возможного сжатия). Делаем их
        # действительно небольшими, чтобы блоки могли «ужаться», а не исчезнуть.
        min_bed_h = float(dp(56 if cols == 2 else 50))
        min_patient_info_h = float(dp(64))
        # Резервируем верхний отступ, чтобы блок пациента был на одной линии
        # с верхней кромкой области графика (внутренний padding=dp(8) у GraphWidget).
        top_align_offset = float(dp(8))
        min_gaps_h = top_align_offset

        def _required_h(cam_visible: bool, bed_visible: bool) -> float:
            return (
                patient_info_h
                + (camera_h + camera_panel_pad_v if cam_visible else 0.0)
                + (bed_h if bed_visible else 0.0)
                + values_h
                + values_panel_pad_v
                + min_gaps_h
            )

        # Приоритет видимости (от обязательного к опциональному):
        # ФИО (всегда) > 4 индикатора > кнопки (койка/период) > камера.
        # Скрываем элементы только если даже при всех минимальных высотах
        # они физически не помещаются. Так на любых разумных размерах
        # сохраняем фото и две кнопки видимыми, а на ультра-мелких — каскад.
        required_min_full = (
            min_patient_info_h
            + min_camera_h
            + camera_panel_pad_v
            + min_bed_h
            + min_values_h
            + values_panel_pad_v
            + min_gaps_h
        )
        required_min_no_cam = (
            min_patient_info_h
            + min_bed_h
            + min_values_h
            + values_panel_pad_v
            + min_gaps_h
        )

        if required_min_full > sidebar_h:
            hide_camera = True
            camera_h = 0.0
            if required_min_no_cam > sidebar_h:
                hide_bed = True
                bed_h = 0.0

        # После эскалации досжимаем элементы, если что-то ещё переполняет.
        # Порядок сжатия: камера → индикаторы → кнопки → ФИО (самые «обязательные»
        # ужимаются последними).
        used_h = _required_h(cam_visible=not hide_camera, bed_visible=not hide_bed)
        if used_h > sidebar_h:
            overflow = used_h - sidebar_h
            if not hide_camera:
                shrink_cam = min(max(0.0, camera_h - min_camera_h), overflow)
                camera_h -= shrink_cam
                overflow -= shrink_cam
            if overflow > 0:
                shrink_values = min(max(0.0, values_h - min_values_h), overflow)
                values_h -= shrink_values
                overflow -= shrink_values
            if overflow > 0 and not hide_bed:
                shrink_bed = min(max(0.0, bed_h - min_bed_h), overflow)
                bed_h -= shrink_bed
                overflow -= shrink_bed
            if overflow > 0:
                shrink_patient = min(max(0.0, patient_info_h - min_patient_info_h), overflow)
                patient_info_h -= shrink_patient
                overflow -= shrink_patient
            if overflow > 0:
                shrink_values_extra = min(max(0.0, values_h - float(dp(126 if cols == 2 else 148))), overflow)
                values_h -= shrink_values_extra
                overflow -= shrink_values_extra

        top_aligned_sidebar = bool(sidebar_h >= float(dp(620)))

        # Свободную высоту распределяем только между группами, не растягивая фото.
        used_h = _required_h(cam_visible=not hide_camera, bed_visible=not hide_bed)
        free_gap_h = max(0.0, sidebar_h - used_h)
        if hide_bed:
            # Без кнопок только две группы: ФИО и индикаторы — гэп между ними поглощает всё.
            gap_camera_bed = 0.0
            gap_bed_values = max(base_gap, free_gap_h) if not top_aligned_sidebar else base_gap
        elif top_aligned_sidebar:
            if hide_camera:
                gap_camera_bed = 0.0
                gap_bed_values = base_gap
            else:
                gap_camera_bed = base_gap
                gap_bed_values = base_gap
        elif hide_camera:
            gap_camera_bed = 0.0
            gap_bed_values = max(base_gap, free_gap_h)
        else:
            gap_camera_bed = max(base_gap, free_gap_h * 0.52)
            gap_bed_values = max(base_gap, free_gap_h - gap_camera_bed)
        if hide_camera:
            gap_camera_bed = 0.0

        profile.update(
            {
                "value_cols": cols,
                "patient_info_height": patient_info_h,
                "bed_height": bed_h,
                "camera_height": camera_h,
                "values_height": values_h,
                "container_spacing": 0.0,
                "base_gap": base_gap,
                "gap_camera_bed": gap_camera_bed,
                "gap_bed_values": gap_bed_values,
                "value_card_height": value_card_h,
                "values_spacing": values_spacing,
                "values_panel_pad_v": values_panel_pad_v,
                "camera_panel_pad_v": camera_panel_pad_v,
                "hide_camera": hide_camera,
                "hide_bed": hide_bed,
                "top_aligned_sidebar": top_aligned_sidebar,
            }
        )
        return profile

    def _get_value_grid_cols(self) -> int:
        if not self._is_live_sidebar_layout():
            return 1
        return int(self._get_live_sidebar_metrics().get("value_cols", 1) or 1)

    def _update_value_grid_layout(self) -> None:
        grid = getattr(self, "values_grid", None)
        if grid is None:
            return
        metrics = self._get_live_sidebar_metrics()
        cols = int(metrics.get("value_cols", 1) or 1)
        self._value_grid_cols = cols
        grid.cols = cols
        grid.rows = 2 if cols == 2 else 4
        variant = "grid" if cols == 2 else "stack"
        for widget in getattr(self, "value_slots", {}).values():
            widget.set_compact_tile_mode(True, layout_variant=variant)
            if hasattr(widget, "set_layout_density"):
                widget.set_layout_density(metrics.get("name", "normal"))
        if hasattr(self, "tile_values_panel") and self.tile_values_panel is not None:
            self.tile_values_panel.size_hint_y = None
            self.tile_values_panel.height = float(metrics.get("values_height", dp(180)))
            pad_v = float(metrics.get("values_panel_pad_v", dp(12)))
            self.tile_values_panel.padding = (dp(4), pad_v / 2.0, dp(4), pad_v / 2.0) if cols == 2 else (0, 0, 0, 0)

            raw_spacing = getattr(grid, "spacing", dp(4))
            try:
                if isinstance(raw_spacing, (tuple, list)):
                    grid_spacing = float(raw_spacing[1] if len(raw_spacing) > 1 else raw_spacing[0])
                else:
                    grid_spacing = float(raw_spacing or 0)
            except Exception:
                grid_spacing = float(dp(4))

            pad = getattr(self.tile_values_panel, "padding", (0, 0, 0, 0))
            if isinstance(pad, (tuple, list)):
                pad_v = float((pad[1] if len(pad) > 1 else pad[0]) + (pad[3] if len(pad) > 3 else pad[0]))
            else:
                pad_v = float(pad) * 2.0

            rows = 2 if cols == 2 else 4
            gaps = grid_spacing * max(0, rows - 1)
            available_h = max(1.0, float(self.tile_values_panel.height) - pad_v - gaps)
            card_h = min(float(metrics.get("value_card_height", available_h / float(rows))), available_h / float(rows))

            for widget in getattr(self, "value_slots", {}).values():
                widget.size_hint_y = None
                widget.height = card_h

            self._update_tile_camera_panel_layout()
            self._redistribute_tile_sidebar_gaps()

    def _update_tile_camera_panel_layout(self) -> None:
        """Синхронизировать размер блока камеры в live-sidebar верстке."""
        if not self._is_live_sidebar_layout():
            return
        panel = getattr(self, "tile_camera_panel", None)
        if panel is None:
            return

        metrics = self._get_live_sidebar_metrics()
        hide_camera = bool(metrics.get("hide_camera"))
        # Панель камеры всегда занимает полную ширину правой колонки, как и остальные блоки.
        panel.size_hint_x = 1
        panel.size_hint_y = None
        panel.padding = (0, 0, 0, 0)

        # Ширину берём из ширины самой панели (после layout), либо из ширины контейнера/обёртки.
        panel_w = float(getattr(panel, "width", 0) or 0)
        if panel_w <= 1:
            container = getattr(self, "tile_sidebar_container", None)
            if container is not None:
                try:
                    panel_w = max(1.0, float(container.width or 0))
                except Exception:
                    panel_w = 1.0
        if panel_w <= 1 and hasattr(self, "tile_sidebar_host"):
            try:
                panel_w = max(1.0, float(self.tile_sidebar_host.width or 0))
            except Exception:
                panel_w = 1.0
        if panel_w <= 1 and hasattr(self, "tile_sidebar_panel"):
            try:
                pad = getattr(self.tile_sidebar_panel, "padding", (0, 0, 0, 0))
                if isinstance(pad, (tuple, list)):
                    pad_x = float(pad[0] if len(pad) > 0 else 0) + float(pad[2] if len(pad) > 2 else pad[0])
                else:
                    pad_x = float(pad or 0) * 2.0
                panel_w = max(1.0, float(self.tile_sidebar_panel.width or 0) - pad_x)
            except Exception:
                panel_w = 1.0

        # Высота камеры берется из метрик (там уже учтены ограничения по сайдбару
        # и aspect ratio изображения), а если метрика 0 — fallback на panel_w * 0.58.
        configured_h = float(metrics.get("camera_height", 0) or 0)
        if configured_h <= 0:
            aspect = 0.58
            try:
                texture = getattr(getattr(self.camera_widget, "image_widget", None), "texture", None)
                if texture and texture.size and texture.size[0] > 0:
                    aspect = max(0.2, min(2.0, float(texture.size[1]) / float(texture.size[0])))
            except Exception:
                aspect = 0.58
            configured_h = panel_w * aspect
        panel_h = 0.0 if hide_camera else configured_h
        panel.height = panel_h
        panel.opacity = 0 if hide_camera else 1
        if hasattr(self, "camera_container"):
            self.camera_container.size_hint_x = 1
            self.camera_container.size_hint_y = None
            self.camera_container.height = 0 if hide_camera else panel_h
            self.camera_container.opacity = 0 if hide_camera else 1
        if hasattr(self, "camera_widget"):
            self.camera_widget.size_hint_x = 1
            self.camera_widget.size_hint_y = None
            self.camera_widget.height = 0 if hide_camera else panel_h
            self.camera_widget.opacity = 0 if hide_camera else 1
            try:
                self.camera_widget._update_bg()
            except Exception:
                pass
        self._redistribute_tile_sidebar_gaps()

    def _redistribute_tile_sidebar_gaps(self) -> None:
        """Раздать фактический остаток высоты только промежуткам между группами."""
        if not self._is_live_sidebar_layout():
            return
        container = getattr(self, "tile_sidebar_container", None)
        gap_top = getattr(self, "tile_gap_top", None)
        gap_patient_camera = getattr(self, "tile_gap_patient_camera", None)
        gap_camera_bed = getattr(self, "tile_gap_camera_bed", None)
        gap_bed_values = getattr(self, "tile_gap_bed_values", None)
        gap_bottom = getattr(self, "tile_gap_bottom", None)
        patient_panel = getattr(self, "patient_info_panel", None)
        camera_panel = getattr(self, "tile_camera_panel", None)
        bed_panel = getattr(self, "_bed_panel", None)
        values_panel = getattr(self, "tile_values_panel", None)
        if None in (container, gap_top, gap_patient_camera, gap_camera_bed, gap_bed_values, gap_bottom, patient_panel, camera_panel, bed_panel, values_panel):
            return

        try:
            available_h = float(container.height or 0)
        except Exception:
            available_h = 0.0
        if available_h <= 0:
            return

        hide_camera = float(getattr(camera_panel, "height", 0) or 0) <= 1 or float(getattr(camera_panel, "opacity", 1) or 0) <= 0
        hide_bed = float(getattr(bed_panel, "height", 0) or 0) <= 1 or float(getattr(bed_panel, "opacity", 1) or 0) <= 0
        metrics = self._get_live_sidebar_metrics()
        top_aligned_sidebar = bool(metrics.get("top_aligned_sidebar"))
        fixed_h = (
            float(getattr(patient_panel, "height", 0) or 0)
            + float(getattr(values_panel, "height", 0) or 0)
        )
        if not hide_camera:
            fixed_h += float(getattr(camera_panel, "height", 0) or 0)
        if not hide_bed:
            fixed_h += float(getattr(bed_panel, "height", 0) or 0)
        free_h = max(0.0, available_h - fixed_h)

        base_gap = float(dp(8))
        # Минимальный верхний отступ выравнивает блок пациента с верхней кромкой
        # области графика (внутренний padding=dp(8) у GraphWidget).
        top_align_offset = float(dp(8))
        if top_aligned_sidebar:
            top_h = max(top_align_offset, min(float(dp(14)), free_h))
            rem = max(0.0, free_h - top_h)
            if hide_camera and hide_bed:
                # Видимы только ФИО и индикаторы — один большой гэп между ними.
                gap0 = 0.0
                gap1 = 0.0
                gap2 = min(float(dp(46)), rem)
                rem = max(0.0, rem - gap2)
            elif hide_camera:
                gap0 = 0.0
                gap1 = 0.0
                gap2 = min(float(dp(46)), rem)
                rem = max(0.0, rem - gap2)
            elif hide_bed:
                # Видимы ФИО, камера и индикаторы. Гэпы вокруг кнопок схлопываем.
                gap0 = min(float(dp(34)), rem)  # patient -> camera
                rem = max(0.0, rem - gap0)
                gap1 = 0.0
                gap2 = min(float(dp(46)), rem)  # camera -> indicators
                rem = max(0.0, rem - gap2)
            else:
                gap0 = min(float(dp(34)), rem)  # patient -> camera
                rem = max(0.0, rem - gap0)
                gap1 = min(float(dp(34)), rem)  # camera -> bed/range
                rem = max(0.0, rem - gap1)
                gap2 = min(float(dp(46)), rem)  # bed/range -> indicators
                rem = max(0.0, rem - gap2)
            bottom_h = rem

            gap_top.size_hint_y = None
            gap_patient_camera.size_hint_y = None
            gap_camera_bed.size_hint_y = None
            gap_bed_values.size_hint_y = None
            gap_bottom.size_hint_y = None
            gap_top.height = top_h
            gap_patient_camera.height = gap0
            gap_camera_bed.height = gap1
            gap_bed_values.height = gap2
            gap_bottom.height = bottom_h
            return

        # Сначала резервируем верхний отступ для визуального выравнивания с графиком,
        # остальную свободную высоту делим между группами.
        top_h = min(top_align_offset, free_h)
        free_for_gaps = max(0.0, free_h - top_h)
        if hide_camera and hide_bed:
            bottom_h = 0.0
            gap0 = 0.0
            gap1 = 0.0
            gap2 = free_for_gaps
        elif hide_camera:
            bottom_h = 0.0
            gap0 = 0.0
            gap1 = 0.0
            gap2 = free_for_gaps
        elif hide_bed:
            # Видимы 3 группы (ФИО, камера, индикаторы) — два равных гэпа.
            bottom_h = 0.0
            gap0 = free_for_gaps / 2.0
            gap1 = 0.0
            gap2 = free_for_gaps - gap0
        elif free_for_gaps >= base_gap * 3.0:
            # В обычном режиме свободная высота живет только между группами:
            # пациент, фото, кнопки, показатели.
            bottom_h = 0.0
            gap_each = free_for_gaps / 3.0
            gap0 = gap_each
            gap1 = gap_each
            gap2 = free_for_gaps - gap0 - gap1
        else:
            bottom_h = 0.0
            gap0 = free_for_gaps / 3.0
            gap1 = free_for_gaps / 3.0
            gap2 = free_for_gaps - gap0 - gap1

        gap_top.size_hint_y = None
        gap_patient_camera.size_hint_y = None
        gap_camera_bed.size_hint_y = None
        gap_bed_values.size_hint_y = None
        gap_bottom.size_hint_y = None
        gap_top.height = top_h
        gap_patient_camera.height = gap0
        gap_camera_bed.height = gap1
        gap_bed_values.height = gap2
        gap_bottom.height = bottom_h

    def _update_tile_sidebar_host_height(self, *_args) -> None:
        if not self._is_live_sidebar_layout():
            return
        host = getattr(self, "tile_sidebar_host", None)
        container = getattr(self, "tile_sidebar_container", None)
        if host is None or container is None:
            return

        host.size_hint = (1, 1)
        container.size_hint = (1, 1)

    def _update_graph_row_layout(self) -> None:
        """Держать оба графических ряда строго одинаковой высоты."""
        graphs_container = getattr(self, "graphs_container", None)
        first_row = getattr(self, "first_row_graph_container", None)
        second_row = getattr(self, "second_row", None)
        if graphs_container is None or first_row is None or second_row is None:
            return

        try:
            total_h = float(graphs_container.height or 0)
        except Exception:
            total_h = 0.0
        if total_h <= 0:
            return

        spacing = getattr(graphs_container, "spacing", 0)
        try:
            if isinstance(spacing, (tuple, list)):
                spacing_y = float(spacing[1] if len(spacing) > 1 else spacing[0])
            else:
                spacing_y = float(spacing or 0)
        except Exception:
            spacing_y = 0.0

        row_h = max(1.0, (total_h - spacing_y) / 2.0)
        for row in (first_row, second_row):
            row.size_hint_y = None
            row.height = row_h

    def _update_primary_block_layout(self) -> None:
        """Синхронизировать два главных блока: графики и sidebar.

        Обе колонки сидят в одном горизонтальном BoxLayout с size_hint_y=1, поэтому
        в идеале сами получают одинаковую высоту от родителя. Дополнительно вешаем
        страхующее зеркалирование: tile_sidebar_panel.{height,y} <- tile_graphs_panel,
        чтобы при субпиксельных расхождениях в layout-проходах визуально колонки
        всегда имели идентичные размеры.
        """
        if not self._is_live_sidebar_layout():
            return
        graphs_panel = getattr(self, "tile_graphs_panel", None)
        sidebar_panel = getattr(self, "tile_sidebar_panel", None)
        if graphs_panel is None or sidebar_panel is None:
            return
        for panel in (graphs_panel, sidebar_panel):
            panel.size_hint_y = 1
            panel.height = dp(0)

        # Зеркалирование высоты sidebar-колонки за графиковой. Делаем один раз,
        # после первой инициализации обеих панелей.
        if not getattr(self, "_primary_block_mirror_bound", False):
            def _mirror_sidebar_to_graphs(*_args):
                gp = getattr(self, "tile_graphs_panel", None)
                sp = getattr(self, "tile_sidebar_panel", None)
                if gp is None or sp is None:
                    return
                try:
                    g_h = float(gp.height or 0)
                    g_y = float(gp.y or 0)
                except Exception:
                    return
                if g_h <= 0:
                    return
                # Чтобы не плодить лишние layout-проходы — выставляем только при реальной разнице.
                if abs(float(sp.height) - g_h) > 0.5:
                    sp.size_hint_y = None
                    sp.height = g_h
                if abs(float(sp.y) - g_y) > 0.5:
                    sp.y = g_y

            graphs_panel.bind(height=_mirror_sidebar_to_graphs, y=_mirror_sidebar_to_graphs)
            self._primary_block_mirror_bound = True
            from kivy.clock import Clock as _Clock
            _Clock.schedule_once(lambda *_: _mirror_sidebar_to_graphs(), 0)

    def _update_viewer_primary_block_layout(self) -> None:
        """Синхронизировать панели графиков/сайдбара в run_bed_viewer.

        В viewer-режиме колонки тоже стоят рядом в одном горизонтальном контейнере.
        На resize у Kivy могут появляться субпиксельные расхождения, поэтому
        страхуемся зеркалированием высоты/y правой колонки относительно левой.
        """
        if not (self.viewer_mode and not self.viewer_toolbar_in_titlebar):
            return
        graphs_panel = getattr(self, "viewer_graphs_panel", None)
        sidebar_panel = getattr(self, "viewer_sidebar_panel", None)
        if graphs_panel is None or sidebar_panel is None:
            return

        for panel in (graphs_panel, sidebar_panel):
            panel.size_hint_y = 1
            panel.height = dp(0)

        if not getattr(self, "_viewer_primary_block_mirror_bound", False):
            def _mirror_viewer_sidebar(*_args):
                gp = getattr(self, "viewer_graphs_panel", None)
                sp = getattr(self, "viewer_sidebar_panel", None)
                if gp is None or sp is None:
                    return
                try:
                    g_h = float(gp.height or 0)
                    g_y = float(gp.y or 0)
                except Exception:
                    return
                if g_h <= 0:
                    return
                if abs(float(sp.height) - g_h) > 0.5:
                    sp.size_hint_y = None
                    sp.height = g_h
                if abs(float(sp.y) - g_y) > 0.5:
                    sp.y = g_y

            graphs_panel.bind(height=_mirror_viewer_sidebar, y=_mirror_viewer_sidebar)
            self._viewer_primary_block_mirror_bound = True
            from kivy.clock import Clock as _Clock
            _Clock.schedule_once(lambda *_: _mirror_viewer_sidebar(), 0)

    @staticmethod
    def _get_primary_block_padding(compact: bool, tiny: bool):
        pad = dp(5) if tiny else (dp(6) if compact else dp(8))
        return (pad, pad, pad, pad)

    def _build_monitor_menu(self):
        """Верхнее меню монитора с переиспользованием существующих actions."""
        monitor_items: list = []
        if not self.viewer_mode:
            monitor_items.append(("Выбрать кровать", lambda: self._show_bed_selection_menu(None)))
            monitor_items.append(("Настроить сетку", self._show_dashboard_grid_menu))
        monitor_items.extend(
            [
                ("Выбрать период", lambda: self._show_time_range_menu(None)),
                ("Выбрать исследование", lambda: self._show_study_selection_menu(None) if self.viewer_mode else None),
                ("Экспорт", lambda: self._show_export_popup()),
                ("Сохранить конфигурацию", self._save_monitor_config),
            ]
        )
        menu_spec = {"Монитор": monitor_items}
        return AppMenuBar(
            menu_spec=menu_spec,
            app_title=None,
            status_text=None,
        )

    def _update_responsive_layout(self, *_args):
        """Адаптировать компоновку под размер плитки/окна."""
        try:
            w = float(self.width)
            h = float(self.height)
        except Exception:
            return
        if w <= 0 or h <= 0:
            return

        live_sidebar_layout = self._is_live_sidebar_layout()
        if live_sidebar_layout:
            metrics = self._get_live_sidebar_metrics()
            compact = bool(metrics.get("compact"))
            tiny = bool(metrics.get("tiny"))
            profile_name = str(metrics.get("name", "normal"))
            self._value_grid_cols = int(metrics.get("value_cols", 1) or 1)
        else:
            metrics = {"name": "normal", "value_cols": 1, "hide_camera": False, "container_spacing": float(dp(6))}
            compact = w < float(dp(760)) or h < float(dp(430))
            tiny = w < float(dp(560)) or h < float(dp(320))
            profile_name = "normal"

        self._layout_profile_name = profile_name

        if self.show_menu_bar:
            self.main_container.padding = dp(6) if compact else dp(10)
            self.main_container.spacing = dp(6) if compact else dp(10)
        else:
            side_pad = dp(0) if self.align_content_to_host_titlebar else (dp(6) if compact else dp(10))
            bottom_pad = dp(6) if compact else dp(10)
            self.main_container.padding = (side_pad, UI_TOPBAR_CONTENT_GAP, side_pad, bottom_pad)
            self.main_container.spacing = dp(0)

        if hasattr(self, "top_container"):
            self.top_container.spacing = dp(6) if compact else dp(10)
            self.top_container.padding = (0, 0, 0, 0) if self.viewer_mode else (0, 0, 0, 0)
            if live_sidebar_layout:
                self.top_container.size_hint_y = None
                self.top_container.height = 0
                self.top_container.opacity = 0
            elif self.viewer_mode:
                if self.viewer_toolbar_in_titlebar:
                    self.top_container.opacity = 1
                    self.top_container.size_hint_y = 0.12 if compact else 0.10
                    self.top_container.height = dp(0)
                else:
                    self.top_container.opacity = 0
                    self.top_container.size_hint_y = None
                    self.top_container.height = 0
            else:
                self.top_container.opacity = 1
                if self.external_status_bar:
                    if compact:
                        self.top_container.size_hint_y = None
                        self.top_container.height = max(float(dp(78)), min(float(dp(108)), h * 0.16))
                    else:
                        self.top_container.size_hint_y = 0.16
                        self.top_container.height = dp(0)
                elif compact:
                    self.top_container.size_hint_y = None
                    self.top_container.height = max(float(dp(118)), min(float(dp(170)), h * 0.24))
                else:
                    self.top_container.size_hint_y = 0.21
                    self.top_container.height = dp(0)

        if hasattr(self, "graphs_main_container"):
            self.graphs_main_container.spacing = dp(5) if tiny else (dp(6) if compact else dp(10))
            if live_sidebar_layout:
                self.graphs_main_container.padding = 0
                self.graphs_main_container.size_hint_y = 1
                self.graphs_main_container.height = dp(0)
            elif self.viewer_mode and not self.viewer_toolbar_in_titlebar:
                self.graphs_main_container.size_hint_y = 1
                self.graphs_main_container.height = dp(0)
                if hasattr(self, "viewer_graphs_panel"):
                    self.viewer_graphs_panel.size_hint_x = 0.72
                if hasattr(self, "viewer_sidebar_panel"):
                    self.viewer_sidebar_panel.size_hint_x = 0.28
            elif self.viewer_mode or (not compact):
                self.graphs_main_container.size_hint_y = 1
                self.graphs_main_container.height = dp(0)
            else:
                self.graphs_main_container.size_hint_y = 1
                self.graphs_main_container.height = dp(0)

        if hasattr(self, "graphs_container"):
            self.graphs_container.spacing = dp(3) if tiny else (dp(4) if compact else dp(5))
            if live_sidebar_layout:
                self.graphs_container.size_hint_x = 1
            self._update_graph_row_layout()

        if live_sidebar_layout:
            self._update_primary_block_layout()
        elif self.viewer_mode and not self.viewer_toolbar_in_titlebar:
            self._update_viewer_primary_block_layout()

        if hasattr(self, "_bed_panel"):
            if self.viewer_mode:
                if not self.viewer_toolbar_in_titlebar:
                    self._bed_panel.size_hint_x = 1
                    self._bed_panel.width = dp(0)
                    self._bed_panel.size_hint_y = None
                    viewer_controls_h = float(dp(132))
                    if hasattr(self, "viewer_buttons_col"):
                        try:
                            viewer_controls_h = max(viewer_controls_h, float(self.viewer_buttons_col.height or 0) + float(dp(16)))
                        except Exception:
                            viewer_controls_h = float(dp(132))
                    if hasattr(self, "viewer_playback_panel"):
                        try:
                            viewer_controls_h = max(
                                viewer_controls_h,
                                float(self.viewer_buttons_col.height or 0)
                                + float(self.viewer_playback_panel.height or 0)
                                + float(dp(24)),
                            )
                        except Exception:
                            pass
                    try:
                        viewer_controls_h = max(viewer_controls_h, float(self._bed_panel.minimum_height or 0))
                    except Exception:
                        pass
                    self._bed_panel.height = viewer_controls_h
                    self._bed_panel.opacity = 1
                    self._bed_panel.padding = dp(6)
                    self._bed_panel.spacing = dp(4)
                elif self.viewer_toolbar_in_titlebar:
                    self._bed_panel.size_hint_x = None
                    self._bed_panel.width = 0
                    self._bed_panel.opacity = 0
                else:
                    self._bed_panel.size_hint_x = None
                    self._bed_panel.width = min(float(dp(286)), max(float(dp(180)), w * 0.30))
                    self._bed_panel.opacity = 1
            elif live_sidebar_layout:
                hide_bed = bool(metrics.get("hide_bed"))
                self._bed_panel.size_hint_x = 1
                self._bed_panel.width = dp(0)
                self._bed_panel.size_hint_y = None
                self._bed_panel.padding = (0, 0, 0, 0) if self.grid_tile_layout else (dp(6) if compact else dp(8))
                self._bed_panel.spacing = dp(5) if tiny else dp(6)
                self._bed_panel.height = 0 if hide_bed else float(metrics.get("bed_height", dp(78)))
                self._bed_panel.opacity = 0 if hide_bed else 1
                self._bed_panel.disabled = bool(hide_bed)
            elif self._use_dashboard_grid_layout():
                self._bed_panel.size_hint = (None, None)
                self._bed_panel.padding = (0, 0, 0, 0)
                self._bed_panel.spacing = dp(4)
                self._bed_panel.opacity = 1
                self._bed_panel.disabled = False
            else:
                self._bed_panel.width = dp(0)
                self._bed_panel.size_hint_x = 0.28 if compact else 0.30

        if hasattr(self, "camera_container"):
            if self.viewer_mode:
                self.camera_container.opacity = 1
                if not self.viewer_toolbar_in_titlebar:
                    self.camera_container.size_hint_x = 1
                    self.camera_container.width = dp(0)
                    self.camera_container.size_hint_y = None
                    viewer_cam_w = 0.0
                    try:
                        viewer_cam_w = float(self.camera_container.width or 0)
                    except Exception:
                        viewer_cam_w = 0.0
                    if viewer_cam_w <= 1.0 and hasattr(self, "viewer_sidebar_panel"):
                        try:
                            viewer_cam_w = max(
                                float(dp(180)),
                                float(self.viewer_sidebar_panel.width or 0) - float(dp(6)),
                            )
                        except Exception:
                            viewer_cam_w = float(dp(220))
                    aspect = 0.75
                    try:
                        texture = getattr(getattr(self.camera_widget, "image_widget", None), "texture", None)
                        if texture and texture.size and texture.size[0] > 0:
                            aspect = max(0.2, min(2.0, float(texture.size[1]) / float(texture.size[0])))
                    except Exception:
                        aspect = 0.75
                    self.camera_container.height = max(float(dp(80)), viewer_cam_w * aspect)
                elif self.viewer_toolbar_in_titlebar:
                    self.camera_container.size_hint_x = None
                    self.camera_container.width = min(float(dp(190)), max(float(dp(104)), w * 0.16))
                else:
                    self.camera_container.size_hint_x = None
                    self.camera_container.width = min(float(dp(220)), max(float(dp(132)), w * 0.18))
            elif live_sidebar_layout:
                hide_camera = bool(metrics.get("hide_camera"))
                self.camera_container.opacity = 0 if hide_camera else 1
                self.camera_widget.opacity = 0 if hide_camera else 1
                self.camera_container.size_hint_x = 1
                self.camera_container.width = dp(0)
                self.camera_container.size_hint_y = 1
                self.camera_container.height = dp(0)
            elif self._use_dashboard_grid_layout():
                self.camera_container.size_hint = (None, None)
                self.camera_container.opacity = 1
                self.camera_widget.opacity = 1
            else:
                if metrics.get("ultra_tiny"):
                    self.camera_container.size_hint_x = None
                    self.camera_container.width = 0
                    self.camera_container.opacity = 0
                    self.camera_widget.opacity = 0
                else:
                    self.camera_container.opacity = 1
                    self.camera_widget.opacity = 1
                    self.camera_container.width = dp(0)
                    self.camera_container.size_hint_x = 0.20 if tiny else (0.24 if compact else 0.35)

        if hasattr(self, "values_container"):
            self.values_container.spacing = dp(6) if compact else dp(10)
            if live_sidebar_layout:
                self.values_container.size_hint_x = 1
                self.values_container.size_hint_y = 1
                self.values_container.spacing = dp(0)
            elif self._use_dashboard_grid_layout():
                self.values_container.size_hint = (None, None)
                self.values_container.spacing = dp(0)
            elif not self.viewer_mode:
                self.values_container.size_hint_x = 0.30 if compact else 0.35

        if live_sidebar_layout and hasattr(self, "tile_sidebar_container"):
            self.tile_sidebar_container.spacing = 0
            self.tile_sidebar_container.size_hint = (1, 1)
            self._update_tile_sidebar_host_height()
        if live_sidebar_layout and hasattr(self, "tile_gap_top"):
            self.tile_gap_top.height = 0
        if live_sidebar_layout and hasattr(self, "patient_info_panel"):
            patient_h = float(metrics.get("patient_info_height", dp(70)))
            self.patient_info_panel.size_hint_y = None
            self.patient_info_panel.height = patient_h
            patient_pad_y = dp(3)
            self.patient_info_panel.padding = (dp(7), patient_pad_y, dp(7), patient_pad_y)
            self.patient_info_panel.spacing = dp(1)
            info_labels = (
                getattr(self, "patient_info_name_label", None),
                getattr(self, "patient_info_history_label", None),
                getattr(self, "patient_info_age_label", None),
                getattr(self, "patient_info_admitted_label", None),
            )
            inner_h = max(float(dp(48)), patient_h - float(patient_pad_y * 2) - float(dp(3)))
            name_h = min(float(dp(19)), max(float(dp(16)), inner_h * 0.28))
            row_h = max(float(dp(14)), (inner_h - name_h) / 3.0)
            for idx, lbl in enumerate(info_labels):
                if lbl is not None:
                    lbl.height = name_h if idx == 0 else row_h
                    lbl.font_size = dp(10) if tiny else dp(10.5)
            if hasattr(self, "patient_info_name_label"):
                self.patient_info_name_label.font_size = dp(11) if tiny else dp(12)
            # Запоминаем базовый padding/высоты, чтобы пустой режим мог идемпотентно
            # пересчитывать вертикальное центрирование, не накапливая ошибок.
            self._patient_info_base_padding = (dp(7), float(patient_pad_y), dp(7), float(patient_pad_y))
            self._patient_info_base_row_h = float(row_h)
            self._sync_patient_info_empty_style()
        if live_sidebar_layout and hasattr(self, "tile_gap_patient_camera"):
            self.tile_gap_patient_camera.height = 0
        if live_sidebar_layout and hasattr(self, "tile_gap_camera_bed"):
            hide_bed_for_gap = bool(metrics.get("hide_bed"))
            hide_cam_for_gap = bool(metrics.get("hide_camera"))
            # Гэп камера-кнопки скрываем, если нет камеры или нет кнопок (или обоих).
            self.tile_gap_camera_bed.height = 0 if (hide_cam_for_gap or hide_bed_for_gap) else float(metrics.get("gap_camera_bed", 0.0))
            self.tile_gap_camera_bed.opacity = 0 if (hide_cam_for_gap or hide_bed_for_gap) else 1
        if live_sidebar_layout and hasattr(self, "tile_gap_bed_values"):
            self.tile_gap_bed_values.height = float(metrics.get("gap_bed_values", 0.0))
            self.tile_gap_bed_values.opacity = 1
        if live_sidebar_layout and hasattr(self, "tile_gap_bottom"):
            if not bool(metrics.get("top_aligned_sidebar")):
                self.tile_gap_bottom.height = 0
        if live_sidebar_layout and hasattr(self, "tile_graphs_panel"):
            self.tile_graphs_panel.size_hint_x = float(metrics.get("graph_ratio", 0.72))
            self.tile_graphs_panel.padding = self._get_primary_block_padding(compact=compact, tiny=tiny)
        if live_sidebar_layout and hasattr(self, "tile_sidebar_panel"):
            self.tile_sidebar_panel.size_hint_x = float(metrics.get("sidebar_ratio", 0.28))
            self.tile_sidebar_panel.spacing = dp(5) if tiny else (dp(6) if compact else dp(8))
            self.tile_sidebar_panel.padding = self._get_primary_block_padding(compact=compact, tiny=tiny)
        if live_sidebar_layout and hasattr(self, "tile_values_panel"):
            # size/padding задаются централизованно в _update_value_grid_layout
            pass
        if live_sidebar_layout and hasattr(self, "values_grid"):
            if self._value_grid_cols == 1:
                self.values_grid.spacing = float(metrics.get("values_spacing", dp(8)))
            else:
                self.values_grid.spacing = float(metrics.get("values_spacing", dp(10)))
            self._update_value_grid_layout()
            self._update_tile_camera_panel_layout()
            self._redistribute_tile_sidebar_gaps()

        for graph in getattr(self, "graph_slots", {}).values():
            if hasattr(graph, "set_layout_density"):
                graph.set_layout_density(profile_name)
        for widget in getattr(self, "value_slots", {}).values():
            if hasattr(widget, "set_layout_density"):
                widget.set_layout_density(profile_name)

        if self.viewer_mode and hasattr(self, "patient_title_label"):
            if self.viewer_toolbar_in_titlebar:
                title_fs = dp(9) if compact else dp(10)
                name_fs = dp(11) if compact else dp(13)
                title_h = dp(14) if compact else dp(16)
                name_h = dp(22) if compact else dp(26)
            else:
                title_fs = dp(10) if compact else dp(12)
                name_fs = dp(12) if compact else dp(15)
                title_h = dp(18) if compact else dp(22)
                name_h = dp(30) if compact else dp(38)
            self.patient_title_label.font_size = title_fs
            self.patient_title_label.height = title_h
            self.patient_name_label.font_size = name_fs
            self.patient_name_label.height = name_h

        if self.viewer_mode and not self.viewer_toolbar_in_titlebar and hasattr(self, "patient_container"):
            self.patient_container.size_hint_y = None
            self.patient_container.height = dp(58) if compact else dp(68)
            self.patient_container.padding = (dp(8), dp(6), dp(8), dp(6))
            self.patient_container.spacing = dp(2)

        if self.viewer_mode and not self.viewer_toolbar_in_titlebar and hasattr(self, "viewer_graphs_panel"):
            # Чуть уменьшаем долю графиков, чтобы у правой колонки было место
            # под камеру + ФИО + 3 кнопки + 4 индикатора без переполнения.
            self.viewer_graphs_panel.size_hint_x = 0.72 if compact else 0.76
            self.viewer_graphs_panel.padding = (dp(6), dp(6), dp(6), dp(6)) if compact else (dp(8), dp(8), dp(8), dp(8))

        if self.viewer_mode and not self.viewer_toolbar_in_titlebar and hasattr(self, "viewer_sidebar_panel"):
            self.viewer_sidebar_panel.size_hint_x = 0.28 if compact else 0.24
            self.viewer_sidebar_panel.padding = (dp(6), dp(6), dp(6), dp(6)) if compact else (dp(7), dp(7), dp(7), dp(7))
        if self.viewer_mode and not self.viewer_toolbar_in_titlebar and hasattr(self, "viewer_sidebar_container"):
            self.viewer_sidebar_container.spacing = dp(6) if compact else dp(8)
            # Приводим все элементы правой колонки к одинаковой рабочей ширине.
            for _w in (
                getattr(self, "camera_container", None),
                getattr(self, "patient_container", None),
                getattr(self, "_bed_panel", None),
                getattr(self, "values_container", None),
            ):
                if _w is None:
                    continue
                try:
                    _w.size_hint_x = 1
                    _w.width = dp(0)
                except Exception:
                    continue
            # Адаптивная высота блока 4-х индикаторов: чем выше окно, тем больше
            # карточки, но не меньше dp(140), чтобы текст не наезжал.
            try:
                self_h = float(self.height or 0)
            except Exception:
                self_h = 0.0
            if hasattr(self, "values_container") and self.values_container is not None:
                values_h = max(float(dp(140)), min(float(dp(220)), self_h * 0.30))
                self.values_container.size_hint_y = None
                self.values_container.height = values_h

    def _apply_view_window_to_graphs(self):
        """Применить текущее окно просмотра к графикам (для оси X, hover и фильтрации)."""
        if not self.viewer_mode:
            return
        if not (self._view_start and self._view_end):
            return
        try:
            view_span_seconds = max(1, int((self._view_end - self._view_start).total_seconds()))
        except Exception:
            view_span_seconds = 60
        self._refresh_viewer_auto_periods()
        chosen_seconds = self._get_auto_resolution_seconds_for_span(view_span_seconds)
        self._viewer_resolution_seconds = chosen_seconds
        for g in getattr(self, "graph_slots", {}).values():
            try:
                g.clear_hover()
                g.set_absolute_time_window(self._view_start, self._view_end)
                g.set_resolution_seconds(chosen_seconds)
            except Exception:
                pass

    def _set_view_span_minutes(self, minutes: int, center_time: datetime | None = None):
        """Задать длину окна просмотра (viewer_mode), центрируя по center_time (или текущему центру)."""
        if not self.viewer_mode:
            return
        if not (self._full_start and self._full_end):
            return
        full_span = max(0.0, (self._full_end - self._full_start).total_seconds())
        if full_span <= 0:
            return

        target_span = min(full_span, max(60.0, float(minutes) * 60.0))
        view_start = self._view_start or self._full_start
        view_end = self._view_end or self._full_end
        if view_end <= view_start:
            view_start, view_end = self._full_start, self._full_end
        center = center_time if center_time is not None else (view_start + (view_end - view_start) / 2)

        new_start = center - timedelta(seconds=target_span / 2.0)
        if new_start < self._full_start:
            new_start = self._full_start
        max_start = self._full_end - timedelta(seconds=target_span)
        if new_start > max_start:
            new_start = max_start
        new_end = new_start + timedelta(seconds=target_span)

        self._view_start, self._view_end = new_start, new_end
        self._apply_view_window_to_graphs()

        # После изменения масштаба скрываем hover до нового движения мыши
        try:
            self._hover_suspend_until_leave = True
            self._hover_suspend_base_pos = self._last_mouse_pos
            for g in getattr(self, "graph_slots", {}).values():
                g.clear_hover()
        except Exception:
            pass

    def _get_view_scale_options(self) -> list[tuple[str, int]]:
        """Список доступных масштабов без дубликатов фактического окна просмотра."""
        base_scales = [
            ("1 день", 24 * 60),
            ("4 часа", 4 * 60),
            ("2 часа", 2 * 60),
            ("1 час", 60),
            ("30 минут", 30),
            ("15 минут", 15),
            ("5 минут", 5),
            ("1 минута", 1),
        ]
        if not (self._full_start and self._full_end):
            return base_scales

        try:
            full_span_minutes = max(
                1,
                int(round((self._full_end - self._full_start).total_seconds() / 60.0)),
            )
        except Exception:
            return base_scales

        options: list[tuple[str, int]] = []
        seen_targets: set[int] = set()
        full_period_added = False

        for title, minutes in base_scales:
            actual_minutes = min(full_span_minutes, minutes)
            if actual_minutes in seen_targets:
                continue
            seen_targets.add(actual_minutes)

            if actual_minutes == full_span_minutes and minutes > full_span_minutes:
                if full_period_added:
                    continue
                options.append(("Весь период", actual_minutes))
                full_period_added = True
            else:
                options.append((title, actual_minutes))

        return options

    def _pan_view_by_pixels(self, dx_px: float, graph_widget):
        """Сдвинуть окно просмотра пропорционально drag на графике."""
        if not self.viewer_mode:
            return
        if not (self._full_start and self._full_end and self._graph_pan_start_view_start and self._graph_pan_start_view_end):
            return

        plot_width = None
        try:
            if getattr(graph_widget, "_plot_area", None):
                _x0, _y0, plot_width, _h = graph_widget._plot_area
        except Exception:
            plot_width = None
        if not plot_width or plot_width <= 1:
            try:
                plot_width = float(graph_widget.graph_container.width) - float(dp(16))
            except Exception:
                plot_width = 1.0
        plot_width = max(1.0, float(plot_width))

        start_span = (self._graph_pan_start_view_end - self._graph_pan_start_view_start).total_seconds()
        full_span = (self._full_end - self._full_start).total_seconds()
        if start_span <= 0 or full_span <= 0:
            return

        shift_seconds = -float(dx_px) * (start_span / plot_width)
        new_start = self._graph_pan_start_view_start + timedelta(seconds=shift_seconds)
        max_start = self._full_end - timedelta(seconds=start_span)
        if new_start < self._full_start:
            new_start = self._full_start
        if new_start > max_start:
            new_start = max_start
        new_end = new_start + timedelta(seconds=start_span)

        self._view_start, self._view_end = new_start, new_end
        self._apply_view_window_to_graphs()

    def _shift_view_window_by_seconds(self, delta_seconds: float) -> bool:
        """Сдвинуть окно просмотра на delta_seconds, оставаясь в пределах full-диапазона."""
        if not self.viewer_mode:
            return False
        if not (self._full_start and self._full_end and self._view_start and self._view_end):
            return False
        try:
            span = max(1.0, float((self._view_end - self._view_start).total_seconds()))
            full_span = max(1.0, float((self._full_end - self._full_start).total_seconds()))
        except Exception:
            return False
        if full_span <= 0 or span <= 0:
            return False

        max_start = self._full_end - timedelta(seconds=span)
        new_start = self._view_start + timedelta(seconds=float(delta_seconds))
        if new_start < self._full_start:
            new_start = self._full_start
        if new_start > max_start:
            new_start = max_start
        new_end = new_start + timedelta(seconds=span)

        changed = (abs((new_start - self._view_start).total_seconds()) > 0.01)
        self._view_start, self._view_end = new_start, new_end
        self._apply_view_window_to_graphs()
        if self.viewer_mode:
            try:
                self._refresh_viewer_value_indicators_to_window_end()
                self._update_viewer_image_for_time(self._view_end)
            except Exception:
                pass
        return changed

    def _viewer_seek_to_start(self, *_args):
        self._set_viewer_playback_state(0)
        if not (self._full_start and self._view_start and self._view_end):
            return
        try:
            span = max(1.0, float((self._view_end - self._view_start).total_seconds()))
        except Exception:
            return
        self._view_start = self._full_start
        self._view_end = self._full_start + timedelta(seconds=span)
        if self._full_end and self._view_end > self._full_end:
            self._view_end = self._full_end
            self._view_start = self._full_end - timedelta(seconds=span)
        self._apply_view_window_to_graphs()
        self._refresh_viewer_value_indicators_to_window_end()
        self._update_viewer_image_for_time(self._view_end)

    def _viewer_seek_to_end(self, *_args):
        self._set_viewer_playback_state(0)
        if not (self._full_end and self._view_start and self._view_end):
            return
        try:
            span = max(1.0, float((self._view_end - self._view_start).total_seconds()))
        except Exception:
            return
        self._view_end = self._full_end
        self._view_start = self._full_end - timedelta(seconds=span)
        if self._full_start and self._view_start < self._full_start:
            self._view_start = self._full_start
            self._view_end = self._full_start + timedelta(seconds=span)
        self._apply_view_window_to_graphs()
        self._refresh_viewer_value_indicators_to_window_end()
        self._update_viewer_image_for_time(self._view_end)

    def _set_viewer_playback_speed(self, speed: int, *_args):
        try:
            sp = int(speed)
        except Exception:
            sp = 1
        if sp not in (1, 2, 4, 8):
            sp = 1
        self._viewer_playback_speed = sp
        if hasattr(self, "viewer_speed_button") and self.viewer_speed_button is not None:
            self.viewer_speed_button.text = f"x{sp}"

    def _cycle_viewer_playback_speed(self, *_args):
        current = int(getattr(self, "_viewer_playback_speed", 1) or 1)
        nxt = {1: 2, 2: 4, 4: 8, 8: 1}.get(current, 1)
        self._set_viewer_playback_speed(nxt)

    def _set_viewer_playback_state(self, direction: int):
        """Установить состояние проигрывания: -1 назад, 0 пауза, 1 вперед."""
        try:
            d = int(direction)
        except Exception:
            d = 0
        if d not in (-1, 0, 1):
            d = 0
        self._viewer_playback_state = d
        self._update_viewer_playback_button_states()
        if d == 0:
            self._stop_viewer_playback_timer()
        else:
            self._ensure_viewer_playback_timer()

    def _update_viewer_playback_button_states(self) -> None:
        state = int(getattr(self, "_viewer_playback_state", 0) or 0)
        btn_back = getattr(self, "viewer_play_back_btn", None)
        btn_pause = getattr(self, "viewer_pause_btn", None)
        btn_fwd = getattr(self, "viewer_play_fwd_btn", None)
        try:
            if btn_back is not None:
                apply_rounded_button(
                    btn_back,
                    base_rgba=(0.36, 0.43, 0.62, 1) if state == -1 else UI_BTN_MUTED,
                    radius_px=dp(10),
                    border_alpha=0.08,
                )
            if btn_pause is not None:
                apply_rounded_button(
                    btn_pause,
                    base_rgba=(0.72, 0.51, 0.19, 1) if state == 0 else UI_BTN_MUTED,
                    radius_px=dp(10),
                    border_alpha=0.08,
                )
            if btn_fwd is not None:
                apply_rounded_button(
                    btn_fwd,
                    base_rgba=(0.24, 0.56, 0.30, 1) if state == 1 else UI_BTN_MUTED,
                    radius_px=dp(10),
                    border_alpha=0.08,
                )
        except Exception:
            pass

    def _ensure_viewer_playback_timer(self) -> None:
        if self._viewer_playback_event is not None:
            return
        self._viewer_playback_event = Clock.schedule_interval(self._tick_viewer_playback, 0.2)

    def _stop_viewer_playback_timer(self) -> None:
        if self._viewer_playback_event is None:
            return
        try:
            Clock.unschedule(self._viewer_playback_event)
        except Exception:
            pass
        self._viewer_playback_event = None

    def _tick_viewer_playback(self, dt: float):
        direction = int(getattr(self, "_viewer_playback_state", 0) or 0)
        if direction == 0:
            self._stop_viewer_playback_timer()
            return
        speed = int(getattr(self, "_viewer_playback_speed", 1) or 1)
        delta_seconds = float(dt) * float(self._viewer_playback_base_rate) * float(speed) * float(direction)
        moved = self._shift_view_window_by_seconds(delta_seconds)
        if moved:
            return
        # Дошли до границы диапазона — ставим паузу.
        self._set_viewer_playback_state(0)

    def _normalize_graph_display_mode(self, mode: str | None) -> str:
        normalized = str(mode or "").strip().lower()
        if normalized in {"bars", "rect", "rects", "rectangle", "rectangles", "bucket", "buckets"}:
            return "bars"
        if normalized in {"points", "point", "line", "raw"}:
            return "points"
        return "bars" if self.viewer_mode else "points"

    def _default_graph_settings(self, slot_id: str) -> dict:
        return {
            "display_mode": "bars" if self.viewer_mode else "points",
            "show_time_axis": True if self.viewer_mode else slot_id == "graph2",
        }

    def _graph_slot_ids(self) -> tuple[str, ...]:
        slots = getattr(self, "graph_slots", None)
        if isinstance(slots, dict) and slots:
            return tuple(slots.keys())
        return ("graph1", "graph2", "graph3", "graph4")

    def _value_slot_ids(self) -> tuple[str, ...]:
        slots = getattr(self, "value_slots", None)
        if isinstance(slots, dict) and slots:
            return tuple(slots.keys())
        return ("value1", "value2", "value3", "value4", "value5", "value6")

    def _load_graph_settings_from_config(self) -> dict:
        raw = self.monitor_config.get("graph_settings", {}) if isinstance(self.monitor_config, dict) else {}
        settings: dict[str, dict] = {}
        for slot_id in self._graph_slot_ids():
            defaults = self._default_graph_settings(slot_id)
            slot_raw = raw.get(slot_id, {}) if isinstance(raw, dict) else {}
            if not isinstance(slot_raw, dict):
                slot_raw = {}
            settings[slot_id] = {
                "display_mode": self._normalize_graph_display_mode(slot_raw.get("display_mode", defaults["display_mode"])),
                "show_time_axis": bool(slot_raw.get("show_time_axis", defaults["show_time_axis"])),
            }
        return settings

    def _get_graph_settings(self, slot_id: str) -> dict:
        if not isinstance(getattr(self, "graph_settings", None), dict):
            self.graph_settings = {}
        if slot_id not in self.graph_settings:
            self.graph_settings[slot_id] = self._default_graph_settings(slot_id)
        settings = self.graph_settings[slot_id]
        settings["display_mode"] = self._normalize_graph_display_mode(settings.get("display_mode"))
        settings["show_time_axis"] = bool(settings.get("show_time_axis", self._default_graph_settings(slot_id)["show_time_axis"]))
        return settings

    def _apply_graph_settings_to_widget(self, slot_id: str, graph=None) -> None:
        graph = graph or getattr(self, "graph_slots", {}).get(slot_id)
        if graph is None:
            return
        settings = self._get_graph_settings(slot_id)
        mode = settings.get("display_mode", "bars" if self.viewer_mode else "points")
        try:
            graph.set_time_axis_visible(bool(settings.get("show_time_axis", True)))
            graph.set_display_mode(mode)
            res_seconds = self._get_resolution_seconds_for_graphs()
            if mode == "bars":
                graph.set_resolution_seconds(res_seconds if res_seconds is not None else 60)
            elif not self.viewer_mode:
                graph.set_resolution_seconds(None)
        except Exception:
            pass

    def _persist_graph_settings(self) -> None:
        self.monitor_config["graph_settings"] = {
            slot_id: dict(self._get_graph_settings(slot_id))
            for slot_id in self._graph_slot_ids()
        }
        self._save_monitor_config()

    def _load_dashboard_grid_config(self) -> dict:
        if self.viewer_mode:
            try:
                cfg = LayoutConfig.load_viewer_dashboard_grid()
            except Exception:
                cfg = LayoutConfig.create_default_dashboard_grid("graphs_2_values_4")
            return self._normalize_dashboard_grid_config(cfg)
        cfg = self.monitor_config.get("dashboard_grid") if isinstance(self.monitor_config, dict) else None
        if not isinstance(cfg, dict):
            try:
                cfg = LayoutConfig.create_default_dashboard_grid()
            except Exception:
                cfg = {"cols": 5, "rows": 4, "items": {}}
        return self._normalize_dashboard_grid_config(cfg)

    def _normalize_dashboard_grid_config(self, cfg: dict) -> dict:
        cfg = dict(cfg or {})
        cols = max(1, int(cfg.get("cols", 5) or 5))
        rows = max(1, int(cfg.get("rows", 4) or 4))
        items = cfg.get("items", {}) if isinstance(cfg.get("items", {}), dict) else {}
        normalized = {"cols": cols, "rows": rows, "items": {}}
        for item_id, item in items.items():
            if not isinstance(item, dict):
                continue
            if str(item_id) == "settings_panel":
                continue
            normalized_item_id = "patient_panel" if str(item_id) == "bed_panel" and "patient_panel" not in items else str(item_id)
            col = max(0, min(cols - 1, int(item.get("col", 0) or 0)))
            row = max(0, min(rows - 1, int(item.get("row", 0) or 0)))
            colspan = max(1, min(cols - col, int(item.get("colspan", 1) or 1)))
            rowspan = max(1, min(rows - row, int(item.get("rowspan", 1) or 1)))
            normalized["items"][normalized_item_id] = {
                "col": col,
                "row": row,
                "colspan": colspan,
                "rowspan": rowspan,
                "visible": bool(item.get("visible", True)),
            }
        return normalized

    def _use_dashboard_grid_layout(self) -> bool:
        return bool(self.grid_tile_layout)

    def _set_graph_display_mode(self, slot_id: str, mode: str) -> None:
        settings = self._get_graph_settings(slot_id)
        settings["display_mode"] = self._normalize_graph_display_mode(mode)
        self._apply_graph_settings_to_widget(slot_id)
        self._persist_graph_settings()

    def _set_graph_time_axis_visible(self, slot_id: str, visible: bool) -> None:
        settings = self._get_graph_settings(slot_id)
        settings["show_time_axis"] = bool(visible)
        self._apply_graph_settings_to_widget(slot_id)
        self._persist_graph_settings()

    def _show_graph_context_menu(self, slot_id: str, clicked_time: datetime | None = None):
        """Настройки графика по правому клику."""
        self._clear_dashboard_grid_hover()
        settings = self._get_graph_settings(slot_id)
        current_mode = settings.get("display_mode", "bars" if self.viewer_mode else "points")
        show_time_axis = bool(settings.get("show_time_axis", True))
        if self.manager is not None:
            try:
                from components.action_list_screen import ActionListScreen

                nav_screen_name = self._get_navigation_screen_name()
                screen = ActionListScreen(
                    name=f"{nav_screen_name}_{slot_id}_graph_actions",
                    title_text="Настройки графика",
                    subtitle_text="Тип отображения, параметр и шкала времени",
                    previous_screen=nav_screen_name,
                )
                sections = [
                    (
                        "Тип отображения",
                        [
                            {
                                "text": ("Выбрано: " if current_mode == "bars" else "") + "Прямоугольниками",
                                "on_press": lambda sid=slot_id: self._set_graph_display_mode(sid, "bars"),
                                "return_back": True,
                                "base_rgba": UI_BTN_SUCCESS if current_mode == "bars" else (0.22, 0.22, 0.24, 1),
                            },
                            {
                                "text": ("Выбрано: " if current_mode == "points" else "") + "Поточечно",
                                "on_press": lambda sid=slot_id: self._set_graph_display_mode(sid, "points"),
                                "return_back": True,
                                "base_rgba": UI_BTN_SUCCESS if current_mode == "points" else (0.22, 0.22, 0.24, 1),
                            },
                        ],
                    ),
                    (
                        "Отображаемый параметр",
                        [
                            {
                                "text": "Открыть выбор параметра",
                                "on_press": lambda sid=slot_id: self._open_parameter_selection_for_slot(sid),
                                "return_back": False,
                                "base_rgba": UI_BTN_MUTED,
                            }
                        ],
                    ),
                    (
                        "Шкала таймлайна",
                        [
                            {
                                "text": ("Выбрано: " if show_time_axis else "") + "Включить шкалу таймлайна",
                                "on_press": lambda sid=slot_id: self._set_graph_time_axis_visible(sid, True),
                                "return_back": True,
                                "base_rgba": UI_BTN_SUCCESS if show_time_axis else (0.22, 0.22, 0.24, 1),
                            },
                            {
                                "text": ("Выбрано: " if not show_time_axis else "") + "Отключить шкалу таймлайна",
                                "on_press": lambda sid=slot_id: self._set_graph_time_axis_visible(sid, False),
                                "return_back": True,
                                "base_rgba": UI_BTN_SUCCESS if not show_time_axis else (0.22, 0.22, 0.24, 1),
                            },
                        ],
                    ),
                ]
                if self.viewer_mode:
                    scale_actions = []
                    for title, mins in self._get_view_scale_options():
                        scale_actions.append(
                            {
                                "text": title,
                                "on_press": lambda m=mins, ct=clicked_time: self._set_view_span_minutes(m, center_time=ct),
                                "return_back": True,
                                "base_rgba": (0.22, 0.22, 0.24, 1),
                            }
                        )
                    sections.append(("Выбор масштаба", scale_actions))
                screen.set_sections(sections)
                if self._replace_managed_screen(screen):
                    return
            except Exception:
                pass

        host_w = float(self.width or Window.width or dp(320))
        host_h = float(self.height or Window.height or dp(240))
        ultra = host_w <= float(dp(520)) or host_h <= float(dp(420))
        compact = host_w <= float(dp(720)) or host_h <= float(dp(540))

        menu_spacing = dp(4) if ultra else (dp(6) if compact else dp(8))
        menu_pad = (
            (dp(8), dp(8), dp(8), dp(6))
            if ultra
            else ((dp(10), dp(10), dp(10), dp(8)) if compact else (dp(12), dp(12), dp(12), dp(10)))
        )
        menu = BoxLayout(orientation="vertical", spacing=menu_spacing, padding=menu_pad)
        apply_rounded_panel(menu, base_rgba=(0.11, 0.11, 0.12, 1), radius_px=dp(12), border_alpha=0.12)
        btn_h = dp(32) if ultra else (dp(36) if compact else dp(42))
        btn_fs = dp(11) if ultra else (dp(12) if compact else dp(13))
        section_h = dp(16) if ultra else (dp(18) if compact else dp(20))
        section_fs = dp(10) if ultra else (dp(11) if compact else dp(12))
        max_popup_w = dp(360) if ultra else (dp(440) if compact else dp(520))
        popup_w = max(float(dp(156)), min(float(max_popup_w), host_w - float(dp(12))))

        popup = Popup(
            title="Настройки графика",
            content=menu,
            size_hint=(None, None),
            size=(popup_w, dp(220)),
            auto_dismiss=True,
        )
        apply_popup_theme(popup)

        section_param = Label(
            text="Выбор параметра для отображения",
            size_hint_y=None,
            height=section_h,
            font_size=section_fs,
            color=UI_TEXT_MUTED,
            halign="left",
            valign="middle",
            text_size=(0, 0),
        )
        section_param.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
        menu.add_widget(section_param)

        btn_param = Button(
            text="Открыть выбор параметра",
            size_hint_y=None,
            height=btn_h,
            font_size=btn_fs,
            background_color=(0, 0, 0, 0),
            background_normal="",
            background_down="",
        )
        btn_param.color = UI_TEXT_PRIMARY
        apply_rounded_button(btn_param, base_rgba=UI_BTN_MUTED)
        btn_param.bind(on_press=lambda *_: (popup.dismiss(), self._open_parameter_selection_for_slot(slot_id)))
        menu.add_widget(btn_param)

        if self.viewer_mode:
            section_scale = Label(
                text="Выбор масштаба",
                size_hint_y=None,
                height=section_h,
                font_size=section_fs,
                color=UI_TEXT_MUTED,
                halign="left",
                valign="middle",
                text_size=(0, 0),
            )
            section_scale.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0], None)))
            menu.add_widget(section_scale)

            scales = self._get_view_scale_options()
            for title, mins in scales:
                btn = Button(
                    text=title,
                    size_hint_y=None,
                    height=btn_h,
                    font_size=btn_fs,
                    background_color=(0, 0, 0, 0),
                    background_normal="",
                    background_down="",
                )
                btn.color = UI_TEXT_PRIMARY
                apply_rounded_button(btn, base_rgba=(0.22, 0.22, 0.24, 1))
                btn.bind(
                    on_press=lambda *_args, m=mins, ct=clicked_time: (
                        popup.dismiss(),
                        self._set_view_span_minutes(m, center_time=ct),
                    )
                )
                menu.add_widget(btn)

            # Динамическая высота popup под кол-во секций/кнопок
            total_items = 2 + 1 + len(scales)  # 2 секции + 1 кнопка параметра + кнопки масштаба
            content_h = (btn_h * (1 + len(scales))) + (section_h * 2) + (menu_spacing * max(0, total_items - 1)) + dp(18)
            popup.height = content_h + dp(56)  # title bar + separator
        else:
            total_items = 2  # секция + одна кнопка
            content_h = btn_h + section_h + (menu_spacing * max(0, total_items - 1)) + dp(18)
            popup.height = content_h + dp(56)

        popup.open()

    def _set_patient_label_text(self, text: str | None):
        t = (text or "").strip()
        if hasattr(self, "patient_name_label"):
            self.patient_name_label.text = t if t else "—"
        if self.viewer_mode and self._use_dashboard_grid_layout():
            self._sync_viewer_patient_dashboard_panel(t if t else None)

    def _sync_viewer_patient_dashboard_panel(self, name: str | None) -> None:
        """Синхронизировать patient_panel в модульной сетке bed viewer."""
        if not hasattr(self, "patient_info_panel"):
            return
        t = (name or "").strip()
        has_patient = bool(t and t not in ("—", "Нет данных о пациенте"))
        bed_text = str(getattr(self, "_current_bed_display_text", "") or "—").strip() or "Койка: —"
        study = getattr(self, "current_study", None) or {}
        history = str(study.get("worklist_numb") or study.get("patient_numb") or "—").strip() or "—"
        self._dashboard_patient_info_data = {
            "has_patient": has_patient,
            "bed": bed_text,
            "name": t if has_patient else "Пациент отсутствует",
            "history": history if has_patient else "—",
            "age": "—",
            "admitted": "—",
            "admitted_short": "—",
        }
        self._update_dashboard_patient_panel_layout()

    def _refresh_patient_context(self):
        """Подготовить таймлайн пациентов на период и выставить начальный текст ФИО."""
        if not self.viewer_mode:
            return
        if not self._is_database_online():
            self._set_patient_label_text(None)
            return
        if not (self.history_start and self.history_end):
            self._set_patient_label_text(None)
            return

        # Если выбрали study — это приоритет: обычно 1 пациент на весь период
        pid = None
        try:
            if self.current_study:
                pid = self.current_study.get("patient_id")
        except Exception:
            pid = None

        if pid is not None:
            try:
                pid_i = int(pid)
            except Exception:
                pid_i = None
            if pid_i is not None:
                name = self._patient_name_cache.get(pid_i)
                if name is None:
                    try:
                        name = self.data_source.get_patient_name(pid_i) or ""
                    except Exception:
                        name = ""
                    if name:
                        self._patient_name_cache[pid_i] = name
                self._patient_timeline = [
                    {"begin_dt": self.history_start, "end_dt": self.history_end, "patient_id": pid_i, "name": name}
                ]
                self._patient_starts = [self.history_start]
                self._patient_multi = False
                self._last_patient_id = pid_i
                self._set_patient_label_text(name or f"ID пациента: {pid_i}")
                return

        bed_id = self.data_source.get_current_bed_id()
        if bed_id is None:
            self._set_patient_label_text(None)
            return

        try:
            studies = self.data_source.get_studies_for_bed_between(int(bed_id), self.history_start, self.history_end)
        except Exception:
            studies = []

        timeline: list[dict] = []
        unique_pids: set[int] = set()
        for st in studies or []:
            bdt = st.get("begin_dt")
            edt = st.get("end_dt")
            pid = st.get("patient_id")
            if bdt is None or edt is None or pid is None:
                continue
            try:
                pid_i = int(pid)
            except Exception:
                continue
            name = self._patient_name_cache.get(pid_i)
            if name is None:
                try:
                    name = self.data_source.get_patient_name(pid_i) or ""
                except Exception:
                    name = ""
                if name:
                    self._patient_name_cache[pid_i] = name
            timeline.append({"begin_dt": bdt, "end_dt": edt, "patient_id": pid_i, "name": name})
            unique_pids.add(pid_i)

        timeline.sort(key=lambda x: x["begin_dt"])
        self._patient_timeline = timeline
        self._patient_starts = [x["begin_dt"] for x in timeline]
        self._patient_multi = len(unique_pids) > 1
        self._last_patient_id = None

        if not timeline:
            self._set_patient_label_text("Нет данных о пациенте")
        elif len(unique_pids) == 1:
            # один пациент на весь период
            only = next(iter(unique_pids))
            name = next((x.get("name") for x in timeline if x.get("patient_id") == only), "") or ""
            self._last_patient_id = only
            self._set_patient_label_text(name or f"ID пациента: {only}")
        else:
            self._set_patient_label_text("Несколько пациентов")

    def _patient_at_time(self, t: datetime) -> tuple[int | None, str | None]:
        """Найти пациента (id, name) по времени t по таймлайну study."""
        if not self._patient_timeline:
            return None, None
        if getattr(t, "tzinfo", None) is not None:
            t = t.replace(tzinfo=None)

        i = bisect_right(self._patient_starts, t) - 1
        if i < 0:
            return None, None
        # Попробуем текущий и далее (на случай одинаковых begin_dt)
        for j in range(i, min(i + 3, len(self._patient_timeline))):
            it = self._patient_timeline[j]
            bdt = it.get("begin_dt")
            edt = it.get("end_dt")
            if bdt is None or edt is None:
                continue
            try:
                if bdt <= t <= edt:
                    return it.get("patient_id"), it.get("name")
            except Exception:
                continue
        return None, None

    def _update_patient_label_for_time(self, t: datetime):
        """Если пациентов несколько — обновить ФИО при hover по времени."""
        if not self.viewer_mode or not hasattr(self, "patient_name_label"):
            return
        if not self._patient_multi:
            return
        pid, name = self._patient_at_time(t)
        if pid is None:
            if self.patient_name_label.text != "Несколько пациентов":
                self._set_patient_label_text("Несколько пациентов")
            self._last_patient_id = None
            return
        if self._last_patient_id == pid:
            return
        self._last_patient_id = pid
        self._set_patient_label_text((name or "").strip() or f"ID пациента: {pid}")
    
    def _load_available_signals(self):
        """Загрузка доступных сигналов из БД"""
        if self._is_database_online():
            try:
                # Показываем все параметры из signal_param (включая неактивные),
                # чтобы пользователь мог назначить любой измеряемый сигнал.
                self.available_signals = self.data_source.get_available_signals(include_inactive=True)
                print(f"[MonitorScreen] Загружено доступных сигналов из БД: {len(self.available_signals)}")
                for signal in self.available_signals[:5]:  # Показываем первые 5
                    print(f"  Signal ID: {signal['signal_id']}, Name: {signal['name']}, Unit: {signal['unit']}")
            except Exception as e:
                print(f"[MonitorScreen] Ошибка загрузки доступных сигналов: {e}")
                self.available_signals = []
    
    def _get_param_info(self) -> dict:
        """
        Получить информацию о параметрах с названиями из БД
        
        Returns:
            dict: Словарь с информацией о параметрах
        """
        # Базовые цвета и единицы измерения
        base_info = {
            'spo2': {'color': '#FF4444', 'unit': '%'},
            'pulse': {'color': '#44FF44', 'unit': 'уд/мин'},
            'breathing': {'color': '#4444FF', 'unit': 'вдох/мин'},
            'temperature': {'color': '#FFFF44', 'unit': '°C'}
        }
        
        param_info = {}
        
        # Если используется БД, получаем названия из signal_param
        if isinstance(self.data_source, DatabaseDataSource):
            for param_key in ['spo2', 'pulse', 'breathing', 'temperature']:
                signal_name = self.data_source.get_signal_name_by_key(param_key)
                param_info[param_key] = {
                    'title': signal_name,
                    'color': base_info[param_key]['color'],
                    'unit': base_info[param_key]['unit']
                }
        else:
            # Для тестового режима используем значения по умолчанию
            defaults = {
                'spo2': 'SPO2',
                'pulse': 'Пульс',
                'breathing': 'Дыхание',
                'temperature': 'Температура'
            }
            for param_key in ['spo2', 'pulse', 'breathing', 'temperature']:
                param_info[param_key] = {
                    'title': defaults[param_key],
                    'color': base_info[param_key]['color'],
                    'unit': base_info[param_key]['unit']
                }
        
        return param_info

    def _apply_slot_metas_to_widgets(self):
        """Обновить заголовки/цвета/единицы у графиков и цифровых блоков."""
        param_info = self._build_param_info()

        def get_meta_for_slot(slot_id: str):
            cur = self.slot_signal_ids.get(slot_id)
            if isinstance(self.data_source, DatabaseDataSource):
                if cur is None:
                    return None
                return param_info.get(f"signal_{cur}")
            return param_info.get(str(cur))

        # Графики
        for slot_id, graph in self.graph_slots.items():
            meta = get_meta_for_slot(slot_id)
            if not meta:
                continue
            graph.apply_param_meta(
                title=meta.get("name", ""),
                color=meta.get("color", "#FFFFFF"),
                unit=meta.get("unit", ""),
                min_value=meta.get("min", 0.0),
                max_value=meta.get("max", 100.0),
            )
            self._apply_graph_settings_to_widget(slot_id, graph)

        # Цифры
        for slot_id, widget in self.value_slots.items():
            meta = get_meta_for_slot(slot_id)
            if not meta:
                continue
            title = meta.get("name", "")
            color = meta.get("color", "#FFFFFF")
            unit = meta.get("unit", "")
            widget.title_label.text = title
            if hasattr(widget, "set_base_color"):
                widget.set_base_color(color)
            else:
                widget.title_label.color = widget._hex_to_rgb(color)
                widget.value_label.color = widget._hex_to_rgb(color)
            if widget.unit_label is not None:
                widget.unit_label.text = unit
                widget.unit_label.color = widget._hex_to_rgb(color)
            if hasattr(widget, "set_normal_range"):
                widget.set_normal_range(meta.get("min"), meta.get("max"))
            widget._update_font_sizes()
    
    def _create_bed_selection_panel(self):
        """Создание панели выбора кровати"""
        bed_panel = BoxLayout(
            orientation='vertical',
            size_hint_x=None if self.viewer_mode else 0.30,
            width=dp(200) if self.viewer_mode else dp(0),
            spacing=dp(6),
            padding=dp(8)
        )
        if not (self.grid_tile_layout and not self.viewer_mode):
            apply_rounded_panel(bed_panel)
        if self.viewer_mode:
            bed_panel.size_hint_x = None
            if self.viewer_toolbar_in_titlebar:
                bed_panel.width = 0
                bed_panel.opacity = 0
                bed_panel.padding = (0, 0, 0, 0)
                bed_panel.spacing = 0
            else:
                bed_panel.width = dp(286)
                bed_panel.size_hint_y = None
                bed_panel.bind(minimum_height=bed_panel.setter("height"))

        if self.viewer_mode:
            # На экране с графиками нет выбора кровати — только исследование, период, экспорт.
            self.bed_button = None

            self.study_button = Button(
                text="Исследование: выбрать…",
                background_color=(0, 0, 0, 0),
                background_normal="",
                background_down="",
                halign="center",
                valign="middle",
                shorten=True,
                shorten_from="right",
                text_size=(0, 0),
                font_size=dp(12),
                size_hint=(1, 1),
            )
            self.study_button.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0] - dp(10), None)))
            self.study_button.bind(on_press=self._show_study_selection_menu)
            self._set_study_button_text(self.current_study)

            self.time_range_button = Button(
                text=self._format_absolute_range(),
                background_color=(0, 0, 0, 0),
                background_normal="",
                background_down="",
                halign="center",
                valign="middle",
                shorten=True,
                shorten_from="right",
                text_size=(0, 0),
                font_size=dp(12),
                size_hint=(1, 1),
            )
            self.time_range_button.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0] - dp(10), None)))
            self.time_range_button.bind(on_press=self._show_time_range_menu)

            export_btn = Button(
                text="Экспорт",
                background_color=(0, 0, 0, 0),
                background_normal="",
                background_down="",
                halign="center",
                valign="middle",
                shorten=True,
                shorten_from="right",
                text_size=(0, 0),
                font_size=dp(12),
                size_hint=(1, 1),
            )
            export_btn.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0] - dp(10), None)))
            export_btn.bind(on_press=self._show_export_popup)

            table_btn_rgba = UI_BTN_MUTED
            apply_rounded_button(self.study_button, base_rgba=table_btn_rgba)
            apply_rounded_button(self.time_range_button, base_rgba=table_btn_rgba)
            apply_rounded_button(export_btn, base_rgba=table_btn_rgba)

            if self.viewer_toolbar_in_titlebar:
                for b in (self.study_button, self.time_range_button, export_btn):
                    b.font_size = dp(11)
                    b.size_hint = (None, 1)
                self.study_button.size_hint_x = None
                self.study_button.width = dp(480)
                self.time_range_button.size_hint_x = None
                self.time_range_button.width = dp(170)
                export_btn.size_hint_x = None
                export_btn.width = dp(90)
                toolbar_w = dp(480) + dp(170) + dp(90) + dp(8) * 2
                self.viewer_title_toolbar = BoxLayout(
                    orientation="horizontal",
                    spacing=dp(8),
                    size_hint_x=None,
                    width=toolbar_w,
                    size_hint_y=1,
                )
                self.viewer_title_toolbar.add_widget(self.study_button)
                self.viewer_title_toolbar.add_widget(self.time_range_button)
                self.viewer_title_toolbar.add_widget(export_btn)
            else:
                buttons_col = BoxLayout(
                    orientation="vertical",
                    spacing=dp(6),
                    size_hint=(1, None),
                )
                buttons_col.bind(minimum_height=buttons_col.setter("height"))
                self.viewer_buttons_col = buttons_col
                for btn in (self.study_button, self.time_range_button, export_btn):
                    btn.size_hint = (1, None)
                    btn.height = dp(36)
                    btn.font_size = dp(12)
                    btn.bind(size=lambda inst, s: setattr(inst, "text_size", (max(1, s[0] - dp(12)), s[1])))
                    buttons_col.add_widget(btn)
                bed_panel.add_widget(buttons_col)

                # Панель управления проигрыванием истории (viewer only).
                playback_panel = BoxLayout(
                    orientation="vertical",
                    spacing=dp(6),
                    size_hint=(1, None),
                    height=dp(84),
                )
                controls_row = BoxLayout(
                    orientation="horizontal",
                    spacing=dp(6),
                    size_hint=(1, None),
                    height=dp(42),
                )
                self.viewer_seek_start_btn = Button(
                    text="|<",
                    background_color=(0, 0, 0, 0),
                    background_normal="",
                    background_down="",
                    font_size=dp(19),
                    bold=True,
                    halign="center",
                    valign="middle",
                    text_size=(0, 0),
                )
                self.viewer_play_back_btn = Button(
                    text="<<",
                    background_color=(0, 0, 0, 0),
                    background_normal="",
                    background_down="",
                    font_size=dp(19),
                    bold=True,
                    halign="center",
                    valign="middle",
                    text_size=(0, 0),
                )
                self.viewer_pause_btn = Button(
                    text="||",
                    background_color=(0, 0, 0, 0),
                    background_normal="",
                    background_down="",
                    font_size=dp(19),
                    bold=True,
                    halign="center",
                    valign="middle",
                    text_size=(0, 0),
                )
                self.viewer_play_fwd_btn = Button(
                    text=">>",
                    background_color=(0, 0, 0, 0),
                    background_normal="",
                    background_down="",
                    font_size=dp(19),
                    bold=True,
                    halign="center",
                    valign="middle",
                    text_size=(0, 0),
                )
                self.viewer_seek_end_btn = Button(
                    text=">|",
                    background_color=(0, 0, 0, 0),
                    background_normal="",
                    background_down="",
                    font_size=dp(19),
                    bold=True,
                    halign="center",
                    valign="middle",
                    text_size=(0, 0),
                )
                self.viewer_speed_button = Button(
                    text="x1",
                    background_color=(0, 0, 0, 0),
                    background_normal="",
                    background_down="",
                    font_size=dp(16),
                    bold=True,
                    halign="center",
                    valign="middle",
                    text_size=(0, 0),
                )
                self.viewer_seek_start_btn.bind(on_press=self._viewer_seek_to_start)
                self.viewer_play_back_btn.bind(on_press=lambda *_: self._set_viewer_playback_state(-1))
                self.viewer_pause_btn.bind(on_press=lambda *_: self._set_viewer_playback_state(0))
                self.viewer_play_fwd_btn.bind(on_press=lambda *_: self._set_viewer_playback_state(1))
                self.viewer_seek_end_btn.bind(on_press=self._viewer_seek_to_end)
                self.viewer_speed_button.bind(on_press=self._cycle_viewer_playback_speed)

                for btn in (
                    self.viewer_seek_start_btn,
                    self.viewer_play_back_btn,
                    self.viewer_pause_btn,
                    self.viewer_play_fwd_btn,
                    self.viewer_seek_end_btn,
                    self.viewer_speed_button,
                ):
                    btn.size_hint = (1, None)
                    btn.height = dp(42)
                    btn.bind(size=lambda inst, s: setattr(inst, "text_size", (max(1, s[0]), max(1, s[1]))))
                    apply_rounded_button(btn, base_rgba=UI_BTN_MUTED, radius_px=dp(10), border_alpha=0.08)
                    controls_row.add_widget(btn)

                playback_panel.add_widget(controls_row)
                bed_panel.add_widget(playback_panel)
                self.viewer_playback_panel = playback_panel
                self._set_viewer_playback_speed(1)
                self._set_viewer_playback_state(0)

            if isinstance(self.data_source, DatabaseDataSource):
                self._load_beds()
        else:
            # В live-режиме на маленьких раскладках (4/6) верхняя панель низкая,
            # поэтому делаем переключаемую верстку: обычная (в столбик) и compact (2 кнопки в 2 столбца).
            stack_container = BoxLayout(orientation="vertical", spacing=dp(6), size_hint=(1, 1))
            bed_panel.add_widget(stack_container)

            compact_row = GridLayout(
                cols=1,
                rows=2,
                spacing=dp(6),
                size_hint_x=1,
                size_hint_y=None,
                height=0,
                opacity=0,
            )
            bed_panel.add_widget(compact_row)

            # Метка для кровати
            bed_label = Label(
                text="Кровать:",
                size_hint_y=None,
                height=dp(22),
                color=UI_TEXT_MUTED,
                font_size=dp(13),
                halign='left',
                text_size=(dp(180), None)
            )
            stack_container.add_widget(bed_label)

            # Кнопка выбора кровати
            self.bed_button = Button(
                text="Загрузка...",
                size_hint_y=None,
                height=dp(40),
                font_size=dp(13),
                background_color=(0, 0, 0, 0),
                background_normal="",
                background_down="",
                halign="center",
                valign="middle",
                shorten=True,
                shorten_from="right",
                text_size=(0, 0),
            )
            self.bed_button.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0] - dp(10), None)))
            self.bed_button.bind(on_press=self._show_bed_selection_menu)
            apply_rounded_button(self.bed_button, base_rgba=UI_BTN_MUTED)
            stack_container.add_widget(self.bed_button)
            
            # Загружаем список кроватей и устанавливаем текущую (только для БД)
            if self._db_state == "demo":
                self.bed_button.text = "ДЕМО"
                self.bed_button.disabled = True
            elif isinstance(self.data_source, DatabaseDataSource) and self._is_database_online():
                self._load_beds()
            else:
                self.bed_button.text = "БД недоступна"
                self.bed_button.disabled = True
                self.bed_button.background_color = (0.2, 0.2, 0.2, 1)
            
            # Метка для диапазона
            range_label = Label(
                text="Период:" if self.viewer_mode else "Диапазон:",
                size_hint_y=None,
                height=dp(22),
                color=UI_TEXT_MUTED,
                font_size=dp(13),
                halign='left',
                text_size=(dp(180), None)
            )
            stack_container.add_widget(range_label)
            
            # Кнопка выбора диапазона
            self.time_range_button = Button(
                text=self.current_time_range.label,
                size_hint_y=None,
                height=dp(40),
                font_size=dp(13),
                background_color=(0, 0, 0, 0),
                background_normal="",
                background_down="",
                halign="center",
                valign="middle",
                shorten=True,
                shorten_from="right",
                text_size=(0, 0),
            )
            self.time_range_button.bind(size=lambda inst, s: setattr(inst, "text_size", (s[0] - dp(10), None)))
            self.time_range_button.bind(on_press=self._show_time_range_menu)
            apply_rounded_button(self.time_range_button, base_rgba=UI_BTN_MUTED)
            stack_container.add_widget(self.time_range_button)

            # Compact reflow for small monitors (2/4/6 layouts):
            # if the top panel gets too small, hide labels and fit two buttons cleanly.
            def _reflow_compact(*_args):
                try:
                    h = float(bed_panel.height)
                except Exception:
                    return

                is_compact = (not self.viewer_mode) and (h > 0) and (h < float(dp(150)))

                if is_compact:
                    bed_label.height = 0
                    bed_label.opacity = 0
                    range_label.height = 0
                    range_label.opacity = 0
                    bed_panel.padding = (0, 0, 0, 0) if self.grid_tile_layout else dp(6)
                    bed_panel.spacing = dp(6)
                    stack_container.size_hint_y = None
                    stack_container.height = 0
                    stack_container.opacity = 0
                    compact_row.opacity = 1
                else:
                    bed_label.height = dp(22)
                    bed_label.opacity = 1
                    range_label.height = dp(22)
                    range_label.opacity = 1
                    bed_panel.padding = (0, 0, 0, 0) if self.grid_tile_layout else dp(8)
                    bed_panel.spacing = dp(6)
                    stack_container.size_hint_y = 1
                    stack_container.height = 0
                    stack_container.opacity = 1
                    compact_row.opacity = 0

                # Compute available height for buttons
                pad = bed_panel.padding
                try:
                    if isinstance(pad, (tuple, list)):
                        pad_t = float(pad[1] if len(pad) > 1 else pad[0])
                        pad_b = float(pad[3] if len(pad) > 3 else pad[0])
                    else:
                        pad_t = pad_b = float(pad)
                except Exception:
                    pad_t = pad_b = float(dp(6))

                try:
                    row_spacing = compact_row.spacing
                    if isinstance(row_spacing, (tuple, list)):
                        row_spacing = float(row_spacing[1] if len(row_spacing) > 1 else row_spacing[0])
                    else:
                        row_spacing = float(row_spacing)
                except Exception:
                    row_spacing = float(dp(6))

                label_h = 0.0 if is_compact else float(dp(44))  # two labels total (22+22)
                gaps = float(bed_panel.spacing) * (1 if is_compact else 3)
                avail = max(1.0, h - pad_t - pad_b - label_h - gaps)
                if is_compact:
                    btn_h = max(float(dp(30)), (avail - row_spacing) / 2.0)
                else:
                    btn_h = max(float(dp(30)), min(float(dp(46)), avail / 2.0))
                fs = max(float(dp(10)), min(float(dp(16)), btn_h * 0.34))

                # Перекладываем кнопки между контейнерами:
                if is_compact:
                    # В compact-режиме кнопки идут в 2 строки и занимают всю высоту блока.
                    compact_row.height = avail
                    if self.bed_button.parent is not compact_row:
                        try:
                            if self.bed_button.parent:
                                self.bed_button.parent.remove_widget(self.bed_button)
                        except Exception:
                            pass
                        compact_row.add_widget(self.bed_button)
                    if self.time_range_button.parent is not compact_row:
                        try:
                            if self.time_range_button.parent:
                                self.time_range_button.parent.remove_widget(self.time_range_button)
                        except Exception:
                            pass
                        compact_row.add_widget(self.time_range_button)

                    self.bed_button.size_hint_x = 1
                    self.time_range_button.size_hint_x = 1
                    self.bed_button.size_hint_y = 1
                    self.time_range_button.size_hint_y = 1
                else:
                    compact_row.height = 0
                    # Возвращаем в столбик
                    if self.bed_button.parent is not stack_container:
                        try:
                            if self.bed_button.parent:
                                self.bed_button.parent.remove_widget(self.bed_button)
                        except Exception:
                            pass
                        stack_container.add_widget(self.bed_button, index=1)
                    if self.time_range_button.parent is not stack_container:
                        try:
                            if self.time_range_button.parent:
                                self.time_range_button.parent.remove_widget(self.time_range_button)
                        except Exception:
                            pass
                        stack_container.add_widget(self.time_range_button, index=3)

                    self.bed_button.size_hint_y = None
                    self.time_range_button.size_hint_y = None
                    self.bed_button.height = btn_h
                    self.time_range_button.height = btn_h

                self.bed_button.font_size = fs
                self.time_range_button.font_size = fs
                for btn in (self.bed_button, self.time_range_button):
                    try:
                        btn.width = 0
                        btn.size_hint_x = 1
                        btn.text_size = (max(1, float(btn.width or 0) - float(dp(10))), None)
                    except Exception:
                        pass

            bed_panel.bind(size=_reflow_compact)
            _reflow_compact()
        
        return bed_panel

    def _apply_rounded_button_style(self, btn: Button, base_rgba=(0.30, 0.30, 0.30, 1.0), radius_px=None):
        # Backward compatible wrapper (older code paths still call this)
        apply_rounded_button(btn, base_rgba=base_rgba, radius_px=radius_px)

    def _get_navigation_screen_name(self) -> str:
        """Имя реального ScreenManager-экрана, на который нужно возвращаться."""
        return self.navigation_screen_name or self.name

    def _replace_managed_screen(self, screen) -> bool:
        if self.manager is None:
            return False
        try:
            self._clear_dashboard_grid_hover()
            if self.manager.has_screen(screen.name):
                existing = self.manager.get_screen(screen.name)
                self.manager.remove_widget(existing)
            self.manager.add_widget(screen)
            self.manager.current = screen.name
            return True
        except Exception:
            return False

    def _show_study_selection_menu(self, instance):
        """Переход на экран выбора study/worklist (только viewer_mode)."""
        if not self.manager:
            return

        study_screen = None
        for screen in self.manager.screens:
            if isinstance(screen, StudySelectionScreen) or (
                hasattr(screen, "name") and "study_selection" in screen.name
            ):
                study_screen = screen
                break

        if not study_screen:
            return

        # Подтянем свежий список (если БД доступна)
        if isinstance(self.data_source, DatabaseDataSource):
            try:
                study_screen.set_studies(self.data_source.get_recent_studies(limit=200))
                study_screen.set_on_refresh(lambda: self.data_source.get_recent_studies(limit=200))
                study_screen.set_on_open_study_id(lambda sid: self.data_source.get_study_by_id(sid))
            except Exception:
                pass

        study_screen.set_on_study_selected(self._on_study_selected_from_screen)
        nav_screen_name = self._get_navigation_screen_name()
        study_screen.previous_screen = nav_screen_name
        study_screen.next_screen_on_select = nav_screen_name

        self.manager.current = study_screen.name

    def _on_study_selected_from_screen(self, study: dict):
        """Применить выбранное study: кровать + диапазон истории."""
        self.current_study = study

        self._set_study_button_text(study)

        # Study -> bed (study.bed_id; fallback: room_id/block_id)
        if isinstance(self.data_source, DatabaseDataSource):
            try:
                bed_id = study.get("bed_id")
                bed_name = None
                if bed_id is None:
                    room_id = study.get("room_id")
                    block_id = study.get("block_id")
                    if room_id is not None and block_id is not None:
                        bed = self.data_source.get_bed_by_room_block(int(room_id), int(block_id))
                        if bed:
                            bed_id = bed.get("bed_id") or bed.get("id")
                            bed_name = bed.get("bed_name") or bed.get("name")
                else:
                    try:
                        bed = self.data_source.get_bed_info(int(bed_id))
                        if bed:
                            bed_name = bed.get("bed_name") or bed.get("name")
                    except Exception:
                        pass
                if bed_id is not None:
                    self.data_source.set_bed_id(int(bed_id))
                    self._set_bed_button_text(bed_name, int(bed_id))
                    self._refresh_patient_info()
            except Exception:
                pass

        # Study -> период
        start_dt = study.get("begin_dt")
        end_dt = study.get("end_dt")
        if start_dt and end_dt:
            self.set_history_range(start_dt, end_dt)
            self.reload_historical_data()

    def _show_export_popup(self, *args):
        """Полноэкранная страница выбора формата экспорта CSV/XLS/PDF."""
        if not isinstance(self.data_source, DatabaseDataSource):
            self._show_info_popup("Экспорт доступен только в режиме базы данных.")
            return
        if not self._is_database_online():
            self._show_info_popup("База данных недоступна. Экспорт остановлен до восстановления связи.")
            return
        if not (self.history_start and self.history_end):
            self._show_info_popup("Сначала выберите период.")
            return
        if self.data_source.get_current_bed_id() is None:
            self._show_info_popup("Сначала выберите кровать.")
            return

        # Проверка наличия reportlab в текущем Python (venv)
        try:
            import importlib.util
            has_reportlab = bool(importlib.util.find_spec("reportlab"))
        except Exception:
            has_reportlab = False
        try:
            from components.export_screen import ExportScreen

            nav_screen_name = self._get_navigation_screen_name()
            export_screen = ExportScreen(
                name=f"{nav_screen_name}_export",
                export_dir=self.export_dir,
                aggregation_options=self._get_export_aggregation_period_options(),
                has_reportlab=has_reportlab,
                previous_screen=nav_screen_name,
                on_choose_dir=self._choose_export_dir_for_screen,
                on_export=self._run_export_from_screen,
            )
            if self._replace_managed_screen(export_screen):
                return
        except Exception:
            pass

        self._show_info_popup("Не удалось открыть страницу экспорта.")

    def _choose_export_dir_for_screen(self) -> str | None:
        selected = self._choose_export_dir()
        if selected:
            self.export_dir = Path(selected)
            return str(self.export_dir)
        return None

    def _run_export_from_screen(self, fmt: str, aggregation_seconds: int | None, include_images: bool):
        self._export_history_tabular(
            fmt,
            aggregation_seconds=aggregation_seconds,
            include_images=include_images,
        )

    def _get_export_aggregation_period_options(self) -> list[tuple[int, str]]:
        return [
            (60, "1 мин"),
            (300, "5 мин"),
            (900, "15 мин"),
            (1800, "30 мин"),
            (3600, "1 час"),
            (3 * 3600, "3 часа"),
            (6 * 3600, "6 часов"),
            (12 * 3600, "12 часов"),
            (24 * 3600, "24 часа"),
        ]

    def _format_export_aggregation_period_label(self, seconds: int) -> str:
        if seconds % (24 * 3600) == 0:
            days = max(1, seconds // (24 * 3600))
            return f"{days} д"
        if seconds % 3600 == 0:
            hours = max(1, seconds // 3600)
            return f"{hours} ч"
        minutes = max(1, seconds // 60)
        return f"{minutes} мин"

    def _choose_export_dir(self) -> str | None:
        """
        Выбор папки для экспорта.
        Пытаемся через plyer (если есть), иначе через tkinter.
        """
        # 1) plyer (нативный диалог, если доступен)
        try:
            from plyer import filechooser  # type: ignore

            paths = filechooser.choose_dir(title="Выберите папку для экспорта")
            if paths and len(paths) > 0:
                return paths[0]
        except Exception:
            pass

        # 2) tkinter (стандартная библиотека)
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            try:
                root.attributes("-topmost", True)
            except Exception:
                pass
            folder = filedialog.askdirectory(title="Выберите папку для экспорта")
            try:
                root.destroy()
            except Exception:
                pass
            return folder or None
        except Exception:
            return None

    def _show_info_popup(self, text: str):
        try:
            from components.message_screen import MessageScreen

            current_screen = None
            if self.manager is not None:
                current_screen = self.manager.current
            if self.manager is not None:
                message_screen = MessageScreen(
                    name=f"{self._get_navigation_screen_name()}_message",
                    title_text="Информация",
                    message_text=text,
                    previous_screen=current_screen or self._get_navigation_screen_name(),
                )
                if self._replace_managed_screen(message_screen):
                    return
        except Exception:
            pass

        from kivy.uix.label import Label
        from kivy.uix.scrollview import ScrollView
        from kivy.metrics import dp

        lbl = Label(
            text=text,
            font_size=dp(14),
            halign="left",
            valign="top",
            text_size=(0, 0),
            size_hint_y=None,
        )
        style_popup_label_body(lbl)

        # переносим/скроллим длинные пути, чтобы не "выползало" из бокса
        def _sync_text_size(instance, size):
            instance.text_size = (size[0], None)
            instance.texture_update()
            instance.height = instance.texture_size[1]

        lbl.bind(size=_sync_text_size)
        _sync_text_size(lbl, (dp(520), dp(200)))

        scroll = ScrollView(do_scroll_x=False, do_scroll_y=True, bar_width=dp(10))
        style_scrollview_popup(scroll)
        scroll.add_widget(lbl)
        popup = Popup(
            title="Информация",
            content=scroll,
            size_hint=(0.7, 0.38),
        )
        apply_popup_theme(popup)
        popup.open()

    def _export_history_tabular(
        self,
        fmt: str,
        aggregation_seconds: int | None = None,
        include_images: bool = False,
    ):
        """Экспорт истории в CSV/XLS/PDF: все параметры из каталога signal_param за выбранный период."""
        if not self._is_database_online():
            self._show_info_popup("База данных недоступна. Экспорт не выполнен.")
            return
        from pathlib import Path
        from utils.history_tabular_exporter import (
            export_history_csv,
            export_history_xls_spreadsheetml,
            export_history_pdf,
            export_image_frames,
        )

        bed_id = int(self.data_source.get_current_bed_id())
        start_dt = self.history_start
        end_dt = self.history_end

        if isinstance(self.data_source, DatabaseDataSource) and not (self.available_signals or []):
            self._load_available_signals()

        signal_ids: list[int] = []
        for s in self.available_signals or []:
            try:
                signal_ids.append(int(s["signal_id"]))
            except Exception:
                continue
        signal_ids = sorted(set(signal_ids))
        if not signal_ids:
            self._show_info_popup("Нет параметров в каталоге сигналов для экспорта.")
            return

        # Мета по сигналам
        meta = {}
        for s in self.available_signals or []:
            try:
                meta[int(s["signal_id"])] = {"name": s.get("name", ""), "unit": s.get("unit", "")}
            except Exception:
                continue

        # Данные по всем signal_id из каталога за период
        points = self.data_source.get_signal_values_between(bed_id, signal_ids, start_dt, end_dt)
        if not points:
            self._show_info_popup("За выбранный период нет данных по сигналам.")
            return
        rows = []
        for p in points:
            sid = int(p["signal_id"])
            m = meta.get(sid, {})
            rows.append(
                {
                    "ts": p["ts"].isoformat(sep=" "),
                    "param_key": sid,  # внутренний ключ для pivot (в файл не пишем)
                    "name": m.get("name", ""),
                    "unit": m.get("unit", ""),
                    "value": f"{p['value']:.6g}",
                }
            )

        export_dir = self.export_dir
        stem = f"history_bed{bed_id}_{start_dt.strftime('%Y%m%d_%H%M')}_{end_dt.strftime('%Y%m%d_%H%M')}"
        if aggregation_seconds:
            stem += f"_agg_{int(aggregation_seconds)}s"
        try:
            fmt_l = fmt.lower()
            if fmt_l == "csv":
                out = export_history_csv(rows, export_dir, stem, aggregation_seconds=aggregation_seconds)
            elif fmt_l == "xls":
                out = export_history_xls_spreadsheetml(rows, export_dir, stem, aggregation_seconds=aggregation_seconds)
            else:
                # pdf
                bed_name = None
                try:
                    if hasattr(self, "available_beds") and self.available_beds:
                        b = next((bb for bb in self.available_beds if int(bb.get("id")) == int(bed_id)), None)
                        if b:
                            bed_name = b.get("name")
                except Exception:
                    bed_name = None
                if not bed_name:
                    bed_name = f"Кровать {bed_id}"
                out = export_history_pdf(
                    rows,
                    export_dir,
                    stem,
                    title=f"Экспорт истории ({bed_name})",
                    aggregation_seconds=aggregation_seconds,
                )

            message = f"Сохранено:\n{out}"
            if include_images and isinstance(self.data_source, DatabaseDataSource):
                image_frames = self.data_source.get_image_frames_between(bed_id, start_dt, end_dt)
                images_dir, images_count = export_image_frames(
                    image_frames,
                    export_dir,
                    f"{stem}_images",
                    aggregation_seconds=aggregation_seconds,
                )
                if images_dir and images_count:
                    message += f"\n\nИзображения:\n{images_dir}\nСохранено кадров: {images_count}"
                else:
                    message += "\n\nИзображения: за выбранный период кадры не найдены."
            self._show_info_popup(message)
        except Exception as e:
            self._show_info_popup(str(e))
    
    def _load_beds(self):
        """Загрузка списка кроватей и установка текущей"""
        if not isinstance(self.data_source, DatabaseDataSource):
            return
        if not self._is_database_online():
            self.available_beds = []
            if getattr(self, "bed_button", None) is not None:
                self.bed_button.text = "БД недоступна"
                self.bed_button.disabled = True
            return
        
        try:
            beds = self.data_source.get_available_beds()
            if beds:
                self.available_beds = beds
                current_bed_id = self.data_source.get_current_bed_id()
                
                # Обновляем текст кнопки
                if current_bed_id:
                    current_bed = next((b for b in beds if b['id'] == current_bed_id), None)
                    if current_bed:
                        self._set_bed_button_text(current_bed.get('name'), int(current_bed_id))
                    else:
                        self._set_bed_button_text(None, int(current_bed_id))
                else:
                    if beds:
                        self._set_bed_button_text(beds[0].get('name'), int(beds[0].get('id') or 0) or None)
                    else:
                        self._set_bed_button_text("Не выбрана")
            else:
                self.available_beds = []
                self._set_bed_button_text("Нет доступных кроватей")
            self._refresh_patient_info()
        except Exception as e:
            print(f"Ошибка загрузки списка кроватей: {e}")
            self.available_beds = []
            self._set_bed_button_text("Ошибка загрузки")

    def _refresh_patient_info(self) -> None:
        """Обновить инфо-блок пациента для live main.py sidebar."""
        if self.viewer_mode or not self._is_database_online():
            return
        if not hasattr(self, "patient_info_panel"):
            return
        try:
            bed_id = self.data_source.get_current_bed_id()
            info = self.data_source.get_current_patient_info_for_bed(int(bed_id)) if bed_id is not None else None
        except Exception:
            info = None
        self._patient_info_cache = info or {}
        self._apply_patient_info_to_panel(self._patient_info_cache)

    def _sync_patient_info_empty_style(self) -> None:
        """Привести стиль/раскладку patient_info_panel к режиму «пациент отсутствует».

        В пустом режиме:
        - обе видимые строки имеют единый шрифт/цвет/жирность;
        - нижние два лейбла свёрнуты в высоту 0 (они невидимы и не влияют на блок);
        - фраза целиком вертикально центрирована внутри панели через дополнительный
          верхний padding (равный половине свободного пространства).
        В обычном режиме history-лейбл и нижние лейблы возвращаются к штатной геометрии.
        """
        name_lbl = getattr(self, "patient_info_name_label", None)
        hist_lbl = getattr(self, "patient_info_history_label", None)
        age_lbl = getattr(self, "patient_info_age_label", None)
        adm_lbl = getattr(self, "patient_info_admitted_label", None)
        panel = getattr(self, "patient_info_panel", None)
        if hist_lbl is None:
            return
        if self._use_dashboard_grid_layout():
            if name_lbl is not None:
                name_lbl.halign = "left"
                name_lbl.valign = "middle"
                name_lbl.opacity = 1
            hist_lbl.bold = False
            hist_lbl.shorten = True
            hist_lbl.halign = "left"
            hist_lbl.valign = "middle"
            hist_lbl.opacity = 1
            if panel is not None:
                panel.padding = (dp(8), dp(8), dp(8), dp(8))
            self._update_dashboard_patient_panel_layout()
            return

        base_padding = getattr(self, "_patient_info_base_padding", None)
        base_row_h = float(getattr(self, "_patient_info_base_row_h", 0.0) or 0.0)

        if getattr(self, "_patient_info_empty", False):
            if name_lbl is not None:
                hist_lbl.font_size = name_lbl.font_size
                hist_lbl.color = name_lbl.color
                hist_lbl.height = name_lbl.height
                # Центруем обе строки и по горизонтали, и по вертикали — в пустом
                # режиме фраза смотрится сбалансированно и не «прилипает» к углу.
                name_lbl.halign = "center"
                name_lbl.valign = "middle"
            hist_lbl.bold = True
            hist_lbl.shorten = False
            hist_lbl.halign = "center"
            hist_lbl.valign = "middle"

            if age_lbl is not None:
                age_lbl.height = 0
                age_lbl.opacity = 0
            if adm_lbl is not None:
                adm_lbl.height = 0
                adm_lbl.opacity = 0

            if panel is not None and name_lbl is not None and base_padding is not None:
                try:
                    pad_l, pad_t, pad_r, pad_b = (float(v) for v in base_padding)
                    spacing = float(panel.spacing or 0)
                    visible_h = float(name_lbl.height) + float(hist_lbl.height) + spacing
                    free = float(panel.height) - pad_t - pad_b - visible_h
                    if free > 0:
                        panel.padding = (pad_l, pad_t + free / 2.0, pad_r, pad_b)
                    else:
                        panel.padding = (pad_l, pad_t, pad_r, pad_b)
                except Exception:
                    pass
        else:
            hist_lbl.bold = False
            hist_lbl.shorten = True
            hist_lbl.color = UI_TEXT_PRIMARY
            hist_lbl.halign = "left"
            hist_lbl.valign = "middle"
            if name_lbl is not None:
                name_lbl.halign = "left"
                name_lbl.valign = "middle"
            if age_lbl is not None and base_row_h > 0:
                age_lbl.height = base_row_h
            if adm_lbl is not None and base_row_h > 0:
                adm_lbl.height = base_row_h
            if panel is not None and base_padding is not None:
                try:
                    panel.padding = tuple(base_padding)
                except Exception:
                    pass

    def _apply_patient_info_to_panel(self, info: dict | None) -> None:
        info = info or {}
        name_raw = str(info.get("patient_name") or "").strip()
        # Считаем пациента отсутствующим, если в info нет ни имени, ни номера, ни id.
        has_patient = bool(
            name_raw
            or str(info.get("patient_numb") or "").strip()
            or info.get("patient_id")
        )

        if not has_patient:
            # Сообщение разбиваем на две строки, чтобы оно гарантированно умещалось
            # в узких плитках без обрезания. Стили обеих строк выравниваем (одинаковый
            # шрифт/цвет/жирность). Остальные строки очищаем и прячем.
            self._patient_info_empty = True
            bed_text = str(getattr(self, "_current_bed_display_text", "") or self.monitor_config.get("bed_name") or "").strip()
            if self._use_dashboard_grid_layout():
                self._dashboard_patient_info_data = {
                    "has_patient": False,
                    "bed": bed_text or "Койка: —",
                    "name": "Пациент отсутствует",
                    "history": "—",
                    "age": "—",
                    "admitted": "—",
                    "admitted_short": "—",
                }
                self._sync_patient_info_empty_style()
                return
            if hasattr(self, "patient_info_name_label"):
                self.patient_info_name_label.text = bed_text or "Койка: —"
                self.patient_info_name_label.opacity = 1
            if hasattr(self, "patient_info_history_label"):
                self.patient_info_history_label.text = "Пациент отсутствует"
                self.patient_info_history_label.opacity = 1
            for attr in (
                "patient_info_age_label",
                "patient_info_admitted_label",
            ):
                lbl = getattr(self, attr, None)
                if lbl is not None:
                    lbl.text = ""
                    lbl.opacity = 0 if not self._use_dashboard_grid_layout() else 1
            if self._use_dashboard_grid_layout():
                if hasattr(self, "patient_info_age_label"):
                    self.patient_info_age_label.text = "ИБ: —"
                if hasattr(self, "patient_info_admitted_label"):
                    self.patient_info_admitted_label.text = "Возраст: —"
            self._sync_patient_info_empty_style()
            return

        # Пациент есть -> возвращаем нормальный многострочный вид.
        self._patient_info_empty = False
        for attr in (
            "patient_info_history_label",
            "patient_info_age_label",
            "patient_info_admitted_label",
        ):
            lbl = getattr(self, attr, None)
            if lbl is not None:
                lbl.opacity = 1
        self._sync_patient_info_empty_style()

        name = name_raw or "—"
        bed_text = str(getattr(self, "_current_bed_display_text", "") or self.monitor_config.get("bed_name") or "").strip() or "—"
        history_numb = str(info.get("patient_numb") or info.get("worklist_numb") or "").strip() or "—"
        age = info.get("patient_age")
        age_text = f"{int(age)} лет" if age is not None else "—"
        admitted_at = info.get("admitted_at")
        admitted_text = "—"
        try:
            if admitted_at is not None:
                admitted_text = admitted_at.strftime("%d.%m.%Y %H:%M")
                admitted_short = admitted_at.strftime("%d.%m.%y %H:%M")
            else:
                admitted_short = "—"
        except Exception:
            admitted_text = str(admitted_at or "—")
            admitted_short = admitted_text

        if self._use_dashboard_grid_layout():
            self._dashboard_patient_info_data = {
                "has_patient": True,
                "bed": bed_text,
                "name": name,
                "history": history_numb,
                "age": age_text,
                "admitted": admitted_text,
                "admitted_short": admitted_short,
            }
            self._update_dashboard_patient_panel_layout()
            return

        if hasattr(self, "patient_info_name_label"):
            self.patient_info_name_label.text = f"Койка: {bed_text}"
        if hasattr(self, "patient_info_history_label"):
            self.patient_info_history_label.text = f"ФИО: {name}"
        if hasattr(self, "patient_info_age_label"):
            self.patient_info_age_label.text = f"ИБ: {history_numb}"
        if hasattr(self, "patient_info_admitted_label"):
            self.patient_info_admitted_label.text = f"Возраст: {age_text}  Поступил: {admitted_text}"
        self._update_dashboard_patient_panel_layout()
    
    def _show_bed_selection_menu(self, instance):
        """Переход на экран выбора кровати"""
        self._clear_dashboard_grid_hover()
        if isinstance(self.data_source, DatabaseDataSource) and not self._is_database_online():
            self._show_info_popup("База данных недоступна. Повторите после восстановления связи.")
            return
        if (not hasattr(self, 'available_beds') or not self.available_beds) and isinstance(self.data_source, DatabaseDataSource):
            # Иногда в viewer-mode кровати могли ещё не подгрузиться — попробуем подгрузить лениво
            self._load_beds()
        if not hasattr(self, 'available_beds') or not self.available_beds:
            self._show_info_popup("Нет доступных кроватей для выбора")
            return
        
        # Переходим на экран выбора кровати
        if self.manager:
            # Ищем экран выбора кровати по типу или по имени
            bed_screen = None
            for screen in self.manager.screens:
                if isinstance(screen, BedSelectionScreen) or (hasattr(screen, 'name') and 'bed_selection' in screen.name):
                    bed_screen = screen
                    break
            
            if bed_screen:
                # Обновляем данные на экране выбора
                current_bed_id = None
                if isinstance(self.data_source, DatabaseDataSource):
                    current_bed_id = self.data_source.get_current_bed_id()
                
                bed_screen.set_beds(self.available_beds)
                bed_screen.set_current_bed_id(current_bed_id)
                bed_screen.set_on_bed_selected(self._on_bed_selected_from_window)
                # ВАЖНО: чтобы кнопка "Назад" возвращала на этот монитор
                bed_screen.previous_screen = self._get_navigation_screen_name()
                # В viewer_app при открытии выбора кровати из монитора
                # не нужно автоматически переходить "вперед" на выбор периода.
                if hasattr(bed_screen, "next_screen_on_select"):
                    bed_screen.next_screen_on_select = None
                # И точно не закрываем приложение на "Назад"
                if hasattr(bed_screen, "on_back"):
                    bed_screen.on_back = None
                
                # Переключаемся на экран
                self.manager.current = bed_screen.name
    
    def _show_time_range_menu(self, instance):
        """Переход на экран выбора временного диапазона"""
        self._clear_dashboard_grid_hover()
        if self.manager:
            # Viewer-mode: абсолютный диапазон дат/времени
            if self.viewer_mode:
                dt_range_screen = None
                for screen in self.manager.screens:
                    if isinstance(screen, DateTimeRangeSelectionScreen) or (
                        hasattr(screen, "name") and "date_time_range_selection" in screen.name
                    ):
                        dt_range_screen = screen
                        break
                if dt_range_screen:
                    # Установим текущее значение (если нет — по умолчанию последние 6ч)
                    if self.history_start and self.history_end:
                        dt_range_screen.set_current_range(self.history_start, self.history_end)
                    dt_range_screen.set_on_range_selected(self._on_absolute_range_selected_from_screen)
                    # ВАЖНО: "Назад" должен возвращать на этот монитор
                    dt_range_screen.previous_screen = self._get_navigation_screen_name()
                    self.manager.current = dt_range_screen.name
                    return

            # Ищем экран выбора диапазона по типу или по имени
            time_range_screen = None
            for screen in self.manager.screens:
                if isinstance(screen, TimeRangeSelectionScreen) or (hasattr(screen, 'name') and 'time_range_selection' in screen.name):
                    time_range_screen = screen
                    break
            
            if time_range_screen:
                # Обновляем данные на экране выбора
                time_range_screen.set_current_time_range(self.current_time_range)
                time_range_screen.set_on_time_range_selected(self._on_time_range_selected_from_screen)
                # ВАЖНО: "Назад" должен возвращать на этот монитор
                time_range_screen.previous_screen = self._get_navigation_screen_name()
                
                # Переключаемся на экран
                self.manager.current = time_range_screen.name
    
    def _on_time_range_selected_from_screen(self, time_range: TimeRange):
        """Обработчик выбора временного диапазона из экрана"""
        self.current_time_range = time_range
        
        # Обновляем текст кнопки
        if hasattr(self, "time_range_button") and self.time_range_button is not None:
            self.time_range_button.text = time_range.label
        
        # Фильтрация данных по выбранному диапазону
        for slot_id, graph in getattr(self, "graph_slots", {}).items():
            self._apply_graph_settings_to_widget(slot_id, graph)
        self._filter_graphs_by_time_range()
        
        # Сохраняем конфигурацию
        self._save_monitor_config()

    def _show_resolution_menu(self, instance):
        """Переход на экран выбора разрешения графиков (viewer_mode)."""
        if not self.manager:
            return
        time_range_screen = None
        for screen in self.manager.screens:
            if isinstance(screen, TimeRangeSelectionScreen) or (
                hasattr(screen, "name") and "time_range_selection" in screen.name
            ):
                time_range_screen = screen
                break

        if time_range_screen:
            time_range_screen.set_current_time_range(self.current_resolution)
            time_range_screen.set_on_time_range_selected(self._on_resolution_selected_from_screen)
            time_range_screen.previous_screen = self._get_navigation_screen_name()
            self.manager.current = time_range_screen.name

    def _on_resolution_selected_from_screen(self, time_range: TimeRange):
        """Обработчик выбора разрешения."""
        self.current_resolution = time_range
        self._viewer_resolution_seconds = int(time_range.seconds)
        if hasattr(self, "resolution_button"):
            self.resolution_button.text = time_range.label
        for g in self.graph_slots.values():
            g.set_resolution_seconds(self._viewer_resolution_seconds)
        self._save_monitor_config()

    def _on_absolute_range_selected_from_screen(self, start_dt: datetime, end_dt: datetime):
        """Обработчик выбора абсолютного диапазона (viewer)."""
        self.set_history_range(start_dt, end_dt)
        # Загружаем историю в выбранном диапазоне
        self.reload_historical_data()
    
    def _on_bed_selected_from_window(self, bed_id: int, bed_name: str):
        """Обработчик выбора кровати из окна выбора"""
        if not isinstance(self.data_source, DatabaseDataSource):
            return
        
        try:
            # Устанавливаем новую кровать
            self.data_source.set_bed_id(bed_id)
            
            # Если вручную выбрали кровать — больше не привязаны к исследованию
            if self.viewer_mode:
                self.current_study = None
                self._set_study_button_text(None)

            # Обновляем текст кнопки
            self._set_bed_button_text(bed_name, int(bed_id))
            self._refresh_patient_info()
            
            # Очищаем текущие данные графиков (2 слота)
            for g in getattr(self, "graph_slots", {}).values():
                try:
                    g.clear_data()
                except Exception:
                    pass
            
            # Загружаем исторические данные для новой кровати
            if self.viewer_mode and self.history_start and self.history_end:
                self.reload_historical_data()
            else:
                self._load_historical_data()
            
            # Сохраняем конфигурацию
            self._save_monitor_config()
            
            print(f"Выбрана кровать: {bed_name} (ID: {bed_id})")
        except Exception as e:
            print(f"Ошибка при выборе кровати: {e}")
    
    def _setup_graph_click_handlers(self):
        """Контекстное меню (правый клик) и panning (левый drag/swipe) на графиках."""
        for slot_id, graph in self.graph_slots.items():
            graph.bind(
                on_touch_down=lambda inst, touch, sid=slot_id, g=graph: self._on_graph_touch_down(inst, touch, sid, g),
                on_touch_move=lambda inst, touch, sid=slot_id, g=graph: self._on_graph_touch_move(inst, touch, sid, g),
                on_touch_up=lambda inst, touch, sid=slot_id, g=graph: self._on_graph_touch_up(inst, touch, sid, g),
            )

    def _on_graph_touch_down(self, _instance, touch, slot_id: str, graph_widget):
        if not graph_widget.collide_point(*touch.pos):
            return False

        button = getattr(touch, "button", None)
        if button == "right":
            clicked_time = None
            try:
                clicked_time = graph_widget.x_to_time(float(touch.pos[0]))
            except Exception:
                clicked_time = None
            self._show_graph_context_menu(slot_id, clicked_time=clicked_time)
            return True

        # Панорамирование доступно только в viewer-mode и только при левом клике/таче.
        if not self.viewer_mode:
            return False
        if button not in (None, "left"):
            return False
        if not (self._full_start and self._full_end and self._view_start and self._view_end):
            return False

        self._graph_pan_active = True
        self._graph_pan_touch_uid = getattr(touch, "uid", None)
        self._graph_pan_owner = graph_widget
        self._graph_pan_start_x = float(touch.pos[0])
        self._graph_pan_start_view_start = self._view_start
        self._graph_pan_start_view_end = self._view_end
        self._graph_pan_moved = False

        try:
            touch.grab(graph_widget)
        except Exception:
            pass
        return True

    def _on_graph_touch_move(self, _instance, touch, _slot_id: str, graph_widget):
        if not self._graph_pan_active:
            return False
        if self._graph_pan_owner is not graph_widget:
            return False

        uid = getattr(touch, "uid", None)
        if self._graph_pan_touch_uid is not None and uid != self._graph_pan_touch_uid:
            return False

        dx = float(touch.pos[0]) - float(self._graph_pan_start_x)
        if abs(dx) < float(dp(4)):
            return True

        self._graph_pan_moved = True
        self._pan_view_by_pixels(dx, graph_widget)
        return True

    def _on_graph_touch_up(self, _instance, touch, _slot_id: str, graph_widget):
        if not self._graph_pan_active:
            return False
        if self._graph_pan_owner is not graph_widget:
            return False

        uid = getattr(touch, "uid", None)
        if self._graph_pan_touch_uid is not None and uid != self._graph_pan_touch_uid:
            return False

        try:
            touch.ungrab(graph_widget)
        except Exception:
            pass

        moved = self._graph_pan_moved
        self._graph_pan_active = False
        self._graph_pan_touch_uid = None
        self._graph_pan_owner = None
        self._graph_pan_start_view_start = None
        self._graph_pan_start_view_end = None
        self._graph_pan_moved = False

        # После panning скрываем hover до нового движения мыши.
        if moved:
            try:
                self._hover_suspend_until_leave = True
                self._hover_suspend_base_pos = self._last_mouse_pos
                for g in getattr(self, "graph_slots", {}).values():
                    g.clear_hover()
            except Exception:
                pass
        return moved

    def _init_default_slots(self):
        """Дефолтные назначения 2 графика + 4 цифровых блока."""
        if isinstance(self.data_source, DatabaseDataSource):
            sids = self.config.get_signal_ids()
            g1 = sids.get("spo2")
            g2 = sids.get("pulse")
            v3 = sids.get("breathing")
            v4 = sids.get("temperature")
            self.slot_signal_ids = {
                "graph1": g1,
                "graph2": g2,
                "graph3": v3,
                "graph4": v4,
                "value1": g1,
                "value2": g2,
                "value3": v3,
                "value4": v4,
                "value5": g1,
                "value6": g2,
            }
        else:
            self.slot_signal_ids = {
                "graph1": "spo2",
                "graph2": "pulse",
                "graph3": "breathing",
                "graph4": "temperature",
                "value1": "spo2",
                "value2": "pulse",
                "value3": "breathing",
                "value4": "temperature",
                "value5": "spo2",
                "value6": "pulse",
            }

    def _build_param_info(self):
        """Список параметров для выбора."""
        param_info = {}
        if isinstance(self.data_source, DatabaseDataSource) and self.available_signals:
            seen_signatures: set[tuple[str, str, float, float]] = set()

            def valid_db_range(signal: dict) -> tuple[float, float] | None:
                db_min = signal.get("db_min")
                db_max = signal.get("db_max")
                if db_min is None or db_max is None:
                    return None
                try:
                    min_value = float(db_min)
                    max_value = float(db_max)
                except Exception:
                    return None
                if max_value <= min_value:
                    return None
                return min_value, max_value

            for i, signal in enumerate(self.available_signals):
                signal_id = signal["signal_id"]
                key = f"signal_{signal_id}"
                registry_range = get_display_range_by_signal_id(signal_id)
                registry_meta = get_signal_meta_by_signal_id(signal_id) or {}
                db_range = valid_db_range(signal)
                if db_range is not None:
                    disp_min, disp_max = db_range
                elif registry_range is not None:
                    disp_min, disp_max = registry_range
                else:
                    disp_min = signal["min"]
                    disp_max = signal["max"]
                name = registry_meta.get("title") or signal["name"]
                unit = registry_meta.get("unit") or signal.get("unit", "")
                signature = (
                    str(name).strip().lower(),
                    str(unit).strip().lower(),
                    round(float(disp_min), 6),
                    round(float(disp_max), 6),
                )
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)
                param_info[key] = {
                    "name": name,
                    "color": registry_meta.get("color") or self._colors_palette[i % len(self._colors_palette)],
                    "min": disp_min,
                    "max": disp_max,
                    "signal_id": signal_id,
                    "unit": unit,
                }
        else:
            base = self._get_param_info()
            for k in ["spo2", "pulse", "breathing", "temperature"]:
                info = base.get(k, {"title": k, "color": "#FFFFFF", "unit": ""})
                rng = get_display_range(k)
                meta = get_signal_meta(k)
                param_info[k] = {
                    "name": info["title"],
                    "color": info["color"],
                    "min": rng[0],
                    "max": rng[1],
                    "signal_id": k,
                    "unit": info.get("unit", meta.get("unit", "")),
                }
        return param_info

    def _get_linked_slot_id(self, slot_id: str) -> str | None:
        linked = {
            "graph1": "value1",
            "value1": "graph1",
            "graph2": "value2",
            "value2": "graph2",
            "graph3": "value3",
            "value3": "graph3",
            "graph4": "value4",
            "value4": "graph4",
            "value5": "graph1",
            "value6": "graph2",
        }
        return linked.get(slot_id)

    def _normalize_linked_slots(self):
        """Поддержать старые конфиги: если value1/value2 не заданы, берём сигнал графика."""
        for graph_slot, value_slot in (("graph1", "value1"), ("graph2", "value2"), ("graph3", "value3"), ("graph4", "value4")):
            graph_sig = self.slot_signal_ids.get(graph_slot)
            if self.slot_signal_ids.get(value_slot) is None and graph_sig is not None:
                self.slot_signal_ids[value_slot] = graph_sig

    def _get_param_keys_with_data_for_current_period(self) -> set[str]:
        """Ключи параметров, у которых есть данные за текущий период просмотра."""
        if not isinstance(self.data_source, DatabaseDataSource):
            return set()
        if not (self.history_start and self.history_end):
            return set()
        bed_id = self.data_source.get_current_bed_id()
        if bed_id is None or not self.available_signals:
            return set()

        signal_ids: list[int] = []
        for signal in self.available_signals:
            sid = signal.get("signal_id")
            if sid is None:
                continue
            try:
                signal_ids.append(int(sid))
            except Exception:
                pass
        if not signal_ids:
            return set()

        try:
            available_signal_ids = self.data_source.get_signal_ids_with_data_between(
                int(bed_id),
                signal_ids,
                self.history_start,
                self.history_end,
            )
        except Exception:
            return set()

        return {f"signal_{sid}" for sid in available_signal_ids}

    def _open_parameter_selection_for_slot(self, slot_id: str):
        """Открыть экран выбора параметра для слота."""
        self._clear_dashboard_grid_hover()
        if not self.manager:
            return

        param_screen = None
        for screen in self.manager.screens:
            if isinstance(screen, ParameterSelectionScreen) or (hasattr(screen, "name") and "parameter_selection" in screen.name):
                param_screen = screen
                break
        if not param_screen:
            param_screen = ParameterSelectionScreen(name=f"{self.name}_parameter_selection")
            self.manager.add_widget(param_screen)

        # ВАЖНО: "Назад" должен возвращать на текущий экран монитора в этом ScreenManager
        param_screen.previous_screen = self._get_navigation_screen_name()

        param_info = self._build_param_info()
        current = self.slot_signal_ids.get(slot_id)
        if isinstance(self.data_source, DatabaseDataSource):
            current_key = f"signal_{current}" if current is not None else None
        else:
            current_key = current

        if slot_id.startswith("value"):
            title_text = "Выбор параметра для цифрового блока"
            current_prefix = "Сейчас в блоке"
        else:
            title_text = "Выбор параметра для графика"
            current_prefix = "Сейчас на графике"

        param_screen.set_selection_title(title_text, current_prefix)
        param_screen.set_param_info(param_info)
        param_screen.set_available_param_keys(self._get_param_keys_with_data_for_current_period())
        param_screen.set_current_param_key(current_key)
        param_screen.set_on_parameter_selected(lambda key, data: self._on_slot_param_selected(slot_id, key, data))
        self.manager.current = param_screen.name

    def _on_slot_param_selected(self, slot_id: str, param_key: str, param_data: dict):
        """Применение выбранного параметра к конкретному слоту."""
        if slot_id.startswith("graph"):
            widget = self.graph_slots.get(slot_id)
        else:
            widget = self.value_slots.get(slot_id)
        if widget is None:
            return

        if isinstance(self.data_source, DatabaseDataSource):
            new_signal_id = param_data.get("signal_id")
        else:
            new_signal_id = param_key

        with self._slots_lock:
            self.slot_signal_ids[slot_id] = new_signal_id
            self._normalize_linked_slots()

        # Сначала меняем метаданные слотов. Для целевого графика это очистит старую
        # серию до загрузки новых данных, а неизменившиеся графики больше не трогаем.
        self._apply_slot_metas_to_widgets()

        if slot_id.startswith("graph"):
            # Подгружаем историю для обновленного графика
            if self.viewer_mode and self.history_start and self.history_end:
                self._schedule_history_reload()
            else:
                self._load_historical_data_for_slot(slot_id)
        self._save_monitor_config()

    def _load_historical_data_for_slot(self, slot_id: str):
        """Загрузка исторических данных только для одного граф-слота."""
        if not slot_id.startswith("graph"):
            return
        graph = self.graph_slots.get(slot_id)
        if not graph:
            return

        sig = self.slot_signal_ids.get(slot_id)
        if sig is None:
            return

        try:
            if isinstance(self.data_source, DatabaseDataSource):
                if not self._is_database_online():
                    graph.clear_data()
                    graph.set_empty_message("БД недоступна")
                    return
                if self.history_start and self.history_end:
                    data = self.data_source.get_historical_data_between(sig, self.history_start, self.history_end)
                else:
                    data = self.data_source.get_historical_data(sig, hours=6)
            else:
                # test mode: sig == param_key
                if self.history_start and self.history_end:
                    data = self.data_storage.load_data_between(str(sig), self.history_start, self.history_end)
                else:
                    data = self.data_storage.load_data(str(sig), hours=6)

            if data:
                values, times = zip(*data)
                graph.load_historical_data(list(values), list(times))
            if not (self.viewer_mode and self.history_start and self.history_end):
                try:
                    graph.filter_data_by_time_range(self.current_time_range.minutes)
                except Exception:
                    pass
        except Exception as e:
            print(f"Ошибка загрузки исторических данных для {slot_id}: {e}")

    
    def _load_monitor_config(self):
        """Загрузка конфигурации монитора из сохраненной раскладки"""
        if not self.layout_config_id or not self.monitor_config:
            return
        
        try:
            # Разрешение (если сохранено)
            res_str = self.monitor_config.get("resolution")
            if res_str:
                try:
                    self.current_resolution = TimeRange[res_str]
                except Exception:
                    pass
            # Загружаем кровать, если указана
            bed_id = self.monitor_config.get('bed_id')
            bed_name = self.monitor_config.get('bed_name')
            if bed_id and isinstance(self.data_source, DatabaseDataSource):
                self.data_source.set_bed_id(bed_id)
                # Загружаем список кроватей и обновляем кнопку
                if isinstance(self.data_source, DatabaseDataSource):
                    self._load_beds()
                    # После загрузки кроватей обновим текст кнопки
                    Clock.schedule_once(lambda dt: self._update_bed_button_after_load(bed_id, bed_name), 0.5)
            
            # Новая схема: slots
            slots = self.monitor_config.get("slots")
            if isinstance(slots, dict) and slots:
                for slot_id, info in slots.items():
                    if isinstance(self.data_source, DatabaseDataSource):
                        sid = info.get("signal_id")
                        if sid is not None:
                            self.slot_signal_ids[slot_id] = sid
                    else:
                        pk = info.get("param_key")
                        if pk:
                            self.slot_signal_ids[slot_id] = pk
            else:
                # Legacy: graphs + display_values
                graphs_config = self.monitor_config.get("graphs", {})
                if isinstance(graphs_config, dict):
                    if graphs_config.get("spo2", {}).get("signal_id") is not None:
                        self.slot_signal_ids["graph1"] = graphs_config["spo2"]["signal_id"]
                    if graphs_config.get("pulse", {}).get("signal_id") is not None:
                        self.slot_signal_ids["graph2"] = graphs_config["pulse"]["signal_id"]

                display_values = self.monitor_config.get("display_values", {})
                # В старом формате это были ключи spo2/pulse...
                if isinstance(display_values, dict):
                    p1 = display_values.get("param1")
                    p2 = display_values.get("param2")
                    if isinstance(self.data_source, DatabaseDataSource):
                        sids = self.config.get_signal_ids()
                        if p1 in sids:
                            self.slot_signal_ids["value1"] = sids.get(p1)
                        if p2 in sids:
                            self.slot_signal_ids["value2"] = sids.get(p2)
                    else:
                        if p1:
                            self.slot_signal_ids["value1"] = p1
                        if p2:
                            self.slot_signal_ids["value2"] = p2

            self.graph_settings = self._load_graph_settings_from_config()
            self.dashboard_grid_config = self._load_dashboard_grid_config()
            if getattr(self, "dashboard_grid_layout", None) is not None:
                self.dashboard_grid_layout.set_config(self.dashboard_grid_config, self._get_dashboard_widget_map())
                self._attach_dashboard_settings_button(self.dashboard_grid_layout)
            self._normalize_linked_slots()
            # Применим метаданные к виджетам (заголовки/цвет/единицы)
            self._apply_slot_metas_to_widgets()
            
            # Загружаем исторические данные
            Clock.schedule_once(lambda dt: self._schedule_history_reload(), 1.0)
        except Exception as e:
            print(f"Ошибка загрузки конфигурации монитора: {e}")
    
    def _update_bed_button_after_load(self, bed_id: int, bed_name: str):
        """Обновление кнопки кровати после загрузки списка кроватей"""
        if hasattr(self, 'bed_button'):
            self._set_bed_button_text(bed_name, int(bed_id))
    
    def _save_monitor_config(self):
        """Сохранение текущей конфигурации монитора в раскладку"""
        if not self.layout_config_id:
            return
        
        try:
            # Загружаем текущую конфигурацию раскладки
            layout_config = LayoutConfig.get_config(self.layout_config_id)
            if not layout_config:
                return
            
            # Обновляем конфигурацию текущего монитора
            if self.monitor_index < len(layout_config.get('monitors', [])):
                monitor_config = layout_config['monitors'][self.monitor_index]
                
                # Сохраняем кровать
                if isinstance(self.data_source, DatabaseDataSource):
                    bed_id = self.data_source.get_current_bed_id()
                    if bed_id:
                        monitor_config['bed_id'] = bed_id
                        # Находим имя кровати
                        if hasattr(self, 'available_beds') and self.available_beds:
                            bed = next((b for b in self.available_beds if b['id'] == bed_id), None)
                            monitor_config['bed_name'] = bed['name'] if bed else None
                
                # Сохраняем временной диапазон
                monitor_config['time_range'] = self.current_time_range.name
                # Сохраняем разрешение графиков
                if hasattr(self, "current_resolution"):
                    monitor_config["resolution"] = self.current_resolution.name
                
                # Новая схема: slots
                slots = {}
                if isinstance(self.data_source, DatabaseDataSource):
                    for slot_id, sid in self.slot_signal_ids.items():
                        if sid is not None:
                            slots[slot_id] = {"signal_id": int(sid)}
                else:
                    for slot_id, key in self.slot_signal_ids.items():
                        if key:
                            slots[slot_id] = {"param_key": str(key)}
                monitor_config["slots"] = slots
                monitor_config["graph_settings"] = {
                    slot_id: dict(self._get_graph_settings(slot_id))
                    for slot_id in self._graph_slot_ids()
                }
                monitor_config["dashboard_grid"] = self._normalize_dashboard_grid_config(self.dashboard_grid_config)

                # Legacy-поля оставляем для совместимости (минимально)
                monitor_config["graphs"] = monitor_config.get("graphs", {})
                monitor_config["display_values"] = monitor_config.get("display_values", {})
                
                # Сохраняем обновленную конфигурацию
                LayoutConfig.save_config(layout_config)
        except Exception as e:
            print(f"Ошибка сохранения конфигурации монитора: {e}")
    
    def _filter_graphs_by_time_range(self):
        """Фильтрация данных графиков по текущему временному диапазону"""
        if self.viewer_mode and self.history_start and self.history_end:
            # В viewer режиме показываем ровно выбранный диапазон, не режем "последними N минутами"
            return
        minutes = self.current_time_range.minutes
        for g in self.graph_slots.values():
            g.filter_data_by_time_range(minutes)
    
    def _load_historical_data(self):
        """Загрузка исторических данных из БД или файла (за последние 6 часов)"""
        try:
            # Загружаем историю только для 2 граф-слотов
            if isinstance(self.data_source, DatabaseDataSource):
                if not self._is_database_online():
                    return
                bed_id = self.data_source.get_current_bed_id()
                if bed_id is None:
                    print("Не выбрана кровать для загрузки данных")
                    return

            for slot_id in self._graph_slot_ids():
                self._load_historical_data_for_slot(slot_id)

            # В viewer-режиме индикаторы значений могут быть привязаны к сигналам,
            # которые не отображаются на графиках (например, дыхание/температура).
            # Загружаем для них историю отдельно, чтобы цифры обновлялись при hover.
            if self.viewer_mode:
                self._load_viewer_value_only_history()
                self._refresh_viewer_value_indicators_to_window_end()
            
            # Устанавливаем текущий временной диапазон для всех графиков (только для относительного режима)
            if not (self.viewer_mode and self.history_start and self.history_end):
                minutes = self.current_time_range.minutes
                for g in self.graph_slots.values():
                    g.filter_data_by_time_range(minutes)
            # После загрузки данных сразу пересчитаем hover для текущей позиции мыши.
            if self.viewer_mode:
                try:
                    Clock.schedule_once(lambda _dt: self._refresh_hover_now(), 0.05)
                    Clock.schedule_once(lambda _dt: self._refresh_hover_now(), 0.20)
                except Exception:
                    pass
        except Exception as e:
            print(f"Ошибка загрузки исторических данных: {e}")

    def _load_viewer_value_only_history(self) -> None:
        """Подгрузить историю для value-слотов, чьи сигналы не показаны на графиках.

        Используется в viewer-режиме, чтобы 4 индикатора в правой колонке могли
        отображать значения по hover, даже если для них нет соответствующего графика
        (типичный случай: дыхание/температура).
        """
        self._viewer_value_history = {}
        if not self.viewer_mode:
            return
        if not (self.history_start and self.history_end):
            return
        if not self._is_database_online():
            return

        graph_sigs: set[int] = set()
        for graph_slot in self._graph_slot_ids():
            sid = self.slot_signal_ids.get(graph_slot)
            if sid is None:
                continue
            try:
                graph_sigs.add(int(sid))
            except Exception:
                continue

        for slot_id in ("value1", "value2", "value3", "value4"):
            sid = self.slot_signal_ids.get(slot_id)
            if sid is None:
                continue
            try:
                sid_i = int(sid)
            except Exception:
                continue
            if sid_i in graph_sigs:
                continue  # значение возьмётся напрямую с графика
            try:
                data = self.data_source.get_historical_data_between(
                    sid_i, self.history_start, self.history_end
                )
                self._viewer_value_history[slot_id] = list(data) if data else []
            except Exception as e:
                print(f"[viewer] history load failed for {slot_id}: {e}")
                self._viewer_value_history[slot_id] = []

    def _viewer_value_at_time(self, slot_id: str, t: datetime) -> float | None:
        """Получить значение для value-слота на момент времени `t` в viewer-режиме."""
        if not self.viewer_mode or t is None:
            return None
        sid = self.slot_signal_ids.get(slot_id)
        if sid is None:
            return None

        # 1) Если сигнал уже отображается на одном из графиков — берём оттуда
        #    (точно ту же точку, что показывает hover на графике).
        for graph_slot in self._graph_slot_ids():
            gsid = self.slot_signal_ids.get(graph_slot)
            if gsid is None:
                continue
            try:
                same = int(gsid) == int(sid)
            except Exception:
                same = str(gsid) == str(sid)
            if not same:
                continue
            graph = self.graph_slots.get(graph_slot)
            if graph is None:
                continue
            try:
                p = graph.nearest_point(t)
                if p:
                    return float(p[2])
            except Exception:
                pass
            return None

        # 2) Иначе — ищем ближайшую точку в кэше истории value-слота.
        cache = self._viewer_value_history.get(slot_id) or []
        if not cache:
            return None
        try:
            best_val: float | None = None
            best_diff: float | None = None
            for value, ts in cache:
                try:
                    diff = abs((ts - t).total_seconds())
                except Exception:
                    continue
                if best_diff is None or diff < best_diff:
                    best_diff = diff
                    best_val = float(value)
            return best_val
        except Exception:
            return None

    def _refresh_viewer_value_indicators_to_window_end(self) -> None:
        """Установить индикаторы на последнее значение в окне просмотра.

        Вызывается после загрузки исторических данных, чтобы 4 индикатора
        в правой колонке показывали актуальное значение, даже до hover.
        """
        if not self.viewer_mode:
            return
        target_t = self._view_end or self.history_end
        if target_t is None:
            return
        for slot_id, widget in getattr(self, "value_slots", {}).items():
            try:
                val = self._viewer_value_at_time(slot_id, target_t)
                widget.set_value(val if val is not None else None)
            except Exception:
                continue
    
    def _update_data(self, dt):
        """
        Обновление данных каждую секунду и добавление новых точек на графики.
        
        Этот метод вызывается каждую секунду (1.0 секунда) и получает новые значения
        для каждого параметра в формате float из источника данных.
        
        Для работы с БД данные берутся из таблицы signals с фильтрацией по bed_id и signal_id.
        """
        # Ленивая загрузка исторических данных при первом обновлении
        if not self._historical_data_loaded:
            self._load_historical_data()
            self._historical_data_loaded = True
        
        # Обновление времени генератора (только для тестового генератора)
        if hasattr(self.data_source, 'update'):
            self.data_source.update(dt)
        
        def get_test_value(key: str):
            if key == "spo2":
                return self.data_source.get_spo2()
            if key == "pulse":
                return self.data_source.get_pulse()
            if key == "breathing":
                return self.data_source.get_breathing()
            if key == "temperature":
                return self.data_source.get_temperature()
            return None

        current_time = datetime.now()

        # Цифры
        if isinstance(self.data_source, DatabaseDataSource):
            for slot_id, widget in self.value_slots.items():
                sid = self.slot_signal_ids.get(slot_id)
                if sid is None:
                    continue
                value = self.data_source.get_value(int(sid))
                if value is not None:
                    widget.set_value(value)
        else:
            for slot_id, widget in self.value_slots.items():
                key = self.slot_signal_ids.get(slot_id)
                if not key:
                    continue
                widget.set_value(get_test_value(str(key)))

        # Графики (добавляем точки)
        if not hasattr(self, "_last_added_values"):
            self._last_added_values = {}

        if isinstance(self.data_source, DatabaseDataSource):
            for slot_id, graph in self.graph_slots.items():
                sid = self.slot_signal_ids.get(slot_id)
                if sid is None:
                    continue
                value = self.data_source.get_value(int(sid))
                if value is None:
                    continue
                last = self._last_added_values.get(slot_id)
                if last is None or abs(last - value) > 0.0001:
                    graph.add_data_point(float(value), current_time)
                    self._last_added_values[slot_id] = float(value)
        else:
            for slot_id, graph in self.graph_slots.items():
                key = self.slot_signal_ids.get(slot_id)
                if not key:
                    continue
                value = get_test_value(str(key))
                graph.add_data_point(float(value) if value is not None else 0.0, current_time)
    
    def _update_graphs(self, dt):
        """Обновление отображения графиков"""
        if not self._is_live_presentation_allowed():
            return
        for g in self.graph_slots.values():
            g.update_graph()
    
    def on_stop(self):
        """Остановка обновлений при закрытии"""
        if self._stopped:
            return
        self._stopped = True
        if self._db_retry_event is not None:
            try:
                self._db_retry_event.cancel()
            except Exception:
                pass
            self._db_retry_event = None
        # Hover unbind (viewer_mode)
        if self.viewer_mode:
            self._unbind_hover()
            self._set_viewer_playback_state(0)
        if self.data_update_event:
            Clock.unschedule(self.data_update_event)
        if self.graph_update_event:
            Clock.unschedule(self.graph_update_event)
        if self.camera_update_event:
            Clock.unschedule(self.camera_update_event)
            self.camera_update_event = None

        # Останавливаем поток
        self._stop_event.set()
        try:
            self._history_controller.cancel_all()
            self._history_controller.join_workers(timeout=2.0)
        except Exception:
            pass
        if self._data_thread and self._data_thread.is_alive():
            try:
                self._data_thread.join(timeout=1.5)
            except Exception:
                pass
        
        # Закрытие подключения к базе данных, если используется
        if isinstance(self.data_source, DatabaseDataSource):
            self.data_source.close()

