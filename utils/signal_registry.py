"""
Реестр сигналов: ID по умолчанию, диапазоны отображения, единицы, цвета.

Импорт:
    from utils.signal_registry import SIGNAL_REGISTRY, DEFAULT_SIGNAL_IDS, get_display_range
"""

from __future__ import annotations

import configparser
from pathlib import Path

# ---------------------------------------------------------------------------
# Дефолтные signal_id  (соответствуют signal_param в БД «med»)
# Переопределяются через config.ini:
#   [DATABASE]        signal_id_<key>
#   [SIGNAL_REGISTRY] signal_id_<key>
# ---------------------------------------------------------------------------
DEFAULT_SIGNAL_IDS: dict[str, int] = {
    "spo2": 76,           # o2 (%)
    "pulse": 77,          # пульс (1/мин)
    "breathing": 50,      # частота вздоха (1/min)
    "temperature": 57,    # температура (C)
    "systolic_bp": 1,     # систолическое давление (мм.рт.с)
    "diastolic_bp": 2,    # диастолическое давление (мм.рт.с)
    "mean_bp": 3,         # среднее давление (мм.рт.с)
    "nibp_systolic": 4,   # неинвазивное систолическое (мм.рт.с)
    "nibp_diastolic": 5,  # неинвазивное диастолическое (мм.рт.с)
    "nibp_mean": 6,       # неинвазивное среднее (мм.рт.с)
    "ibp_systolic": 7,    # инвазивное систолическое (мм.рт.с)
    "ibp_diastolic": 8,   # инвазивное диастолическое (мм.рт.с)
    "ibp_mean": 9,        # инвазивное среднее (мм.рт.с)
    "co2": 23,            # CO2 (%)
    "etco2": 56,          # ETCO2 (%)
    "fio2": 53,           # FiO2 (%)
    "eto2": 54,           # EtO2 (%)
    "skin_temp": 60,      # температура кожи (C)
    "plethysmogram": 75,  # плетизмограмм (%)
    "spont_rr": 46,       # частота вдоха спонтанная (1/min)
}


# ---------------------------------------------------------------------------
# Диапазоны отображения на графике  (min, max)
#
# Подобраны по клинически значимым границам:
#   • «рабочий» диапазон захватывает норму + умеренные отклонения;
#   • для критических выбросов данные всё равно видны (выходят за пределы,
#     но график автоматически растянет ось при необходимости).
# ---------------------------------------------------------------------------
DISPLAY_RANGES: dict[str, tuple[float, float]] = {
    # ── Оксигенация ────────────────────────────────────────
    "spo2":           (85,  100),    # SpO2 %     норма 95-100, <90 критично
    "plethysmogram":  (0,   100),    # плетизмограмм %

    # ── Пульс / ЧСС ───────────────────────────────────────
    "pulse":          (40,  160),    # уд/мин     брадикардия <60, тахикардия >100

    # ── Дыхание ────────────────────────────────────────────
    "breathing":      (0,   40),     # вдох/мин   норма 12-20
    "spont_rr":       (0,   40),     # 1/min

    # ── Давление (мм.рт.ст.) ──────────────────────────────
    "systolic_bp":    (40,  250),    # систолическое    норма 90-140
    "diastolic_bp":   (20,  150),    # диастолическое   норма 60-90
    "mean_bp":        (30,  170),    # среднее          норма 70-105
    "nibp_systolic":  (40,  250),
    "nibp_diastolic": (20,  150),
    "nibp_mean":      (30,  170),
    "ibp_systolic":   (40,  250),
    "ibp_diastolic":  (20,  150),
    "ibp_mean":       (30,  170),

    # ── Температура (°C) ───────────────────────────────────
    "temperature":    (34,  42),     # норма 36.0-37.5, гипертермия >38.5
    "skin_temp":      (30,  40),     # кожа обычно на 1-2° ниже

    # ── Газы ───────────────────────────────────────────────
    "co2":            (0,   10),     # CO2 %
    "etco2":          (0,   10),     # ETCO2 %    норма 4-6 (≈35-45 mmHg)
    "fio2":           (15,  100),    # FiO2 %     воздух 21%, чистый O2 100%
    "eto2":           (15,  100),    # EtO2 %
}


# ---------------------------------------------------------------------------
# Мета-данные: заголовок, цвет, единица измерения
# ---------------------------------------------------------------------------
SIGNAL_META: dict[str, dict] = {
    "spo2":           {"title": "SPO2",             "color": "#FF4444", "unit": "%"},
    "pulse":          {"title": "Пульс",            "color": "#44FF44", "unit": "уд/мин"},
    "breathing":      {"title": "Дыхание",          "color": "#4488FF", "unit": "вдох/мин"},
    "temperature":    {"title": "Температура",      "color": "#FFAA22", "unit": "°C"},
    "systolic_bp":    {"title": "Сист. АД",         "color": "#FF6666", "unit": "мм.рт.ст"},
    "diastolic_bp":   {"title": "Диаст. АД",        "color": "#FF9999", "unit": "мм.рт.ст"},
    "mean_bp":        {"title": "Ср. АД",           "color": "#FFCCCC", "unit": "мм.рт.ст"},
    "nibp_systolic":  {"title": "НИАД сист.",       "color": "#FF6666", "unit": "мм.рт.ст"},
    "nibp_diastolic": {"title": "НИАД диаст.",      "color": "#FF9999", "unit": "мм.рт.ст"},
    "nibp_mean":      {"title": "НИАД ср.",         "color": "#FFCCCC", "unit": "мм.рт.ст"},
    "ibp_systolic":   {"title": "ИАД сист.",        "color": "#CC4444", "unit": "мм.рт.ст"},
    "ibp_diastolic":  {"title": "ИАД диаст.",       "color": "#CC7777", "unit": "мм.рт.ст"},
    "ibp_mean":       {"title": "ИАД ср.",          "color": "#CCAAAA", "unit": "мм.рт.ст"},
    "co2":            {"title": "CO2",              "color": "#FFFF44", "unit": "%"},
    "etco2":          {"title": "ETCO2",            "color": "#DDDD22", "unit": "%"},
    "fio2":           {"title": "FiO2",             "color": "#44DDFF", "unit": "%"},
    "eto2":           {"title": "EtO2",             "color": "#22BBDD", "unit": "%"},
    "skin_temp":      {"title": "Т кожи",           "color": "#FFCC44", "unit": "°C"},
    "plethysmogram":  {"title": "Плетизмо",         "color": "#44FFAA", "unit": "%"},
    "spont_rr":       {"title": "ЧД спонт.",        "color": "#6688FF", "unit": "вдох/мин"},
}


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

SIGNAL_REGISTRY = SIGNAL_META


def _get_config_path() -> Path | None:
    """Найти config.ini в проекте или текущей рабочей директории."""
    candidates = [
        Path(__file__).resolve().parent.parent / "config.ini",
        Path("config.ini").resolve(),
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _parse_range(raw_value: str) -> tuple[float, float] | None:
    """Распарсить диапазон из строки вида 'min,max'."""
    if not raw_value:
        return None
    parts = [part.strip() for part in raw_value.split(",")]
    if len(parts) != 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except (TypeError, ValueError):
        return None


def _apply_ini_overrides():
    """Переопределить реестр сигналов значениями из config.ini."""
    config_path = _get_config_path()
    if config_path is None:
        return

    config = configparser.ConfigParser()
    try:
        config.read(config_path, encoding="utf-8")
    except Exception:
        return

    for key in list(DEFAULT_SIGNAL_IDS.keys()):
        signal_id = None
        for section in ("SIGNAL_REGISTRY", "DATABASE"):
            try:
                if config.has_option(section, f"signal_id_{key}"):
                    signal_id = config.getint(section, f"signal_id_{key}")
                    break
            except Exception:
                pass
        if signal_id is not None:
            DEFAULT_SIGNAL_IDS[key] = signal_id

        try:
            raw_range = config.get("SIGNAL_REGISTRY", f"range_{key}", fallback="").strip()
        except Exception:
            raw_range = ""
        parsed_range = _parse_range(raw_range)
        if parsed_range is not None:
            DISPLAY_RANGES[key] = parsed_range

        if key not in SIGNAL_META:
            SIGNAL_META[key] = {"title": key, "color": "#AAAAAA", "unit": ""}

        for field in ("title", "color", "unit"):
            try:
                value = config.get("SIGNAL_REGISTRY", f"{field}_{key}", fallback="").strip()
            except Exception:
                value = ""
            if value:
                SIGNAL_META[key][field] = value


_apply_ini_overrides()

def get_display_range(key: str) -> tuple[float, float]:
    """Вернуть (min, max) для отображения на графике.

    Если ключ не найден — возвращает (0, 100) как безопасный fallback.
    """
    return DISPLAY_RANGES.get(key, (0, 100))


def get_signal_meta(key: str) -> dict:
    """Вернуть {title, color, unit} для сигнала.

    Если ключ не найден — возвращает разумные значения по умолчанию.
    """
    return SIGNAL_META.get(key, {"title": key, "color": "#AAAAAA", "unit": ""})


def get_default_signal_id(key: str) -> int | None:
    """Вернуть signal_id по умолчанию для ключа параметра."""
    return DEFAULT_SIGNAL_IDS.get(key)


def iter_configured_signal_ranges() -> list[dict]:
    """Вернуть диапазоны из config.ini/SIGNAL_REGISTRY, привязанные к signal_id.

    Используется для начального заполнения signal_param.signal_min/signal_max.
    """
    ranges: list[dict] = []
    for key, signal_id in DEFAULT_SIGNAL_IDS.items():
        display_range = DISPLAY_RANGES.get(key)
        if signal_id is None or display_range is None:
            continue
        min_value, max_value = display_range
        ranges.append(
            {
                "key": key,
                "signal_id": int(signal_id),
                "min": float(min_value),
                "max": float(max_value),
                "meta": SIGNAL_META.get(key, {}),
            }
        )
    return ranges


# Обратный маппинг signal_id → key (строится автоматически)
_SIGNAL_ID_TO_KEY: dict[int, str] = {v: k for k, v in DEFAULT_SIGNAL_IDS.items()}


def get_display_range_by_signal_id(signal_id: int) -> tuple[float, float] | None:
    """Вернуть (min, max) для отображения по signal_id.

    Возвращает None, если signal_id не найден в реестре
    (вызывающий код может использовать fallback из БД).
    """
    key = _SIGNAL_ID_TO_KEY.get(signal_id)
    if key is None:
        return None
    return DISPLAY_RANGES.get(key)


def get_signal_meta_by_signal_id(signal_id: int) -> dict | None:
    """Вернуть meta-данные сигнала по signal_id, если он есть в реестре."""
    key = _SIGNAL_ID_TO_KEY.get(signal_id)
    if key is None:
        return None
    return SIGNAL_META.get(key)
