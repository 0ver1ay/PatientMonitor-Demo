"""
Главный экран управления окнами мониторов
Позволяет создавать и управлять несколькими окнами мониторов пациентов
"""
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.metrics import dp
from utils.layout_config import LayoutConfig
from utils.config_loader import ConfigLoader
from utils.database_source import DatabaseDataSource

from utils.popup_style import style_scrollview_popup
from utils.ui_style import (
    UI_BTN_DANGER,
    UI_BTN_SUCCESS,
    UI_CONTENT_PADDING_UNDER_TITLEBAR,
    UI_TEXT_MUTED,
    UI_TEXT_PRIMARY,
    UI_TEXT_STRONG,
    apply_rounded_button,
    apply_rounded_panel,
)
from components.confirm_action_screen import ConfirmActionScreen


class MainWindowManagerScreen(Screen):
    """Главный экран управления окнами мониторов"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'main_window_manager'
        self._layout_presets = [
            (count, f'{count} {self._monitor_word(count)}')
            for count in range(1, 9)
        ]
        self.quick_card = None
        self.layout_selector_button = None
        self._last_layout_preset = None
        self._layout_preset_screen_name = "layout_preset_selection_screen"
        self.layouts_scroll = None
        self._layouts_scroll_reset_trigger = Clock.create_trigger(self._reset_layouts_scroll_top, 0)
        self._beds_cache = None
        self._main_container = None
        self._intro_card = None
        self._saved_header = None

        self._create_ui()
    
    def _create_ui(self):
        """Создание пользовательского интерфейса"""
        main_container = BoxLayout(
            orientation='vertical',
            spacing=dp(14),
            padding=UI_CONTENT_PADDING_UNDER_TITLEBAR
        )
        self._main_container = main_container
        self.add_widget(main_container)

        intro_card = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=dp(88),
            spacing=dp(4),
            padding=(dp(16), dp(14), dp(16), dp(12))
        )
        self._intro_card = intro_card
        apply_rounded_panel(intro_card, base_rgba=(0.13, 0.13, 0.14, 1), radius_px=dp(12), border_alpha=0.06)

        intro_title = Label(
            text='Раскладки мониторов',
            size_hint_y=None,
            height=dp(28),
            font_size=dp(20),
            bold=True,
            color=UI_TEXT_STRONG,
            halign='left',
            text_size=(None, None)
        )
        intro_title.bind(size=intro_title.setter('text_size'))
        intro_subtitle = Label(
            text='Создавайте новые окна раскладки и быстро открывайте сохранённые конфигурации.',
            size_hint_y=None,
            height=dp(22),
            font_size=dp(12),
            color=UI_TEXT_MUTED,
            halign='left',
            text_size=(None, None)
        )
        intro_subtitle.bind(size=intro_subtitle.setter('text_size'))
        intro_card.add_widget(intro_title)
        intro_card.add_widget(intro_subtitle)
        main_container.add_widget(intro_card)

        quick_card = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=dp(108),
            spacing=dp(8),
            padding=(dp(14), dp(12), dp(14), dp(12))
        )
        self.quick_card = quick_card
        apply_rounded_panel(quick_card, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(12), border_alpha=0.06)

        quick_title = Label(
            text='Новая раскладка',
            size_hint_y=None,
            height=dp(24),
            font_size=dp(16),
            bold=True,
            color=UI_TEXT_STRONG,
            halign='left',
            text_size=(None, None)
        )
        quick_title.bind(size=quick_title.setter('text_size'))
        quick_card.add_widget(quick_title)

        layout_button = Button(
            text=self._get_layout_selector_text(),
            size_hint_y=None,
            height=dp(48),
            font_size=dp(14),
            bold=True,
            halign='left',
            valign='middle',
            background_color=(0, 0, 0, 0),
            background_normal='',
            background_down='',
            shorten=True,
            shorten_from='right',
        )
        self.layout_selector_button = layout_button
        layout_button.padding = (dp(14), 0)
        layout_button.bind(size=lambda inst, s: setattr(inst, 'text_size', (max(1, s[0] - dp(42)), s[1])))
        layout_button.color = UI_TEXT_STRONG
        apply_rounded_button(layout_button, base_rgba=(0.30, 0.50, 0.36, 1), radius_px=dp(10), border_alpha=0.10)
        layout_button.bind(on_release=lambda *_: self._open_layout_preset_screen())
        quick_card.add_widget(layout_button)
        main_container.add_widget(quick_card)

        saved_header = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(36),
            spacing=dp(8)
        )
        self._saved_header = saved_header
        saved_label = Label(
            text='Сохранённые раскладки',
            size_hint=(None, None),
            width=self._measure_text_w('Сохранённые раскладки', dp(16), padding=dp(6)),
            height=dp(36),
            font_size=dp(16),
            bold=True,
            color=UI_TEXT_STRONG,
            halign='left',
            valign='middle',
            text_size=(None, None)
        )
        saved_label.bind(size=saved_label.setter('text_size'))
        self.layouts_count_label = Label(
            text='0',
            size_hint=(None, None),
            width=dp(36),
            height=dp(36),
            font_size=dp(13),
            color=UI_TEXT_PRIMARY,
            halign='center',
            valign='middle'
        )
        self.layouts_count_label.bind(size=lambda inst, s: setattr(inst, 'text_size', s))
        apply_rounded_panel(self.layouts_count_label, base_rgba=(0.18, 0.18, 0.19, 1), radius_px=dp(8), border_alpha=0.05)
        saved_header.add_widget(saved_label)
        saved_header.add_widget(self.layouts_count_label)
        saved_header.add_widget(Widget())
        main_container.add_widget(saved_header)

        saved_card = BoxLayout(
            orientation='vertical',
            size_hint=(1, 1),
            padding=(dp(6), dp(6), dp(6), dp(6))
        )
        apply_rounded_panel(saved_card, base_rgba=(0.12, 0.12, 0.13, 1), radius_px=dp(12), border_alpha=0.06)

        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True, bar_width=dp(10))
        self.layouts_scroll = scroll
        style_scrollview_popup(scroll)

        self.layouts_container = GridLayout(
            cols=2,
            size_hint_y=None,
            spacing=dp(8),
            padding=(dp(4), dp(4), dp(4), dp(4))
        )
        self.layouts_container.bind(minimum_height=self.layouts_container.setter('height'))
        scroll.add_widget(self.layouts_container)
        saved_card.add_widget(scroll)
        main_container.add_widget(saved_card)

        Window.bind(size=lambda *_: self._on_manager_window_resized())
        try:
            Window.bind(
                on_maximize=lambda *_: self._schedule_layouts_scroll_reset(),
                on_restore=lambda *_: self._schedule_layouts_scroll_reset(),
            )
        except Exception:
            pass

        self._update_layouts_list()

    def _on_manager_window_resized(self, *_args):
        self._apply_layouts_grid_cols()
        self._schedule_layouts_scroll_reset()

    def _get_layout_grid_cols(self) -> int:
        width = float(getattr(Window, "width", 0) or 0)
        if width and width <= 1100:
            return 1
        return 2

    def _apply_layouts_grid_cols(self) -> None:
        if hasattr(self, "layouts_container") and self.layouts_container is not None:
            self.layouts_container.cols = self._get_layout_grid_cols()

    def _measure_text_w(self, text: str, font_size: float, padding: float = 0.0) -> float:
        try:
            cl = CoreLabel(text=text, font_size=font_size, bold=False)
            cl.refresh()
            return float(cl.texture.size[0]) + float(padding)
        except Exception:
            return dp(100)

    @staticmethod
    def _monitor_word(count: int) -> str:
        tail10 = count % 10
        tail100 = count % 100
        if tail10 == 1 and tail100 != 11:
            return "монитор"
        if tail10 in (2, 3, 4) and tail100 not in (12, 13, 14):
            return "монитора"
        return "мониторов"

    def _get_layout_selector_text(self) -> str:
        if self._last_layout_preset is None:
            return "Выбрать количество мониторов"
        return f"Количество мониторов: {self._last_layout_preset}"

    def _open_layout_preset_screen(self):
        """Открыть отдельную страницу выбора количества мониторов."""
        from components.layout_preset_selection_screen import LayoutPresetSelectionScreen

        if self.manager is None:
            return

        screen_name = self._layout_preset_screen_name
        if self.manager.has_screen(screen_name):
            screen = self.manager.get_screen(screen_name)
            screen.previous_screen = self.name
            if hasattr(screen, "set_on_select"):
                screen.set_on_select(self._select_layout_preset)
        else:
            screen = LayoutPresetSelectionScreen(
                name=screen_name,
                presets=self._layout_presets,
                on_select=self._select_layout_preset,
                previous_screen=self.name,
            )
            self.manager.add_widget(screen)

        self.manager.current = screen_name

    def _select_layout_preset(self, monitor_count: int):
        self._last_layout_preset = monitor_count
        if self.layout_selector_button is not None:
            self.layout_selector_button.text = self._get_layout_selector_text()
        self._create_new_layout(monitor_count)

    def _reset_layout_selector(self):
        self._last_layout_preset = None
        if self.layout_selector_button is not None:
            self.layout_selector_button.text = self._get_layout_selector_text()

    def _replace_managed_screen(self, screen) -> bool:
        if self.manager is None:
            return False
        try:
            if self.manager.has_screen(screen.name):
                existing = self.manager.get_screen(screen.name)
                self.manager.remove_widget(existing)
            self.manager.add_widget(screen)
            self.manager.current = screen.name
            return True
        except Exception:
            return False

    def _build_bed_chips(self, chips: list[str]) -> BoxLayout:
        grid = GridLayout(
            cols=4,
            size_hint_y=None,
            spacing=dp(6),
            row_default_height=dp(28),
            row_force_default=True,
        )
        max_chip_count = 8
        row_count = 2
        grid.height = row_count * dp(28) + max(0, row_count - 1) * dp(6)

        for chip_text in chips[:max_chip_count]:
            chip = Label(
                text=chip_text,
                size_hint=(1, None),
                height=dp(28),
                font_size=dp(12),
                color=UI_TEXT_PRIMARY,
                halign='center',
                valign='middle',
                shorten=True,
                shorten_from='right',
            )
            chip.bind(size=lambda inst, s: setattr(inst, 'text_size', (max(1, s[0] - dp(12)), None)))
            apply_rounded_panel(chip, base_rgba=(0.18, 0.18, 0.19, 1), radius_px=dp(8), border_alpha=0.05)
            grid.add_widget(chip)

        while len(grid.children) < max_chip_count:
            grid.add_widget(Widget(size_hint=(1, None), height=dp(28)))

        return grid

    def _schedule_layouts_scroll_reset(self, *_args):
        self._layouts_scroll_reset_trigger()

    def _reset_layouts_scroll_top(self, *_args):
        scroll = getattr(self, 'layouts_scroll', None)
        if scroll is None:
            return
        try:
            scroll.scroll_y = 1.0
            Clock.schedule_once(lambda _dt: setattr(scroll, 'scroll_y', 1.0), 0.05)
        except Exception:
            pass
    
    def _open_layout(self, monitor_count: int, config_id: str = None):
        """Открытие раскладки с указанным количеством мониторов - создает одно отдельное окно через subprocess"""
        import subprocess
        import sys
        import os
        
        # Создаем одно окно с несколькими мониторами
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'run_monitor_window.py')
        window_id = f'layout_{monitor_count}_monitors'
        
        # Если указан config_id, передаем его как параметр
        args = [sys.executable, script_path, window_id, str(monitor_count)]
        if config_id:
            args.append(config_id)
        
        # Запускаем отдельный процесс для окна с раскладкой (без новой консоли на Windows)
        try:
            if not os.path.exists(script_path):
                raise FileNotFoundError(f"Не найден файл запуска: {script_path}")
            creationflags = 0
            if sys.platform == "win32":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            proc = subprocess.Popen(
                args,
                creationflags=creationflags,
                cwd=os.path.dirname(os.path.dirname(__file__)),
            )
            print(f"[MainWindowManager] layout window started pid={proc.pid} monitors={monitor_count}")
            # Разрешаем дочернему процессу поднять окно на передний план (Win focus rules).
            if sys.platform == "win32":
                try:
                    from utils.kivy_windows_titlebar import win32_allow_set_foreground_window

                    win32_allow_set_foreground_window(proc.pid)
                except Exception:
                    pass
        except Exception as e:
            print(f"Ошибка создания окна раскладки: {e}")
            self._show_layout_open_failure(monitor_count, str(e))

    def _show_layout_open_failure(self, monitor_count: int, error: str) -> None:
        """Показать ошибку запуска внешнего окна и предложить встроенный fallback."""
        screen = ConfirmActionScreen(
            name="layout_open_failure_screen",
            title_text="Не удалось открыть окно раскладки",
            message_text=(
                "Отдельное окно мониторов не запустилось.\n\n"
                f"Причина: {error}\n\n"
                "Можно открыть раскладку во встроенном режиме текущего окна."
            ),
            action_text="Открыть в этом окне",
            previous_screen=self.name,
            on_confirm=lambda: self._open_layout_fallback(monitor_count),
        )
        if not self._replace_managed_screen(screen):
            # Крайний случай: менеджер экранов недоступен.
            self._open_layout_fallback(monitor_count)
    
    def _create_new_layout(self, monitor_count: int):
        """Создание новой раскладки с настройками."""
        from components.layout_creation_screen import LayoutCreationScreen

        self._reset_layout_selector()
        screen = LayoutCreationScreen(
            name="layout_creation_screen",
            monitor_count=monitor_count,
            beds=self._get_available_beds(),
            previous_screen=self.name,
            on_create=lambda name, beds: self._create_layout_from_screen(monitor_count, name, beds),
        )
        if not self._replace_managed_screen(screen):
            self._open_layout_fallback(monitor_count)

    def _create_layout_from_screen(self, monitor_count: int, name: str, beds: list[dict]) -> tuple[bool, str]:
        config = LayoutConfig.create_default_config(monitor_count, name)
        for i, bed in enumerate(beds):
            if i >= len(config.get("monitors", [])):
                break
            config["monitors"][i]["bed_id"] = bed.get("id")
            config["monitors"][i]["bed_name"] = bed.get("name") or bed.get("bed_name")
        if LayoutConfig.save_config(config):
            self._update_layouts_list()
            return True, ""
        return False, "Не удалось сохранить раскладку"

    def _get_available_beds(self):
        if self._beds_cache is not None:
            return list(self._beds_cache)

        beds = []
        db = None
        try:
            cfg = ConfigLoader()
            db = DatabaseDataSource(
                host=cfg.get_db_host(),
                port=cfg.get_db_port(),
                database=cfg.get_db_name(),
                user=cfg.get_db_user(),
                password=cfg.get_db_password(),
                signal_ids=cfg.get_signal_ids(),
            )
            beds = db.get_available_beds() or []
        except Exception:
            beds = []
        finally:
            try:
                if db:
                    db.close()
            except Exception:
                pass

        self._beds_cache = beds
        return list(beds)

    def _update_layouts_list(self):
        """Обновление списка сохраненных раскладок"""
        # Очищаем контейнер
        self.layouts_container.clear_widgets()
        self._apply_layouts_grid_cols()
        
        # Загружаем сохраненные конфигурации
        configs = LayoutConfig.load_all_configs()
        self.layouts_count_label.text = str(len(configs))
        
        if not configs:
            empty_card = BoxLayout(
                orientation='vertical',
                size_hint_y=None,
                height=dp(140),
                spacing=dp(8),
                padding=(dp(14), dp(18), dp(14), dp(18))
            )
            apply_rounded_panel(empty_card, base_rgba=(0.13, 0.13, 0.14, 1), radius_px=dp(10), border_alpha=0.05)

            no_layouts_label = Label(
                text='Пока нет сохранённых раскладок',
                size_hint_y=None,
                height=dp(34),
                font_size=dp(18),
                bold=True,
                color=UI_TEXT_STRONG
            )
            hint_label = Label(
                text='Выберите количество мониторов выше, чтобы создать первую раскладку.',
                size_hint_y=None,
                height=dp(28),
                font_size=dp(12),
                color=UI_TEXT_MUTED,
                halign='center',
                valign='middle'
            )
            hint_label.bind(size=lambda inst, s: setattr(inst, 'text_size', s))
            empty_card.add_widget(Widget())
            empty_card.add_widget(no_layouts_label)
            empty_card.add_widget(hint_label)
            empty_card.add_widget(Widget())
            self.layouts_container.add_widget(empty_card)
            self.layouts_container.height = dp(140)
            self._schedule_layouts_scroll_reset()
            return
        
        # Добавляем карточки для каждой раскладки
        for config in configs:
            monitors = config.get('monitors', []) or []
            chips = []
            for idx, monitor in enumerate(monitors):
                bed_name = (monitor.get('bed_name') or '').strip()
                chips.append(bed_name if bed_name else f"Монитор {idx + 1}: —")
            chips_h = 2 * dp(28) + dp(6)

            layout_card = BoxLayout(
                orientation='vertical',
                size_hint_x=1,
                size_hint_y=None,
                height=dp(132) + chips_h,
                spacing=dp(8),
                padding=(dp(14), dp(15), dp(14), dp(15))
            )
            apply_rounded_panel(layout_card, base_rgba=(0.13, 0.13, 0.14, 1), radius_px=dp(10), border_alpha=0.05)

            # Выше строка — Kivy центрирует по вертикали: равный «воздух» над/под заголовком и бейджем
            top_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44), spacing=dp(10))
            name_label = Label(
                text=config.get('name', 'Без названия'),
                size_hint=(1, None),
                height=dp(32),
                font_size=dp(18),
                bold=True,
                color=UI_TEXT_STRONG,
                halign='left',
                valign='middle',
                shorten=True,
                shorten_from='right',
            )
            name_label.bind(size=lambda inst, s: setattr(inst, 'text_size', (max(1, s[0]), None)))
            badge = Label(
                text=f"{config.get('monitor_count', 1)} экр.",
                size_hint=(None, None),
                width=dp(64),
                height=dp(28),
                font_size=dp(12),
                color=UI_TEXT_PRIMARY,
                halign='center',
                valign='middle'
            )
            badge.bind(size=lambda inst, s: setattr(inst, 'text_size', s))
            apply_rounded_panel(badge, base_rgba=(0.18, 0.18, 0.19, 1), radius_px=dp(8), border_alpha=0.05)
            top_row.add_widget(name_label)
            top_row.add_widget(badge)
            layout_card.add_widget(top_row)

            info_label = Label(
                text='Кровати в раскладке:',
                size_hint_y=None,
                height=dp(20),
                font_size=dp(12),
                color=UI_TEXT_MUTED,
                halign='left',
                valign='middle',
            )
            info_label.bind(size=lambda inst, s: setattr(inst, 'text_size', (max(1, s[0]), None)))
            layout_card.add_widget(info_label)

            layout_card.add_widget(self._build_bed_chips(chips))

            actions = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(34), spacing=dp(8))
            actions.add_widget(Widget())
            buttons_box = BoxLayout(
                orientation='horizontal',
                size_hint=(None, 1),
                width=dp(228),
                spacing=dp(8),
            )
            open_button = Button(
                text='Открыть',
                size_hint=(1, 1),
                font_size=dp(13),
                background_color=(0, 0, 0, 0),
                background_normal='',
                background_down=''
            )
            open_button.color = UI_TEXT_PRIMARY
            apply_rounded_button(open_button, base_rgba=UI_BTN_SUCCESS)
            open_button.bind(
                on_press=lambda instance, cid=config.get('id'): self._open_saved_layout(cid)
            )
            delete_button = Button(
                text='Удалить',
                size_hint_x=None,
                width=dp(96),
                font_size=dp(13),
                background_color=(0, 0, 0, 0),
                background_normal='',
                background_down=''
            )
            delete_button.color = UI_TEXT_PRIMARY
            apply_rounded_button(delete_button, base_rgba=UI_BTN_DANGER)
            delete_button.bind(
                on_press=lambda instance, cid=config.get('id'): self._confirm_delete_layout(cid)
            )
            buttons_box.add_widget(open_button)
            buttons_box.add_widget(delete_button)
            actions.add_widget(buttons_box)
            layout_card.add_widget(actions)

            self.layouts_container.add_widget(layout_card)
        self._schedule_layouts_scroll_reset()
    
    def _open_saved_layout(self, config_id: str):
        """Открытие сохраненной раскладки"""
        config = LayoutConfig.get_config(config_id)
        if config:
            monitor_count = config.get('monitor_count', 1)
            self._open_layout(monitor_count, config_id)
    
    def _delete_layout(self, config_id: str):
        """Удаление раскладки"""
        if LayoutConfig.delete_config(config_id):
            self._update_layouts_list()

    def _confirm_delete_layout(self, config_id: str):
        config = LayoutConfig.get_config(config_id)
        title = str((config or {}).get('name') or 'эту раскладку')
        from components.confirm_action_screen import ConfirmActionScreen

        screen = ConfirmActionScreen(
            name="layout_delete_confirm_screen",
            title_text="Подтвердите удаление",
            message_text=f'Удалить раскладку "{title}"?\nЭто действие нельзя отменить.',
            action_text="Удалить",
            on_confirm=lambda: self._delete_layout(config_id),
            previous_screen=self.name,
        )
        self._replace_managed_screen(screen)
    
    def _open_layout_fallback(self, monitor_count: int):
        """Fallback - открытие раскладки через ScreenManager (старый способ)"""
        layout_screen_name = f'layout_{monitor_count}_monitors'

        # Пересоздаем экран раскладки при каждом открытии:
        # это гарантирует актуальную вёрстку и чистое состояние embedded MonitorScreen.
        if self.manager and self.manager.has_screen(layout_screen_name):
            existing_screen = self.manager.get_screen(layout_screen_name)
            try:
                if hasattr(existing_screen, "on_pre_leave"):
                    existing_screen.on_pre_leave()
            except Exception:
                pass
            self.manager.remove_widget(existing_screen)

        # Создаем новый экран раскладки
        from components.layout_screen import LayoutScreen
        layout_screen = LayoutScreen(name=layout_screen_name, monitor_count=monitor_count)

        # Добавляем экран в менеджер экранов
        if self.manager:
            self.manager.add_widget(layout_screen)
            self.manager.current = layout_screen_name
