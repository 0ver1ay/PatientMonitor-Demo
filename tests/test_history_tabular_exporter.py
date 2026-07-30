import csv
import tempfile
import unittest
from pathlib import Path

from utils.history_tabular_exporter import (
    _aggregate_rows_by_period,
    export_image_frames,
    export_history_csv,
    export_history_xls_spreadsheetml,
    select_image_frames_for_export,
)


class HistoryTabularExporterTests(unittest.TestCase):
    def test_aggregate_rows_by_period_computes_mean_per_bucket(self):
        rows = [
            {"ts": "2026-01-01 00:00:10", "param_key": 1, "name": "A", "unit": "u", "value": "10"},
            {"ts": "2026-01-01 00:00:40", "param_key": 1, "name": "A", "unit": "u", "value": "20"},
            {"ts": "2026-01-01 00:01:10", "param_key": 1, "name": "A", "unit": "u", "value": "40"},
            {"ts": "2026-01-01 00:00:20", "param_key": 2, "name": "B", "unit": "bpm", "value": "5"},
        ]

        aggregated = _aggregate_rows_by_period(rows, 60)

        self.assertEqual(
            aggregated,
            [
                {"ts": "2026-01-01 00:00:00", "param_key": "1", "name": "A", "unit": "u", "value": "15"},
                {"ts": "2026-01-01 00:00:00", "param_key": "2", "name": "B", "unit": "bpm", "value": "5"},
                {"ts": "2026-01-01 00:01:00", "param_key": "1", "name": "A", "unit": "u", "value": "40"},
            ],
        )

    def test_export_history_csv_without_aggregation_preserves_raw_timestamps(self):
        rows = [
            {"ts": "2026-01-01 00:00:10", "param_key": 1, "name": "A", "unit": "u", "value": "10"},
            {"ts": "2026-01-01 00:00:40", "param_key": 1, "name": "A", "unit": "u", "value": "20"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            out_path = export_history_csv(rows, Path(tmp), "raw_export", aggregation_seconds=None)
            with out_path.open("r", encoding="utf-8", newline="") as fh:
                data = list(csv.reader(fh))

        self.assertEqual(data[0], ["ts", "A (u)"])
        self.assertEqual(data[1], ["2026-01-01 00:00:10", "10"])
        self.assertEqual(data[2], ["2026-01-01 00:00:40", "20"])

    def test_export_history_csv_with_aggregation_writes_bucketed_rows(self):
        rows = [
            {"ts": "2026-01-01 00:00:10", "param_key": 1, "name": "A", "unit": "u", "value": "10"},
            {"ts": "2026-01-01 00:00:40", "param_key": 1, "name": "A", "unit": "u", "value": "20"},
            {"ts": "2026-01-01 00:01:20", "param_key": 1, "name": "A", "unit": "u", "value": "50"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            out_path = export_history_csv(rows, Path(tmp), "agg_export", aggregation_seconds=60)
            with out_path.open("r", encoding="utf-8", newline="") as fh:
                data = list(csv.reader(fh))

        self.assertEqual(data[0], ["ts", "A (u)"])
        self.assertEqual(data[1], ["2026-01-01 00:00:00", "15"])
        self.assertEqual(data[2], ["2026-01-01 00:01:00", "50"])
        self.assertEqual(len(data), 3)

    def test_export_history_xls_with_aggregation_uses_bucketed_timestamp(self):
        rows = [
            {"ts": "2026-01-01 00:00:10", "param_key": 1, "name": "A", "unit": "u", "value": "10"},
            {"ts": "2026-01-01 00:00:40", "param_key": 1, "name": "A", "unit": "u", "value": "20"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            out_path = export_history_xls_spreadsheetml(rows, Path(tmp), "agg_export", aggregation_seconds=60)
            xml = out_path.read_text(encoding="utf-8")

        self.assertIn("2026-01-01 00:00:00", xml)
        self.assertIn(">15<", xml)
        self.assertNotIn("2026-01-01 00:00:10", xml)

    def test_select_image_frames_for_export_keeps_last_frame_per_bucket(self):
        frames = [
            {"ts": "2026-01-01 00:00:05", "image_bytes": b"\xff\xd8\xff\x00one"},
            {"ts": "2026-01-01 00:00:50", "image_bytes": b"\xff\xd8\xff\x00two"},
            {"ts": "2026-01-01 00:01:05", "image_bytes": b"\xff\xd8\xff\x00three"},
        ]

        selected = select_image_frames_for_export(frames, aggregation_seconds=60)

        self.assertEqual(len(selected), 2)
        self.assertEqual(selected[0]["ts"].isoformat(sep=" "), "2026-01-01 00:00:50")
        self.assertEqual(selected[0]["image_bytes"], b"\xff\xd8\xff\x00two")
        self.assertEqual(selected[1]["ts"].isoformat(sep=" "), "2026-01-01 00:01:05")

    def test_export_image_frames_creates_folder_and_writes_selected_files(self):
        frames = [
            {"ts": "2026-01-01 00:00:05", "image_bytes": b"\xff\xd8\xff\x00one"},
            {"ts": "2026-01-01 00:00:50", "image_bytes": b"\xff\xd8\xff\x00two"},
            {"ts": "2026-01-01 00:01:05", "image_bytes": b"\x89PNG\r\n\x1a\nthree"},
        ]

        with tempfile.TemporaryDirectory() as tmp:
            images_dir, count = export_image_frames(
                frames,
                Path(tmp),
                "report_images",
                aggregation_seconds=60,
            )
            written_files = sorted(p.name for p in images_dir.iterdir())

        self.assertEqual(count, 2)
        self.assertEqual(written_files, ["0001_20260101_000050.jpg", "0002_20260101_000105.png"])


if __name__ == "__main__":
    unittest.main()
