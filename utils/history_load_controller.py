from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import threading
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class HistoryLoadKey:
    bed_id: int
    start: datetime
    end: datetime
    signal_ids: Tuple[int, ...]

    @classmethod
    def from_parts(
        cls,
        bed_id: int,
        start: datetime,
        end: datetime,
        signal_ids: Iterable[int],
    ) -> "HistoryLoadKey":
        unique = tuple(sorted({int(sid) for sid in signal_ids}))
        return cls(bed_id=int(bed_id), start=start, end=end, signal_ids=unique)


def split_signal_rows(
    rows: Sequence[dict],
) -> Dict[int, List[Tuple[float, datetime]]]:
    """Разложить пакетный ответ get_signal_values_between по signal_id."""
    out: Dict[int, List[Tuple[float, datetime]]] = {}
    for row in rows or ():
        try:
            sid = int(row["signal_id"])
            value = float(row["value"])
            ts = row["ts"]
        except Exception:
            continue
        if ts is None:
            continue
        if getattr(ts, "tzinfo", None) is not None:
            ts = ts.replace(tzinfo=None)
        out.setdefault(sid, []).append((value, ts))
    return out


class HistoryLoadController:
    """Фоновая загрузка истории с generation token и отменой устаревших запросов."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._generation = 0
        self._cancel_event = threading.Event()
        self._workers: List[threading.Thread] = []

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    def begin_request(self) -> Tuple[int, threading.Event]:
        """Отменить предыдущую загрузку и вернуть (generation, cancel_event)."""
        with self._lock:
            self._generation += 1
            self._cancel_event.set()
            self._cancel_event = threading.Event()
            return self._generation, self._cancel_event

    def is_current(self, generation: int) -> bool:
        with self._lock:
            return generation == self._generation

    def cancel_all(self) -> None:
        with self._lock:
            self._generation += 1
            self._cancel_event.set()

    def run_in_background(self, target: Callable[..., None], *args, **kwargs) -> threading.Thread:
        thread = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
        with self._lock:
            self._workers = [t for t in self._workers if t.is_alive()]
            self._workers.append(thread)
        thread.start()
        return thread

    def join_workers(self, timeout: float = 2.0) -> None:
        with self._lock:
            workers = list(self._workers)
        deadline = timeout
        for thread in workers:
            if not thread.is_alive():
                continue
            started = datetime.now()
            thread.join(timeout=max(0.05, deadline))
            elapsed = (datetime.now() - started).total_seconds()
            deadline = max(0.0, deadline - elapsed)

    def fetch_with_retry(
        self,
        fetch_fn: Callable[[], object],
        *,
        generation: int,
        cancel_event: threading.Event,
        attempts: Sequence[float] = (0.5, 1.0, 2.0),
    ) -> object:
        last_error: Optional[Exception] = None
        for index, delay in enumerate(attempts):
            if cancel_event.is_set() or not self.is_current(generation):
                raise RuntimeError("history load cancelled")
            try:
                return fetch_fn()
            except Exception as exc:
                last_error = exc
                if index >= len(attempts) - 1:
                    break
                if cancel_event.wait(delay):
                    raise RuntimeError("history load cancelled") from exc
        if last_error is not None:
            raise last_error
        raise RuntimeError("history load failed")
