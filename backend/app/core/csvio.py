import csv
import io
from typing import Callable

from fastapi import UploadFile
from fastapi.responses import StreamingResponse

from app.core.errors import bad_request

MAX_IMPORT_ROWS = 5000


async def read_csv(file: UploadFile, required: set[str], allowed: set[str]) -> list[dict]:
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise bad_request("CSV file too large (max 5 MB)", "FILE_TOO_LARGE")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise bad_request("CSV must be UTF-8 encoded", "INVALID_CSV")
    reader = csv.DictReader(io.StringIO(text))
    headers = {(h or "").strip().lower() for h in (reader.fieldnames or [])}
    if not required <= headers:
        raise bad_request(f"Missing required column(s): {', '.join(sorted(required - headers))}", "INVALID_CSV_HEADERS")
    unknown = headers - allowed
    if unknown:
        raise bad_request(f"Unknown column(s): {', '.join(sorted(unknown))}", "INVALID_CSV_HEADERS")
    rows = [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items()} for r in reader]
    if len(rows) > MAX_IMPORT_ROWS:
        raise bad_request(f"Too many rows (max {MAX_IMPORT_ROWS})", "INVALID_CSV")
    return rows


def _safe(v):
    s = "" if v is None else str(v)
    # neutralise spreadsheet formula injection
    return "'" + s if s[:1] in ("=", "+", "-", "@") and not s.lstrip("-").replace(".", "", 1).isdigit() else s


def csv_response(filename: str, headers: list[str], rows: list[list]) -> StreamingResponse:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for r in rows:
        w.writerow([_safe(c) for c in r])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})
