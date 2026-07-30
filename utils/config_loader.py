"""
Загрузчик конфигурации из config.ini
"""
import configparser
import os
from pathlib import Path
from typing import Any


class ConfigLoader:
    """Класс для загрузки конфигурации из config.ini"""

    LAYOUT_GRID_SECTION = "LAYOUT_GRID"
    _LAYOUT_GRID_OPTIONS = {
        2: ("2x1", "1x2"),
        3: ("2x2", "3x1", "1x3"),
        4: ("2x2", "4x1", "1x4"),
        5: ("2x3", "3x2"),
        6: ("2x3", "3x2"),
        7: ("2x4", "4x2", "3x3"),
        8: ("2x4", "4x2", "3x3"),
    }
    
    def __init__(self, config_file: str = 'config.ini'):
        """
        Инициализация загрузчика конфигурации
        
        Args:
            config_file: Путь к файлу конфигурации
        """
        self.config_file = config_file
        self.config = configparser.ConfigParser(
            interpolation=None,
            inline_comment_prefixes=('#', ';'),
        )
        self.config_path: Path | None = None
        self._config_mtime_ns: int | None = None
        self._load_config()
    
    def _resolve_config_path(self) -> Path | None:
        """Найти локальный config.local.ini или обычный config.ini."""
        requested = Path(self.config_file)
        script_dir = Path(__file__).parent.parent
        candidates: list[Path] = []

        # Явно переданный путь имеет приоритет.
        if requested.name != "config.ini" or requested.is_absolute():
            candidates.append(requested)
            if not requested.is_absolute():
                candidates.append(script_dir / requested)
        else:
            for base in (Path.cwd(), script_dir):
                candidates.append(base / "config.local.ini")
                candidates.append(base / "config.ini")

        seen: set[str] = set()
        for path in candidates:
            key = str(path.resolve()) if path.exists() else str(path)
            if key in seen:
                continue
            seen.add(key)
            if path.exists():
                return path.resolve()
        return None

    def _load_config(self):
        """Загрузка конфигурации из файла"""
        config_path = self._resolve_config_path()
        if config_path is None:
            print(f"Файл конфигурации {self.config_file} не найден. Используются значения по умолчанию.")
            print(f"Ожидаемые файлы: config.local.ini или config.ini")
            return

        self.config_path = config_path
        self.config = configparser.ConfigParser(
            interpolation=None,
            inline_comment_prefixes=('#', ';'),
        )
        self.config.read(self.config_path, encoding='utf-8')
        try:
            self._config_mtime_ns = self.config_path.stat().st_mtime_ns
        except Exception:
            self._config_mtime_ns = None
        print(f"Загружена конфигурация из: {config_path}")

    def _env_override(self, env_name: str, fallback: str) -> str:
        value = os.environ.get(env_name)
        if value is None:
            return fallback
        value = value.strip()
        return value if value else fallback

    def validate_database_settings(self, *, require_password: bool = False) -> list[str]:
        """Проверить обязательные параметры подключения к БД."""
        issues: list[str] = []
        if not self.get_db_host():
            issues.append("host не задан")
        try:
            port = int(self.get_db_port())
        except Exception:
            port = 0
        if port <= 0:
            issues.append("port некорректен")
        if not self.get_db_name():
            issues.append("database не задан")
        if not self.get_db_user():
            issues.append("user не задан")
        if require_password and not self.get_db_password():
            issues.append("password не задан")
        return issues
    def reload(self):
        """Принудительно перечитать config.ini с диска."""
        self._load_config()

    def reload_if_changed(self) -> bool:
        """Перечитать config.ini, если файл на диске изменился."""
        if self.config_path is None:
            self._load_config()
            return True
        try:
            current_mtime_ns = self.config_path.stat().st_mtime_ns
        except Exception:
            return False
        if self._config_mtime_ns != current_mtime_ns:
            self._load_config()
            return True
        return False

    def get_config_path(self) -> str:
        """Получить абсолютный путь до активного config.ini."""
        if self.config_path is not None:
            return str(self.config_path)
        return str(Path(self.config_file).resolve())

    def _ensure_section(self, section: str):
        """Создать секцию при отсутствии."""
        if not self.config.has_section(section):
            self.config.add_section(section)

    def get_value(self, section: str, key: str, fallback: Any = None) -> Any:
        """Универсальное чтение значения из конфигурации."""
        try:
            return self.config.get(section, key, fallback=fallback)
        except Exception:
            return fallback

    def set_value(self, section: str, key: str, value: Any):
        """Универсальная запись значения в конфигурацию (в память)."""
        self._ensure_section(section)
        self.config.set(section, key, str(value))

    def save(self) -> bool:
        """Сохранить текущую конфигурацию на диск."""
        try:
            if self.config_path is None:
                self._load_config()
            target = self.config_path or Path(self.config_file).resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as fp:
                self.config.write(fp)
            self.config_path = target
            try:
                self._config_mtime_ns = target.stat().st_mtime_ns
            except Exception:
                self._config_mtime_ns = None
            return True
        except Exception as e:
            print(f"Ошибка сохранения конфигурации: {e}")
            return False

    def to_settings_dict(self) -> dict:
        """Собрать текущие настройки для UI формы."""
        return {
            "database": {
                "mode": self.get_mode(),
                "host": self.get_db_host(),
                "port": self.get_db_port(),
                "database": self.get_db_name(),
                "user": self.get_db_user(),
                "password": self.get_db_password(),
                "display_value_1": self.get_display_value_1(),
                "display_value_2": self.get_display_value_2(),
                "camera_image_path": self.get_camera_image_path(),
            },
            "viewer_auto_periods": self.get_viewer_auto_periods(),
            "layout_grid": self.get_layout_grid_settings(),
            "signal_registry": self._get_signal_registry(),
        }

    def apply_settings_dict(self, data: dict) -> bool:
        """Применить данные формы к конфигу и сохранить файл."""
        db = data.get("database", {}) if isinstance(data, dict) else {}
        for key in ("mode", "host", "database", "user", "password", "display_value_1", "display_value_2", "camera_image_path"):
            if key in db:
                self.set_value("DATABASE", key, db.get(key, ""))
        if "port" in db:
            try:
                port = int(db.get("port"))
            except Exception:
                port = 6000
            self.set_value("DATABASE", "port", max(1, port))

        viewer = data.get("viewer_auto_periods", {}) if isinstance(data, dict) else {}
        if isinstance(viewer, dict):
            for key, value in viewer.items():
                try:
                    ivalue = max(1, int(value))
                except Exception:
                    continue
                self.set_value("VIEWER_AUTO_PERIODS", key, ivalue)

        layout_grid = data.get("layout_grid", {}) if isinstance(data, dict) else {}
        if isinstance(layout_grid, dict):
            for monitor_count in range(2, 9):
                key = f"layout_{monitor_count}"
                value = str(layout_grid.get(key, "")).strip()
                if value in self.get_layout_grid_options(monitor_count):
                    self.set_value(self.LAYOUT_GRID_SECTION, key, value)

        sig = data.get("signal_registry", {}) if isinstance(data, dict) else {}
        if isinstance(sig, dict):
            for key, value in sig.items():
                self.set_value("SIGNAL_REGISTRY", key, value)

        return self.save()

    def _get_signal_registry(self) -> dict:
        """Вернуть секцию SIGNAL_REGISTRY в виде словаря."""
        if not self.config.has_section("SIGNAL_REGISTRY"):
            return {}
        out = {}
        for k, v in self.config.items("SIGNAL_REGISTRY", raw=True):
            out[k] = v
        return out

    def set_db_host(self, value: str):
        self.set_value("DATABASE", "host", value)

    def set_db_port(self, value: int):
        self.set_value("DATABASE", "port", max(1, int(value)))

    def set_db_name(self, value: str):
        self.set_value("DATABASE", "database", value)

    def set_db_user(self, value: str):
        self.set_value("DATABASE", "user", value)

    def set_db_password(self, value: str):
        self.set_value("DATABASE", "password", value)

    def set_mode(self, value: str):
        self.set_value("DATABASE", "mode", "database")

    def set_display_value_1(self, value: str):
        self.set_value("DATABASE", "display_value_1", value)

    def set_display_value_2(self, value: str):
        self.set_value("DATABASE", "display_value_2", value)

    def set_camera_image_path(self, value: str):
        self.set_value("DATABASE", "camera_image_path", value)
    
    def get_mode(self) -> str:
        """
        Получить безопасный режим работы.

        Синтетические данные доступны только при одновременном явном указании
        mode=demo в config.ini и PATIENTMONITOR_ALLOW_DEMO_MODE=1 в окружении.
        
        Returns:
            str: 'database' или 'demo'
        """
        try:
            mode = self.config.get('DATABASE', 'mode', fallback='database').lower()
            demo_allowed = os.environ.get("PATIENTMONITOR_ALLOW_DEMO_MODE", "").strip().lower()
            if mode in {"demo", "test"} and demo_allowed in {"1", "true", "yes", "on"}:
                return "demo"
            return "database"
        except Exception:
            return 'database'
    
    def get_db_host(self) -> str:
        """Получить хост базы данных"""
        try:
            value = self.config.get('DATABASE', 'host', fallback='localhost')
        except Exception:
            value = 'localhost'
        return self._env_override('PATIENTMONITOR_DB_HOST', value)
    
    def get_db_port(self) -> int:
        """Получить порт базы данных"""
        try:
            value = self.config.get('DATABASE', 'port', fallback='6000')
        except Exception:
            value = '6000'
        value = self._env_override('PATIENTMONITOR_DB_PORT', str(value))
        try:
            return int(value)
        except Exception:
            return 6000
    
    def get_db_name(self) -> str:
        """Получить имя базы данных"""
        try:
            value = self.config.get('DATABASE', 'database', fallback='med')
        except Exception:
            value = 'med'
        return self._env_override('PATIENTMONITOR_DB_NAME', value)
    
    def get_db_user(self) -> str:
        """Получить пользователя базы данных"""
        try:
            value = self.config.get('DATABASE', 'user', fallback='postgres')
        except Exception:
            value = 'postgres'
        return self._env_override('PATIENTMONITOR_DB_USER', value)
    
    def get_db_password(self) -> str:
        """Получить пароль базы данных"""
        try:
            value = self.config.get('DATABASE', 'password', fallback='')
        except Exception:
            value = ''
        return self._env_override('PATIENTMONITOR_DB_PASSWORD', value)    
    def get_signal_ids(self) -> dict:
        """
        Получить маппинг signal_id для параметров
        
        Returns:
            dict: Словарь с signal_id для каждого параметра
        """
        try:
            return {
                'spo2': self.config.getint('DATABASE', 'signal_id_spo2', fallback=76),
                'pulse': self.config.getint('DATABASE', 'signal_id_pulse', fallback=77),
                'breathing': self.config.getint('DATABASE', 'signal_id_breathing', fallback=50),
                'temperature': self.config.getint('DATABASE', 'signal_id_temperature', fallback=57)
            }
        except:
            return {
                'spo2': 76,
                'pulse': 77,
                'breathing': 50,
                'temperature': 57
            }
    
    def get_display_value_1(self) -> str:
        """Получить название первого параметра для отображения"""
        try:
            return self.config.get('DATABASE', 'display_value_1', fallback='spo2')
        except:
            return 'spo2'
    
    def get_display_value_2(self) -> str:
        """Получить название второго параметра для отображения"""
        try:
            return self.config.get('DATABASE', 'display_value_2', fallback='pulse')
        except:
            return 'pulse'
    
    def get_camera_image_path(self) -> str:
        """Получить путь к изображению камеры"""
        try:
            return self.config.get('DATABASE', 'camera_image_path', fallback='')
        except:
            return ''

    def get_viewer_auto_periods(self) -> dict:
        """
        Получить таблицу авто-шагов агрегации для viewer_mode.        Значения задаются в секундах в секции [VIEWER_AUTO_PERIODS].
        """
        defaults = {
            "range_1m": 5,
            "range_5m": 10,
            "range_15m": 30,
            "range_30m": 60,
            "range_1h": 120,
            "range_2h": 300,
            "range_4h": 600,
            "range_1d": 1800,
            "range_over_1d": 3600,
        }
        out = dict(defaults)
        try:
            section = "VIEWER_AUTO_PERIODS"
            for key, fallback in defaults.items():
                out[key] = max(1, self.config.getint(section, key, fallback=fallback))
        except Exception:
            return defaults
        return out

    @classmethod
    def get_layout_grid_options(cls, monitor_count: int) -> tuple[str, ...]:
        return cls._LAYOUT_GRID_OPTIONS.get(int(monitor_count), ())

    @classmethod
    def get_default_layout_grid(cls, monitor_count: int) -> str:
        options = cls.get_layout_grid_options(monitor_count)
        if options:
            return options[0]
        return "1x1"

    def get_layout_grid_choice(self, monitor_count: int) -> str:
        monitor_count = int(monitor_count)
        if monitor_count <= 1:
            return "1x1"
        key = f"layout_{monitor_count}"
        options = self.get_layout_grid_options(monitor_count)
        default = self.get_default_layout_grid(monitor_count)
        value = str(self.get_value(self.LAYOUT_GRID_SECTION, key, fallback=default) or "").strip()
        return value if value in options else default

    def get_layout_grid_dimensions(self, monitor_count: int) -> tuple[int, int]:
        choice = self.get_layout_grid_choice(monitor_count)
        try:
            cols_text, rows_text = choice.lower().split("x", 1)
            cols = max(1, int(cols_text))
            rows = max(1, int(rows_text))
            return cols, rows
        except Exception:
            return 1, 1

    def get_layout_grid_settings(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for monitor_count in range(2, 9):
            out[f"layout_{monitor_count}"] = self.get_layout_grid_choice(monitor_count)
        return out