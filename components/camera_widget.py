"""
Виджет для отображения изображения с камеры
"""
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.anchorlayout import AnchorLayout
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp
from kivy.clock import Clock
from io import BytesIO
import os


class CameraWidget(BoxLayout):
    """Виджет для отображения JPEG изображения с камеры"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.spacing = dp(0)
        self.padding = dp(0)
        self._compact_tile_mode = False

        # Фон/рамка (чтобы не было "белого квадрата" без изображения)
        self._bg_color = None
        self._bg_border_color = None
        self._bg_rect = None
        self._bg_border = None
        self._image_color = None
        self._image_rect = None
        
        # Путь к изображению (можно настроить через конфиг)
        self.image_path = None
        self._core_image = None
        self.update_interval = None
        
        # Создание UI
        self._create_ui()

        # Рисуем фон/рамку
        self._ensure_canvas()
        self.bind(pos=self._update_bg, size=self._update_bg)
    
    def _create_ui(self):
        """Создание пользовательского интерфейса"""
        # Контейнер для изображения (квадратное) + оверлей-плейсхолдер
        self.image_container = AnchorLayout(anchor_x="center", anchor_y="center")

        self.image_widget = Image(
            source="",
            allow_stretch=True,
            keep_ratio=True,
            size_hint=(1, 1),
        )
        # Саму картинку рисуем ниже через RoundedRectangle, чтобы получить скругленные углы.
        self.image_widget.opacity = 0
        self.image_container.add_widget(self.image_widget)

        self.placeholder_label = Label(
            text="Нет\nизображения",
            color=(0.75, 0.75, 0.75, 1),
            font_size=dp(12),
            halign="center",
            valign="middle",
            bold=True,
            text_size=(0, None),
        )
        self.placeholder_label.bind(size=self._update_placeholder_text)
        self.placeholder_label.opacity = 1
        self.image_container.add_widget(self.placeholder_label)

        self.add_widget(self.image_container)
        
        # Метка статуса (скрыта, но можно использовать для отладки)
        self.status_label = Label(
            text="",
            size_hint_y=None,
            height=0,
            color=(0.7, 0.7, 0.7, 1),
            font_size=dp(10)
        )
        self.status_label.opacity = 0
        self.add_widget(self.status_label)

    def _ensure_canvas(self):
        if self._bg_rect is not None:
            return
        with self.canvas.before:
            self._bg_color = Color(0.12, 0.12, 0.14, 1)
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
            self._image_color = Color(1, 1, 1, 0)
            self._image_rect = RoundedRectangle(pos=self.pos, size=(0, 0), radius=[dp(10)])
        with self.canvas.after:
            self._bg_border_color = Color(1, 1, 1, 0.05)
            self._bg_border = Line(rounded_rectangle=[self.x, self.y, self.width, self.height, dp(10)], width=dp(1))

    def _update_bg(self, *args):
        if self._bg_rect is None or self._bg_border is None:
            return
        x, y = self.x, self.y
        w, h = self.width, self.height
        # tex_coords покрывают всю текстуру по умолчанию.
        tex_coords = (0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0)
        texture = None
        try:
            texture = getattr(self.image_widget, "texture", None)
            if texture is not None:
                if self._bg_color is not None:
                    self._bg_color.rgba = (0, 0, 0, 0)
                tex_w, tex_h = texture.size
                if tex_w > 0 and tex_h > 0 and float(self.width) > 0 and float(self.height) > 0:
                    # Изображение заполняет весь виджет (cover-режим): сохраняем aspect ratio
                    # картинки, а лишнее по сторонам/сверху-снизу симметрично обрезаем через
                    # tex_coords, чтобы все элементы правой колонки оставались одной ширины.
                    tex_aspect = float(tex_w) / float(tex_h)
                    widget_aspect = float(self.width) / float(self.height)
                    if tex_aspect > widget_aspect:
                        # Картинка шире виджета по соотношению сторон -> обрезаем боковые поля.
                        crop_u = max(0.0, (1.0 - widget_aspect / tex_aspect) / 2.0)
                        u0 = crop_u
                        u1 = 1.0 - crop_u
                        v0, v1 = 0.0, 1.0
                    elif tex_aspect < widget_aspect:
                        # Картинка выше виджета по соотношению -> обрезаем верх и низ.
                        crop_v = max(0.0, (1.0 - tex_aspect / widget_aspect) / 2.0)
                        v0 = crop_v
                        v1 = 1.0 - crop_v
                        u0, u1 = 0.0, 1.0
                    else:
                        u0, u1, v0, v1 = 0.0, 1.0, 0.0, 1.0
                    tex_coords = (u0, v0, u1, v0, u1, v1, u0, v1)
            elif self._bg_color is not None:
                self._bg_color.rgba = (0.12, 0.12, 0.14, 1)
        except Exception:
            pass
        if self._image_rect is not None and self._image_color is not None:
            if texture is not None:
                self._image_color.a = 1
                self._image_rect.texture = texture
                self._image_rect.pos = (x, y)
                self._image_rect.size = (w, h)
                try:
                    self._image_rect.tex_coords = tex_coords
                except Exception:
                    pass
            else:
                self._image_color.a = 0
                self._image_rect.texture = None
                self._image_rect.size = (0, 0)
        self._bg_rect.pos = (x, y)
        self._bg_rect.size = (w, h)
        self._bg_border.rounded_rectangle = [x, y, w, h, dp(10)]

    def _update_placeholder_text(self, instance, size):
        instance.text_size = (max(1, size[0] - dp(10)), None)

    def set_compact_tile_mode(self, enabled: bool) -> None:
        self._compact_tile_mode = bool(enabled)
        if self._bg_border_color is not None:
            self._bg_border_color.a = 0.08 if enabled else 0.05
        if self._bg_color is not None:
            self._bg_color.rgba = (0.12, 0.12, 0.14, 1)
        if hasattr(self, "image_widget") and getattr(self.image_widget, "texture", None) is not None:
            self.image_widget.opacity = 0
        if hasattr(self, "placeholder_label"):
            self.placeholder_label.font_size = dp(11) if enabled else dp(12)
        self._update_bg()
    
    def set_image_path(self, path: str):
        """
        Установить путь к изображению
        
        Args:
            path: Путь к файлу изображения или URL
        """
        self.image_path = path
        self._update_image()

    def set_image_bytes(self, image_bytes: bytes | None):
        """Установить изображение напрямую из байтов БД."""
        if not image_bytes:
            self._clear_image("", (0.7, 0.7, 0.7, 1), show_status_text=False)
            return

        try:
            raw_bytes = bytes(image_bytes)
            ext = self._detect_image_ext(raw_bytes)
            cropped_bytes, cropped_ext = self._crop_bottom_flat_band(raw_bytes, ext)
            self._core_image = CoreImage(BytesIO(cropped_bytes), ext=cropped_ext)
            self.image_widget.source = ""
            self.image_widget.texture = self._core_image.texture
            self.image_widget.opacity = 0
            if hasattr(self, "placeholder_label"):
                self.placeholder_label.opacity = 0
            self._update_bg()
            self.status_label.text = ""
            self.status_label.height = 0
            self.status_label.opacity = 0
        except Exception as e:
            self._clear_image(f"Ошибка загрузки: {e}", (0.8, 0.4, 0.4, 1), show_status_text=True)

    def show_placeholder(
        self,
        status_text: str = "Изображение не найдено",
        status_color=(0.7, 0.7, 0.7, 1),
    ):
        """Показать placeholder с произвольным текстом состояния."""
        self._clear_image(status_text, status_color, show_status_text=False)
    
    def _update_image(self):
        """Обновление изображения"""
        if self.image_path and os.path.exists(self.image_path):
            try:
                with open(self.image_path, "rb") as f:
                    raw_bytes = f.read()
                ext = os.path.splitext(self.image_path)[1].lstrip(".").lower() or self._detect_image_ext(raw_bytes)
                cropped_bytes, cropped_ext = self._crop_bottom_flat_band(raw_bytes, ext)
                self._core_image = CoreImage(BytesIO(cropped_bytes), ext=cropped_ext)
                self.image_widget.source = ""
                self.image_widget.texture = self._core_image.texture
                self.image_widget.opacity = 0
                if hasattr(self, "placeholder_label"):
                    self.placeholder_label.opacity = 0
                self._update_bg()
                self.status_label.text = ""
                self.status_label.height = 0
                self.status_label.opacity = 0
            except Exception as e:
                self._clear_image(f"Ошибка загрузки: {e}", (0.8, 0.4, 0.4, 1), show_status_text=True)
        else:
            self._clear_image("", (0.7, 0.7, 0.7, 1), show_status_text=False)

    def _clear_image(self, status_text: str, status_color, show_status_text: bool = False):
        try:
            self.image_widget.source = ""
            self.image_widget.texture = None
        except Exception:
            pass
        self._core_image = None
        self.image_widget.opacity = 0
        if hasattr(self, "placeholder_label"):
            self.placeholder_label.opacity = 1
        self._update_bg()
        self.status_label.text = status_text if show_status_text else ""
        self.status_label.color = status_color
        self.status_label.height = dp(18) if show_status_text else 0
        self.status_label.opacity = 1 if show_status_text else 0

    @staticmethod
    def _crop_bottom_flat_band(image_bytes: bytes, ext: str) -> tuple[bytes, str]:
        """Обрезать нижнюю однотонную серую полосу, если она встроена в кадр."""
        try:
            from PIL import Image as PILImage
        except Exception:
            return image_bytes, ext

        try:
            img = PILImage.open(BytesIO(image_bytes)).convert("RGB")
            w, h = img.size
            if w < 8 or h < 8:
                return image_bytes, ext

            x0 = max(0, int(w * 0.08))
            x1 = min(w, int(w * 0.92))
            sample_step = max(1, (x1 - x0) // 80)

            def _is_flat_dark_gray_row(y: int) -> bool:
                pixels = [img.getpixel((x, y)) for x in range(x0, x1, sample_step)]
                if not pixels:
                    return False
                means = [sum(p) / 3.0 for p in pixels]
                row_mean = sum(means) / len(means)
                if row_mean < 28 or row_mean > 95:
                    return False
                max_channel_spread = max(max(p) - min(p) for p in pixels)
                max_brightness_delta = max(means) - min(means)
                return max_channel_spread <= 18 and max_brightness_delta <= 16

            crop_y = h
            y = h - 1
            while y > 0 and _is_flat_dark_gray_row(y):
                crop_y = y
                y -= 1

            removed = h - crop_y
            if removed < max(4, int(h * 0.04)) or crop_y < int(h * 0.35):
                return image_bytes, ext

            cropped = img.crop((0, 0, w, crop_y))
            out = BytesIO()
            cropped.save(out, format="PNG")
            return out.getvalue(), "png"
        except Exception:
            return image_bytes, ext

    @staticmethod
    def _detect_image_ext(image_bytes: bytes) -> str:
        if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"
        if image_bytes.startswith(b"\xff\xd8\xff"):
            return "jpg"
        if image_bytes.startswith(b"GIF87a") or image_bytes.startswith(b"GIF89a"):
            return "gif"
        if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
            return "webp"
        return "jpg"
    
    def start_auto_update(self, interval: float = 1.0, image_path: str = None):
        """
        Запустить автоматическое обновление изображения
        
        Args:
            interval: Интервал обновления в секундах
            image_path: Путь к изображению (опционально)
        """
        if image_path:
            self.set_image_path(image_path)
        
        if self.update_interval:
            Clock.unschedule(self.update_interval)
        
        self.update_interval = Clock.schedule_interval(
            lambda dt: self._update_image(),
            interval
        )
    
    def stop_auto_update(self):
        """Остановить автоматическое обновление"""
        if self.update_interval:
            Clock.unschedule(self.update_interval)
            self.update_interval = None

