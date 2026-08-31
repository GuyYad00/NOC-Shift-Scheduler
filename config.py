"""Configuration constants for the NOC Shift Scheduler."""

from datetime import time

# Shift types and labels
SHIFT_TYPES = ["בוקר", "ערב", "לילה", "כונן"]
REGULAR_SHIFTS = ["בוקר", "ערב", "לילה"]

# חזרה למתכונת של עובד אחד בכל משמרת (ללא ימי בוקר כפולים)
DOUBLE_MORNING_DAY_INDICES: tuple[int, ...] = ()


def slots_for_day_shift(day_index: int, shift_type: str) -> list[int]:
    """מספר סלוטים לסוג משמרת ביום נתון."""
    if shift_type == "בוקר" and day_index in DOUBLE_MORNING_DAY_INDICES:
        return [0, 1]
    return [0]


def normalize_assignment_key(key: tuple) -> tuple:
    """מאחד מפתח (d,s) או (d,s,slot) לצורת (d,s,slot)."""
    if len(key) == 2:
        return (key[0], key[1], 0)
    return (key[0], key[1], key[2])


def iter_all_slot_keys(num_days: int):
    """כל משבצות השיבוץ לשבוע."""
    for d in range(num_days):
        for s in SHIFT_TYPES:
            for slot in slots_for_day_shift(d, s):
                yield (d, s, slot)


def schedule_row_defs() -> list[tuple[str, str, int]]:
    """שורות תצוגה בטבלה ובייצוא. שורת בוקר ב מוצגת רק כשיש ימי בוקר כפולים."""
    if DOUBLE_MORNING_DAY_INDICES:
        rows: list[tuple[str, str, int]] = [
            ("בוקר (א)", "בוקר", 0),
            ("בוקר (ב)", "בוקר", 1),
        ]
    else:
        rows = [(SHIFT_LABELS["בוקר"], "בוקר", 0)]
    for shift_type in ("ערב", "לילה", "כונן"):
        rows.append((SHIFT_LABELS[shift_type], shift_type, 0))
    return rows

# Time windows for shifts
SHIFT_TIMES = {
    "בוקר": (time(7, 0), time(16, 0)),
    "ערב": (time(15, 30), time(23, 30)),
    "לילה": (time(23, 0), time(7, 0)),
}

DAY_NAMES_HEB = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"]

# Points for fairness balancing (weight per day/shift).
# Weekday night is deliberately low vs בוקר/ערב so "premium" shifts drive most of the gap;
# Fri/Sat night keep higher weights (תוספת שבת/שישי).
SHIFT_WEIGHTS = {
    "weekday": {"בוקר": 1.0, "ערב": 1.0, "לילה": 0.12, "כונן": 0.4},
    "friday":  {"בוקר": 1.0, "ערב": 1.5, "לילה": 1.5, "כונן": 0.4},
    "saturday":{"בוקר": 1.5, "ערב": 1.2, "לילה": 0.28, "כונן": 0.4},
}

# Display labels for the GUI
SHIFT_LABELS = {
    "בוקר": "בוקר  07:00-16:00",
    "ערב":  "ערב  15:30-23:30",
    "לילה": "לילה  23:00-07:00",
    "כונן": "כונן",
}

# Logic constraints - Defaults (Now customizable via UI)
DEFAULT_MIN_SHIFTS = 3
DEFAULT_MAX_CONSECUTIVE_DAYS = 6
PREFERENCE_BONUS = 0.2         # Score bonus for preferred shifts (⭐)
MIN_GAP_HOURS = 8

# Extra objective weight: spread כונן shifts evenly among employees who marked כונן in Sheets
ONCALL_BALANCE_WEIGHT = 80.0

# Heatmap Colors
COLOR_HEATMAP_EMPTY = "#FFCDD2"   # Light red for zero availability
COLOR_HEATMAP_LOW = "#FFF9C4"     # Light yellow for 1 available person

# Rest period constraints
FORBIDDEN_CONSECUTIVE = [
    ("ערב", "בוקר"),
    ("לילה", "בוקר"),
]

# WhatsApp Messaging
WHATSAPP_MSG_HEADER = "📢 *סידור משמרות NOC לשבוע הקרוב:* 📢\n\n"

# UI settings
APP_TITLE = "NOC Shift Scheduler - מערכת שיבוץ משמרות"
APP_WIDTH = 1350
APP_HEIGHT = 900