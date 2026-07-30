"""
Виджет для отображения цифровых значений из signals_value
"""
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.metrics import dp
from kivy.core.text import Label as CoreLabel

from utils.ui_style import apply_rounded_panel


class ValueDisplayWidget(BoxLayout):
    """Виджет для отображения цифрового значения параметра"""

    _VALUE_FONT_SCALE = 1.15
    _UNIT_FONT_SCALE = 1.45
    
    def __init__(self, title: str, color: str = "#FFFFFF", unit: str = "", show_unit: bool = True, **kwargs):
        """
        Инициализация виджета отображения значения
        
        Args:
            title: Название параметра
            color: Цвет текста (hex или RGB)
            unit: Единица измерения (например, "%", "°C", "уд/мин")
        """
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.spacing = dp(5)
        self.padding = dp(10)
        
        self.title = title
        self.color = color
        self._base_text_rgba = self._hex_to_rgb(color)
        self.unit = unit
        self.show_unit = bool(show_unit)
        self.current_value = None
        self._normal_range: tuple[float, float] | None = None
        self._on_select = None
        self._on_context_select = None
        self._compact_tile_mode = False
        self._tile_layout_variant = "stack"
        self._layout_density = "normal"
        
        # Создание UI
        self._create_ui()
        # Адаптивные размеры шрифтов под размер виджета
        self.bind(size=self._update_font_sizes)

    def set_on_select(self, callback):
        """Callback при клике по виджету (для выбора параметра)."""
        self._on_select = callback

    def set_on_context_select(self, callback):
        """Callback при правом клике по виджету (для быстрого выбора параметра)."""
        self._on_context_select = callback

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if hasattr(touch, "button") and touch.button == "right":
                if callable(self._on_context_select):
                    self._on_context_select()
                    return True
            # Touch может быть без button (мобилка) — разрешаем
            if not hasattr(touch, "button") or touch.button == "left":
                if callable(self._on_select):
                    self._on_select()
                    return True
        return super().on_touch_down(touch)
    
    def _create_ui(self):
        """Создание пользовательского интерфейса"""
        self.card = BoxLayout(
            orientation='vertical',
            spacing=dp(5),
            padding=dp(10),
            size_hint=(1, 1),
        )
        apply_rounded_panel(
            self.card,
            base_rgba=(0.125, 0.125, 0.135, 1),
            radius_px=dp(10),
            border_alpha=0.05,
        )
        self.add_widget(self.card)

        # Заголовок (фиксированная высота, чтобы не наезжал на числа)
        self.title_label = Label(
            text=self.title,
            size_hint_y=None,
            height=dp(30),
            color=self._base_text_rgba,
            font_size=dp(13),
            bold=False,
            halign='center',
            valign='middle',
            shorten=True,
            shorten_from='right',
            text_size=(None, None)
        )
        self.title_label.bind(size=self._update_title_text_bounds)
        self.card.add_widget(self.title_label)
        
        # Контейнер для значения и единицы измерения
        self.value_container = BoxLayout(
            orientation='horizontal',
            size_hint_y=1,
            spacing=dp(5)
        )
        
        # Значение (большой шрифт)
        self.value_label = Label(
            text="--",
            size_hint_x=0.7,
            color=self._base_text_rgba,
            font_size=dp(48),
            bold=False,
            halign='center',
            valign='middle',
            text_size=(None, None)
        )
        self.value_label.bind(size=self._center_text)
        self.value_container.add_widget(self.value_label)
        
        # Единица измерения справа от значения (если указана)
        self.unit_label = None
        if self.unit and self.show_unit:
            self.unit_label = Label(
                text=self.unit,
                size_hint_x=0.3,
                color=self._base_text_rgba,
                font_size=dp(20),
                halign='left',
                valign='middle',
                text_size=(None, None)
            )
            self.unit_label.bind(size=self._update_unit_text_bounds)
            self.value_container.add_widget(self.unit_label)
        
        self.card.add_widget(self.value_container)
        if self.unit_label is None:
            self.value_label.size_hint_x = 1
        # Инициализация размеров после создания
        self._update_font_sizes()

    def set_compact_tile_mode(self, enabled: bool, layout_variant: str = "stack") -> None:
        """Компактный режим для узкой правой колонки в multi-monitor tile layout."""
        self._compact_tile_mode = bool(enabled)
        self._tile_layout_variant = "grid" if str(layout_variant) == "grid" else "stack"
        self.spacing = 0
        self.padding = 0

        if enabled:
            apply_rounded_panel(
                self.card,
                base_rgba=(0.125, 0.125, 0.135, 1),
                radius_px=dp(10),
                border_alpha=0.05,
            )
            if self._tile_layout_variant == "grid":
                self.card.orientation = "vertical"
                self.card.spacing = dp(1)
                self.card.padding = dp(8)
                self.title_label.size_hint_x = 1
                self.title_label.size_hint_y = None
                self.value_container.orientation = "vertical"
                self.value_container.spacing = dp(0)
                self.value_container.size_hint_x = 1
                self.value_label.size_hint_x = 1
                self.value_label.size_hint_y = None
                self.value_label.halign = "center"
                self.title_label.halign = "center"
                self.value_container.size_hint_y = None
                if self.unit_label is not None:
                    self.unit_label.size_hint_x = 1
                    self.unit_label.size_hint_y = None
                    self.unit_label.height = dp(14)
                    self.unit_label.halign = "center"
            else:
                # В узкой вертикальной колонке карточки читаются лучше в одну строку:
                # "Пульс 87.0 уд/мин" вместо трёх отдельных строк.
                self.card.orientation = "horizontal"
                self.card.spacing = dp(8)
                self.card.padding = (dp(12), dp(1), dp(10), dp(1))
                self.title_label.size_hint_x = 0.62
                self.title_label.size_hint_y = 1
                self.title_label.halign = "left"
                self.value_container.orientation = "horizontal"
                self.value_container.spacing = dp(4) if self.unit_label is not None else 0
                self.value_container.size_hint_x = 0.38 if self.unit_label is not None else 0.44
                self.value_container.size_hint_y = 1
                self.value_label.size_hint_x = 0.64 if self.unit_label is not None else 1
                self.value_label.size_hint_y = 1
                self.value_label.halign = "right"
                if self.unit_label is not None:
                    self.unit_label.size_hint_x = 0.36
                    self.unit_label.size_hint_y = 1
                    self.unit_label.halign = "left"
        else:
            self.card.orientation = "vertical"
            self.card.spacing = dp(5)
            self.card.padding = dp(10)
            self.title_label.size_hint_x = 1
            self.title_label.size_hint_y = None
            self.value_container.orientation = "horizontal"
            self.value_container.spacing = dp(5) if self.unit_label is not None else 0
            self.value_container.size_hint_x = 1
            self.value_label.size_hint_x = 0.7 if self.unit_label is not None else 1
            self.value_label.size_hint_y = 1
            self.value_label.halign = "center"
            self.title_label.halign = "center"
            self.value_container.size_hint_y = 1
            if self.unit_label is not None:
                self.unit_label.size_hint_x = 0.3
                self.unit_label.size_hint_y = 1
                self.unit_label.halign = "left"

        self._update_font_sizes()

    def set_layout_density(self, density: str) -> None:
        density = str(density or "normal").strip().lower()
        if density not in {"normal", "compact", "tiny", "ultra_tiny"}:
            density = "normal"
        self._layout_density = density
        self._update_font_sizes()

    def set_base_color(self, color) -> None:
        self.color = color
        self._base_text_rgba = self._hex_to_rgb(color)
        self.title_label.color = self._base_text_rgba
        if self.unit_label is not None:
            self.unit_label.color = self._base_text_rgba
        self._apply_value_color()

    def set_normal_range(self, low, high) -> None:
        """Задать нормальный диапазон; None отключает тревожную окраску."""
        if low is None or high is None:
            self._normal_range = None
            self._apply_value_color()
            return
        try:
            low_f = float(low)
            high_f = float(high)
        except Exception:
            self._normal_range = None
            self._apply_value_color()
            return
        if high_f <= low_f:
            self._normal_range = None
        else:
            self._normal_range = (low_f, high_f)
        self._apply_value_color()

    def _apply_value_color(self) -> None:
        color = self._base_text_rgba
        rng = self._normal_range
        value = self.current_value
        if rng is not None and value is not None:
            low, high = rng
            value_f = float(value)
            span = max(0.0001, high - low)
            border_margin = span * 0.08
            if value_f < low or value_f > high:
                color = (1.0, 0.23, 0.18, 1)
            elif (value_f - low) <= border_margin or (high - value_f) <= border_margin:
                color = (1.0, 0.68, 0.22, 1)
        self.value_label.color = color
    
    def _hex_to_rgb(self, hex_color):
        """Конвертация hex цвета в RGB (0-1)"""
        if isinstance(hex_color, str):
            hex_color = hex_color.lstrip('#')
            if len(hex_color) == 6:
                return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4)) + (1,)
        return hex_color
    
    def _center_text(self, instance, size):
        """Центрирование текста"""
        instance.text_size = (size[0], size[1])

    def _update_title_text_bounds(self, instance, size):
        instance.text_size = (max(1, size[0] - dp(6)), size[1])

    def _update_unit_text_bounds(self, instance, size):
        # Для единиц измерения важнее сохранить одну строку и уменьшить шрифт,
        # чем переносить текст и выталкивать его из карточки.
        instance.text_size = (max(1, size[0] - dp(4)), None)

    def _clamp(self, v: float, vmin: float, vmax: float) -> float:
        return max(vmin, min(vmax, v))

    def _fit_font_to_bounds(
        self,
        text: str,
        font_size: float,
        min_size: float,
        max_size: float,
        width: float,
        height: float,
        bold: bool = False,
    ) -> float:
        """Подобрать шрифт по реальной текстуре, чтобы строка не обрезалась."""
        text = str(text or "")
        width = max(1.0, float(width or 1))
        height = max(1.0, float(height or 1))
        size = self._clamp(float(font_size), float(min_size), float(max_size))
        for _ in range(12):
            try:
                probe = CoreLabel(text=text, font_size=size, bold=bold)
                probe.refresh()
                tex_w, tex_h = probe.texture.size if probe.texture else (0, 0)
            except Exception:
                break
            if tex_w <= width and tex_h <= height:
                return self._clamp(size, float(min_size), float(max_size))
            scale = min(width / max(tex_w, 1), height / max(tex_h, 1))
            next_size = max(float(min_size), size * max(0.35, min(0.98, scale * 0.96)))
            if abs(next_size - size) < 0.2:
                return self._clamp(next_size, float(min_size), float(max_size))
            size = next_size
        return self._clamp(size, float(min_size), float(max_size))

    def _update_font_sizes(self, *args):
        """
        Делаем шрифты адаптивными, чтобы в любых раскладках (1/2/4/6) цифры не наезжали.
        """
        if self.height <= 0 or self.width <= 0:
            return

        # Пропорции подобраны под текущую верстку (заголовок + значение)
        if self._compact_tile_mode:
            if self._tile_layout_variant == "grid":
                title_fs = self._clamp(self.height * 0.15, dp(13), dp(22))
                value_fs = self._clamp(self.height * 0.44 * self._VALUE_FONT_SCALE, dp(34), dp(92))
                unit_fs = self._clamp(value_fs * 0.34 * self._UNIT_FONT_SCALE, dp(12), dp(22))
                self.title_label.height = self._clamp(self.height * 0.22, dp(22), dp(34))
                value_h = self._clamp(self.height * 0.55, dp(44), dp(104))
                unit_h = self._clamp(self.height * 0.14, dp(10), dp(18))
                content_h = self.title_label.height + value_h + (unit_h if self.unit_label is not None else 0)
                content_h += float(getattr(self.card, "spacing", 0) or 0)
                free_h = max(0.0, float(self.height) - content_h)
                pad_y = self._clamp(free_h * 0.5, dp(2), dp(10))
                self.card.padding = (dp(6), pad_y, dp(6), pad_y)
            else:
                # Стек-режим: всё внутри карточки идёт в одну строку.
                avail_h = max(1.0, float(self.height))
                title_scale = {
                    "normal": 0.39,
                    "compact": 0.38,
                    "tiny": 0.35,
                    "ultra_tiny": 0.33,
                }.get(self._layout_density, 0.39)
                value_scale = {
                    "normal": 0.575,
                    "compact": 0.552,
                    "tiny": 0.518,
                    "ultra_tiny": 0.483,
                }.get(self._layout_density, 0.575)
                unit_scale = {
                    "normal": 0.38,
                    "compact": 0.36,
                    "tiny": 0.33,
                    "ultra_tiny": 0.30,
                }.get(self._layout_density, 0.38)
                self.title_label.height = avail_h
                title_fs = self._clamp(avail_h * title_scale, dp(9), dp(14))
                value_fs = self._clamp(avail_h * value_scale, dp(11), dp(24))
                unit_fs = self._clamp(avail_h * unit_scale, dp(9), dp(15)) if self.unit_label is not None else dp(9)
                value_h = avail_h
                unit_h = avail_h
        else:
            title_fs = self._clamp(self.height * 0.14, dp(12), dp(18))
            value_fs = self._clamp(self.height * 0.55 * self._VALUE_FONT_SCALE, dp(25), dp(82))
            unit_fs = self._clamp(value_fs * 0.58, dp(16), dp(36))
            self.title_label.height = self._clamp(self.height * 0.22, dp(26), dp(40))
            value_h = 0
            unit_h = 0

        title_text = (self.title_label.text or self.title or "").strip()
        title_chars = max(4, len(title_text))
        title_width = float(getattr(self.title_label, "width", 0) or 0)
        available_title_w = max(title_width - dp(8), dp(54)) if title_width > 0 else max(self.width - dp(16), dp(54))
        if self._compact_tile_mode and self._tile_layout_variant == "stack":
            title_factor = {
                "normal": 0.56,
                "compact": 0.55,
                "tiny": 0.53,
                "ultra_tiny": 0.51,
            }.get(self._layout_density, 0.56)
        elif self._compact_tile_mode and self._tile_layout_variant == "grid":
            title_factor = 0.48
        else:
            title_factor = 0.62 if self._compact_tile_mode else 0.56
        max_title_fs_by_width = available_title_w / (title_chars * title_factor)
        title_max = dp(24) if (self._compact_tile_mode and self._tile_layout_variant == "grid") else dp(18)
        title_fs = self._clamp(min(title_fs, max_title_fs_by_width), dp(9), title_max)
        title_fs = self._fit_font_to_bounds(
            title_text,
            title_fs,
            dp(9) if (self._compact_tile_mode and self._tile_layout_variant == "grid") else dp(7),
            title_max,
            available_title_w,
            max(1.0, float(getattr(self.title_label, "height", 0) or dp(18)) - dp(2)),
            bool(getattr(self.title_label, "bold", False)),
        )
        self.title_label.font_size = title_fs

        value_text = (self.value_label.text or "--").strip()
        # Подбор шрифта лучше делать по "самому длинному" формату, который
        # визуально похож на текущий: иначе целые значения (например "15")
        # получаются заметно крупнее, чем дробные ("84.4").
        sizing_text = value_text
        if value_text != "--" and "." not in value_text:
            sizing_text = f"{value_text}.0"
        chars = max(2, len(sizing_text))
        value_width = float(getattr(self.value_label, "width", 0) or 0)
        if value_width > 0:
            available_value_w = max(value_width - dp(4), dp(28))
        else:
            available_value_w = max(self.width * (0.86 if (self._compact_tile_mode and self._tile_layout_variant == "stack") else (0.72 if self._compact_tile_mode else 0.68)), dp(56))
        max_fs_by_width = available_value_w / (chars * 0.6)
        if self._compact_tile_mode and self._tile_layout_variant == "stack":
            value_min_fs = {
                "normal": dp(12),
                "compact": dp(10),
                "tiny": dp(8),
                "ultra_tiny": dp(7),
            }.get(self._layout_density, dp(12))
        elif self._compact_tile_mode and self._tile_layout_variant == "grid":
            value_min_fs = {
                "normal": dp(28),
                "compact": dp(24),
                "tiny": dp(20),
                "ultra_tiny": dp(16),
            }.get(self._layout_density, dp(28))
        else:
            value_min_fs = dp(16)
        value_max = dp(110) if (self._compact_tile_mode and self._tile_layout_variant == "grid") else dp(82)
        value_fs = self._clamp(min(value_fs, max_fs_by_width), value_min_fs, value_max)
        value_fs = self._fit_font_to_bounds(
            sizing_text,
            value_fs,
            value_min_fs,
            value_max,
            available_value_w,
            max(1.0, float(value_h or getattr(self.value_container, "height", 0) or self.height * 0.58) - dp(2)),
            bool(getattr(self.value_label, "bold", False)),
        )
        self.value_label.font_size = value_fs
        if self._compact_tile_mode:
            self.value_label.height = value_h
            self.value_container.height = value_h if self._tile_layout_variant == "stack" else value_h + (unit_h if self.unit_label is not None else 0)

        if self.unit_label is not None:
            unit_text = (self.unit_label.text or "").strip()
            uchars = max(1, len(unit_text))
            unit_width = float(getattr(self.unit_label, "width", 0) or 0)
            if unit_width > 0:
                available_unit_w = max(unit_width - dp(2), dp(18))
            else:
                available_unit_w = max(self.width * (0.86 if (self._compact_tile_mode and self._tile_layout_variant == "stack") else (0.72 if self._compact_tile_mode else 0.28)), dp(28))
            max_unit_fs_by_width = available_unit_w / (uchars * 0.58)
            if self._compact_tile_mode and self._tile_layout_variant == "stack":
                unit_min_fs = {
                    "normal": dp(9),
                    "compact": dp(8),
                    "tiny": dp(7),
                    "ultra_tiny": dp(6),
                }.get(self._layout_density, dp(9))
            elif self._compact_tile_mode and self._tile_layout_variant == "grid":
                unit_min_fs = {
                    "normal": dp(9),
                    "compact": dp(8),
                    "tiny": dp(7),
                    "ultra_tiny": dp(6),
                }.get(self._layout_density, dp(8))
            else:
                unit_min_fs = dp(14)
            unit_fs = self._clamp(min(unit_fs, max_unit_fs_by_width), unit_min_fs, dp(36))
            self.unit_label.font_size = unit_fs
            if self._compact_tile_mode:
                self.unit_label.height = unit_h
    
    def set_value(self, value: float):
        """
        Установить значение для отображения
        
        Args:
            value: Значение (float)
        """
        if value is not None:
            self.current_value = float(value)
            # Форматирование значения
            if self.current_value == int(self.current_value):
                display_value = f"{int(self.current_value)}"
            else:
                display_value = f"{self.current_value:.1f}"
            
            self.value_label.text = display_value
        else:
            self.value_label.text = "--"
            self.current_value = None

        self._apply_value_color()
        # Пересчёт шрифтов под новую длину числа
        self._update_font_sizes()
    
    def get_value(self) -> float:
        """Получить текущее значение"""
        return self.current_value

