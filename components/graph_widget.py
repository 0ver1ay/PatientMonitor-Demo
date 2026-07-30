"""
Модульный компонент графика для монитора пациента
"""
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.stencilview import StencilView
from kivy.graphics import Color, Line, Rectangle, RoundedRectangle, Ellipse
from kivy.graphics.instructions import InstructionGroup
from kivy.metrics import dp
from kivy.core.text import Label as CoreLabel
from collections import deque
from datetime import datetime, timedelta, date
from bisect import bisect_left, bisect_right
import math
import logging

from utils.ui_style import UI_TEXT_MUTED, UI_TEXT_PRIMARY, UI_TEXT_STRONG, apply_rounded_panel


logger = logging.getLogger(__name__)


class GraphWidget(BoxLayout):
    """Виджет графика для отображения данных монитора"""
    
    def __init__(self, title, color, min_value=0, max_value=100, unit: str = "", **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.spacing = dp(6)
        self.padding = dp(8)
        
        self.title = title
        self.color = color
        self.min_value = min_value
        self.max_value = max_value
        self.unit = unit
        self._base_title_text = title
        self._layout_density = "normal"
        # Колбэки клика по графику (для выбора параметра графика).
        self._on_select = None
        self._on_context_select = None
        
        # Данные графика (увеличиваем для хранения больше данных)
        self.data_points = deque(maxlen=50000)  # Достаточно для 24 часов (86400 секунд)
        self.time_points = deque(maxlen=50000)
        
        # Текущий временной диапазон для отображения
        self.current_time_range_minutes = None
        self._live_time_axis_enabled = True
        # Разрешение/агрегация по времени (секунды). None = без агрегации.
        self.resolution_seconds: int | None = None
        # Режим отрисовки: "bars" = интервальные прямоугольники, "points" = сырые точки/линия.
        self.display_mode = "points"

        # Абсолютное окно времени для X-оси (viewer_mode).
        # Когда установлено, ось X строится по времени (а не по индексам).
        self.absolute_time_window: tuple[datetime, datetime] | None = None

        # Кэш того, что реально рисуется (источник правды для hover).
        self._display_times: list[datetime] = []
        self._display_values: list[float] = []
        self._display_bucket_ranges: list[tuple[float, float] | None] = []
        self._plot_area: tuple[float, float, float, float] | None = None  # (x0, y0, w, h) в координатах окна
        self._y_scale: tuple[float, float] | None = None  # (min_val, max_val) после padding
        
        # Графические инструкции (создаются один раз и обновляются)
        self._bg_rect = None
        self._bg_border = None
        self._grid_lines = []
        self._max_v_grid = 24
        self._x_axis_band_h = dp(26)
        self._x_tick_mark_color = None
        self._x_tick_marks: list[Line] = []
        self._x_minor_tick_color = None
        self._x_minor_tick_marks: list[Line] = []
        self._day_boundary_color = None
        self._day_boundary_lines: list[Line] = []
        self._x_axis_sep = None
        self._plot_group = None
        self._plot_line_color = None
        self._plot_lines: list[Line] = []
        self._plot_rects: list[Rectangle] = []
        self._plot_single_lines: list[Line] = []
        self._plot_point_markers: list[Ellipse] = []
        self._single_point_marker = None
        self._single_point_color = None
        self._hover_line = None
        self._hover_line_color = None
        self._hover_marker = None
        self._hover_marker_color = None
        self._tooltip_bg = None

        # Индикатор значения/времени в шапке (рядом с заголовком)
        self._header_indicator_container = None
        self._header_indicator_label: Label | None = None
        self._header_indicator_active: bool = False
        self._header_indicator_anchor_x: float | None = None

        # Hover state
        self._hover_time: datetime | None = None
        self._hover_show_tooltip: bool = False
        self._hover_last_idx: int | None = None
        self._hover_anchor_pos: tuple[float, float] | None = None
        self._hover_prefer_upper: bool | None = None
        self._needs_redraw = True
        self._last_live_redraw_end_time: datetime | None = None
        self._debug_render_logging = True
        self._debug_last_render_signature = None

        # Одиночное значение в бакете: по умолчанию показываем точкой, а не полоской.
        self.single_value_bucket_as_point = True

        # Временная шкала (подписи снизу внутри графика)
        self._x_tick_rects: list[Rectangle] = []
        self._x_tick_texts: list[str] = []
        self._x_tick_key = None

        # Y-ось: подписи значений
        self._y_tick_rects: list[Rectangle] = []
        self._y_tick_count = 5
        self._y_axis_label_w = dp(36)
        self._plot_top_inset = dp(8)
        self._x_tick_font_size = dp(11)
        self._y_tick_font_size = dp(10)
        self._show_header = True
        self._show_time_axis = True
        self._show_corner_badge = False
        self._latest_value_text = ""
        # Числовая часть значения (без единицы) — нужна, чтобы на узких бейджах
        # суметь убрать единицу и сохранить читаемые цифры.
        self._latest_value_numeric_text = ""
        self._corner_badge = None
        self._corner_badge_title = None
        self._corner_badge_value = None

        # Создание UI (должно быть ПОСЛЕ инициализации всех полей)
        self._create_ui()

    def set_layout_density(self, density: str) -> None:
        density = str(density or "normal").strip().lower()
        if density not in {"normal", "compact", "tiny", "ultra_tiny"}:
            density = "normal"
        self._layout_density = density
        self._update_responsive_metrics()

    def _init_indicator_style(self):
        """Rounded-rect background + border for the header indicator tooltip."""
        lbl = self._header_indicator_label
        if lbl is None:
            return
        r = dp(6)
        with lbl.canvas.before:
            self._indicator_bg_color = Color(0.15, 0.15, 0.18, 0.0)
            self._indicator_bg_rect = RoundedRectangle(
                pos=lbl.pos, size=lbl.size, radius=[r]
            )
            self._indicator_br_color = Color(1, 1, 1, 0.0)
            self._indicator_br_line = Line(
                rounded_rectangle=[lbl.x, lbl.y, lbl.width, lbl.height, r],
                width=dp(0.8),
            )

        def _upd_indicator_bg(*_a):
            if self._indicator_bg_rect:
                self._indicator_bg_rect.pos = lbl.pos
                self._indicator_bg_rect.size = lbl.size
            if self._indicator_br_line:
                self._indicator_br_line.rounded_rectangle = [
                    lbl.x, lbl.y, lbl.width, lbl.height, r,
                ]

        lbl.bind(pos=_upd_indicator_bg, size=_upd_indicator_bg)

    def _show_indicator_frame(self, visible: bool):
        """Toggle indicator background + border visibility."""
        alpha = 0.95 if visible else 0.0
        border_a = 0.12 if visible else 0.0
        if self._indicator_bg_color:
            self._indicator_bg_color.a = alpha
        if self._indicator_br_color:
            self._indicator_br_color.a = border_a

    def _hide_hover_marker(self):
        """Скрыть маркер hover-точки максимально надёжно."""
        if self._hover_marker_color is not None:
            try:
                # Некоторые драйверы могут "оставлять" 1px даже при size=(0,0),
                # поэтому дополнительно обнуляем alpha.
                self._hover_marker_color.rgba = (1, 1, 1, 0)
            except Exception:
                pass
        if self._hover_marker is not None:
            self._hover_marker.size = (0, 0)
            # на всякий случай уводим за экран, если драйвер/рендерер не любит нулевой размер
            self._hover_marker.pos = (-10000, -10000)

    def _reset_plot_artifacts(self):
        """Жестко очистить все plot-примитивы между сменами таймфрейма."""
        for ln in self._plot_lines or []:
            ln.points = []
        for ln in self._plot_single_lines or []:
            ln.points = []
        for rect in self._plot_rects or []:
            rect.size = (0, 0)
        for marker in self._plot_point_markers or []:
            marker.size = (0, 0)
            marker.pos = (-10000, -10000)
        self._display_times = []
        self._display_values = []
        self._display_bucket_ranges = []
        try:
            self.clear_hover()
        except Exception:
            pass

    def _debug_render_log(self, reason: str, **payload):
        """Диагностика рендера: помогает найти источник "мусорных" точек."""
        if not self._debug_render_logging:
            return
        try:
            parts = [f"{k}={v}" for k, v in payload.items()]
            msg = f"[GRAPH-RENDER] {self.title} | {reason} | " + ", ".join(parts)
            logger.warning(msg)
            print(msg)
        except Exception:
            pass

    def apply_param_meta(self, title: str, color: str, unit: str = "", min_value: float = 0.0, max_value: float = 100.0):
        """Применить метаданные параметра (после выбора пользователем)."""
        next_unit = unit or ""
        meta_changed = (
            self.title != title
            or self.color != color
            or self.unit != next_unit
            or float(self.min_value) != float(min_value)
            or float(self.max_value) != float(max_value)
        )

        self.title = title
        self._base_title_text = title
        self.color = color
        self.unit = next_unit
        self.min_value = min_value
        self.max_value = max_value

        if hasattr(self, "title_label"):
            self.title_label.text = self._base_title_text
            self.title_label.color = self._hex_to_rgb(color)
            self._sync_title_label_width()

        # Сбросим подпись и данные
        if hasattr(self, "value_label"):
            self.value_label.text = ""
        self._latest_value_text = ""
        self._latest_value_numeric_text = ""
        self._update_corner_badge_text()
        if meta_changed:
            self.clear_data()

    def set_resolution_seconds(self, seconds: int | None):
        """Установить шаг/разрешение отображения (агрегация по времени)."""
        prev_resolution = self.resolution_seconds
        if seconds is None:
            self.resolution_seconds = None
        else:
            self.resolution_seconds = max(1, int(seconds))
        if prev_resolution != self.resolution_seconds:
            self._debug_render_log(
                "resolution-change",
                prev=prev_resolution,
                new=self.resolution_seconds,
            )
            self._reset_plot_artifacts()
        self._needs_redraw = True
        self.update_graph()

    def set_display_mode(self, mode: str):
        """Установить режим отрисовки графика: bars или points."""
        normalized = str(mode or "").strip().lower()
        if normalized in {"rect", "rects", "rectangle", "rectangles", "bucket", "buckets"}:
            normalized = "bars"
        elif normalized in {"point", "line", "raw"}:
            normalized = "points"
        if normalized not in {"bars", "points"}:
            normalized = "points"
        if self.display_mode == normalized:
            return
        self.display_mode = normalized
        self._reset_plot_artifacts()
        self._needs_redraw = True
        self._debug_render_log("display-mode-change", mode=self.display_mode)
        self.update_graph()

    def set_single_value_bucket_as_point(self, enabled: bool):
        """Управлять отображением одиночного значения в бакете: точка или линия."""
        self.single_value_bucket_as_point = bool(enabled)
        self._needs_redraw = True
        self._debug_render_log("single-bucket-mode-change", enabled=self.single_value_bucket_as_point)
        self.update_graph()

    def set_absolute_time_window(self, start_dt: datetime | None, end_dt: datetime | None):
        """Установить абсолютное окно времени для X-оси (viewer_mode)."""
        if start_dt is None or end_dt is None:
            self.absolute_time_window = None
        else:
            # приводим к offset-naive (как и в данных)
            if getattr(start_dt, "tzinfo", None) is not None:
                start_dt = start_dt.replace(tzinfo=None)
            if getattr(end_dt, "tzinfo", None) is not None:
                end_dt = end_dt.replace(tzinfo=None)
            self.absolute_time_window = (start_dt, end_dt)
        # При смене study/исторического окна подписи X-оси нужно пересчитать заново.
        self._x_tick_key = None
        self._needs_redraw = True
    
    def _create_ui(self):
        """Создание пользовательского интерфейса"""
        # Header: простой BoxLayout — title | indicator | value
        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(32),
            spacing=dp(8),
            padding=(dp(6), 0, dp(6), 0),
        )
        self.header = header

        self.title_label = Label(
            text=self.title,
            size_hint_x=None,
            width=dp(90),
            color=self._hex_to_rgb(self.color),
            font_size=dp(16),
            bold=True,
            halign="left",
            valign="middle",
            shorten=True,
            shorten_from="right",
        )
        self.title_label.bind(height=lambda inst, h: setattr(inst, "text_size", (inst.width, h)))
        header.add_widget(self.title_label)

        # Контейнер для индикатора: RelativeLayout позволяет свободно двигать label по X
        self._header_indicator_container = RelativeLayout(size_hint_x=1)
        self._indicator_fixed_w = dp(160)
        self._header_indicator_label = Label(
            text="",
            size_hint=(None, None),
            width=self._indicator_fixed_w,
            height=dp(24),
            x=0,
            y=dp(4),
            color=UI_TEXT_PRIMARY,
            font_size=dp(12),
            halign="center",
            valign="middle",
            text_size=(self._indicator_fixed_w - dp(12), dp(24)),
        )
        self._indicator_bg_color = None
        self._indicator_bg_rect = None
        self._indicator_br_color = None
        self._indicator_br_line = None
        self._init_indicator_style()
        self._header_indicator_container.add_widget(self._header_indicator_label)
        header.add_widget(self._header_indicator_container)

        self.value_label = Label(
            text="",
            size_hint_x=None,
            width=dp(110),
            color=UI_TEXT_PRIMARY,
            font_size=dp(14),
            bold=True,
            halign="right",
            valign="middle",
            text_size=(None, None),
            shorten=True,
            shorten_from="left",
        )
        self.value_label.bind(size=self.value_label.setter("text_size"))
        header.add_widget(self.value_label)

        self.graph_clip = StencilView()
        self.graph_container = FloatLayout(size_hint=(None, None))
        self.graph_clip.bind(pos=self._sync_graph_clip_container, size=self._sync_graph_clip_container)
        self.graph_container.bind(size=self._on_graph_size, pos=self._on_graph_pos)
        self.graph_clip.add_widget(self.graph_container)
        self.add_widget(header)
        self.add_widget(self.graph_clip)
        self._sync_title_label_width()
        self.bind(size=self._update_responsive_metrics)
        self._update_responsive_metrics()

        # Подпись для пустого графика (оверлей, НЕ влияет на высоту графика)
        self.empty_label = Label(
            text="Нет данных",
            color=UI_TEXT_MUTED,
            font_size=dp(14),
            halign="center",
            valign="middle",
            size_hint=(1, 1),
            text_size=(0, 0),
        )
        self.empty_label.bind(size=lambda inst, s: setattr(inst, "text_size", s))
        self.empty_label.opacity = 0
        self.graph_container.add_widget(self.empty_label)

        # Tooltip (оверлей, управляется hover-логикой)
        self.tooltip_label = Label(
            text="",
            color=UI_TEXT_STRONG,
            font_size=dp(12),
            halign="left",
            valign="middle",
            size_hint=(None, None),
            opacity=0,
            text_size=(None, None),
        )
        self.tooltip_label.bind(size=self._sync_tooltip_bg, pos=self._sync_tooltip_bg)
        self.graph_container.add_widget(self.tooltip_label)

        # Квадратный бейдж в правом верхнем углу графика: название + текущее значение.
        self._corner_badge = BoxLayout(
            orientation="horizontal",
            size_hint=(None, None),
            width=dp(186),
            height=dp(42),
            padding=(dp(12), dp(5), dp(12), dp(5)),
            spacing=dp(9),
        )
        apply_rounded_panel(
            self._corner_badge,
            base_rgba=(0.14, 0.14, 0.16, 0.95),
            radius_px=dp(8),
            border_alpha=0.10,
        )
        self._corner_badge_title = Label(
            text=self.title,
            size_hint=(None, 1),
            width=dp(58),
            color=self._hex_to_rgb(self.color),
            font_size=dp(13),
            bold=True,
            halign="left",
            valign="middle",
            text_size=(0, 0),
            shorten=True,
            shorten_from="right",
        )
        self._corner_badge_value = Label(
            text="—",
            size_hint=(None, 1),
            width=dp(82),
            color=UI_TEXT_STRONG,
            font_size=dp(14),
            bold=True,
            halign="right",
            valign="middle",
            text_size=(0, 0),
            shorten=True,
            # Срезаем по правому краю, чтобы цифры (слева) сохранялись, а в крайнем
            # случае исчезала единица измерения.
            shorten_from="right",
        )
        self._corner_badge_title.bind(size=lambda inst, s: setattr(inst, "text_size", s))
        self._corner_badge_value.bind(size=lambda inst, s: setattr(inst, "text_size", s))
        self._corner_badge.add_widget(self._corner_badge_title)
        self._corner_badge.add_widget(self._corner_badge_value)
        self._corner_badge.opacity = 0
        self.graph_container.add_widget(self._corner_badge)
        self.graph_container.bind(
            pos=lambda *_: self._update_corner_badge_layout(),
            size=lambda *_: self._update_corner_badge_layout(),
        )
        self._update_corner_badge_layout()

    def _sync_graph_clip_container(self, *_args):
        if not hasattr(self, "graph_clip") or not hasattr(self, "graph_container"):
            return
        self.graph_container.pos = self.graph_clip.pos
        self.graph_container.size = self.graph_clip.size
    
    def _on_graph_size(self, instance, size):
        """Обработчик изменения размера графика"""
        self._ensure_canvas_instructions()
        self._update_background_geometry()
        self._needs_redraw = True
        self.update_graph()
    
    def _on_graph_pos(self, instance, pos):
        """Обработчик изменения позиции графика"""
        self._ensure_canvas_instructions()
        self._update_background_geometry()
        self._needs_redraw = True
        self.update_graph()
    
    def _ensure_canvas_instructions(self):
        """Создаём фон/сетку/линию один раз; дальше только обновляем геометрию и points."""
        if self._bg_rect is not None:
            return

        w = self.graph_container.width
        h = self.graph_container.height
        if w <= 0 or h <= 0:
            return

        with self.graph_container.canvas.before:
            # Фон
            Color(0.12, 0.12, 0.13, 1)
            self._bg_rect = RoundedRectangle(pos=self.graph_container.pos, size=(w, h), radius=[dp(10)])

            # Рамка (легкая)
            Color(1, 1, 1, 0.08)
            self._bg_border = Line(
                rounded_rectangle=[
                    self.graph_container.x,
                    self.graph_container.y,
                    w,
                    h,
                    dp(10),
                ],
                width=dp(1),
            )

            # Сетка (тонкая, полупрозрачная)
            Color(1, 1, 1, 0.06)
            self._grid_lines = []
            for _ in range(5):  # 4 внутренних + ось
                self._grid_lines.append(Line(points=[0, 0, 0, 0], width=dp(1)))
            for _ in range(self._max_v_grid):
                self._grid_lines.append(Line(points=[0, 0, 0, 0], width=dp(1)))

            # "Линейка" для оси времени: разделитель + риски (более заметные)
            self._x_tick_mark_color = Color(1, 1, 1, 0.42)
            self._x_axis_sep = Line(points=[0, 0, 0, 0], width=dp(1.2))
            self._x_tick_marks = []
            for _ in range(self._max_v_grid):
                self._x_tick_marks.append(Line(points=[0, 0, 0, 0], width=dp(2.0)))

            # Minor ticks (между основными) — более короткие и менее заметные
            self._x_minor_tick_color = Color(1, 1, 1, 0.20)
            self._x_minor_tick_marks = []
            for _ in range(self._max_v_grid * 4):
                self._x_minor_tick_marks.append(Line(points=[0, 0, 0, 0], width=dp(1)))

            # Отдельные линии смены суток (чуть ярче обычной сетки).
            self._day_boundary_color = Color(1, 1, 1, 0.22)
            self._day_boundary_lines = []
            for _ in range(self._max_v_grid):
                self._day_boundary_lines.append(Line(points=[0, 0, 0, 0], width=dp(1.6)))

        with self.graph_container.canvas.after:
            # Plot (в отдельной группе, чтобы можно было добавлять сегменты)
            self._plot_group = InstructionGroup()
            self._plot_line_color = Color(*self._hex_to_rgb(self.color))
            self._plot_group.add(self._plot_line_color)

            first_line = Line(points=[], width=dp(2), cap="round", joint="round")
            self._plot_lines = [first_line]
            self._plot_group.add(first_line)
            self._plot_rects = []
            self._plot_single_lines = []

            self.graph_container.canvas.after.add(self._plot_group)

            # Подписи шкалы времени (прямо внутри графика внизу)
            # Рисуем как текстуры (CoreLabel -> Rectangle) для производительности.
            self._x_tick_rects = []
            self._x_tick_texts = []
            for _ in range(self._max_v_grid):
                self._x_tick_rects.append(Rectangle(pos=(0, 0), size=(0, 0)))
                self._x_tick_texts.append("")

            # Подписи Y-оси
            self._y_tick_rects = []
            for _ in range(self._y_tick_count):
                self._y_tick_rects.append(Rectangle(pos=(0, 0), size=(0, 0)))

            # Hover: вертикальная линия + маркер точки
            self._hover_line_color = Color(1, 1, 1, 0.35)
            self._hover_line = Line(points=[], width=dp(1))
            self._hover_marker_color = Color(1, 1, 1, 0.9)
            self._hover_marker = Ellipse(pos=(0, 0), size=(0, 0))

        self._update_background_geometry()

        # Фон тултипа рисуем над всем (на canvas.before tooltip_label)
        try:
            with self.tooltip_label.canvas.before:
                Color(0.09, 0.09, 0.10, 0.9)
                self._tooltip_bg = RoundedRectangle(pos=self.tooltip_label.pos, size=self.tooltip_label.size, radius=[dp(8)])
                Color(1, 1, 1, 0.12)
                self._tooltip_border = Line(rounded_rectangle=[*self.tooltip_label.pos, *self.tooltip_label.size, dp(8)], width=dp(1))
        except Exception:
            self._tooltip_bg = None
            self._tooltip_border = None

    def _update_background_geometry(self):
        """Обновление позиций/размеров фона и сетки без перерисовки canvas."""
        if self._bg_rect is None:
            return

        x, y = self.graph_container.pos
        cw, ch = self.graph_container.size
        if cw <= 0 or ch <= 0:
            return

        self._bg_rect.pos = (x, y)
        self._bg_rect.size = (cw, ch)

        self._bg_border.rounded_rectangle = [x, y, cw, ch, dp(10)]

        # Внутренние отступы и рабочая область plot.
        ix0, iy0, iw, ih = self._compute_plot_geometry()
        y_label_w = float(self._y_axis_label_w)

        # 5 горизонтальных линий (0%, 25%, 50%, 75%, 100%)
        for i in range(5):
            yy = iy0 + (i / 4) * ih
            self._grid_lines[i].points = [ix0, yy, ix0 + iw, yy]

        self._update_y_labels(ix0 - y_label_w, iy0, y_label_w, ih)

        # Вертикальные линии шкалы времени + подписи внизу
        self._update_time_axis(ix0, iy0, iw, ih)

        self._update_corner_badge_layout()

    def _compute_plot_geometry(self) -> tuple[float, float, float, float]:
        x, y = self.graph_container.pos
        cw, ch = self.graph_container.size
        pad = float(dp(8))
        axis_h = float(self._x_axis_band_h)
        y_label_w = float(self._y_axis_label_w)
        plot_top_inset = float(self._plot_top_inset)
        ix0 = x + pad + y_label_w
        iy0 = y + pad + axis_h
        iw = max(cw - pad * 2 - y_label_w, 1)
        ih = max(ch - pad * 2 - axis_h - plot_top_inset, 1)
        return ix0, iy0, iw, ih

    def set_on_select(self, callback) -> None:
        """Колбэк по обычному клику (левый клик / тач) — обычно открывает выбор параметра."""
        self._on_select = callback

    def set_on_context_select(self, callback) -> None:
        """Колбэк по контекстному клику (правый клик)."""
        self._on_context_select = callback

    def on_touch_down(self, touch):
        # Обрабатываем только клики, попавшие в видимую область графика. Hover/курсор
        # остаются на window-level и не зависят от этого хендлера.
        try:
            in_widget = self.collide_point(*touch.pos)
            in_graph = False
            graph_container = getattr(self, "graph_container", None)
            if graph_container is not None:
                try:
                    in_graph = graph_container.collide_point(*touch.pos)
                except Exception:
                    in_graph = False
        except Exception:
            in_widget = False
            in_graph = False

        if in_widget or in_graph:
            button = getattr(touch, "button", None)
            if button == "right":
                if callable(self._on_context_select):
                    try:
                        self._on_context_select()
                    except Exception:
                        pass
                    return True
            elif button is None or button == "left":
                if callable(self._on_select):
                    try:
                        self._on_select()
                    except Exception:
                        pass
                    return True

        return super().on_touch_down(touch)

    def set_header_visible(self, visible: bool) -> None:
        self._show_header = bool(visible)
        self._update_responsive_metrics()

    def set_time_axis_visible(self, visible: bool) -> None:
        self._show_time_axis = bool(visible)
        self._update_responsive_metrics()

    def set_corner_badge_visible(self, visible: bool) -> None:
        self._show_corner_badge = bool(visible)
        self._update_corner_badge_layout()
        self._update_corner_badge_text()

    def _update_corner_badge_text(self) -> None:
        if self._corner_badge_title is not None:
            self._corner_badge_title.text = self.title
            self._corner_badge_title.color = self._hex_to_rgb(self.color)
        if self._corner_badge_value is not None:
            self._corner_badge_value.text = self._latest_value_text or "—"
        self._update_corner_badge_layout()

    def _measure_text_width(self, text: str, font_size, bold: bool = False) -> float:
        try:
            cl = CoreLabel(text=str(text or ""), font_size=font_size, bold=bold)
            cl.refresh()
            return float(cl.texture.size[0]) if cl.texture else 0.0
        except Exception:
            return 0.0

    def _update_corner_badge_layout(self) -> None:
        if self._corner_badge is None:
            return
        self._corner_badge.opacity = 1 if self._show_corner_badge else 0
        if not self._show_corner_badge:
            return
        margin = dp(10)
        graph_w = max(0.0, float(getattr(self.graph_container, "width", 0) or 0))
        max_badge_w = max(float(dp(118)), graph_w - margin * 2)

        pad_l, _pad_t, pad_r, _pad_b = self._corner_badge.padding
        spacing = float(self._corner_badge.spacing)

        # Заголовок
        title_text = self._corner_badge_title.text if self._corner_badge_title else ""
        title_font = self._corner_badge_title.font_size if self._corner_badge_title else dp(12)
        title_needed = self._measure_text_width(title_text, title_font, True) + dp(6)

        # Значение: пробуем "число + единица", если узко — оставляем только число.
        # При совсем малой ширине — уменьшаем шрифт значения, чтобы цифры всегда читались.
        full_value_text = self._latest_value_text or (
            self._corner_badge_value.text if self._corner_badge_value else ""
        )
        numeric_value_text = self._latest_value_numeric_text or full_value_text

        base_value_font = self._corner_badge_value.font_size if self._corner_badge_value else dp(14)
        min_value_font = max(float(dp(10)), float(base_value_font) * 0.72)
        # Минимальный заголовок (хотя бы 3-4 символа), чтобы вообще что-то было видно.
        min_title_w = float(dp(36))
        value_pad = dp(8)

        chosen_value_text = full_value_text
        chosen_value_font = base_value_font
        budget = max_badge_w - pad_l - pad_r - spacing
        # 1) Пробуем полный текст со штатным шрифтом.
        full_value_needed = self._measure_text_width(full_value_text, base_value_font, True) + value_pad
        if full_value_needed + min_title_w <= budget:
            chosen_value_text = full_value_text
            chosen_value_font = base_value_font
        else:
            # 2) Оставляем только числовую часть.
            numeric_needed = self._measure_text_width(numeric_value_text, base_value_font, True) + value_pad
            if numeric_needed + min_title_w <= budget:
                chosen_value_text = numeric_value_text
                chosen_value_font = base_value_font
            else:
                # 3) Уменьшаем шрифт числовой части, пока не влезет (но не ниже min).
                f = float(base_value_font)
                step = max(float(dp(0.5)), f * 0.06)
                while f > min_value_font:
                    f = max(min_value_font, f - step)
                    needed = self._measure_text_width(numeric_value_text, f, True) + value_pad
                    if needed + min_title_w <= budget:
                        break
                chosen_value_text = numeric_value_text
                chosen_value_font = f

        if self._corner_badge_value is not None:
            if self._corner_badge_value.text != chosen_value_text:
                self._corner_badge_value.text = chosen_value_text
            self._corner_badge_value.font_size = chosen_value_font

        value_needed = self._measure_text_width(chosen_value_text, chosen_value_font, True) + value_pad
        content_w = max(
            float(dp(96)),
            min(max_badge_w, title_needed + value_needed + pad_l + pad_r + spacing) - pad_l - pad_r - spacing,
        )
        # Значению отдаём ровно то, что ему нужно (но не меньше его потребности и не больше доступного).
        value_w = min(max(value_needed, float(dp(40))), max(float(dp(40)), content_w - min_title_w))
        title_w = max(min_title_w, content_w - value_w)
        # Если титул не влезает целиком — это допустимо, у него shorten=True по правому краю.

        if self._corner_badge_title is not None:
            self._corner_badge_title.width = title_w
            self._corner_badge_title.text_size = (title_w, self._corner_badge_title.height)
        if self._corner_badge_value is not None:
            self._corner_badge_value.width = value_w
            self._corner_badge_value.text_size = (value_w, self._corner_badge_value.height)
        self._corner_badge.width = min(max_badge_w, title_w + value_w + pad_l + pad_r + spacing)
        self._corner_badge.pos = (
            self.graph_container.right - self._corner_badge.width - margin,
            self.graph_container.top - self._corner_badge.height - margin,
        )

    def _update_y_labels(self, lx: float, iy0: float, lw: float, ih: float):
        """Отрисовать подписи значений вдоль Y-оси."""
        if not self._y_tick_rects:
            return
        y_scale = self._y_scale
        if y_scale is None:
            min_v, max_v = float(self.min_value), float(self.max_value)
        else:
            min_v, max_v = y_scale
        n = self._y_tick_count
        rng = max_v - min_v
        if rng <= 0:
            rng = 1
        for i in range(n):
            rect = self._y_tick_rects[i]
            frac = i / (n - 1) if n > 1 else 0.5
            val = min_v + frac * rng
            yy = iy0 + frac * ih
            if abs(val) < 1:
                txt = f"{val:.2f}"
            elif abs(val) < 10:
                txt = f"{val:.1f}"
            else:
                txt = f"{val:.0f}"
            cl = CoreLabel(text=txt, font_size=self._y_tick_font_size, color=(0.58, 0.58, 0.60, 1))
            cl.refresh()
            tex = cl.texture
            tw, th = tex.size
            rect.texture = tex
            rect.pos = (lx + lw - tw - dp(2), yy - th / 2)
            rect.size = (tw, th)

    def _get_valid_absolute_time_window(self) -> tuple[datetime, datetime] | None:
        abs_win = self.absolute_time_window
        if abs_win and abs_win[0] and abs_win[1]:
            try:
                if abs_win[1] > abs_win[0]:
                    return abs_win[0], abs_win[1]
            except Exception:
                pass
        return None

    def _is_live_time_window_active(self) -> bool:
        return (
            self._live_time_axis_enabled
            and self._get_valid_absolute_time_window() is None
            and bool(self.current_time_range_minutes)
        )

    def set_live_time_axis_enabled(self, enabled: bool) -> None:
        """Разрешить или заморозить автоматический сдвиг live-шкалы."""
        self._live_time_axis_enabled = bool(enabled)
        self._last_live_redraw_end_time = None
        self._needs_redraw = True
        self.update_graph()

    def set_empty_message(self, message: str) -> None:
        """Изменить текст оверлея для loading/empty/offline-состояний."""
        if hasattr(self, "empty_label"):
            self.empty_label.text = str(message or "Нет данных")
            if not self.data_points:
                self.empty_label.opacity = 1

    def _get_live_time_window(self, end: datetime | None = None) -> tuple[datetime, datetime] | None:
        if not self._is_live_time_window_active():
            return None
        try:
            end = end or datetime.now()
            start = end - timedelta(minutes=float(self.current_time_range_minutes))
            if end > start:
                return start, end
        except Exception:
            pass
        return None

    def _should_redraw_live_window(self) -> bool:
        """Нужно ли сдвинуть live-окно без новых точек."""
        win = self._get_live_time_window()
        if not win:
            return False
        _start, end = win
        last_end = self._last_live_redraw_end_time
        if last_end is None:
            return True
        try:
            elapsed_s = (end - last_end).total_seconds()
        except Exception:
            return True
        if elapsed_s <= 0:
            return False
        width = float(getattr(getattr(self, "graph_container", None), "width", 0) or 0)
        span_s = max(float(self.current_time_range_minutes) * 60.0, 1.0)
        seconds_per_pixel = span_s / max(width, 1.0)
        threshold_s = max(0.2, min(0.5, seconds_per_pixel))
        return elapsed_s >= threshold_s

    def _remember_live_redraw_time(self):
        if self._is_live_time_window_active():
            self._last_live_redraw_end_time = datetime.now()
        else:
            self._last_live_redraw_end_time = None

    def _get_time_window_for_axis(self) -> tuple[datetime, datetime] | None:
        """
        Окно времени для X-шкалы.
        Приоритет:
        - absolute_time_window (viewer)
        - относительный диапазон (current_time_range_minutes) для live
        - текущее окно отображаемых данных (display_times)
        """
        abs_win = self._get_valid_absolute_time_window()
        if abs_win:
            return abs_win
        live_win = self._get_live_time_window()
        if live_win:
            return live_win
        if self._display_times:
            try:
                if self._display_times[-1] > self._display_times[0]:
                    return self._display_times[0], self._display_times[-1]
            except Exception:
                pass
        return None

    def _choose_tick_step_seconds(self, span_s: float) -> float:
        """Подобрать шаг рисок по времени под длительность окна."""
        # хотим ~5-7 подписей
        target_ticks = 6.0
        candidates = [
            1, 2, 5, 10, 15, 30,
            60, 120, 300, 600, 900, 1800,
            3600, 7200, 10800, 14400, 21600, 43200,
            86400, 2 * 86400, 7 * 86400,
        ]
        if span_s <= 0:
            return 60.0
        for s in candidates:
            if span_s / float(s) <= target_ticks:
                return float(s)
        return float(candidates[-1])

    def _choose_ruler_steps(self, span_s: float, iw: float) -> tuple[float, float]:
        """
        Подобрать шаги линейки:
        - major: основные риски
        - minor: мелкие риски (между основными)
        """
        candidates = [
            60, 120, 300, 600, 900, 1800,
            3600, 7200, 10800, 14400, 21600, 43200,
            86400, 2 * 86400, 7 * 86400,
        ]
        if span_s <= 0 or iw <= 1:
            return 3600.0, 900.0

        min_major_px = float(dp(60))
        best = float(candidates[-1])
        for s in candidates:
            s = float(s)
            px = iw * s / span_s
            cnt = span_s / s
            if px >= min_major_px and cnt <= float(self._max_v_grid):
                best = s
                break

        # minor step mapping (nice human steps)
        minor_map = {
            300.0: 60.0,     # 5m -> 1m
            600.0: 120.0,    # 10m -> 2m
            900.0: 300.0,    # 15m -> 5m
            1800.0: 600.0,   # 30m -> 10m
            3600.0: 900.0,   # 1h -> 15m
            7200.0: 1800.0,  # 2h -> 30m
            10800.0: 3600.0, # 3h -> 1h
            14400.0: 3600.0, # 4h -> 1h
            21600.0: 7200.0, # 6h -> 2h
            43200.0: 14400.0,# 12h -> 4h
            86400.0: 21600.0,# 24h -> 6h
        }
        minor = minor_map.get(best)
        if minor is None:
            # fallback: 4 minor divisions if possible
            minor = max(60.0, best / 4.0)
        return best, float(minor)

    def _ceil_to_step(self, dt: datetime, step_s: float) -> datetime:
        """Округлить dt вверх до границы step_s (без таймзон)."""
        if getattr(dt, "tzinfo", None) is not None:
            dt = dt.replace(tzinfo=None)
        step_s = max(1.0, float(step_s))

        # Для day/week — работаем по датам
        if step_s >= 86400:
            days = int(round(step_s / 86400))
            if days <= 0:
                days = 1
            ref = date(1970, 1, 1).toordinal()
            ord0 = dt.date().toordinal()
            k = (ord0 - ref + days - 1) // days
            next_ord = ref + k * days
            d = date.fromordinal(next_ord)
            return datetime(d.year, d.month, d.day, 0, 0, 0)

        base = datetime(dt.year, dt.month, dt.day, 0, 0, 0)
        delta = (dt - base).total_seconds()
        n = int(math.ceil(delta / step_s))
        return base + timedelta(seconds=n * step_s)

    def _format_tick(self, ts: datetime, span_s: float, step_s: float) -> str:
        """Формат подписи для шкалы времени."""
        try:
            if step_s < 60:
                return ts.strftime("%H:%M:%S")
            if step_s < 3600 and span_s < 86400:
                return ts.strftime("%H:%M")
            if step_s >= 86400:
                return ts.strftime("%d.%m")
            if span_s >= 86400:
                return ts.strftime("%d.%m %H:%M")
            return ts.strftime("%H:%M")
        except Exception:
            return ""

    def _aggregate_to_period_buckets(
        self,
        values: list[float],
        times: list[datetime],
        period_seconds: int,
        window_start: datetime,
        window_end: datetime,
    ) -> list[dict]:
        """
        Группировка точек в фиксированные бакеты периода.
        Правая граница бакета включительная, чтобы крайняя точка справа попадала в текущий период.
        """
        if not values or not times or period_seconds <= 0 or window_end <= window_start:
            return []

        period_us = int(period_seconds) * 1_000_000
        if period_us <= 0:
            return []

        buckets: dict[int, dict] = {}

        for ts, raw_v in zip(times, values):
            if ts is None:
                continue
            if getattr(ts, "tzinfo", None) is not None:
                ts = ts.replace(tzinfo=None)
            if ts < window_start or ts > window_end:
                continue
            try:
                v = float(raw_v)
            except Exception:
                continue

            us = int(round(ts.timestamp() * 1_000_000))
            bucket_idx = us // period_us
            # Правая граница включается в "левый" интервал (кроме самой левой точки окна).
            if (us % period_us) == 0 and ts > window_start:
                bucket_idx -= 1

            entry = buckets.get(bucket_idx)
            if entry is None:
                entry = {
                    "count": 1,
                    "min": v,
                    "max": v,
                    "single": v,
                    "single_time": ts,
                }
                buckets[bucket_idx] = entry
            else:
                entry["count"] += 1
                if v < entry["min"]:
                    entry["min"] = v
                if v > entry["max"]:
                    entry["max"] = v

        if not buckets:
            return []

        out: list[dict] = []
        for idx in sorted(buckets.keys()):
            b_start = datetime.fromtimestamp((idx * period_us) / 1_000_000)
            b_end = b_start + timedelta(seconds=period_seconds)
            e = buckets[idx]
            out.append(
                {
                    "start": b_start,
                    "end": b_end,
                    "count": int(e["count"]),
                    "min": float(e["min"]),
                    "max": float(e["max"]),
                    "single": float(e["single"]),
                    "single_time": e.get("single_time"),
                }
            )
        return out

    def _update_time_axis(self, ix0: float, iy0: float, iw: float, ih: float):
        """Обновить вертикальную разлиновку времени + подписи внизу графика."""
        # Если инструкций ещё нет — выйдем
        if not self._grid_lines:
            return

        win = self._get_time_window_for_axis()
        if not win:
            # fallback: 5 равномерных линий
            for i in range(self._max_v_grid):
                if i < 5:
                    xx = ix0 + (i / 4) * iw
                    self._grid_lines[5 + i].points = [xx, iy0, xx, iy0 + ih]
                else:
                    self._grid_lines[5 + i].points = [0, 0, 0, 0]
            for r in self._x_tick_rects:
                r.size = (0, 0)
            # ось/риски/линии смены суток спрячем
            if self._x_axis_sep is not None:
                self._x_axis_sep.points = [0, 0, 0, 0]
            for m in self._x_tick_marks or []:
                m.points = [0, 0, 0, 0]
            for m in self._x_minor_tick_marks or []:
                m.points = [0, 0, 0, 0]
            for m in self._day_boundary_lines or []:
                m.points = [0, 0, 0, 0]
            self._x_tick_key = None
            return

        start, end = win
        if getattr(start, "tzinfo", None) is not None:
            start = start.replace(tzinfo=None)
        if getattr(end, "tzinfo", None) is not None:
            end = end.replace(tzinfo=None)
        try:
            if end <= start:
                raise ValueError("bad window")
        except Exception:
            return

        span_s = (end - start).total_seconds()
        major_s, minor_s = self._choose_ruler_steps(span_s, iw)

        # Ключ кеша: подписи зависят не только от длины окна, но и от конкретных
        # start/end. Иначе при переключении на другое study с похожей длительностью
        # могут остаться старые даты на оси.
        try:
            step = max(1, int(minor_s))
            key = (
                int(span_s),
                int(major_s),
                int(minor_s),
                int(iw),
                int(ix0),
                int(iy0),
                int(start.timestamp() // step),
                int(end.timestamp() // step),
            )
        except Exception:
            key = (int(span_s), int(major_s), int(minor_s), int(iw), int(ix0), int(iy0))

        # Major ticks (основные)
        major_ticks: list[tuple[datetime, float]] = []
        t = self._ceil_to_step(start, major_s)
        while t <= end and len(major_ticks) < self._max_v_grid * 3:
            try:
                ratio = (t - start).total_seconds() / max(span_s, 1e-9)
            except Exception:
                ratio = 0.0
            ratio = max(0.0, min(1.0, ratio))
            x = ix0 + ratio * iw
            major_ticks.append((t, x))
            t = t + timedelta(seconds=major_s)

        # Фильтруем major ticks для отображения (минимальная дистанция между линиями)
        min_px_major = float(dp(45))
        filtered: list[tuple[datetime, float]] = []
        last_x = None
        for ts, x in major_ticks:
            if last_x is None or (x - last_x) >= min_px_major:
                filtered.append((ts, x))
                last_x = x
            if len(filtered) >= self._max_v_grid:
                break

        # Minor ticks: риски между major, шаг minor_s (но не рисуем если слишком плотно)
        minor_ticks: list[float] = []
        if minor_s and minor_s < major_s:
            px_minor = iw * float(minor_s) / max(span_s, 1e-9)
            if px_minor >= float(dp(12)):  # иначе будет "шум"
                tm = self._ceil_to_step(start, minor_s)
                seen = set()
                # отметки major, чтобы не дублировать
                for ts, _x in filtered:
                    try:
                        seen.add(int(ts.timestamp() // max(1, int(minor_s))))
                    except Exception:
                        pass
                cap = max(200, self._max_v_grid * 30)
                while tm <= end and len(minor_ticks) < cap:
                    try:
                        k = int(tm.timestamp() // max(1, int(minor_s)))
                    except Exception:
                        k = None
                    if k is None or k not in seen:
                        try:
                            ratio = (tm - start).total_seconds() / max(span_s, 1e-9)
                        except Exception:
                            ratio = 0.0
                        ratio = max(0.0, min(1.0, ratio))
                        minor_ticks.append(ix0 + ratio * iw)
                    tm = tm + timedelta(seconds=minor_s)

        # Вертикальные линии
        for i in range(self._max_v_grid):
            if i < len(filtered):
                xx = filtered[i][1]
                self._grid_lines[5 + i].points = [xx, iy0, xx, iy0 + ih]
            else:
                self._grid_lines[5 + i].points = [0, 0, 0, 0]

        # Линии смены суток (00:00) — на всю высоту области графика.
        day_boundaries_x: list[float] = []
        try:
            d = datetime(start.year, start.month, start.day) + timedelta(days=1)
            while d <= end and len(day_boundaries_x) < self._max_v_grid * 2:
                ratio = (d - start).total_seconds() / max(span_s, 1e-9)
                ratio = max(0.0, min(1.0, ratio))
                day_boundaries_x.append(ix0 + ratio * iw)
                d = d + timedelta(days=1)
        except Exception:
            day_boundaries_x = []
        for i in range(len(self._day_boundary_lines or [])):
            if i < len(day_boundaries_x):
                xx = day_boundaries_x[i]
                self._day_boundary_lines[i].points = [xx, iy0, xx, iy0 + ih]
            else:
                self._day_boundary_lines[i].points = [0, 0, 0, 0]

        # "Линейка" под графиком: разделитель и риски в полосе оси времени
        axis_h = float(self._x_axis_band_h)
        axis_top = iy0  # нижняя граница области графика = верх оси
        axis_bottom = iy0 - axis_h
        if self._x_axis_sep is not None:
            # тонкая линия-разделитель между графиком и осью времени
            self._x_axis_sep.points = [ix0, axis_top, ix0 + iw, axis_top] if self._show_time_axis else [0, 0, 0, 0]
        tick_len = min(dp(11), max(dp(6), axis_h * 0.55))
        minor_len = max(dp(4), tick_len * 0.55)
        # Делаем major/minor риски заметнее: они пересекают ось и уходят немного вверх в график.
        tick_up = min(dp(12), max(dp(6), ih * 0.08))
        minor_up = max(dp(3), tick_up * 0.55)
        tick_y0 = axis_top + tick_up
        tick_y1 = axis_top - tick_len
        minor_y0 = axis_top + minor_up
        minor_y1 = axis_top - minor_len
        for i in range(self._max_v_grid):
            if self._show_time_axis and i < len(filtered) and self._x_tick_marks and i < len(self._x_tick_marks):
                xx = filtered[i][1]
                self._x_tick_marks[i].points = [xx, tick_y0, xx, tick_y1]
            elif self._x_tick_marks and i < len(self._x_tick_marks):
                self._x_tick_marks[i].points = [0, 0, 0, 0]

        # Minor ticks (по шагу minor_s)
        minor_idx = 0
        for xx in minor_ticks:
            if not self._show_time_axis:
                break
            if minor_idx >= len(self._x_minor_tick_marks or []):
                break
            self._x_minor_tick_marks[minor_idx].points = [xx, minor_y0, xx, minor_y1]
            minor_idx += 1
        for j in range(minor_idx, len(self._x_minor_tick_marks or [])):
            self._x_minor_tick_marks[j].points = [0, 0, 0, 0]

        # Подписи
        if key != self._x_tick_key:
            # тексты/текстуры обновляем только при изменении key
            self._x_tick_key = key
            for i in range(self._max_v_grid):
                if self._show_time_axis and i < len(filtered):
                    txt = self._format_tick(filtered[i][0], span_s, major_s)
                    self._x_tick_texts[i] = txt
                else:
                    self._x_tick_texts[i] = ""

        # Подписи должны быть ПОД графиком (в выделенной нижней полосе),
        # чуть ниже, чтобы визуально не "залипали" на сетку.
        label_y = (iy0 - float(self._x_axis_band_h)) + dp(0)
        for i in range(self._max_v_grid):
            rect = self._x_tick_rects[i] if i < len(self._x_tick_rects) else None
            if rect is None:
                continue
            if self._show_time_axis and i < len(filtered) and self._x_tick_texts[i]:
                txt = self._x_tick_texts[i]
                cl = CoreLabel(text=txt, font_size=self._x_tick_font_size, color=(0.68, 0.68, 0.70, 1))
                cl.refresh()
                tex = cl.texture
                tw, th = tex.size
                x = filtered[i][1] - tw / 2
                # clamp inside plot area
                x = max(ix0, min(x, ix0 + iw - tw))
                rect.texture = tex
                rect.pos = (x, label_y)
                rect.size = (tw, th)
            else:
                rect.size = (0, 0)

    def _sync_tooltip_bg(self, *_args):
        """Синхронизировать подложку тултипа с Label."""
        if self._tooltip_bg is not None:
            self._tooltip_bg.pos = self.tooltip_label.pos
            self._tooltip_bg.size = self.tooltip_label.size
        if hasattr(self, "_tooltip_border") and self._tooltip_border is not None:
            self._tooltip_border.rounded_rectangle = [*self.tooltip_label.pos, *self.tooltip_label.size, dp(8)]
    
    def _hex_to_rgb(self, hex_color):
        """Конвертация hex цвета в RGB (0-1)"""
        if isinstance(hex_color, str):
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4)) + (1,)
        return hex_color
    
    def add_data_point(self, value: float, timestamp=None):
        """Добавление точки данных (значение должно быть float)"""
        # Преобразование в float для гарантии правильного типа
        try:
            value = float(value)
        except (ValueError, TypeError):
            # Если значение не может быть преобразовано в float, пропускаем его
            return
        
        if timestamp is None:
            timestamp = datetime.now()
        
        # Убираем timezone для совместимости (приводим к offset-naive)
        if timestamp.tzinfo is not None:
            timestamp = timestamp.replace(tzinfo=None)
        
        self.data_points.append(value)
        self.time_points.append(timestamp)

        # Обновим подпись текущего значения
        try:
            if value is not None:
                if float(value) == int(float(value)):
                    numeric_txt = f"{int(float(value))}"
                else:
                    numeric_txt = f"{float(value):.1f}"
                full_txt = f"{numeric_txt} {self.unit}" if self.unit else numeric_txt
                self.value_label.text = full_txt
                self._latest_value_text = full_txt
                self._latest_value_numeric_text = numeric_txt
                self._update_corner_badge_text()
        except Exception:
            pass

        # Отметим, что нужен перерендер (рисуем таймером, а не на каждую точку)
        self._needs_redraw = True
    
    def update_graph(self):
        """Обновление отображения графика"""
        if not self._needs_redraw and not self._should_redraw_live_window():
            return
        self._ensure_canvas_instructions()
        
        if len(self.data_points) < 1:
            if hasattr(self, "empty_label"):
                self.empty_label.opacity = 1
            # Очистка сегментов линии/точек
            for ln in self._plot_lines or []:
                ln.points = []
            for ln in self._plot_single_lines or []:
                ln.points = []
            for rect in self._plot_rects or []:
                rect.size = (0, 0)
            for marker in self._plot_point_markers or []:
                marker.size = (0, 0)
                marker.pos = (-10000, -10000)
            # Важно: если данных нет, очищаем кэш, иначе hover может показывать "старые" значения
            self._display_times = []
            self._display_values = []
            self._display_bucket_ranges = []
            self._y_scale = None
            try:
                self.clear_hover()
            except Exception:
                pass
            return
        if hasattr(self, "empty_label"):
            self.empty_label.opacity = 0
        
        # Получение размеров контейнера
        width = self.graph_container.width
        height = self.graph_container.height
        
        if width == 0 or height == 0:
            return

        x0, y0, w, h = self._compute_plot_geometry()

        self._plot_area = (x0, y0, w, h)
        # Обновим геометрию сетки/шкалы времени под текущее окно
        self._update_background_geometry()
        
        # Фильтрация данных по текущему временному диапазону
        filtered_values, filtered_times = self._get_filtered_data()
        
        # В viewer_mode / при zoom&pan: дополнительно фильтруем по absolute_time_window (окно просмотра)
        abs_win = self.absolute_time_window
        if abs_win and abs_win[0] and abs_win[1] and filtered_times and len(filtered_times) == len(filtered_values):
            try:
                start_dt, end_dt = abs_win
                if getattr(start_dt, "tzinfo", None) is not None:
                    start_dt = start_dt.replace(tzinfo=None)
                if getattr(end_dt, "tzinfo", None) is not None:
                    end_dt = end_dt.replace(tzinfo=None)
                if end_dt > start_dt:
                    pad_s = max(0, int(self.resolution_seconds or 0)) if self.display_mode == "bars" else 0
                    if pad_s > 0:
                        padded_start = start_dt - timedelta(seconds=pad_s)
                        padded_end = end_dt + timedelta(seconds=pad_s)
                    else:
                        padded_start = start_dt
                        padded_end = end_dt
                    left = bisect_left(filtered_times, padded_start)
                    right = bisect_right(filtered_times, padded_end)
                    filtered_times = filtered_times[left:right]
                    filtered_values = filtered_values[left:right]
            except Exception:
                pass

        if not filtered_values:
            for ln in self._plot_lines or []:
                ln.points = []
            for ln in self._plot_single_lines or []:
                ln.points = []
            for rect in self._plot_rects or []:
                rect.size = (0, 0)
            for marker in self._plot_point_markers or []:
                marker.size = (0, 0)
                marker.pos = (-10000, -10000)
            self._display_times = []
            self._display_values = []
            self._display_bucket_ranges = []
            return

        use_bucket_mode = (
            self.display_mode == "bars"
            and self.resolution_seconds is not None
            and len(filtered_times) == len(filtered_values)
        )
        # При наличии абсолютного исторического окна (viewer_mode / zoom&pan)
        # не возвращаемся в sparse point/line fallback: он как раз и создаёт
        # визуальный "мусор" поверх bucket-отрисовки.
        sparse_line_allowed = False
        abs_win = self.absolute_time_window
        use_sparse_line_mode = use_bucket_mode and sparse_line_allowed and len(filtered_values) <= 5
        buckets: list[dict] = []
        live_win = self._get_live_time_window()
        if use_bucket_mode and not use_sparse_line_mode and filtered_times:
            abs_win = self._get_valid_absolute_time_window()
            if abs_win:
                win_start = abs_win[0]
                win_end = abs_win[1]
            elif live_win:
                win_start = live_win[0]
                win_end = live_win[1]
            else:
                win_start = filtered_times[0]
                win_end = filtered_times[-1]
            if getattr(win_start, "tzinfo", None) is not None:
                win_start = win_start.replace(tzinfo=None)
            if getattr(win_end, "tzinfo", None) is not None:
                win_end = win_end.replace(tzinfo=None)
            if win_end <= win_start:
                win_end = win_start + timedelta(seconds=max(1, int(self.resolution_seconds or 1)))
            agg_pad_s = max(1, int(self.resolution_seconds or 1))
            buckets = self._aggregate_to_period_buckets(
                filtered_values,
                filtered_times,
                max(1, int(self.resolution_seconds)),
                win_start - timedelta(seconds=agg_pad_s),
                win_end + timedelta(seconds=agg_pad_s),
            )

        # Y-ось: клинический диапазон — основа; расширяется при выходе данных.
        if use_bucket_mode and not use_sparse_line_mode and buckets:
            data_min = min(b["min"] for b in buckets)
            data_max = max(b["max"] for b in buckets)
        else:
            data_min = min(filtered_values)
            data_max = max(filtered_values)
        cfg_min, cfg_max = self.min_value, self.max_value
        if data_max < cfg_min or data_min > cfg_max:
            min_val = data_min
            max_val = data_max
        else:
            min_val = cfg_min
            max_val = cfg_max
            if data_min < min_val:
                min_val = data_min
            if data_max > max_val:
                max_val = data_max
        
        # На компактных раскладках пиковые сигналы (АД и т.п.) визуально упираются
        # в верхнюю границу. Даем больше воздуха сверху, чем снизу.
        range_val = max_val - min_val
        if range_val == 0:
            range_val = 1
        compact_graph = self.height < float(dp(260)) or self._layout_density in {"compact", "tiny", "ultra_tiny"}
        top_padding = range_val * (0.22 if compact_graph else 0.14)
        bottom_padding = range_val * (0.08 if compact_graph else 0.10)
        min_val -= bottom_padding
        max_val += top_padding
        if min_val < 0 and data_min >= 0:
            min_val = 0

        self._y_scale = (min_val, max_val)

        # Обновим подписи Y-оси с актуальной шкалой
        if self._plot_area:
            _pa_x0, pa_y0, _pa_w, pa_h = self._plot_area
            pad = dp(8)
            y_label_w = float(self._y_axis_label_w)
            lx = self.graph_container.x + pad
            self._update_y_labels(lx, pa_y0, y_label_w, pa_h)

        # Обновляем цвет линии/точек
        if self._plot_line_color is not None:
            self._plot_line_color.rgba = self._hex_to_rgb(self.color)

        # Сначала полностью очищаем примитивы, затем заполняем активный режим.
        for ln in self._plot_lines or []:
            ln.points = []
        for ln in self._plot_single_lines or []:
            ln.points = []
        for rect in self._plot_rects or []:
            rect.size = (0, 0)
        for marker in self._plot_point_markers or []:
            marker.size = (0, 0)
            marker.pos = (-10000, -10000)
        single_points: list[tuple[float, float]] = []
        line_i = 0

        if use_bucket_mode and not use_sparse_line_mode:
            abs_win = self._get_valid_absolute_time_window()
            if abs_win:
                axis_start = abs_win[0]
                axis_end = abs_win[1]
            elif live_win:
                axis_start = live_win[0]
                axis_end = live_win[1]
            else:
                axis_start = filtered_times[0]
                axis_end = filtered_times[-1]
            if getattr(axis_start, "tzinfo", None) is not None:
                axis_start = axis_start.replace(tzinfo=None)
            if getattr(axis_end, "tzinfo", None) is not None:
                axis_end = axis_end.replace(tzinfo=None)
            if axis_end <= axis_start:
                axis_end = axis_start + timedelta(seconds=max(1, int(self.resolution_seconds or 1)))
            axis_span_s = max((axis_end - axis_start).total_seconds(), 1e-9)

            # Кэшируем то, что реально рисуем для hover.
            self._display_times = []
            self._display_values = []
            self._display_bucket_ranges = []
            visible_buckets: list[dict] = []
            edge_pad_s = float(max(1, int(self.resolution_seconds or 1)))
            draw_start = axis_start - timedelta(seconds=edge_pad_s)
            draw_end = axis_end + timedelta(seconds=edge_pad_s)

            for b in buckets:
                b_start = b["start"]
                b_end = b["end"]
                # Берём по одному соседнему периоду за край окна, чтобы не было
                # визуальных "дыр" на границах при мелком таймфрейме/скролле.
                if b_end < draw_start or b_start > draw_end:
                    continue
                visible_buckets.append(b)

            # В bucket-режиме постоянные point-маркеры полностью отключены:
            # они остаются только в sparse-line режиме, иначе дают артефакты
            # при смене масштаба и смешиваются с бакетной отрисовкой.
            render_single_as_point = False

            flat_bucket_px_h = float(dp(2.0))
            need_rects = 0
            need_lines = 0
            bucket_meta: list[dict] = []

            for idx, b in enumerate(visible_buckets):
                is_flat_bucket = False
                chain_prev = False
                chain_next = False
                if b["count"] >= 2:
                    try:
                        y_min_probe = y0 + max(0.0, min(1.0, (b["min"] - min_val) / max(max_val - min_val, 1e-9))) * h
                        y_max_probe = y0 + max(0.0, min(1.0, (b["max"] - min_val) / max(max_val - min_val, 1e-9))) * h
                        if abs(y_max_probe - y_min_probe) <= flat_bucket_px_h:
                            is_flat_bucket = True
                        else:
                            need_rects += 1
                    except Exception:
                        need_rects += 1
                bucket_meta.append(
                    {
                        "flat_bucket": is_flat_bucket,
                        "chain_prev": chain_prev,
                        "chain_next": chain_next,
                    }
                )

                if is_flat_bucket:
                    need_rects += 1
                elif b["count"] == 1:
                    need_rects += 1
            while len(self._plot_rects) < need_rects and self._plot_group is not None:
                r = Rectangle(pos=(0, 0), size=(0, 0))
                self._plot_rects.append(r)
                self._plot_group.add(r)
            while len(self._plot_single_lines) < need_lines and self._plot_group is not None:
                ln = Line(points=[], width=dp(2), cap="none", joint="miter")
                self._plot_single_lines.append(ln)
                self._plot_group.add(ln)
            for ln in self._plot_single_lines:
                try:
                    ln.cap = "none"
                    ln.joint = "miter"
                except Exception:
                    pass

            rect_i = 0
            for idx, b in enumerate(visible_buckets):
                meta = bucket_meta[idx]
                b_start = b["start"]
                b_end = b["end"]
                # Привязка bucket-hover и индикатора идёт к правой границе периода:
                # пользователь воспринимает бакет как "значение на конец интервала".
                b_anchor_ts = b_end

                left_ratio = (b_start - axis_start).total_seconds() / axis_span_s
                right_ratio = (b_end - axis_start).total_seconds() / axis_span_s
                left_ratio = max(0.0, min(1.0, float(left_ratio)))
                right_ratio = max(0.0, min(1.0, float(right_ratio)))
                x_left = x0 + min(left_ratio, right_ratio) * w
                x_right = x0 + max(left_ratio, right_ratio) * w
                x_left = self._clamp_plot_x(x_left, x0, w)
                x_right = self._clamp_plot_x(x_right, x0, w)
                if x_right <= x_left:
                    x_right = min(x0 + w, x_left + dp(1))

                if b["count"] >= 2:
                    y_min = y0 + max(0.0, min(1.0, (b["min"] - min_val) / max(max_val - min_val, 1e-9))) * h
                    y_max = y0 + max(0.0, min(1.0, (b["max"] - min_val) / max(max_val - min_val, 1e-9))) * h
                    y_min = self._clamp_plot_y(y_min, y0, h)
                    y_max = self._clamp_plot_y(y_max, y0, h)
                    yy0 = min(y_min, y_max)
                    yy1 = max(y_min, y_max)
                    hh_raw = abs(yy1 - yy0)
                    if meta["flat_bucket"]:
                        # Плоские бакеты рисуем как тонкий прямоугольник.
                        # Это убирает "точки" на концах, которые давали Line-сегменты.
                        y_mid = self._clamp_plot_y((y_min + y_max) * 0.5, y0, h)
                        rr = self._plot_rects[rect_i]
                        rr.pos = (x_left, y_mid - dp(0.6))
                        rr.size = (max(x_right - x_left, dp(1)), dp(1.2))
                        rect_i += 1
                    else:
                        hh = max(hh_raw, dp(1))
                        rr = self._plot_rects[rect_i]
                        rr.pos = (x_left, yy0)
                        rr.size = (max(x_right - x_left, dp(1)), min(hh, max(dp(1), (y0 + h) - yy0)))
                        rect_i += 1

                    self._display_times.append(b_anchor_ts)
                    self._display_values.append((float(b["min"]) + float(b["max"])) * 0.5)
                    self._display_bucket_ranges.append((float(b["min"]), float(b["max"])))
                elif b["count"] == 1:
                    y_single = y0 + max(0.0, min(1.0, (b["single"] - min_val) / max(max_val - min_val, 1e-9))) * h
                    y_single = self._clamp_plot_y(y_single, y0, h)
                    single_ts = b.get("single_time") or b_anchor_ts
                    if getattr(single_ts, "tzinfo", None) is not None:
                        single_ts = single_ts.replace(tzinfo=None)
                    single_ratio = (single_ts - axis_start).total_seconds() / axis_span_s
                    single_ratio = max(0.0, min(1.0, float(single_ratio)))
                    x_single = x0 + single_ratio * w
                    x_single = self._clamp_plot_x(x_single, x0, w)

                    if render_single_as_point and axis_start <= single_ts <= axis_end:
                        single_points.append((x_single, y_single))
                    else:
                        # Штрих держим внутри границ своего бакета, чтобы
                        # соседние одиночные периоды не налезали друг на друга.
                        bucket_w = max(float(x_right - x_left), float(dp(1)))
                        inset = min(float(dp(1)), bucket_w * 0.2)
                        seg_l = x_left + inset
                        seg_r = x_right - inset
                        if seg_r <= seg_l:
                            seg_l = x_left
                            seg_r = x_right
                        if seg_r <= seg_l:
                            seg_r = seg_l + dp(1)
                        rr = self._plot_rects[rect_i]
                        rr.pos = (seg_l, y_single - dp(0.6))
                        rr.size = (max(seg_r - seg_l, dp(1)), dp(1.2))
                        rect_i += 1

                    # Для одиночного бакета hover должен липнуть к реальному
                    # timestamp точки, иначе на мелких окнах маркер может
                    # считаться "вне окна" до правой границы периода.
                    self._display_times.append(single_ts)
                    self._display_values.append(float(b["single"]))
                    self._display_bucket_ranges.append(None)
                else:
                    pass

            for ln in self._plot_lines or []:
                ln.points = []

            # Скрываем неиспользованные примитивы
            for i in range(rect_i, len(self._plot_rects)):
                self._plot_rects[i].size = (0, 0)
            for i in range(line_i, len(self._plot_single_lines)):
                self._plot_single_lines[i].points = []
        else:
            self._display_bucket_ranges = []
            # Создание точек для линии (fallback без периода)
            line_segments: list[list[float]] = []
            current_segment: list[float] = []
            sparse_points = []
            abs_win = self._get_valid_absolute_time_window()
            abs_ok = False
            time_window_ok = False
            vis_start = None
            vis_end = None
            if abs_win:
                try:
                    vis_start, vis_end = abs_win
                    if getattr(vis_start, "tzinfo", None) is not None:
                        vis_start = vis_start.replace(tzinfo=None)
                    if getattr(vis_end, "tzinfo", None) is not None:
                        vis_end = vis_end.replace(tzinfo=None)
                    abs_ok = vis_end > vis_start
                    time_window_ok = abs_ok
                except Exception:
                    abs_ok = False
                    time_window_ok = False
                    vis_start = None
                    vis_end = None
            elif live_win:
                try:
                    vis_start, vis_end = live_win
                    time_window_ok = vis_end > vis_start
                except Exception:
                    time_window_ok = False
                    vis_start = None
                    vis_end = None

            self._display_times = list(filtered_times)
            self._display_values = [float(v) for v in filtered_values]
            gap_threshold_s = self._point_gap_threshold_seconds(self._display_times)
            prev_ts = None
            # "Поточечно" означает raw-серию как в main.py: без bucket-агрегации,
            # но с линией между соседними реальными точками. Постоянные маркеры
            # на каждую точку в плотных рядах превращаются в визуальные артефакты.
            raw_points_only = False
            for i, (ts, value) in enumerate(zip(self._display_times, self._display_values)):
                if time_window_ok and vis_start is not None and vis_end is not None:
                    try:
                        ratio = (ts - vis_start).total_seconds() / max((vis_end - vis_start).total_seconds(), 1e-9)
                    except Exception:
                        ratio = i / max(len(self._display_values) - 1, 1)
                    ratio = max(0.0, min(1.0, ratio))
                    x = x0 + ratio * w
                else:
                    x = x0 + (i / max(len(self._display_values) - 1, 1)) * w
                normalized = (value - min_val) / max(max_val - min_val, 1)
                normalized = max(0.0, min(1.0, float(normalized)))
                y = y0 + normalized * h
                x = self._clamp_plot_x(x, x0, w)
                y = self._clamp_plot_y(y, y0, h)
                split_segment = False
                if prev_ts is not None and gap_threshold_s is not None:
                    try:
                        split_segment = (ts - prev_ts).total_seconds() > gap_threshold_s
                    except Exception:
                        split_segment = False
                if split_segment and current_segment:
                    line_segments.append(current_segment)
                    current_segment = []
                if raw_points_only:
                    if vis_start is None or vis_end is None or vis_start <= ts <= vis_end:
                        single_points.append((x, y))
                else:
                    current_segment.extend([x, y])
                prev_ts = ts
                if use_sparse_line_mode and (
                    not time_window_ok or vis_start is None or vis_end is None or vis_start <= ts <= vis_end
                ):
                    sparse_points.append((x, y))
            if current_segment:
                line_segments.append(current_segment)

            if raw_points_only:
                for ln in self._plot_lines:
                    ln.points = []
            else:
                render_segments: list[list[float]] = []
                for seg in line_segments:
                    if len(seg) < 4:
                        continue
                    simplified = self._simplify_dense_line_points(seg)
                    render_segments.extend(self._chunk_line_points(simplified))
                needed_lines = len(render_segments)
                while len(self._plot_lines) < max(1, needed_lines) and self._plot_group is not None:
                    ln = Line(points=[], width=dp(1.8), cap="round", joint="round")
                    self._plot_lines.append(ln)
                    self._plot_group.add(ln)
                for ln in self._plot_lines:
                    try:
                        ln.cap = "round"
                        ln.joint = "round"
                        ln.width = dp(1.8)
                    except Exception:
                        pass
                line_idx = 0
                for seg in render_segments:
                    if line_idx < len(self._plot_lines):
                        self._plot_lines[line_idx].points = seg
                        line_idx += 1
                for i in range(line_idx, len(self._plot_lines)):
                    self._plot_lines[i].points = []
            if use_sparse_line_mode:
                single_points.extend(sparse_points)

        # Постоянные маркеры-точки показываем только там, где это действительно
        # помогает чтению графика (например, в минутном окне).
        need_point_markers = len(single_points)
        while len(self._plot_point_markers) < need_point_markers and self._plot_group is not None:
            marker = Ellipse(pos=(-10000, -10000), size=(0, 0))
            self._plot_point_markers.append(marker)
            self._plot_group.add(marker)
        raw_points_only = self.display_mode == "points" and self.absolute_time_window is not None
        point_r = dp(1.7) if raw_points_only else (dp(3.2) if use_sparse_line_mode else dp(2.6))
        for i, (px, py) in enumerate(single_points):
            marker = self._plot_point_markers[i]
            marker.pos = (px - point_r, py - point_r)
            marker.size = (point_r * 2, point_r * 2)
        for i in range(need_point_markers, len(self._plot_point_markers)):
            self._plot_point_markers[i].size = (0, 0)
            self._plot_point_markers[i].pos = (-10000, -10000)

        # Если hover активен — пересчитаем позицию по новому кэшу
        if self._hover_time is not None:
            try:
                self.set_hover_time(
                    self._hover_time,
                    show_tooltip=self._hover_show_tooltip,
                    anchor_pos=self._hover_anchor_pos,
                    tooltip_text=self.tooltip_label.text,
                    prefer_upper=self._hover_prefer_upper,
                )
            except Exception:
                pass

        # Сброс флага после успешной отрисовки
        visible_marker_count = 0
        for marker in self._plot_point_markers or []:
            try:
                if marker.size and marker.size[0] > 0 and marker.size[1] > 0:
                    visible_marker_count += 1
            except Exception:
                pass
        abs_span_s = None
        try:
            if self.absolute_time_window and self.absolute_time_window[0] and self.absolute_time_window[1]:
                abs_span_s = int((self.absolute_time_window[1] - self.absolute_time_window[0]).total_seconds())
        except Exception:
            abs_span_s = None
        render_sig = (
            self.display_mode,
            int(self.resolution_seconds or 0),
            bool(use_bucket_mode),
            bool(use_sparse_line_mode),
            int(len(single_points)),
            int(visible_marker_count),
            int(line_i),
            int(len(self._plot_rects or [])),
            int(abs_span_s or 0),
        )
        if render_sig != self._debug_last_render_signature:
            self._debug_last_render_signature = render_sig
            self._debug_render_log(
                "render-state",
                mode=self.display_mode,
                res=self.resolution_seconds,
                abs_span_s=abs_span_s,
                bucket_mode=use_bucket_mode,
                sparse_mode=use_sparse_line_mode,
                single_points=len(single_points),
                visible_markers=visible_marker_count,
                plot_lines=len(self._plot_lines or []),
                single_lines=line_i,
                rects=len(self._plot_rects or []),
                display_times=len(self._display_times or []),
            )
        self._needs_redraw = False
        self._remember_live_redraw_time()

    def _format_tooltip_time(self, ts: datetime) -> str:
        """Форматировать timestamp для тултипа в зависимости от длины периода."""
        try:
            abs_win = self.absolute_time_window
            if abs_win and abs_win[0] and abs_win[1] and abs_win[1] > abs_win[0]:
                span = abs_win[1] - abs_win[0]
                if span <= timedelta(hours=6):
                    return ts.strftime("%H:%M:%S")
                if span <= timedelta(days=2):
                    return ts.strftime("%d.%m %H:%M")
                return ts.strftime("%d.%m.%Y %H:%M")
        except Exception:
            pass
        return ts.strftime("%H:%M:%S")

    def _format_header_indicator(self, ts: datetime, val: float) -> str:
        """Короткая строка для индикатора в шапке: время + значение."""
        try:
            time_txt = ts.strftime("%H:%M:%S")
        except Exception:
            time_txt = ""
        try:
            vtxt = self.format_value(val)
        except Exception:
            vtxt = str(val)
        if self.unit:
            vtxt = f"{vtxt} {self.unit}"
        if time_txt:
            return f"{time_txt}  {vtxt}"
        return vtxt

    def _sync_title_label_width(self):
        """Ширина заголовка по фактической длине текста, но не шире доступного места."""
        if not hasattr(self, "title_label") or self.title_label is None:
            return
        try:
            lbl = self.title_label
            cl = CoreLabel(text=lbl.text, font_size=lbl.font_size, bold=lbl.bold)
            cl.refresh()
            tw = cl.texture.size[0] if cl.texture else 0
            max_w = max(dp(40), self.width * 0.34)
            new_w = min(max_w, max(dp(40), tw + dp(8)))
            lbl.width = new_w
            lbl.text_size = (new_w, lbl.height)
        except Exception:
            pass

    def _clamp(self, value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    def _clamp_plot_x(self, x: float, x0: float, width: float) -> float:
        return self._clamp(float(x), float(x0), float(x0 + width))

    def _clamp_plot_y(self, y: float, y0: float, height: float) -> float:
        return self._clamp(float(y), float(y0), float(y0 + height))

    def _update_responsive_metrics(self, *_args):
        """Ужать шапку и оси на маленьких раскладках, чтобы график не вылезал."""
        try:
            w = float(self.width)
            h = float(self.height)
        except Exception:
            return
        if w <= 0 or h <= 0:
            return

        density_scale = {
            "normal": 1.00,
            "compact": 0.95,
            "tiny": 0.88,
            "ultra_tiny": 0.82,
        }.get(self._layout_density, 1.00)
        header_h = self._clamp(h * 0.18 * density_scale, float(dp(22)), float(dp(32)))
        axis_h = self._clamp(h * 0.12 * density_scale, float(dp(16)), float(dp(26)))
        y_label_w = self._clamp(w * 0.08, float(dp(24)), float(dp(36)))
        indicator_w = self._clamp(w * 0.30, float(dp(84)), float(dp(160)))
        title_fs = self._clamp(header_h * 0.50, float(dp(11)), float(dp(16)))
        value_fs = self._clamp(header_h * 0.42, float(dp(10)), float(dp(14)))
        indicator_fs = self._clamp(header_h * 0.36, float(dp(9)), float(dp(12)))

        self._x_axis_band_h = axis_h if self._show_time_axis else 0
        self._y_axis_label_w = y_label_w
        self._plot_top_inset = self._clamp(h * 0.05, float(dp(4)), float(dp(12)))
        self._x_tick_font_size = self._clamp(axis_h * 0.46, float(dp(8)), float(dp(11)))
        self._y_tick_font_size = self._clamp(y_label_w * 0.30, float(dp(8)), float(dp(10)))

        if hasattr(self, "header"):
            self.header.height = header_h if self._show_header else 0
            self.header.opacity = 1 if self._show_header else 0
            self.header.spacing = self._clamp(w * 0.01, float(dp(4)), float(dp(8)))

        if hasattr(self, "title_label"):
            self.title_label.font_size = title_fs
            self.title_label.height = header_h
            self._sync_title_label_width()

        if hasattr(self, "_header_indicator_label") and self._header_indicator_label is not None:
            self._indicator_fixed_w = indicator_w
            self._header_indicator_label.width = indicator_w
            self._header_indicator_label.height = self._clamp(header_h * 0.78, float(dp(18)), float(dp(24)))
            self._header_indicator_label.y = max(0.0, (header_h - self._header_indicator_label.height) * 0.5)
            self._header_indicator_label.font_size = indicator_fs
            self._header_indicator_label.text_size = (indicator_w - dp(12), self._header_indicator_label.height)

        if hasattr(self, "value_label"):
            self.value_label.width = self._clamp(w * 0.24, float(dp(56)), float(dp(110)))
            self.value_label.font_size = value_fs
            self.value_label.text_size = (self.value_label.width, header_h)

        if hasattr(self, "empty_label"):
            self.empty_label.font_size = self._clamp(h * 0.08, float(dp(11)), float(dp(14)))
        if hasattr(self, "tooltip_label"):
            self.tooltip_label.font_size = self._clamp(h * 0.06, float(dp(10)), float(dp(12)))
        if self._corner_badge is not None:
            badge_h = self._clamp(h * 0.18, float(dp(36)), float(dp(46)))
            self._corner_badge.width = self._clamp(w * 0.34, float(dp(150)), float(dp(220)))
            self._corner_badge.height = badge_h
            self._corner_badge.padding = (dp(12), dp(5), dp(12), dp(5))
            if self._corner_badge_title is not None:
                self._corner_badge_title.font_size = self._clamp(badge_h * 0.38, float(dp(11)), float(dp(15)))
            if self._corner_badge_value is not None:
                self._corner_badge_value.font_size = self._clamp(badge_h * 0.38, float(dp(11)), float(dp(15)))
        self._update_corner_badge_layout()
        self._update_corner_badge_text()

        self._needs_redraw = True
        self._update_background_geometry()

    def format_value(self, value: float) -> str:
        """Форматирование значения для тултипа."""
        try:
            v = float(value)
        except Exception:
            return str(value)
        if abs(v - int(v)) < 1e-9:
            return str(int(v))
        return f"{v:.2f}".rstrip("0").rstrip(".")

    def _point_gap_threshold_seconds(self, times: list[datetime]) -> float | None:
        """Порог разрыва для raw point-mode, чтобы не соединять отдельные пачки данных."""
        if len(times) < 2:
            return None
        gaps = []
        prev = times[0]
        for ts in times[1:]:
            try:
                gap = (ts - prev).total_seconds()
            except Exception:
                gap = 0
            if gap > 0:
                gaps.append(float(gap))
            prev = ts
        if not gaps:
            return None
        gaps.sort()
        median = gaps[len(gaps) // 2]
        return max(5.0, median * 8.0)

    def _point_snap_tolerance_seconds(self) -> float | None:
        """Максимальная дистанция hover до точки в raw point-mode."""
        if self.display_mode != "points" or not self.absolute_time_window:
            return None
        threshold = self._point_gap_threshold_seconds(self._display_times)
        if threshold is None:
            return 5.0
        return max(2.0, threshold * 0.5)

    def _simplify_dense_line_points(self, points: list[float]) -> list[float]:
        """Снизить плотность raw-линии до нескольких точек на пиксель по X."""
        if len(points) < 8:
            return points
        simplified: list[float] = []
        i = 0
        n = len(points)
        while i < n:
            x_key = int(round(points[i]))
            bucket: list[tuple[float, float]] = []
            while i < n and int(round(points[i])) == x_key:
                bucket.append((float(points[i]), float(points[i + 1])))
                i += 2
            if len(bucket) <= 2:
                for x, y in bucket:
                    simplified.extend([x, y])
                continue

            first = bucket[0]
            last = bucket[-1]
            min_pt = min(bucket, key=lambda item: item[1])
            max_pt = max(bucket, key=lambda item: item[1])
            ordered: list[tuple[float, float]] = []
            for pt in (first, min_pt, max_pt, last):
                if not ordered or ordered[-1] != pt:
                    ordered.append(pt)
            for x, y in ordered:
                simplified.extend([x, y])
        return simplified

    def _chunk_line_points(self, points: list[float], max_vertices: int = 96) -> list[list[float]]:
        """Разбить длинную Line на короткие strips, чтобы драйвер не давал перетяжки."""
        if len(points) < 4:
            return []
        max_vertices = max(2, int(max_vertices))
        max_floats = max_vertices * 2
        chunks: list[list[float]] = []
        start = 0
        n = len(points)
        while start < n - 2:
            end = min(n, start + max_floats)
            if end - start >= 4:
                chunks.append(points[start:end])
            if end >= n:
                break
            # Перекрываем последнюю вершину, чтобы линия не имела видимых разрывов.
            start = max(start + 2, end - 2)
        return chunks

    def x_to_time(self, x: float) -> datetime | None:
        """Преобразовать X (координаты окна) в datetime по текущей оси X."""
        if not self._plot_area:
            return None
        x0, _y0, w, _h = self._plot_area
        if w <= 0:
            return None
        rel = (x - x0) / w
        rel = max(0.0, min(1.0, rel))

        abs_win = self.absolute_time_window
        if abs_win and abs_win[0] and abs_win[1]:
            try:
                if abs_win[1] > abs_win[0]:
                    total = (abs_win[1] - abs_win[0]).total_seconds()
                    return abs_win[0] + timedelta(seconds=rel * total)
            except Exception:
                pass

        # Fallback: по индексам в уже отрисованных точках
        n = len(self._display_times)
        if n <= 0:
            return None
        idx = int(round(rel * max(n - 1, 1)))
        idx = max(0, min(n - 1, idx))
        return self._display_times[idx]

    def nearest_point(
        self,
        t: datetime,
        mouse_y: float | None = None,
        prefer_upper: bool | None = None,
    ) -> tuple[int, datetime, float, float, float] | None:
        """
        Найти ближайшую отрисованную точку к заданному времени.
        Возвращает (idx, ts, value, x, y) в координатах окна.

        mouse_y — Y-координата мыши в координатах окна. Если задана и точка
        является bucket-диапазоном (min/max), маркер «прилипает» к нижней
        границе (min), когда курсор ниже середины бара, иначе к верхней (max).
        prefer_upper — принудительно выбрать верхнюю/нижнюю границу диапазона.
        Используется для синхронного hover между несколькими графиками.
        """
        if not self._plot_area or not self._y_scale:
            return None
        if not self._display_times or not self._display_values:
            return None
        if len(self._display_times) != len(self._display_values):
            return None

        if getattr(t, "tzinfo", None) is not None:
            t = t.replace(tzinfo=None)

        times = self._display_times
        i = bisect_left(times, t)
        if i <= 0:
            idx = 0
        elif i >= len(times):
            idx = len(times) - 1
        else:
            t0 = times[i - 1]
            t1 = times[i]
            idx = i - 1 if abs((t - t0).total_seconds()) <= abs((t1 - t).total_seconds()) else i

        ts = times[idx]
        tolerance_s = self._point_snap_tolerance_seconds()
        if tolerance_s is not None:
            try:
                if abs((t - ts).total_seconds()) > tolerance_s:
                    return None
            except Exception:
                return None
        val = float(self._display_values[idx])
        x0, y0, w, h = self._plot_area
        min_val, max_val = self._y_scale
        y_range = max(max_val - min_val, 1e-9)

        # Bucket range: выбираем lo/hi в зависимости от позиции курсора
        if idx < len(self._display_bucket_ranges):
            rng = self._display_bucket_ranges[idx]
            if rng is not None:
                try:
                    lo, hi = float(rng[0]), float(rng[1])
                    if prefer_upper is not None and lo != hi:
                        val = hi if prefer_upper else lo
                    elif mouse_y is not None and lo != hi:
                        lo_y = y0 + max(0.0, min(1.0, (lo - min_val) / y_range)) * h
                        hi_y = y0 + max(0.0, min(1.0, (hi - min_val) / y_range)) * h
                        mid_y = (lo_y + hi_y) / 2.0
                        val = lo if mouse_y < mid_y else hi
                    else:
                        val = hi
                except Exception:
                    pass

        abs_win = self.absolute_time_window
        abs_ok = False
        if abs_win and abs_win[0] and abs_win[1]:
            try:
                abs_ok = abs_win[1] > abs_win[0]
            except Exception:
                abs_ok = False

        if abs_ok:
            try:
                ratio = (ts - abs_win[0]).total_seconds() / max((abs_win[1] - abs_win[0]).total_seconds(), 1e-9)
            except Exception:
                ratio = idx / max(len(times) - 1, 1)
            ratio = max(0.0, min(1.0, ratio))
            x = x0 + ratio * w
        else:
            x = x0 + (idx / max(len(times) - 1, 1)) * w

        norm = (val - min_val) / y_range
        y = y0 + max(0.0, min(1.0, norm)) * h
        return idx, ts, val, x, y

    def has_time_in_display_window(self, t: datetime) -> bool:
        """Проверить, попадает ли время t в диапазон отрисованных точек."""
        if getattr(t, "tzinfo", None) is not None:
            t = t.replace(tzinfo=None)
        abs_win = self.absolute_time_window
        if abs_win and abs_win[0] and abs_win[1]:
            try:
                start_dt, end_dt = abs_win
                if getattr(start_dt, "tzinfo", None) is not None:
                    start_dt = start_dt.replace(tzinfo=None)
                if getattr(end_dt, "tzinfo", None) is not None:
                    end_dt = end_dt.replace(tzinfo=None)
                if end_dt > start_dt:
                    if self.display_mode == "points":
                        if not self._display_times:
                            return False
                        return self._display_times[0] <= t <= self._display_times[-1]
                    return start_dt <= t <= end_dt
            except Exception:
                pass
        if not self._display_times:
            return False
        try:
            return self._display_times[0] <= t <= self._display_times[-1]
        except Exception:
            return False

    def time_to_x(self, t: datetime) -> float | None:
        """Преобразовать время в X (координаты окна) по текущей оси X."""
        if not self._plot_area:
            return None
        x0, _y0, w, _h = self._plot_area
        if w <= 0:
            return None
        if getattr(t, "tzinfo", None) is not None:
            t = t.replace(tzinfo=None)

        abs_win = self.absolute_time_window
        if abs_win and abs_win[0] and abs_win[1]:
            try:
                if abs_win[1] > abs_win[0]:
                    ratio = (t - abs_win[0]).total_seconds() / max((abs_win[1] - abs_win[0]).total_seconds(), 1e-9)
                    ratio = max(0.0, min(1.0, ratio))
                    return x0 + ratio * w
            except Exception:
                pass

        # fallback: по индексам отрисованной серии
        n = len(self._display_times)
        if n <= 0:
            return None
        # ближайшая по времени (O(log n))
        i = bisect_left(self._display_times, t)
        if i <= 0:
            idx = 0
        elif i >= n:
            idx = n - 1
        else:
            t0 = self._display_times[i - 1]
            t1 = self._display_times[i]
            idx = i - 1 if abs((t - t0).total_seconds()) <= abs((t1 - t).total_seconds()) else i
        return x0 + (idx / max(n - 1, 1)) * w

    def set_hover_time(
        self,
        t: datetime,
        show_tooltip: bool = True,
        anchor_pos: tuple[float, float] | None = None,
        tooltip_text: str | None = None,
        prefer_upper: bool | None = None,
    ):
        """Показать hover по заданному времени (вертикальная линия + точка + опциональный тултип)."""
        self._ensure_canvas_instructions()
        self._hover_time = t
        self._hover_show_tooltip = bool(show_tooltip)
        if anchor_pos is not None:
            self._hover_anchor_pos = anchor_pos
        self._hover_prefer_upper = prefer_upper

        mouse_y = anchor_pos[1] if anchor_pos else None

        in_window = self.has_time_in_display_window(t)
        if not in_window:
            p = None
        else:
            p = self.nearest_point(t, mouse_y=mouse_y, prefer_upper=prefer_upper)
        if not p:
            # Нет данных в этой серии — но тултип (с данными других графиков) всё равно может быть нужен.
            # Покажем вертикальную линию по времени и тултип (если requested), без маркера точки.
            x = self.time_to_x(t)
            if x is None or not self._plot_area:
                self.clear_hover()
                return

            x0, y0, w, h = self._plot_area
            if self._hover_line is not None:
                self._hover_line.points = [x, y0, x, y0 + h]
            # ВАЖНО: на пустом графике точку не показываем
            self._hide_hover_marker()
            self._hover_last_idx = None

            self.tooltip_label.opacity = 0
            if self._header_indicator_label is not None:
                self._header_indicator_label.text = ""
            self._show_indicator_frame(False)
            return
        idx, ts, val, x, y = p

        self._hover_last_idx = idx

        if self._plot_area:
            x0, y0, w, h = self._plot_area
            if self._hover_line is not None:
                self._hover_line.points = [x, y0, x, y0 + h]

        # Маркер точки (прилипает к верхнему значению текущего бакета/точки).
        if self._hover_marker is not None:
            if self._hover_marker_color is not None:
                try:
                    self._hover_marker_color.rgba = (1, 1, 1, 0.95)
                except Exception:
                    pass
            r = dp(3.5)
            self._hover_marker.pos = (x - r, y - r)
            self._hover_marker.size = (r * 2, r * 2)

        # Tooltip: для истории теперь выводим текст в шапке, а не поверх графика.
        if show_tooltip:
            if tooltip_text is None:
                val_txt = self.format_value(val)
                if self.unit:
                    val_txt = f"{val_txt} {self.unit}"
                tooltip_text = f"{self._format_tooltip_time(ts)}\n{self.title}: {val_txt}"
                if self.resolution_seconds and self.resolution_seconds >= 60:
                    mins = int(round(self.resolution_seconds / 60))
                    tooltip_text += f"\n(период {mins} мин)"
            # Внутриграфиковый tooltip прячем — используем только индикатор в заголовке.
            self.tooltip_label.opacity = 0
        else:
            self.tooltip_label.opacity = 0

        # Индикатор в шапке — обновляем текст, позицию и рамку.
        if self._header_indicator_label is not None:
            try:
                txt = self._format_header_indicator(ts, val)
                self._header_indicator_label.text = txt
                self._position_header_indicator(anchor_pos)
                self._show_indicator_frame(True)
            except Exception:
                self._header_indicator_label.text = ""
                self._show_indicator_frame(False)

    def _position_header_indicator(self, anchor_pos):
        """Сдвинуть tooltip в шапке по горизонтали к позиции мыши.

        Центр label привязан к mouse_x, зажат так, чтобы:
        - не заходить левее контейнера (не перекрывать заголовок);
        - не вылезать правым краем за правый край GraphWidget.
        """
        container = getattr(self, "_header_indicator_container", None)
        lbl = self._header_indicator_label
        if container is None or lbl is None:
            return
        fw = self._indicator_fixed_w
        if anchor_pos is None:
            lbl.x = 0
            return
        container_abs_x = container.x
        mouse_x = anchor_pos[0]
        offset = mouse_x - container_abs_x - fw / 2
        offset = max(0, offset)
        max_right = self.right - dp(6)
        max_offset = max_right - container_abs_x - fw
        if max_offset > 0:
            offset = min(offset, max_offset)
        lbl.x = offset

    def clear_hover(self):
        """Скрыть hover-оверлей."""
        self._hover_time = None
        self._hover_show_tooltip = False
        self._hover_last_idx = None
        self._hover_anchor_pos = None
        self._hover_prefer_upper = None
        if self._hover_line is not None:
            self._hover_line.points = []
        self._hide_hover_marker()
        if hasattr(self, "tooltip_label"):
            self.tooltip_label.opacity = 0
            self.tooltip_label.text = ""
        self._header_indicator_active = False
        if self._header_indicator_label is not None:
            self._header_indicator_label.text = ""
        self._show_indicator_frame(False)
    
    def _get_filtered_data(self):
        """Получение отфильтрованных данных по текущему временному диапазону"""
        if not self.time_points:
            return [], []
        
        # Если диапазон не установлен, показываем все данные
        if self.current_time_range_minutes is None:
            # В обычном режиме всегда есть диапазон; если нет — вернем последние точки (защитно)
            return list(self.data_points), list(self.time_points)
        
        cutoff_time = datetime.now() - timedelta(minutes=self.current_time_range_minutes)
        
        # Убираем timezone из cutoff_time для совместимости
        if cutoff_time.tzinfo is not None:
            cutoff_time = cutoff_time.replace(tzinfo=None)
        
        # ВАЖНО: time_points упорядочены по времени. Идем с конца, пока >= cutoff_time.
        filtered_values_rev = []
        filtered_times_rev = []
        for ts, val in zip(reversed(self.time_points), reversed(self.data_points)):
            if ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)
            if ts < cutoff_time:
                break
            filtered_values_rev.append(val)
            filtered_times_rev.append(ts)

        if not filtered_values_rev:
            return [], []

        filtered_values_rev.reverse()
        filtered_times_rev.reverse()
        return filtered_values_rev, filtered_times_rev
    
    def clear_data(self):
        """Очистка данных графика"""
        self.data_points.clear()
        self.time_points.clear()
        self._latest_value_text = ""
        self._latest_value_numeric_text = ""
        self._update_corner_badge_text()
        # Полная очистка кэша и hover, чтобы не оставались "призрачные" значения/точки
        self._display_times = []
        self._display_values = []
        self._display_bucket_ranges = []
        self._y_scale = None
        for ln in self._plot_lines or []:
            ln.points = []
        for ln in self._plot_single_lines or []:
            ln.points = []
        for rect in self._plot_rects or []:
            rect.size = (0, 0)
        for marker in self._plot_point_markers or []:
            marker.size = (0, 0)
            marker.pos = (-10000, -10000)
        for rect in self._y_tick_rects or []:
            rect.size = (0, 0)
        try:
            self.clear_hover()
        except Exception:
            pass
        self._needs_redraw = True
        self.update_graph()
    
    def filter_data_by_time_range(self, time_range_minutes):
        """Установка временного диапазона для отображения данных"""
        self.current_time_range_minutes = time_range_minutes
        self._needs_redraw = True
        self.update_graph()
    
    def load_historical_data(self, data_points: list, time_points: list):
        """Загрузка исторических данных в график"""
        self.data_points.clear()
        self.time_points.clear()
        
        normalized_points: list[tuple[datetime, float]] = []
        for value, timestamp in zip(data_points, time_points):
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            
            # Убираем timezone для совместимости (приводим к offset-naive)
            if timestamp.tzinfo is not None:
                timestamp = timestamp.replace(tzinfo=None)
            try:
                normalized_points.append((timestamp, float(value)))
            except Exception:
                continue

        normalized_points.sort(key=lambda item: item[0])
        for timestamp, value in normalized_points:
            self.data_points.append(value)
            self.time_points.append(timestamp)
        self._needs_redraw = True
        self.update_graph()
    
    def on_size(self, *args):
        """Обработчик изменения размера"""
        self.update_graph()

