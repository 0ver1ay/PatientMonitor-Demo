"""
Экспорт анестезиологических параметров в XML по сессиям за выбранный период.

Сессии определяются так:
- Если доступна БД: по таблице worklist (по совпадению room_id+block_id кровати) и пересечению по времени.
- Если worklist не дал сессий: автоматически разбиваем по "разрывам" в данных.

Выход: exports/anesthesia_bed{bed_id}_{start}_{end}.xml
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

from utils.database_source import DatabaseDataSource


@dataclass(frozen=True)
class SessionWindow:
    session_id: str
    begin_dt: datetime
    end_dt: datetime
    meta: Dict


def _safe_filename(s: str) -> str:
    return (
        s.replace(":", "")
        .replace(" ", "_")
        .replace("/", "-")
        .replace("\\", "-")
        .replace(".", "")
    )


def _indent_xml(elem: ET.Element):
    # Python 3.9+ supports ET.indent
    try:
        ET.indent(elem, space="  ")
    except Exception:
        pass


def _split_into_sessions_by_gaps(
    points: List[Tuple[datetime, float]],
    gap: timedelta = timedelta(minutes=30),
) -> List[Tuple[datetime, datetime]]:
    if not points:
        return []
    pts = sorted(points, key=lambda x: x[0])
    sessions: List[Tuple[datetime, datetime]] = []
    cur_start = pts[0][0]
    cur_end = pts[0][0]
    for ts, _ in pts[1:]:
        if ts - cur_end > gap:
            sessions.append((cur_start, cur_end))
            cur_start = ts
            cur_end = ts
        else:
            cur_end = ts
    sessions.append((cur_start, cur_end))
    return sessions


def export_anesthesia_parameters_xml(
    db: DatabaseDataSource,
    bed_id: int,
    start_dt: datetime,
    end_dt: datetime,
    export_dir: Optional[Path] = None,
) -> Path:
    export_dir = export_dir or (Path(__file__).parent.parent / "exports")
    export_dir.mkdir(parents=True, exist_ok=True)

    bed_info = db.get_bed_info(bed_id) or {}
    bed_name = bed_info.get("bed_name") or f"bed_{bed_id}"

    # Определяем интересующие сигналы
    params = db.get_anesthesia_signal_params()
    signal_ids = [int(p["signal_id"]) for p in params if p.get("signal_id") is not None]
    signal_meta = {
        int(p["signal_id"]): p
        for p in params
        if p.get("signal_id") is not None
    }

    # Сессии из worklist
    sessions: List[SessionWindow] = []
    wl = db.get_worklist_sessions_for_bed(bed_id, start_dt, end_dt)
    for row in wl:
        s_begin = max(start_dt, row["begin_dt"])
        s_end = min(end_dt, row["end_dt"])
        if s_end <= s_begin:
            continue
        sessions.append(
            SessionWindow(
                session_id=str(row.get("session_id") or "worklist"),
                begin_dt=s_begin,
                end_dt=s_end,
                meta=row,
            )
        )

    # Если worklist пуст — делаем авто-сессии по разрывам (по любому сигналу)
    if not sessions:
        raw = db.get_signal_values_between(bed_id, signal_ids, start_dt, end_dt)
        all_points = [(r["ts"], r["value"]) for r in raw]
        ranges = _split_into_sessions_by_gaps(all_points)
        if not ranges:
            # вообще нет данных — одна "пустая" сессия
            ranges = [(start_dt, end_dt)]
        for i, (a, b) in enumerate(ranges, start=1):
            sessions.append(
                SessionWindow(
                    session_id=f"AUTO_{i}",
                    begin_dt=a,
                    end_dt=b,
                    meta={"source": "auto_gap_split"},
                )
            )

    root = ET.Element(
        "AnesthesiaExport",
        {
            "bed_id": str(bed_id),
            "bed_name": str(bed_name),
            "period_start": start_dt.isoformat(sep=" "),
            "period_end": end_dt.isoformat(sep=" "),
            "generated_at": datetime.now().isoformat(sep=" "),
        },
    )

    bed_el = ET.SubElement(root, "Bed")
    for k in ["bed_id", "bed_name", "bed_numb", "room_id", "block_id", "status_id", "patient_id"]:
        if k in bed_info and bed_info[k] is not None:
            bed_el.set(k, str(bed_info[k]))

    sessions_el = ET.SubElement(root, "Sessions")

    for sess in sessions:
        sess_el = ET.SubElement(
            sessions_el,
            "Session",
            {
                "id": sess.session_id,
                "start": sess.begin_dt.isoformat(sep=" "),
                "end": sess.end_dt.isoformat(sep=" "),
            },
        )

        # meta (минимально)
        meta_el = ET.SubElement(sess_el, "Meta")
        for key in ["patient_id", "doctor_id", "room_id", "block_id", "descr"]:
            val = sess.meta.get(key) if isinstance(sess.meta, dict) else None
            if val is not None and val != "":
                ET.SubElement(meta_el, "Field", {"name": str(key), "value": str(val)})

        # Данные
        rows = db.get_signal_values_between(bed_id, signal_ids, sess.begin_dt, sess.end_dt)
        by_signal: Dict[int, List[Dict]] = {}
        for r in rows:
            sid = int(r["signal_id"])
            by_signal.setdefault(sid, []).append(r)

        signals_el = ET.SubElement(sess_el, "Signals")
        for sid in sorted(by_signal.keys()):
            meta = signal_meta.get(sid, {})
            name = meta.get("signal_descr_rus") or meta.get("signal_name") or f"signal_{sid}"
            unit = meta.get("signal_unit") or ""
            group_name = meta.get("group_name") or ""
            group_descr = meta.get("group_descr_rus") or ""

            sig_el = ET.SubElement(
                signals_el,
                "Signal",
                {
                    "signal_id": str(sid),
                    "name": str(name),
                    "unit": str(unit),
                },
            )
            if group_name:
                sig_el.set("group_name", str(group_name))
            if group_descr:
                sig_el.set("group_descr_rus", str(group_descr))

            vals = [p["value"] for p in by_signal[sid] if p.get("value") is not None]
            if vals:
                sig_el.set("count", str(len(vals)))
                sig_el.set("min", f"{min(vals):.6g}")
                sig_el.set("max", f"{max(vals):.6g}")
                sig_el.set("avg", f"{(sum(vals) / len(vals)):.6g}")
            else:
                sig_el.set("count", "0")

            points_el = ET.SubElement(sig_el, "Points")
            for p in by_signal[sid]:
                ET.SubElement(
                    points_el,
                    "Point",
                    {
                        "ts": p["ts"].isoformat(sep=" "),
                        "value": f"{p['value']:.6g}",
                    },
                )

    _indent_xml(root)

    fname = f"anesthesia_bed{bed_id}_{start_dt.strftime('%Y%m%d_%H%M')}_{end_dt.strftime('%Y%m%d_%H%M')}.xml"
    out_path = export_dir / _safe_filename(fname)

    tree = ET.ElementTree(root)
    tree.write(out_path, encoding="utf-8", xml_declaration=True)
    return out_path

