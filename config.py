"""Configuration constants for the NOC Shift Scheduler."""

from datetime import time

SHIFT_TYPES = ["בוקר", "ערב", "לילה", "כונן"]
REGULAR_SHIFTS = ["בוקר", "ערב", "לילה"]

SHIFT_TIMES = {
    "בוקר": (time(7, 0), time(16, 0)),
    "ערב": (time(15, 30), time(23, 30)),
    "לילה": (time(23, 0), time(7, 0)),
}

DAY_NAMES_HEB = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"]

SHIFT_WEIGHTS = {
    "weekday": {"בוקר": 1.0, "ערב": 1.0, "לילה": 0.5, "כונן": 0.4},
    "friday":  {"בוקר": 1.0, "ערב": 1.5, "לילה": 1.5, "כונן": 0.4},
    "saturday":{"בוקר": 1.5, "ערב": 1.2, "לילה": 0.5, "כונן": 0.4},
}

SHIFT_LABELS = {
    "בוקר": "בוקר  07:00-16:00",
    "ערב":  "ערב  15:30-23:30",
    "לילה": "לילה  23:00-07:00",
    "כונן": "כונן",
}

MIN_SHIFTS_PER_EMPLOYEE = 3
MIN_GAP_HOURS = 8

FORBIDDEN_CONSECUTIVE = [
    ("ערב", "בוקר"),
    ("לילה", "בוקר"),
]

APP_TITLE = "NOC Shift Scheduler - מערכת שיבוץ משמרות"
APP_WIDTH = 1300
APP_HEIGHT = 880
