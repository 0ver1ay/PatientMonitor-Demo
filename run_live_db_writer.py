"""
Генератор live-значений для таблицы signals.

Нужен для тестирования main.py в режиме database:
- пишет в БД новые строки в реальном времени;
- может писать в одну кровать или сразу во все;
- старается держать значения в корректных клинических диапазонах.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

from utils.config_loader import ConfigLoader
from utils.signal_registry import DEFAULT_SIGNAL_IDS, DISPLAY_RANGES


KNOWN_SIGNAL_ID_TO_KEY = {int(v): k for k, v in DEFAULT_SIGNAL_IDS.items()}


@dataclass
class SignalInfo:
    signal_id: int
    name: str
    unit: str
    min_value: float
    max_value: float
    inferred_key: str | None = None
    period_seconds: float = 1.0


@dataclass
class BedState:
    bed_id: int
    heart_rate: float
    spo2: float
    breathing: float
    temperature: float
    fio2: float
    etco2: float
    systolic_bp: float
    diastolic_bp: float
    pleth_level: float
    drift_phase: float
    wave_phase: float


def clamp(value: float, min_value: float, max_value: float) -> float:
    if max_value < min_value:
        min_value, max_value = max_value, min_value
    return max(min_value, min(max_value, value))


def safe_range(min_value: float, max_value: float) -> tuple[float, float]:
    if max_value <= min_value:
        return 0.0, 100.0
    return float(min_value), float(max_value)


def infer_signal_key(signal_id: int, name: str, unit: str) -> str | None:
    known = KNOWN_SIGNAL_ID_TO_KEY.get(int(signal_id))
    if known:
        return known

    title = f"{name} {unit}".strip().lower()
    checks = [
        ("spo2", "spo2"),
        ("пульс", "pulse"),
        ("pulse", "pulse"),
        ("температ", "temperature"),
        ("дых", "breathing"),
        ("rr", "spont_rr"),
        ("спонт", "spont_rr"),
        ("плет", "plethysmogram"),
        ("pleth", "plethysmogram"),
        ("fio2", "fio2"),
        ("eto2", "eto2"),
        ("etco2", "etco2"),
        ("co2", "co2"),
        ("т кожи", "skin_temp"),
        ("skin", "skin_temp"),
        ("ниад сист", "nibp_systolic"),
        ("ниад диаст", "nibp_diastolic"),
        ("ниад ср", "nibp_mean"),
        ("иад сист", "ibp_systolic"),
        ("иад диаст", "ibp_diastolic"),
        ("иад ср", "ibp_mean"),
        ("сист. ад", "systolic_bp"),
        ("диаст. ад", "diastolic_bp"),
        ("ср. ад", "mean_bp"),
    ]
    for needle, key in checks:
        if needle in title:
            return key
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Писать live-значения в таблицу signals для тестов.")
    parser.add_argument("--config", type=str, default="", help="Путь к config.ini. По умолчанию ищется рядом с exe/скриптом и в cwd.")
    parser.add_argument("--bed-id", type=int, help="Писать только в указанную кровать.")
    parser.add_argument("--all-beds", action="store_true", help="Писать сразу во все койки из таблицы bed.")
    parser.add_argument("--active-only", action="store_true", help="Писать только по активным сигналам. По умолчанию берутся все сигналы из signal_param.")
    parser.add_argument("--interval", type=float, default=0.25, help="Шаг планировщика в секундах. Должен быть маленьким, чтобы часть сигналов шла чаще 1 раза в секунду.")
    parser.add_argument("--duration", type=float, default=0.0, help="Длительность работы в секундах. 0 = бесконечно.")
    parser.add_argument("--limit-signals", type=int, default=0, help="Ограничить число сигналов (для отладки).")
    parser.add_argument("--seed", type=int, default=20260302, help="Базовый seed для воспроизводимой симуляции.")
    parser.add_argument("--verbose-every", type=int, default=10, help="Печатать статус каждые N циклов.")
    return parser


def resolve_config_path(cli_value: str) -> str:
    candidates: list[Path] = []
    if cli_value:
        candidates.append(Path(cli_value))

    candidates.append(Path.cwd() / "config.ini")
    candidates.append(Path(__file__).resolve().parent / "config.ini")
    candidates.append(Path(__file__).resolve().parent.parent / "config.ini")

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "config.ini")
        candidates.append(exe_dir.parent / "config.ini")

    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = str(candidate.resolve())
        except Exception:
            resolved = str(candidate)
        if resolved in seen:
            continue
        seen.add(resolved)
        if Path(candidate).exists():
            return str(candidate)
    return "config.ini"


def get_db_config(config_path: str) -> dict:
    cfg = ConfigLoader(config_path)
    return {
        "host": cfg.get_db_host(),
        "port": cfg.get_db_port(),
        "database": cfg.get_db_name(),
        "user": cfg.get_db_user(),
        "password": cfg.get_db_password(),
    }


def load_beds(conn, bed_id: int | None, use_all_beds: bool) -> list[int]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT bed_id
            FROM bed
            ORDER BY bed_id ASC
            """
        )
        rows = cur.fetchall()
    all_beds = [int(row["bed_id"]) for row in rows if row.get("bed_id") is not None]
    if not all_beds:
        raise RuntimeError("В таблице bed не найдено ни одной койки.")
    if bed_id is not None:
        if bed_id not in all_beds:
            raise RuntimeError(f"Койка bed_id={bed_id} не найдена в таблице bed.")
        return [bed_id]
    if use_all_beds:
        return all_beds
    return [all_beds[0]]


def get_signal_period_seconds(signal: SignalInfo) -> float:
    key = signal.inferred_key
    if key in {"plethysmogram", "ibp_systolic", "ibp_diastolic", "ibp_mean"}:
        return 0.25
    if key in {"co2", "etco2"}:
        return 0.5
    if key in {"spo2", "pulse", "breathing", "spont_rr", "systolic_bp", "diastolic_bp", "mean_bp"}:
        return 1.0
    if key in {"fio2", "eto2"}:
        return 2.0
    if key in {"temperature", "skin_temp", "nibp_systolic", "nibp_diastolic", "nibp_mean"}:
        return 10.0

    diverse_periods = (0.5, 1.0, 2.0, 10.0)
    return diverse_periods[signal.signal_id % len(diverse_periods)]


def load_signals(conn, include_inactive: bool = True, limit_signals: int = 0) -> list[SignalInfo]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if include_inactive:
            cur.execute(
                """
                SELECT signal_id, signal_descr_rus, signal_unit, signal_min, signal_max
                FROM signal_param
                ORDER BY signal_id ASC
                """
            )
        else:
            cur.execute(
                """
                SELECT signal_id, signal_descr_rus, signal_unit, signal_min, signal_max
                FROM signal_param
                WHERE status_param = 1 OR status_param IS NULL
                ORDER BY signal_id ASC
                """
            )
        rows = cur.fetchall()

    signals: list[SignalInfo] = []
    for row in rows:
        signal_id = row.get("signal_id")
        if signal_id is None:
            continue
        name = str(row.get("signal_descr_rus") or f"Сигнал {signal_id}").strip()
        unit = str(row.get("signal_unit") or "").strip()
        db_min = row.get("signal_min")
        db_max = row.get("signal_max")
        registry_key = infer_signal_key(int(signal_id), name, unit)
        if db_min is not None and db_max is not None:
            min_value = float(db_min) if db_min is not None else 0.0
            max_value = float(db_max) if db_max is not None else 100.0
        elif registry_key and registry_key in DISPLAY_RANGES:
            min_value, max_value = DISPLAY_RANGES[registry_key]
        else:
            min_value = 0.0
            max_value = 100.0
        min_value, max_value = safe_range(min_value, max_value)
        signals.append(
            SignalInfo(
                signal_id=int(signal_id),
                name=name,
                unit=unit,
                min_value=min_value,
                max_value=max_value,
                inferred_key=registry_key,
                period_seconds=1.0,
            )
        )

    for signal in signals:
        signal.period_seconds = get_signal_period_seconds(signal)

    if limit_signals > 0:
        signals = signals[:limit_signals]
    if not signals:
        raise RuntimeError("В таблице signal_param не найдено сигналов.")
    return signals


def create_bed_state(bed_id: int, seed: int) -> BedState:
    rng = random.Random(seed + bed_id * 9973)
    hr = rng.uniform(68.0, 96.0)
    dia = rng.uniform(62.0, 84.0)
    sys = dia + rng.uniform(34.0, 54.0)
    return BedState(
        bed_id=bed_id,
        heart_rate=hr,
        spo2=rng.uniform(95.0, 99.0),
        breathing=rng.uniform(12.0, 19.0),
        temperature=rng.uniform(36.1, 37.2),
        fio2=rng.choice([21.0, 21.0, 21.0, 30.0, 35.0, 40.0]),
        etco2=rng.uniform(4.2, 5.8),
        systolic_bp=sys,
        diastolic_bp=dia,
        pleth_level=rng.uniform(8.0, 18.0),
        drift_phase=rng.uniform(0.0, math.tau),
        wave_phase=rng.uniform(0.0, math.tau),
    )


def update_bed_state(state: BedState, dt: float, rng: random.Random) -> None:
    dt = max(0.2, float(dt))
    state.drift_phase += dt * 0.12
    state.wave_phase += dt * max(0.4, state.heart_rate / 60.0) * math.tau

    hr_target = 82.0 + math.sin(state.drift_phase * 0.7 + state.bed_id * 0.3) * 8.0
    rr_target = 15.0 + math.sin(state.drift_phase * 0.4 + 0.8) * 2.5
    spo2_target = 97.0 + math.sin(state.drift_phase * 0.21) * 0.7
    temp_target = 36.7 + math.sin(state.drift_phase * 0.08 + 1.4) * 0.25
    etco2_target = 4.8 + math.sin(state.drift_phase * 0.35 + 0.2) * 0.45
    fio2_target = 21.0 + max(0.0, math.sin(state.drift_phase * 0.05)) * 18.0

    state.heart_rate = clamp(state.heart_rate + (hr_target - state.heart_rate) * 0.18 + rng.gauss(0.0, 1.2), 48.0, 135.0)
    state.breathing = clamp(state.breathing + (rr_target - state.breathing) * 0.20 + rng.gauss(0.0, 0.55), 7.0, 32.0)
    state.spo2 = clamp(state.spo2 + (spo2_target - state.spo2) * 0.24 + rng.gauss(0.0, 0.22), 88.0, 100.0)
    state.temperature = clamp(state.temperature + (temp_target - state.temperature) * 0.12 + rng.gauss(0.0, 0.03), 35.2, 38.6)
    state.etco2 = clamp(state.etco2 + (etco2_target - state.etco2) * 0.18 + rng.gauss(0.0, 0.08), 2.5, 7.0)
    state.fio2 = clamp(state.fio2 + (fio2_target - state.fio2) * 0.10 + rng.gauss(0.0, 0.6), 21.0, 60.0)

    map_target = 78.0 + (state.heart_rate - 75.0) * 0.22 + math.sin(state.drift_phase * 0.31) * 4.0
    pulse_pressure_target = 42.0 + math.sin(state.drift_phase * 0.5 + 1.1) * 7.0
    diastolic_target = map_target - pulse_pressure_target / 3.0
    systolic_target = diastolic_target + pulse_pressure_target

    state.diastolic_bp = clamp(
        state.diastolic_bp + (diastolic_target - state.diastolic_bp) * 0.16 + rng.gauss(0.0, 1.2),
        45.0,
        110.0,
    )
    state.systolic_bp = clamp(
        state.systolic_bp + (systolic_target - state.systolic_bp) * 0.16 + rng.gauss(0.0, 1.8),
        state.diastolic_bp + 18.0,
        190.0,
    )
    state.pleth_level = clamp(
        10.0 + (state.spo2 - 90.0) * 1.3 + math.sin(state.wave_phase) * 6.0 + rng.gauss(0.0, 1.1),
        0.0,
        100.0,
    )


def generic_signal_value(signal: SignalInfo, state: BedState, rng: random.Random, now_ts: float) -> float:
    min_v, max_v = safe_range(signal.min_value, signal.max_value)
    span = max_v - min_v
    center = min_v + span * 0.55
    wobble = math.sin(now_ts * 0.15 + state.bed_id * 0.7 + signal.signal_id * 0.13) * span * 0.08
    noise = rng.gauss(0.0, max(span * 0.015, 0.05))
    return clamp(center + wobble + noise, min_v, max_v)


def generate_signal_value(signal: SignalInfo, state: BedState, rng: random.Random, now_ts: float) -> float:
    key = signal.inferred_key

    if key == "spo2":
        value = state.spo2
    elif key == "pulse":
        value = state.heart_rate
    elif key in {"breathing", "spont_rr"}:
        value = state.breathing
    elif key == "temperature":
        value = state.temperature
    elif key == "skin_temp":
        value = state.temperature - 0.8 + rng.gauss(0.0, 0.08)
    elif key == "systolic_bp":
        value = state.systolic_bp
    elif key == "diastolic_bp":
        value = state.diastolic_bp
    elif key == "mean_bp":
        value = state.diastolic_bp + (state.systolic_bp - state.diastolic_bp) / 3.0
    elif key == "nibp_systolic":
        value = state.systolic_bp + rng.gauss(0.0, 1.5)
    elif key == "nibp_diastolic":
        value = state.diastolic_bp + rng.gauss(0.0, 1.2)
    elif key == "nibp_mean":
        value = state.diastolic_bp + (state.systolic_bp - state.diastolic_bp) / 3.0 + rng.gauss(0.0, 1.0)
    elif key == "ibp_systolic":
        value = state.systolic_bp + rng.gauss(0.0, 0.8)
    elif key == "ibp_diastolic":
        value = state.diastolic_bp + rng.gauss(0.0, 0.6)
    elif key == "ibp_mean":
        value = state.diastolic_bp + (state.systolic_bp - state.diastolic_bp) / 3.0 + rng.gauss(0.0, 0.7)
    elif key == "co2":
        value = state.etco2 + rng.gauss(0.0, 0.12)
    elif key == "etco2":
        value = state.etco2
    elif key == "fio2":
        value = state.fio2
    elif key == "eto2":
        value = clamp(state.fio2 - 4.0 + rng.gauss(0.0, 1.2), 15.0, 100.0)
    elif key == "plethysmogram":
        value = state.pleth_level
    else:
        value = generic_signal_value(signal, state, rng, now_ts)

    min_v, max_v = safe_range(signal.min_value, signal.max_value)
    return round(clamp(float(value), min_v, max_v), 2)


def insert_rows(conn, rows: Iterable[tuple[int, int, datetime, float]]) -> None:
    rows = list(rows)
    if not rows:
        return
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO signals (
                bed_id,
                signal_id,
                signals_date_time,
                signals_value
            )
            VALUES %s
            """,
            rows,
            page_size=1000,
        )
    conn.commit()


def main() -> int:
    args = build_parser().parse_args()
    config_path = resolve_config_path(args.config)
    db_config = get_db_config(config_path)

    if args.interval <= 0:
        print("interval должен быть > 0", file=sys.stderr)
        return 2

    with psycopg2.connect(**db_config) as conn:
        beds = load_beds(conn, args.bed_id, args.all_beds)
        signals = load_signals(conn, include_inactive=not args.active_only, limit_signals=args.limit_signals)

        print(f"config.ini: {config_path}")
        print(f"Подключено к {db_config['host']}:{db_config['port']}/{db_config['database']}")
        print(f"Коек: {len(beds)} -> {beds}")
        print(f"Сигналов: {len(signals)}")
        print(f"Шаг планировщика: {args.interval:.2f} c")
        cadence_summary: dict[float, int] = {}
        for signal in signals:
            cadence_summary[signal.period_seconds] = cadence_summary.get(signal.period_seconds, 0) + 1
        cadence_parts = [f"{period:g}s={count}" for period, count in sorted(cadence_summary.items(), key=lambda item: item[0])]
        print(f"Частоты: {', '.join(cadence_parts)}")
        if args.duration > 0:
            print(f"Длительность: {args.duration:.1f} c")
        else:
            print("Длительность: бесконечно (Ctrl+C для остановки)")

        states = {bed_id: create_bed_state(bed_id, args.seed) for bed_id in beds}
        rng = random.Random(args.seed ^ 0x5A5A5A5A)
        started = time.monotonic()
        last_step_mono = started
        cycle = 0
        next_due: dict[tuple[int, int], float] = {}
        for bed_id in beds:
            for signal in signals:
                next_due[(bed_id, signal.signal_id)] = started

        try:
            while True:
                now_mono = time.monotonic()
                dt = max(0.001, now_mono - last_step_mono)
                last_step_mono = now_mono
                now = datetime.now()
                now_ts = time.time()
                rows: list[tuple[int, int, datetime, float]] = []

                for bed_id in beds:
                    state = states[bed_id]
                    update_bed_state(state, dt, rng)
                    for signal in signals:
                        due_key = (bed_id, signal.signal_id)
                        due_at = next_due.get(due_key, now_mono)
                        if now_mono + 1e-9 < due_at:
                            continue
                        value = generate_signal_value(signal, state, rng, now_ts)
                        rows.append((bed_id, signal.signal_id, now, value))
                        next_due[due_key] = max(due_at, now_mono) + signal.period_seconds

                insert_rows(conn, rows)
                cycle += 1

                if args.verbose_every > 0 and (cycle == 1 or cycle % args.verbose_every == 0):
                    sample = states[beds[0]]
                    print(
                        f"[{now:%H:%M:%S}] cycle={cycle} rows={len(rows)} "
                        f"bed={sample.bed_id} HR={sample.heart_rate:.1f} "
                        f"SpO2={sample.spo2:.1f} RR={sample.breathing:.1f} "
                        f"BP={sample.systolic_bp:.0f}/{sample.diastolic_bp:.0f} "
                        f"T={sample.temperature:.1f}"
                    )

                if args.duration > 0 and (time.monotonic() - started) >= args.duration:
                    break
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nОстановлено пользователем.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
