"""Записать диапазоны сигналов из config.ini в signal_param.signal_min/signal_max."""

from __future__ import annotations

from utils.config_loader import ConfigLoader
from utils.database_source import DatabaseDataSource
from utils.signal_registry import iter_configured_signal_ranges


def main() -> int:
    config = ConfigLoader()
    ranges = iter_configured_signal_ranges()
    if not ranges:
        print("Нет диапазонов в SIGNAL_REGISTRY для синхронизации.")
        return 1

    data_source = DatabaseDataSource(
        host=config.get_db_host(),
        port=config.get_db_port(),
        database=config.get_db_name(),
        user=config.get_db_user(),
        password=config.get_db_password(),
        signal_ids=config.get_signal_ids(),
    )
    try:
        updated = data_source.update_signal_display_ranges(ranges)
    finally:
        data_source.close()

    print(f"Обновлено строк signal_param: {updated}")
    for item in ranges:
        meta = item.get("meta") or {}
        title = meta.get("title") or item["key"]
        print(f"  signal_id={item['signal_id']}: {title} -> {item['min']:g}..{item['max']:g}")
    return 0 if updated > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
