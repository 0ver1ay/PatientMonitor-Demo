"""
Экспорт истории сигналов в CSV/XLS/PDF.

Формат экспорта: "wide" (широкая таблица):
- 1 строка = timestamp
- отдельная колонка под каждый параметр (по имени/единице)

В файлы НЕ пишем slot/signal_id (они могут использоваться только для внутренней уникальности).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
import csv


def _safe_filename(s: str) -> str:
    return (
        s.replace(":", "")
        .replace(" ", "_")
        .replace("/", "-")
        .replace("\\", "-")
    )

def _make_unique_headers(base_headers: List[str]) -> List[str]:
    """Дедупликация заголовков (если есть одинаковые имена параметров)."""
    seen: Dict[str, int] = {}
    out: List[str] = []
    for h in base_headers:
        if h not in seen:
            seen[h] = 1
            out.append(h)
            continue
        seen[h] += 1
        out.append(f"{h} ({seen[h]})")
    return out


def _pivot_wide(
    rows: List[Dict],
) -> Tuple[List[str], List[List[str]]]:
    """
    Превращает список точек вида:
      {ts, param_key, name, unit, value}
    в широкую таблицу:
      headers = ["ts", "<param1>", "<param2>", ...]
      data_rows = [[ts, v1, v2, ...], ...]
    """
    # Собираем параметры (в порядке первого появления param_key)
    param_order: List[str] = []
    param_label_by_key: Dict[str, str] = {}

    # Таблица: ts -> key -> value
    by_ts: Dict[str, Dict[str, str]] = {}

    for r in rows:
        ts = "" if r.get("ts") is None else str(r.get("ts"))
        key = r.get("param_key")
        if key is None:
            continue
        key_s = str(key)
        name = "" if r.get("name") is None else str(r.get("name"))
        unit = "" if r.get("unit") is None else str(r.get("unit"))
        label = name.strip() or key_s
        if unit.strip():
            label = f"{label} ({unit.strip()})"

        if key_s not in param_label_by_key:
            param_label_by_key[key_s] = label
            param_order.append(key_s)

        v = "" if r.get("value") is None else str(r.get("value"))
        row_map = by_ts.setdefault(ts, {})
        # если несколько значений попали в один и тот же ts/param — берём последнее
        row_map[key_s] = v

    base_param_headers = [param_label_by_key.get(k, k) for k in param_order]
    unique_param_headers = _make_unique_headers(base_param_headers)

    headers = ["ts"] + unique_param_headers

    # mapping: key -> column index (соотнесём с уникальными заголовками через позицию param_order)
    key_to_idx: Dict[str, int] = {k: i for i, k in enumerate(param_order)}

    # Сортируем timestamps лексикографически (ISO-подобные строки сортируются правильно)
    ts_list = sorted(by_ts.keys())
    data_rows: List[List[str]] = []
    for ts in ts_list:
        vals = [""] * len(param_order)
        row_map = by_ts.get(ts, {})
        for k, v in row_map.items():
            idx = key_to_idx.get(k)
            if idx is not None:
                vals[idx] = v
        data_rows.append([ts] + vals)

    return headers, data_rows


def _aggregate_rows_by_period(rows: List[Dict], aggregation_seconds: int | None) -> List[Dict]:
    """Агрегирует long-rows по временным корзинам, считая mean для каждого параметра."""
    if not aggregation_seconds or int(aggregation_seconds) <= 0:
        return rows

    bucket_seconds = int(aggregation_seconds)
    epoch = datetime(1970, 1, 1)
    param_order: List[str] = []
    param_meta: Dict[str, Dict[str, str]] = {}
    bucket_values: Dict[datetime, Dict[str, List[float]]] = {}
    parsed_any = False

    for r in rows:
        key = r.get("param_key")
        if key is None:
            continue
        key_s = str(key)
        if key_s not in param_meta:
            param_meta[key_s] = {
                "name": "" if r.get("name") is None else str(r.get("name")),
                "unit": "" if r.get("unit") is None else str(r.get("unit")),
            }
            param_order.append(key_s)

        ts_raw = r.get("ts")
        val_raw = r.get("value")
        try:
            ts_dt = datetime.fromisoformat(str(ts_raw))
            val = float(val_raw)
        except Exception:
            continue

        parsed_any = True
        seconds_from_epoch = int((ts_dt - epoch).total_seconds())
        bucket_start = epoch + timedelta(seconds=(seconds_from_epoch // bucket_seconds) * bucket_seconds)
        bucket_row = bucket_values.setdefault(bucket_start, {})
        bucket_row.setdefault(key_s, []).append(val)

    if not parsed_any:
        return rows

    aggregated_rows: List[Dict] = []
    for bucket_start in sorted(bucket_values.keys()):
        row_map = bucket_values[bucket_start]
        ts_out = bucket_start.isoformat(sep=" ")
        for key_s in param_order:
            values = row_map.get(key_s)
            if not values:
                continue
            meta = param_meta.get(key_s, {})
            avg = sum(values) / float(len(values))
            aggregated_rows.append(
                {
                    "ts": ts_out,
                    "param_key": key_s,
                    "name": meta.get("name", ""),
                    "unit": meta.get("unit", ""),
                    "value": f"{avg:.6g}",
                }
            )

    return aggregated_rows


def _coerce_frame_ts(ts_raw) -> datetime | None:
    if isinstance(ts_raw, datetime):
        return ts_raw.replace(tzinfo=None) if ts_raw.tzinfo is not None else ts_raw
    try:
        ts_dt = datetime.fromisoformat(str(ts_raw))
        return ts_dt.replace(tzinfo=None) if ts_dt.tzinfo is not None else ts_dt
    except Exception:
        return None


def _image_extension(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if image_bytes.startswith(b"GIF87a") or image_bytes.startswith(b"GIF89a"):
        return "gif"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "webp"
    return "jpg"


def select_image_frames_for_export(
    frames: List[Dict],
    aggregation_seconds: int | None = None,
) -> List[Dict]:
    """Вернуть все кадры или по одному последнему кадру на bucket."""
    normalized: List[Dict] = []
    for frame in frames:
        ts_dt = _coerce_frame_ts(frame.get("ts"))
        image_bytes = frame.get("image_bytes")
        if ts_dt is None or not image_bytes:
            continue
        try:
            normalized.append({"ts": ts_dt, "image_bytes": bytes(image_bytes)})
        except Exception:
            continue

    normalized.sort(key=lambda item: item["ts"])
    if not aggregation_seconds or int(aggregation_seconds) <= 0:
        return normalized

    bucket_seconds = int(aggregation_seconds)
    epoch = datetime(1970, 1, 1)
    selected_by_bucket: Dict[datetime, Dict] = {}
    for frame in normalized:
        frame_ts = frame["ts"]
        seconds_from_epoch = int((frame_ts - epoch).total_seconds())
        bucket_start = epoch + timedelta(seconds=(seconds_from_epoch // bucket_seconds) * bucket_seconds)
        selected_by_bucket[bucket_start] = frame
    return [selected_by_bucket[key] for key in sorted(selected_by_bucket.keys())]


def export_image_frames(
    frames: List[Dict],
    export_dir: Path,
    folder_name: str,
    aggregation_seconds: int | None = None,
) -> tuple[Path | None, int]:
    """Сохранить кадры в отдельную папку рядом с основным отчетом."""
    selected_frames = select_image_frames_for_export(frames, aggregation_seconds=aggregation_seconds)
    if not selected_frames:
        return None, 0

    images_dir = export_dir / _safe_filename(folder_name)
    images_dir.mkdir(parents=True, exist_ok=True)

    for idx, frame in enumerate(selected_frames, start=1):
        frame_ts = frame["ts"]
        image_bytes = frame["image_bytes"]
        ext = _image_extension(image_bytes)
        ts_part = frame_ts.strftime("%Y%m%d_%H%M%S")
        file_name = f"{idx:04d}_{ts_part}.{ext}"
        (images_dir / file_name).write_bytes(image_bytes)

    return images_dir, len(selected_frames)


def export_history_csv(
    rows: List[Dict],
    export_dir: Path,
    filename_stem: str,
    aggregation_seconds: int | None = None,
) -> Path:
    export_dir.mkdir(parents=True, exist_ok=True)
    out_path = export_dir / _safe_filename(f"{filename_stem}.csv")

    rows = _aggregate_rows_by_period(rows, aggregation_seconds)
    headers, data_rows = _pivot_wide(rows)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(data_rows)
    return out_path


def export_history_xls_spreadsheetml(
    rows: List[Dict],
    export_dir: Path,
    filename_stem: str,
    sheet_name: str = "Data",
    aggregation_seconds: int | None = None,
) -> Path:
    """
    Пишет старый XML-формат Excel 2003 (SpreadsheetML), который Excel открывает как .xls.
    Без внешних зависимостей.
    """
    export_dir.mkdir(parents=True, exist_ok=True)
    out_path = export_dir / _safe_filename(f"{filename_stem}.xls")

    def esc(v: str) -> str:
        return (
            v.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    rows = _aggregate_rows_by_period(rows, aggregation_seconds)
    headers, data_rows = _pivot_wide(rows)

    lines: List[str] = []
    lines.append('<?xml version="1.0"?>')
    lines.append('<?mso-application progid="Excel.Sheet"?>')
    lines.append(
        '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" '
        'xmlns:o="urn:schemas-microsoft-com:office:office" '
        'xmlns:x="urn:schemas-microsoft-com:office:excel" '
        'xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet" '
        'xmlns:html="http://www.w3.org/TR/REC-html40">'
    )
    lines.append(f'<Worksheet ss:Name="{esc(sheet_name)}"><Table>')

    # header row
    lines.append("<Row>")
    for h in headers:
        lines.append(f'<Cell><Data ss:Type="String">{esc(h)}</Data></Cell>')
    lines.append("</Row>")

    # data rows
    for r in data_rows:
        lines.append("<Row>")
        for v in r:
            vv = "" if v is None else str(v)
            # timestamp/strings keep as string; value can be numeric but оставим строкой (проще/без сюрпризов)
            lines.append(f'<Cell><Data ss:Type="String">{esc(vv)}</Data></Cell>')
        lines.append("</Row>")

    lines.append("</Table></Worksheet></Workbook>")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def export_history_pdf(
    rows: List[Dict],
    export_dir: Path,
    filename_stem: str,
    title: str = "Patient Monitor Export",
    aggregation_seconds: int | None = None,
) -> Path:
    """
    Экспорт в PDF через reportlab.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception as e:
        raise RuntimeError(
            "PDF экспорт требует установленный пакет reportlab. "
            "Установите зависимости: pip install -r requirements.txt"
        ) from e

    export_dir.mkdir(parents=True, exist_ok=True)
    out_path = export_dir / _safe_filename(f"{filename_stem}.pdf")

    rows = _aggregate_rows_by_period(rows, aggregation_seconds)
    headers, data_rows = _pivot_wide(rows)

    def _register_unicode_font() -> tuple[str, str | None]:
        """
        Регистрирует TTF-шрифт с поддержкой кириллицы.
        Возвращает (regular_font_name, bold_font_name_or_None).
        """
        # Попробуем несколько типичных путей (Windows + Linux).
        # Также поддержим шрифт, если он будет лежать в проекте (не обязателен).
        project_root = Path(__file__).resolve().parent.parent
        candidates_regular = [
            project_root / "fonts" / "DejaVuSans.ttf",
            project_root / "assets" / "fonts" / "DejaVuSans.ttf",
            # Windows
            Path(r"C:\Windows\Fonts\arial.ttf"),
            Path(r"C:\Windows\Fonts\segoeui.ttf"),
            Path(r"C:\Windows\Fonts\tahoma.ttf"),
            Path(r"C:\Windows\Fonts\calibri.ttf"),
            # Linux
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        ]
        candidates_bold = [
            project_root / "fonts" / "DejaVuSans-Bold.ttf",
            project_root / "assets" / "fonts" / "DejaVuSans-Bold.ttf",
            # Windows
            Path(r"C:\Windows\Fonts\arialbd.ttf"),
            Path(r"C:\Windows\Fonts\segoeuib.ttf"),
            Path(r"C:\Windows\Fonts\tahomabd.ttf"),
            Path(r"C:\Windows\Fonts\calibrib.ttf"),
            # Linux
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        ]

        reg_name = "PMUnicode"
        bold_name = "PMUnicodeBold"

        # Если уже зарегистрированы — просто вернём.
        try:
            if pdfmetrics.getFont(reg_name):
                try:
                    pdfmetrics.getFont(bold_name)
                    return reg_name, bold_name
                except Exception:
                    return reg_name, None
        except Exception:
            pass

        regular_path = next((p for p in candidates_regular if p.exists()), None)
        if not regular_path:
            # Фоллбэк: встроенный Helvetica (без кириллицы)
            return "Helvetica", "Helvetica-Bold"

        try:
            pdfmetrics.registerFont(TTFont(reg_name, str(regular_path)))
        except Exception:
            return "Helvetica", "Helvetica-Bold"

        bold_path = next((p for p in candidates_bold if p.exists()), None)
        if bold_path:
            try:
                pdfmetrics.registerFont(TTFont(bold_name, str(bold_path)))
                return reg_name, bold_name
            except Exception:
                return reg_name, None

        return reg_name, None

    font_regular, font_bold = _register_unicode_font()

    c = canvas.Canvas(str(out_path), pagesize=A4)
    width, height = A4

    x0 = 12 * mm
    y0 = 15 * mm
    y = height - 16 * mm

    def draw_title():
        nonlocal y
        c.setFont(font_bold or font_regular, 13)
        c.drawString(x0, y, title)
        y -= 8 * mm

    def draw_header_line(total_w: float):
        c.setLineWidth(0.5)
        c.line(x0, y + 1.8 * mm, x0 + total_w, y + 1.8 * mm)

    def ellipsize(s: str, max_len: int) -> str:
        if len(s) <= max_len:
            return s
        return s[: max(0, max_len - 3)] + "..."

    # Если колонок много — режем на блоки: ts + N параметров на страницу
    param_headers = headers[1:]
    max_params_per_page = 4  # под 4 слота обычно хватает, но пусть будет ограничение
    chunks: List[List[str]] = []
    for i in range(0, len(param_headers), max_params_per_page):
        chunks.append(param_headers[i : i + max_params_per_page])

    for ci, chunk in enumerate(chunks):
        if ci == 0:
            draw_title()
        else:
            c.showPage()
            y = height - 16 * mm
            draw_title()

        page_headers = ["ts"] + chunk
        # ширины колонок: ts фикс, остальные равномерно
        ts_w = 55 * mm
        other_w = max(20 * mm, (width - x0 * 2 - ts_w) / max(1, len(chunk)))
        col_w = [ts_w] + [other_w] * len(chunk)
        total_w = sum(col_w)

        def draw_row(values: List[str], bold: bool = False):
            nonlocal y
            if bold:
                c.setFont(font_bold or font_regular, 7.8 if len(chunk) > 2 else 8.3)
            else:
                c.setFont(font_regular, 7.8 if len(chunk) > 2 else 8.3)
            xx = x0
            for v, w in zip(values, col_w):
                txt = "" if v is None else str(v)
                txt = ellipsize(txt, 55 if w >= 40 * mm else 28)
                c.drawString(xx, y, txt)
                xx += w
            y -= 4.6 * mm

        draw_row(page_headers, bold=True)
        draw_header_line(total_w)
        y -= 2.2 * mm

        # Индексы параметров для этого чанка
        chunk_indices = [param_headers.index(h) for h in chunk]
        for r in data_rows:
            if y < y0:
                c.showPage()
                y = height - 16 * mm
                draw_title()
                draw_row(page_headers, bold=True)
                draw_header_line(total_w)
                y -= 2.2 * mm

            ts = r[0]
            vals = [r[1 + idx] for idx in chunk_indices]
            draw_row([ts] + vals)

    c.save()
    return out_path

