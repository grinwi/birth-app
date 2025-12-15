import csv
from io import StringIO
from typing import List, Dict

HEADER_KEYS = ["first_name", "last_name", "day", "month", "year"]


def normalize_row(row: Dict[str, str]) -> Dict[str, str]:
  return {
    "first_name": (row.get("first_name") or "").strip(),
    "last_name": (row.get("last_name") or "").strip(),
    "day": (row.get("day") or "").strip(),
    "month": (row.get("month") or "").strip(),
    "year": (row.get("year") or "").strip(),
  }


def validate_row(row: Dict[str, str]) -> None:
  r = normalize_row(row)
  if not r["first_name"]:
    raise ValueError("first_name is required")
  if not r["last_name"]:
    raise ValueError("last_name is required")
  try:
    d = int(r["day"])
    m = int(r["month"])
    y = int(r["year"])
  except Exception:
    raise ValueError("day/month/year must be integers")
  if d < 1 or d > 31:
    raise ValueError("day must be 1-31")
  if m < 1 or m > 12:
    raise ValueError("month must be 1-12")
  if y < 1900 or y > 3000:
    raise ValueError("year must be a realistic year (1900..3000)")
  import datetime
  dt = datetime.date(y, m, d)  # raises if invalid


def parse_csv(csv_text: str) -> List[Dict[str, str]]:
  text = (csv_text or "").strip()
  if not text:
    return []
  f = StringIO(text)
  reader = csv.reader(f)
  rows = list(reader)
  if not rows:
    return []
  header = [h.replace('"', "").strip() for h in rows[0]]
  matches_header = len(header) == len(HEADER_KEYS) and all(header[i] == HEADER_KEYS[i] for i in range(len(HEADER_KEYS)))
  start_idx = 1 if matches_header else 0
  out: List[Dict[str, str]] = []
  for i in range(start_idx, len(rows)):
    vals = rows[i]
    if not vals:
      continue
    obj = {}
    for idx, key in enumerate(HEADER_KEYS):
      v = (vals[idx] if idx < len(vals) else "") or ""
      v = str(v).strip().replace('""', '"')
      if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        v = v[1:-1]
      obj[key] = v
    out.append(normalize_row(obj))
  return out


def to_csv(rows: List[Dict[str, str]]) -> str:
  sio = StringIO()
  writer = csv.writer(sio, quoting=csv.QUOTE_ALL)
  writer.writerow(HEADER_KEYS)
  for r0 in rows:
    r = normalize_row(r0)
    writer.writerow([r[k] for k in HEADER_KEYS])
  return sio.getvalue().rstrip("\n")
