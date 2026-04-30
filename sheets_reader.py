# pyre-ignore-all-errors
"""Google Sheets reader - fetches availability and preference data from a public Google Sheet."""

import re
import csv
import io
import requests
from typing import Dict, List


def extract_sheet_id(url: str) -> str:
    """Extract the unique spreadsheet ID from a Google Sheets URL."""
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
    if match:
        return match.group(1)
    raise ValueError("כתובת Google Sheets לא תקינה")


def extract_gid(url: str) -> str:
    """Extract the tab ID (gid) from the URL, defaults to '0'."""
    match = re.search(r'gid=(\d+)', url)
    return match.group(1) if match else "0"


def fetch_sheet_csv(sheet_id: str, gid: str = "0") -> str:
    """Download the sheet content as a CSV string."""
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()

    # Check if the response is an HTML login page (indicates private sheet)
    if '<html' in response.text[:500].lower():
        raise PermissionError(
            "הגיליון אינו ציבורי.\n"
            'יש לשתף את הגיליון עם "כל מי שיש לו את הקישור יכול לצפות"'
        )
    return response.text


def _fill_forward(cells: list) -> list:
    """Fill empty cells (often from merged cells in Sheets) with the previous non-empty value."""
    result = []
    current = ""
    for cell in cells:
        if cell.strip():
            current = cell.strip()
        result.append(current)
    return result


def _is_checkmark(cell: str) -> bool:
    """Check if a cell contains a valid availability marker, including preference stars."""
    val = cell.strip()
    return val in ("✔️", "✔", "V", "v", "✓", "TRUE", "true", "1", "כן", "x", "X", "⭐", "P")


def _is_preference(cell: str) -> bool:
    """Determine if the user marked this shift as a high priority preference."""
    val = cell.strip()
    return val in ("⭐", "P", "עדיפות")


def parse_availability(csv_text: str) -> dict:
    """
    Parse the CSV data into structured availability and preference maps.
    
    Expected Row Format:
        Row 0: [empty, date1, ..., date2, ...]
        Row 1: [יום, dayname1, ..., dayname2, ...]
        Row 2: [משמרת, בוקר, ערב, לילה, כונן, ...]
        Row 3+: [employee_name, marker/empty, ...]
    """
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)

    if len(rows) < 4:
        raise ValueError("הגיליון לא בפורמט הנכון - חסרות שורות")

    shifts_row = rows[2]

    # Identify columns containing shift data
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

    # Handle merged header cells for dates and days
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

    employees: List[str] = []
    availability: Dict[str, Dict[int, Dict[str, bool]]] = {}
    preferences: Dict[str, Dict[int, Dict[str, bool]]] = {}
    notes: Dict[str, List[str]] = {}

    # Process employee rows
    for row_idx in range(3, len(rows)):
        row = rows[row_idx]
        if not row or not row[0].strip():
            break

        name = row[0].strip()
        employees.append(name)
        avail_days: Dict[int, Dict[str, bool]] = {}
        pref_days: Dict[int, Dict[str, bool]] = {}

        for d in range(num_days):
            avail_shifts: Dict[str, bool] = {}
            pref_shifts: Dict[str, bool] = {}
            for s_idx, shift_type in enumerate(["בוקר", "ערב", "לילה", "כונן"]):
                sc_index = d * shifts_per_day + s_idx
                if sc_index < len(shift_columns):
                    col_idx = shift_columns[sc_index][0]
                    if col_idx < len(row):
                        cell = row[col_idx]
                        # Mark availability
                        is_avail = _is_checkmark(cell)
                        avail_shifts[shift_type] = is_avail
                        
                        # Mark explicit preference
                        pref_shifts[shift_type] = _is_preference(cell)
                        
                        # Store non-marker text as notes
                        if cell.strip() and not is_avail:
                            if name not in notes:
                                notes[name] = []
                            notes[name].append(
                                f"{unique_day_names[d]} {shift_type}: {cell.strip()}"
                            )
                    else:
                        avail_shifts[shift_type] = False
                        pref_shifts[shift_type] = False
                else:
                    avail_shifts[shift_type] = False
                    pref_shifts[shift_type] = False
            avail_days[d] = avail_shifts
            pref_days[d] = pref_shifts

        availability[name] = avail_days
        preferences[name] = pref_days

    return {
        "dates": unique_dates,
        "day_names": unique_day_names,
        "employees": employees,
        "availability": availability,
        "preferences": preferences,
        "notes": notes,
        "num_days": num_days,
    }


def fetch_and_parse(url: str) -> dict:
    """High-level function to fetch and process the sheet in one go."""
    sheet_id = extract_sheet_id(url)
    gid = extract_gid(url)
    csv_text = fetch_sheet_csv(sheet_id, gid)
    return parse_availability(csv_text)