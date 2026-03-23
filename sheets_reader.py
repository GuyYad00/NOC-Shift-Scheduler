"""Google Sheets reader - fetches availability data from a public Google Sheet."""

import re
import csv
import io
import requests


def extract_sheet_id(url: str) -> str:
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
    if match:
        return match.group(1)
    raise ValueError("כתובת Google Sheets לא תקינה")


def extract_gid(url: str) -> str:
    match = re.search(r'gid=(\d+)', url)
    return match.group(1) if match else "0"


def fetch_sheet_csv(sheet_id: str, gid: str = "0") -> str:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()

    if '<html' in response.text[:500].lower():
        raise PermissionError(
            "הגיליון אינו ציבורי.\n"
            'יש לשתף את הגיליון עם "כל מי שיש לו את הקישור יכול לצפות"'
        )
    return response.text


def _fill_forward(cells: list) -> list:
    """Fill empty cells with the previous non-empty value (for merged cells)."""
    result = []
    current = ""
    for cell in cells:
        if cell.strip():
            current = cell.strip()
        result.append(current)
    return result


def _is_checkmark(cell: str) -> bool:
    val = cell.strip()
    return val in ("✔️", "✔", "V", "v", "✓", "TRUE", "true", "1", "כן", "x", "X")


def parse_availability(csv_text: str) -> dict:
    """
    Parse the availability CSV.

    Expected format:
        Row 0: [empty, date1, ..., ..., ..., date2, ..., ..., ..., ...]
        Row 1: [יום, dayname1, ..., dayname2, ...]
        Row 2: [משמרת, בוקר, ערב, לילה, כונן, בוקר, ערב, לילה, כונן, ...]
        Row 3+: [employee_name, ✔️/empty, ...]

    Returns dict with dates, day_names, employees, availability, notes, num_days.
    """
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)

    if len(rows) < 4:
        raise ValueError("הגיליון לא בפורמט הנכון - חסרות שורות")

    shifts_row = rows[2]

    shift_columns = []
    for col_idx, cell in enumerate(shifts_row):
        if col_idx == 0:
            continue
        val = cell.strip()
        if val in ("בוקר", "ערב", "לילה", "כונן"):
            shift_columns.append((col_idx, val))

    if not shift_columns:
        raise ValueError("לא נמצאו עמודות משמרות בשורה 3")

    shifts_per_day = 4
    num_days = len(shift_columns) // shifts_per_day
    if num_days == 0:
        raise ValueError("לא נמצאו ימים בגיליון")

    dates_row_filled = _fill_forward(rows[0])
    days_row_filled = _fill_forward(rows[1])

    unique_dates = []
    unique_day_names = []
    for d in range(num_days):
        col_idx = shift_columns[d * shifts_per_day][0]
        date_val = dates_row_filled[col_idx] if col_idx < len(dates_row_filled) else ""
        day_val = days_row_filled[col_idx] if col_idx < len(days_row_filled) else ""
        unique_dates.append(date_val)
        unique_day_names.append(day_val)

    employees = []
    availability = {}
    notes = {}

    for row_idx in range(3, len(rows)):
        row = rows[row_idx]
        if not row or not row[0].strip():
            break

        name = row[0].strip()
        employees.append(name)
        availability[name] = {}

        for d in range(num_days):
            availability[name][d] = {}
            for s_idx, shift_type in enumerate(["בוקר", "ערב", "לילה", "כונן"]):
                sc_index = d * shifts_per_day + s_idx
                if sc_index < len(shift_columns):
                    col_idx = shift_columns[sc_index][0]
                    if col_idx < len(row):
                        cell = row[col_idx]
                        if _is_checkmark(cell):
                            availability[name][d][shift_type] = True
                        else:
                            availability[name][d][shift_type] = False
                            if cell.strip() and not _is_checkmark(cell):
                                notes.setdefault(name, []).append(
                                    f"{unique_day_names[d]} {shift_type}: {cell.strip()}"
                                )
                    else:
                        availability[name][d][shift_type] = False
                else:
                    availability[name][d][shift_type] = False

    return {
        "dates": unique_dates,
        "day_names": unique_day_names,
        "employees": employees,
        "availability": availability,
        "notes": notes,
        "num_days": num_days,
    }


def fetch_and_parse(url: str) -> dict:
    sheet_id = extract_sheet_id(url)
    gid = extract_gid(url)
    csv_text = fetch_sheet_csv(sheet_id, gid)
    return parse_availability(csv_text)
