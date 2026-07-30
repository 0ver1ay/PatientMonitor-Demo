from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

import psycopg2
from psycopg2.extras import execute_values

from utils.signal_registry import DEFAULT_SIGNAL_IDS


DB_CONFIG = {
    "host": "localhost",
    "port": 6000,
    "dbname": "med",
    "user": "postgres",
    "password": "postgres",
}

STUDY_NUMB = "DMO260326DENS"
BED_ID = 10
PATIENT_ID = 13
DOCTOR_ID = 4
DATE_BEG = datetime(2026, 3, 26, 10, 0, 0)
DATE_END = datetime(2026, 3, 26, 14, 0, 0)
STUDY_DESCR = "Dense demo study with mixed signal frequencies"


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def iter_timepoints(start: datetime, end: datetime, step_seconds: int):
    ts = start
    step = timedelta(seconds=step_seconds)
    while ts <= end:
        yield ts
        ts += step


def mild_noise(rng: random.Random, scale: float) -> float:
    return rng.uniform(-scale, scale)


def generate_dense_rows(start: datetime, end: datetime) -> list[tuple[int, int, datetime, float]]:
    rng = random.Random(260326)
    rows: list[tuple[int, int, datetime, float]] = []

    ids = DEFAULT_SIGNAL_IDS

    for ts in iter_timepoints(start, end, 2):
        t = (ts - start).total_seconds()
        pulse = 78 + 5.0 * math.sin(t / 70.0) + 2.5 * math.sin(t / 17.0) + mild_noise(rng, 1.2)
        if 55 * 60 <= t <= 68 * 60:
            pulse += 10.0 * math.sin((t - 55 * 60) / 18.0)
        rows.append((BED_ID, ids["pulse"], ts, round(clamp(pulse, 58, 125), 2)))

    for ts in iter_timepoints(start, end, 3):
        t = (ts - start).total_seconds()
        rr = 15.5 + 1.8 * math.sin(t / 95.0) + 0.9 * math.sin(t / 22.0) + mild_noise(rng, 0.5)
        if 130 * 60 <= t <= 160 * 60:
            rr += 3.0
        rows.append((BED_ID, ids["breathing"], ts, round(clamp(rr, 10, 30), 2)))

    for ts in iter_timepoints(start, end, 4):
        t = (ts - start).total_seconds()
        spo2 = 98.2 + 0.45 * math.sin(t / 110.0) + mild_noise(rng, 0.18)
        if 70 * 60 <= t <= 80 * 60:
            spo2 -= 2.4 * math.exp(-((t - 75 * 60) ** 2) / (2 * (3.5 * 60) ** 2))
        if 155 * 60 <= t <= 168 * 60:
            spo2 -= 1.2
        rows.append((BED_ID, ids["spo2"], ts, round(clamp(spo2, 89, 100), 2)))

    for ts in iter_timepoints(start, end, 2):
        t = (ts - start).total_seconds()
        etco2 = 4.9 + 0.35 * math.sin(t / 33.0) + 0.18 * math.sin(t / 7.0) + mild_noise(rng, 0.06)
        if 132 * 60 <= t <= 160 * 60:
            etco2 += 0.6
        rows.append((BED_ID, ids["etco2"], ts, round(clamp(etco2, 3.2, 7.0), 3)))

    for ts in iter_timepoints(start, end, 1):
        t = (ts - start).total_seconds()
        pleth = 56 + 28 * (0.5 + 0.5 * math.sin(t / 1.7)) + 5 * math.sin(t / 37.0) + mild_noise(rng, 1.6)
        rows.append((BED_ID, ids["plethysmogram"], ts, round(clamp(pleth, 0, 100), 2)))

    for ts in iter_timepoints(start, end, 15):
        t = (ts - start).total_seconds()
        fio2 = 35.0 + mild_noise(rng, 0.35)
        if t >= 90 * 60:
            fio2 = 40.0 + mild_noise(rng, 0.35)
        if t >= 165 * 60:
            fio2 = 32.0 + mild_noise(rng, 0.3)
        rows.append((BED_ID, ids["fio2"], ts, round(clamp(fio2, 21, 60), 2)))

    for ts in iter_timepoints(start, end, 15):
        t = (ts - start).total_seconds()
        eto2 = 28.0 + 1.0 * math.sin(t / 210.0) + mild_noise(rng, 0.25)
        if t >= 90 * 60:
            eto2 += 3.0
        rows.append((BED_ID, ids["eto2"], ts, round(clamp(eto2, 18, 50), 2)))

    for ts in iter_timepoints(start, end, 30):
        t = (ts - start).total_seconds()
        skin = 33.8 + 0.25 * math.sin(t / 1200.0) + 0.12 * math.sin(t / 200.0) + mild_noise(rng, 0.05)
        rows.append((BED_ID, ids["skin_temp"], ts, round(clamp(skin, 32.5, 35.5), 2)))

    for ts in iter_timepoints(start, end, 8 * 60):
        t = (ts - start).total_seconds()
        sys = 118 + 6 * math.sin(t / 900.0) + mild_noise(rng, 2.5)
        dia = 72 + 4 * math.sin(t / 980.0) + mild_noise(rng, 2.0)
        mean = dia + (sys - dia) / 3.0
        rows.append((BED_ID, ids["nibp_systolic"], ts, round(clamp(sys, 90, 150), 1)))
        rows.append((BED_ID, ids["nibp_diastolic"], ts, round(clamp(dia, 50, 95), 1)))
        rows.append((BED_ID, ids["nibp_mean"], ts, round(clamp(mean, 65, 115), 1)))

    rows.sort(key=lambda item: (item[2], item[1]))
    return rows


def ensure_study(cur) -> int:
    cur.execute(
        """
        SELECT study_id
        FROM study
        WHERE study_numb = %s
        """,
        (STUDY_NUMB,),
    )
    row = cur.fetchone()
    if row:
        study_id = int(row[0])
        cur.execute(
            """
            UPDATE study
            SET patient_id = %s,
                doctor_id = %s,
                bed_id = %s,
                date_beg = %s,
                date_end = %s,
                time_beg = %s,
                time_end = %s,
                study_descr = %s
            WHERE study_id = %s
            """,
            (PATIENT_ID, DOCTOR_ID, BED_ID, DATE_BEG.date(), DATE_END.date(), DATE_BEG, DATE_END, STUDY_DESCR, study_id),
        )
        return study_id

    cur.execute(
        """
        INSERT INTO study (
            study_numb,
            patient_id,
            doctor_id,
            bed_id,
            date_beg,
            date_end,
            time_beg,
            time_end,
            study_descr,
            study_text
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING study_id
        """,
        (
            STUDY_NUMB,
            PATIENT_ID,
            DOCTOR_ID,
            BED_ID,
            DATE_BEG.date(),
            DATE_END.date(),
            DATE_BEG,
            DATE_END,
            STUDY_DESCR,
            "Generated by create_dense_demo_study.py",
        ),
    )
    return int(cur.fetchone()[0])


def replace_signal_rows(cur, rows: list[tuple[int, int, datetime, float]]) -> None:
    signal_ids = sorted({row[1] for row in rows})
    cur.execute(
        """
        DELETE FROM signals
        WHERE bed_id = %s
          AND signal_id = ANY(%s)
          AND signals_date_time >= %s
          AND signals_date_time <= %s
        """,
        (BED_ID, signal_ids, DATE_BEG, DATE_END),
    )
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
        page_size=2000,
    )


def print_summary(rows: list[tuple[int, int, datetime, float]]) -> None:
    counts: dict[int, int] = {}
    for _bed_id, signal_id, _ts, _value in rows:
        counts[signal_id] = counts.get(signal_id, 0) + 1
    print(f"Study: {STUDY_NUMB}")
    print(f"Window: {DATE_BEG} .. {DATE_END}")
    print(f"Inserted rows: {len(rows)}")
    for signal_id, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"signal_id={signal_id}: {count}")


def main() -> None:
    rows = generate_dense_rows(DATE_BEG, DATE_END)
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            study_id = ensure_study(cur)
            replace_signal_rows(cur, rows)
        conn.commit()
    print(f"study_id={study_id}")
    print_summary(rows)


if __name__ == "__main__":
    main()
