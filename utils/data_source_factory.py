from __future__ import annotations

from dataclasses import dataclass

from utils.config_loader import ConfigLoader
from utils.data_generator import DataGenerator
from utils.data_source import DataSource
from utils.database_source import DatabaseDataSource


@dataclass(frozen=True)
class DataSourceCreationResult:
    source: DataSource
    mode: str
    available: bool
    error: str | None = None


def database_retry_delay(attempt: int) -> float:
    """Вернуть задержку перед следующим reconnect с ограниченным backoff."""
    delays = (5.0, 10.0, 30.0, 60.0)
    index = max(0, min(int(attempt), len(delays) - 1))
    return delays[index]


def create_configured_data_source(
    config: ConfigLoader,
    *,
    bed_id: int | None = None,
) -> DataSourceCreationResult:
    """Создать источник без скрытой подмены недоступной БД синтетикой."""
    mode = config.get_mode()
    if mode == "demo":
        return DataSourceCreationResult(
            source=DataGenerator(),
            mode="demo",
            available=True,
        )

    params = {
        "host": config.get_db_host(),
        "port": config.get_db_port(),
        "database": config.get_db_name(),
        "user": config.get_db_user(),
        "password": config.get_db_password(),
        "signal_ids": config.get_signal_ids(),
        "bed_id": bed_id,
    }
    try:
        source = DatabaseDataSource(**params)
        if source.is_available():
            return DataSourceCreationResult(
                source=source,
                mode="database",
                available=True,
            )
        return DataSourceCreationResult(
            source=source,
            mode="database",
            available=False,
            error=(
                f"Нет связи с PostgreSQL "
                f"{params['host']}:{params['port']}/{params['database']}"
            ),
        )
    except Exception as exc:
        source = DatabaseDataSource.disconnected(
            host=params["host"],
            port=params["port"],
            database=params["database"],
            user=params["user"],
            signal_ids=params["signal_ids"],
            bed_id=bed_id,
        )
        return DataSourceCreationResult(
            source=source,
            mode="database",
            available=False,
            error=f"Ошибка подключения к PostgreSQL: {exc}",
        )
