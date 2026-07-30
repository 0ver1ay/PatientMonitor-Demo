"""Apply SQL migrations from ./migrations with autocommit enabled."""

from __future__ import annotations

import argparse
from pathlib import Path

import psycopg2

from utils.config_loader import ConfigLoader


def iter_migration_files(migrations_dir: Path) -> list[Path]:
    return sorted(migrations_dir.glob("*.sql"))


def apply_migrations(migrations_dir: Path, dry_run: bool = False) -> int:
    config = ConfigLoader()
    issues = config.validate_database_settings()
    if issues:
        print("Конфигурация БД неполная:")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    files = iter_migration_files(migrations_dir)
    if not files:
        print(f"Нет SQL-файлов в {migrations_dir}")
        return 1

    print(
        f"Цель: {config.get_db_host()}:{config.get_db_port()}/"
        f"{config.get_db_name()} (user={config.get_db_user()})"
    )
    for path in files:
        print(f"- {path.name}")
        if dry_run:
            continue
        sql = path.read_text(encoding="utf-8")
        conn = psycopg2.connect(
            host=config.get_db_host(),
            port=config.get_db_port(),
            database=config.get_db_name(),
            user=config.get_db_user(),
            password=config.get_db_password(),
        )
        try:
            conn.autocommit = True
            with conn.cursor() as cursor:
                cursor.execute(sql)
            print(f"  OK: {path.name}")
        finally:
            conn.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply PatientMonitor SQL migrations")
    parser.add_argument(
        "--migrations-dir",
        default=str(Path(__file__).resolve().parent / "migrations"),
        help="Directory with *.sql migrations",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only list migrations")
    args = parser.parse_args()
    return apply_migrations(Path(args.migrations_dir), dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
