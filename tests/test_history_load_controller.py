import threading
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from utils.history_load_controller import (
    HistoryLoadController,
    HistoryLoadKey,
    split_signal_rows,
)


class HistoryLoadControllerTests(unittest.TestCase):
    def test_split_signal_rows_groups_by_signal_id(self):
        start = datetime(2026, 1, 1, 12, 0, 0)
        rows = [
            {"signal_id": 76, "value": 98.0, "ts": start},
            {"signal_id": 77, "value": 70.0, "ts": start + timedelta(seconds=1)},
            {"signal_id": 76, "value": 97.5, "ts": start + timedelta(seconds=2)},
            {"signal_id": "bad", "value": 1, "ts": start},
        ]
        series = split_signal_rows(rows)
        self.assertEqual(list(series[76]), [(98.0, start), (97.5, start + timedelta(seconds=2))])
        self.assertEqual(list(series[77]), [(70.0, start + timedelta(seconds=1))])

    def test_stale_generation_is_discarded(self):
        controller = HistoryLoadController()
        gen1, cancel1 = controller.begin_request()
        gen2, cancel2 = controller.begin_request()
        self.assertTrue(cancel1.is_set())
        self.assertFalse(cancel2.is_set())
        self.assertFalse(controller.is_current(gen1))
        self.assertTrue(controller.is_current(gen2))

    def test_cancel_all_bumps_generation(self):
        controller = HistoryLoadController()
        gen, cancel = controller.begin_request()
        controller.cancel_all()
        self.assertTrue(cancel.is_set())
        self.assertFalse(controller.is_current(gen))

    def test_retry_transient_then_success(self):
        controller = HistoryLoadController()
        gen, cancel = controller.begin_request()
        calls = {"n": 0}

        def fetch():
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("temporary")
            return "ok"

        result = controller.fetch_with_retry(
            fetch,
            generation=gen,
            cancel_event=cancel,
            attempts=(0.01, 0.01, 0.01),
        )
        self.assertEqual(result, "ok")
        self.assertEqual(calls["n"], 3)

    def test_retry_aborted_on_cancel(self):
        controller = HistoryLoadController()
        gen, cancel = controller.begin_request()
        cancel.set()

        with self.assertRaises(RuntimeError):
            controller.fetch_with_retry(
                lambda: (_ for _ in ()).throw(RuntimeError("fail")),
                generation=gen,
                cancel_event=cancel,
                attempts=(0.05, 0.05),
            )

    def test_load_key_includes_sorted_unique_signals(self):
        start = datetime(2026, 1, 1, 0, 0, 0)
        end = start + timedelta(hours=1)
        key = HistoryLoadKey.from_parts(5, start, end, [77, 76, 76, 50])
        self.assertEqual(key.signal_ids, (50, 76, 77))
        self.assertEqual(key.bed_id, 5)

    def test_background_worker_respects_generation(self):
        controller = HistoryLoadController()
        results = []
        ready = threading.Event()

        def slow_job(generation, cancel_event):
            time.sleep(0.05)
            if cancel_event.is_set() or not controller.is_current(generation):
                return
            results.append(generation)
            ready.set()

        gen1, cancel1 = controller.begin_request()
        controller.run_in_background(slow_job, gen1, cancel1)
        gen2, cancel2 = controller.begin_request()
        controller.run_in_background(slow_job, gen2, cancel2)
        ready.wait(1.0)
        controller.join_workers(1.0)
        self.assertEqual(results, [gen2])


if __name__ == "__main__":
    unittest.main()
