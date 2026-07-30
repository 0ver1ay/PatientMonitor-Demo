from __future__ import annotations

import argparse
import configparser
import struct
import zlib
from datetime import datetime, timedelta
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values


DEFAULT_BED_ID = 10
DEFAULT_HOURS_BEFORE = 2
DEFAULT_HOURS_AFTER = 2
IMAGE_WIDTH = 64
IMAGE_HEIGHT = 48


def load_db_config(config_path: Path) -> dict:
    parser = configparser.ConfigParser()
    if not parser.read(config_path, encoding="utf-8"):
        raise RuntimeError(f"Не удалось прочитать config: {config_path}")
    db = parser["DATABASE"]
    return {
        "host": db.get("host", "localhost"),
        "port": db.getint("port", 6000),
        "dbname": db.get("database", "med"),
        "user": db.get("user", "postgres"),
        "password": db.get("password", ""),
    }


def png_chunk(tag: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


def build_png(frame_index: int, width: int = IMAGE_WIDTH, height: int = IMAGE_HEIGHT) -> bytes:
    bar_x = frame_index % width
    band_y = (frame_index // 2) % height
    rows: list[bytes] = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            red = (x * 9 + frame_index * 5) % 256
            green = (y * 11 + frame_index * 3) % 256
            blue = ((x + y) * 7 + frame_index * 2) % 256

            if abs(x - bar_x) <= 1:
                red, green, blue = 255, 255, 255
            elif abs(y - band_y) <= 1:
                red, green, blue = 255, 180, 40
            elif (x + frame_index) % 13 == 0:
                red, green, blue = 40, 220, 255

            row.extend((red, green, blue))
        rows.append(bytes(row))

    raw = b"".join(rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(raw, level=6)
    return b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", ihdr) + png_chunk(b"IDAT", idat) + png_chunk(b"IEND", b"")


def iter_timestamps(start_dt: datetime, end_dt: datetime):
    current = start_dt
    step = timedelta(seconds=1)
    while current <= end_dt:
        yield current
        current += step


def build_rows(bed_id: int, start_dt: datetime, end_dt: datetime) -> list[tuple[int, datetime, bytes]]:
    rows: list[tuple[int, datetime, bytes]] = []
    for frame_index, ts in enumerate(iter_timestamps(start_dt, end_dt)):
        rows.append((bed_id, ts, psycopg2.Binary(build_png(frame_index))))
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Заполнить таблицу images тестовыми кадрами раз в секунду.")
    parser.add_argument("--bed-id", type=int, default=DEFAULT_BED_ID, help="Койка для заполнения.")
    parser.add_argument("--hours-before", type=int, default=DEFAULT_HOURS_BEFORE, help="Сколько часов назад заполнить.")
    parser.add_argument("--hours-after", type=int, default=DEFAULT_HOURS_AFTER, help="Сколько часов вперед заполнить.")
    parser.add_argument("--config", type=str, default="config.ini", help="Путь к config.ini.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    now = datetime.now().replace(microsecond=0)
    start_dt = now - timedelta(hours=int(args.hours_before))
    end_dt = now + timedelta(hours=int(args.hours_after))
    config_path = Path(args.config)
    db_config = load_db_config(config_path)
    rows = build_rows(int(args.bed_id), start_dt, end_dt)

    with psycopg2.connect(**db_config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM images
                WHERE bed_id = %s
                  AND images_date_time >= %s
                  AND images_date_time <= %s
                """,
                (int(args.bed_id), start_dt, end_dt),
            )
            execute_values(
                cur,
                """
                INSERT INTO images (
                    bed_id,
                    images_date_time,
                    image
                )
                VALUES %s
                """,
                rows,
                page_size=500,
            )
        conn.commit()

    print(f"bed_id={int(args.bed_id)}")
    print(f"window={start_dt.isoformat(sep=' ')} .. {end_dt.isoformat(sep=' ')}")
    print(f"frames_inserted={len(rows)}")


if __name__ == "__main__":
    main()
