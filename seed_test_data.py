"""
Засеивает БД тестовыми данными для удобной проверки UI:

1. Назначает пациентов всем койкам, кроме одной (по умолчанию bed#3) — она остается
   без зарегистрированного пациента (для проверки сообщения в правой колонке).
2. Создает (или продлевает) запись в `worklist` с временем поступления, чтобы
   на блоке пациента отображалось "Поступил: ...".
3. Записывает в `signals` набор показателей за последние N часов и небольшое окно
   вперед, чтобы графики были заполнены при старте.

Использование:
    python seed_test_data.py                # по умолчанию: 6 часов, bed#3 пустой
    python seed_test_data.py --hours 4 --empty-bed 5
    python seed_test_data.py --no-signals   # только пациенты/worklist без signals
    python seed_test_data.py --skip-patients --hours 2  # только данные сигналов

Скрипт идемпотентен: безопасно запускать повторно, при необходимости актуализирует
существующие записи и удаляет старые тестовые signals в выбранном диапазоне.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

from run_live_db_writer import (
    BedState,
    SignalInfo,
    create_bed_state,
    update_bed_state,
    generate_signal_value,
    get_db_config,
    insert_rows,
    load_beds,
    load_signals,
    resolve_config_path,
)


# Сопоставление койки -> используемый patient_id из таблицы patient.
# Берем существующих пациентов 1..12 (есть в дампе med.sql), чтобы не плодить
# дубликаты. Для койки, попадающей в --empty-bed, регистрация пациента не делается.
DEFAULT_BED_PATIENT_MAP: dict[int, int] = {
    1: 1,
    2: 2,
    3: 3,
    4: 4,
    5: 5,
    6: 6,
    7: 7,
    8: 8,
    9: 9,
    10: 10,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Засеять БД тестовыми пациентами и сигналами для всех коек.")
    parser.add_argument("--config", type=str, default="", help="Путь к config.ini.")
    parser.add_argument("--hours", type=float, default=6.0, help="Сколько часов истории сигналов засеять (по умолчанию 6).")
    parser.add_argument("--forward-minutes", type=float, default=2.0, help="Сколько минут данных записать в будущее, чтобы live сразу был наполнен.")
    parser.add_argument("--step-seconds", type=float, default=1.0, help="Шаг моделирования в секундах для генерации сигналов.")
    parser.add_argument("--seed", type=int, default=20260430, help="Seed для воспроизводимой симуляции.")
    parser.add_argument("--empty-bed", type=int, default=3, help="bed_id, который оставить без пациента (по умолчанию 3).")
    parser.add_argument("--admitted-hours-ago", type=float, default=12.0, help="На сколько часов назад поставить дату/время поступления.")
    parser.add_argument("--skip-patients", action="store_true", help="Не трогать таблицы bed/worklist (только signals).")
    parser.add_argument("--no-signals", action="store_true", help="Не записывать signals (только пациенты/worklist).")
    parser.add_argument("--limit-signals", type=int, default=0, help="Ограничить число сигналов (для отладки).")
    parser.add_argument("--cleanup-existing-signals", action="store_true", help="Перед записью удалить existing signals в [start;end] для перетестируемых коек.")
    return parser


def assign_patients_to_beds(
    conn,
    beds: list[int],
    bed_patient_map: dict[int, int],
    empty_bed: int,
    admitted_at: datetime,
) -> None:
    """Назначить пациентов койкам и завести / актуализировать worklist-записи.

    Для empty_bed обнуляем bed.patient_id и удаляем активные worklist'ы по нашему
    маркеру (worklist_descr LIKE '[seed-test]%'), чтобы койка точно осталась пустой.
    """
    seed_marker = "[seed-test]"
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Узнаем room_id/block_id для каждой кровати: они нужны для worklist.
        cur.execute(
            """
            SELECT bed_id, room_id, block_id
            FROM bed
            WHERE bed_id = ANY(%s)
            """,
            (beds,),
        )
        bed_rows = cur.fetchall()

    bed_meta: dict[int, dict] = {int(r["bed_id"]): dict(r) for r in bed_rows}

    with conn.cursor() as cur:
        # Сначала чистим старые тестовые worklist'ы для всех тестовых коек,
        # чтобы потом перевыставить актуальные с одним сегодняшним admitted_at.
        cur.execute(
            """
            DELETE FROM worklist
            WHERE COALESCE(worklist_descr, '') LIKE %s
            """,
            (f"{seed_marker}%",),
        )
        deleted_worklists = cur.rowcount or 0

        # 1) Сбрасываем patient_id у empty-bed.
        cur.execute(
            """
            UPDATE bed SET patient_id = 0 WHERE bed_id = %s
            """,
            (int(empty_bed),),
        )

        # 2) Назначаем пациентов остальным койкам и создаем worklist.
        for bed_id in beds:
            bed_id_i = int(bed_id)
            if bed_id_i == int(empty_bed):
                continue
            patient_id = int(bed_patient_map.get(bed_id_i, 0) or 0)
            if patient_id <= 0:
                continue

            cur.execute(
                """
                UPDATE bed SET patient_id = %s WHERE bed_id = %s
                """,
                (patient_id, bed_id_i),
            )

            meta = bed_meta.get(bed_id_i)
            if not meta:
                continue
            room_id = meta.get("room_id") or 1
            block_id = meta.get("block_id") or 4

            cur.execute(
                """
                INSERT INTO worklist (
                    worklist_numb, patient_id, doctor_id, room_id, block_id,
                    date_beg, time_beg, date_end, time_end,
                    worklist_descr, worklist_text
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, NULL, NULL,
                    %s, NULL
                )
                """,
                (
                    f"S{bed_id_i:03d}",
                    patient_id,
                    2,  # doctor_id из существующего справочника (Иванов)
                    int(room_id),
                    int(block_id),
                    admitted_at.date(),
                    admitted_at.time().replace(microsecond=0),
                    f"{seed_marker} bed_id={bed_id_i} patient_id={patient_id}",
                ),
            )

    conn.commit()
    print(f"Удалено старых тестовых worklist-записей: {deleted_worklists}")
    print(f"empty_bed={empty_bed}: bed.patient_id обнулён.")
    populated = [bid for bid in beds if int(bid) != int(empty_bed)]
    print(f"Назначены пациенты для коек: {populated}")


def cleanup_signals_in_range(conn, beds: list[int], start: datetime, end: datetime) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM signals
            WHERE bed_id = ANY(%s)
              AND signals_date_time BETWEEN %s AND %s
            """,
            (beds, start, end),
        )
        deleted = cur.rowcount or 0
    conn.commit()
    print(f"Удалено существующих signals в диапазоне [{start}; {end}]: {deleted}")


def seed_signals(
    conn,
    beds: list[int],
    signals: list[SignalInfo],
    start: datetime,
    end: datetime,
    step_seconds: float,
    seed: int,
) -> None:
    """Генерируем точки сигналов от start до end шагом step_seconds.

    Для каждого сигнала используется собственный период (period_seconds), как в
    live-writer. Точки уникальные на bed/signal/timestamp.
    """
    if start >= end:
        return
    if step_seconds <= 0:
        step_seconds = 1.0
    total_seconds = (end - start).total_seconds()

    states: dict[int, BedState] = {bed_id: create_bed_state(bed_id, seed) for bed_id in beds}
    rng = random.Random(seed ^ 0xA5A5A5A5)

    next_due_offset: dict[tuple[int, int], float] = {}
    for bed_id in beds:
        for s in signals:
            next_due_offset[(bed_id, int(s.signal_id))] = 0.0

    rows: list[tuple[int, int, datetime, float]] = []
    rows_total = 0
    batch_threshold = 25000

    t0 = time.monotonic()
    offset = 0.0
    while offset <= total_seconds + 1e-6:
        ts = start + timedelta(seconds=offset)
        ts_unix = ts.timestamp()
        for bed_id in beds:
            state = states[bed_id]
            update_bed_state(state, step_seconds, rng)
            for s in signals:
                key = (bed_id, int(s.signal_id))
                due_at = next_due_offset.get(key, 0.0)
                if offset + 1e-9 < due_at:
                    continue
                value = generate_signal_value(s, state, rng, ts_unix)
                rows.append((int(bed_id), int(s.signal_id), ts, value))
                next_due_offset[key] = max(due_at, offset) + s.period_seconds

        if len(rows) >= batch_threshold:
            insert_rows(conn, rows)
            rows_total += len(rows)
            rows.clear()

        offset += step_seconds

    if rows:
        insert_rows(conn, rows)
        rows_total += len(rows)
        rows.clear()

    elapsed = time.monotonic() - t0
    print(
        f"Засеяно signals: {rows_total} строк за {elapsed:.1f} c "
        f"(коек: {len(beds)}, сигналов: {len(signals)})"
    )


def main() -> int:
    args = build_parser().parse_args()
    config_path = resolve_config_path(args.config)
    db_config = get_db_config(config_path)

    if args.hours <= 0 and not args.no_signals:
        print("--hours должен быть > 0 (или используйте --no-signals).", file=sys.stderr)
        return 2

    print(f"config.ini: {config_path}")
    print(f"DB: {db_config['host']}:{db_config['port']}/{db_config['database']}")

    with psycopg2.connect(**db_config) as conn:
        beds = load_beds(conn, bed_id=None, use_all_beds=True)
        print(f"Найдено коек: {len(beds)} -> {beds}")

        signals = load_signals(conn, include_inactive=True, limit_signals=args.limit_signals)
        print(f"Сигналов в каталоге: {len(signals)}")

        admitted_at = datetime.now() - timedelta(hours=float(args.admitted_hours_ago))

        if not args.skip_patients:
            assign_patients_to_beds(
                conn,
                beds=beds,
                bed_patient_map=DEFAULT_BED_PATIENT_MAP,
                empty_bed=int(args.empty_bed),
                admitted_at=admitted_at,
            )

        if not args.no_signals:
            now = datetime.now().replace(microsecond=0)
            start = now - timedelta(hours=float(args.hours))
            end = now + timedelta(minutes=float(args.forward_minutes))
            print(f"Генерируем signals от {start} до {end} (шаг {args.step_seconds:.2f} c)...")
            if args.cleanup_existing_signals:
                cleanup_signals_in_range(conn, beds, start, end)
            seed_signals(
                conn,
                beds=beds,
                signals=signals,
                start=start,
                end=end,
                step_seconds=float(args.step_seconds),
                seed=int(args.seed),
            )

    print("Готово.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
