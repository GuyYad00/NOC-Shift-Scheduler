# pyre-ignore-all-errors
"""Persistent data storage for fairness scores and application settings."""

import json
import os
import sys
from datetime import datetime
from config import DEFAULT_MIN_SHIFTS, DEFAULT_MAX_CONSECUTIVE_DAYS, normalize_assignment_key, REGULAR_SHIFTS


def get_data_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _scores_path() -> str:
    return os.path.join(get_data_dir(), "noc_scores.json")


def _settings_path() -> str:
    return os.path.join(get_data_dir(), "noc_settings.json")


def load_scores() -> dict:
    path = _scores_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_scores(scores: dict):
    with open(_scores_path(), "w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=2)


def get_current_month_key() -> str:
    return datetime.now().strftime("%Y-%m")


def _parse_month_entry(v) -> float:
    """ניקוד משולב לצורך אלגוריתם / תצוגה כללית (יום משוקלל + מספר לילות)."""
    if isinstance(v, dict):
        return float(v.get("day", 0)) + int(v.get("night", 0))
    if v is None:
        return 0.0
    return float(v)


def _ensure_split_entry(v) -> dict:
    if isinstance(v, dict) and "day" in v and "night" in v:
        return {"day": float(v["day"]), "night": int(v["night"])}
    if isinstance(v, (int, float)):
        return {"day": float(v), "night": 0}
    return {"day": 0.0, "night": 0}


def get_current_month_scores() -> dict:
    """סכום חודשי משולב לכל עובד (לשימוש באלגוריתם האיזון)."""
    all_scores = load_scores()
    month_data = all_scores.get(get_current_month_key(), {})
    return {emp: _parse_month_entry(v) for emp, v in month_data.items()}


def get_current_month_split() -> dict:
    """פורמט {עובד: {\"day\": float, \"night\": int}} לחודש הנוכחי."""
    all_scores = load_scores()
    month_data = all_scores.get(get_current_month_key(), {})
    return {emp: _ensure_split_entry(v) for emp, v in month_data.items()}


def update_month_scores(employee_week_scores: dict):
    """תאימות לאחור: מוסיף את כל הציון לשדה day."""
    day_only = {e: float(v) for e, v in employee_week_scores.items()}
    night_zero = {e: 0 for e in employee_week_scores}
    return update_month_scores_split(day_only, night_zero)


def update_month_scores_split(day_deltas: dict, night_deltas: dict):
    """מצטבר נפרד: משקלי בוקר+ערב+כונן (day) ומספר לילות (night)."""
    all_scores = load_scores()
    month = get_current_month_key()
    if month not in all_scores:
        all_scores[month] = {}

    emps = set(day_deltas) | set(night_deltas)
    for emp in emps:
        cur = _ensure_split_entry(all_scores[month].get(emp, 0))
        cur["day"] += float(day_deltas.get(emp, 0))
        cur["night"] += int(night_deltas.get(emp, 0))
        all_scores[month][emp] = cur

    save_scores(all_scores)
    return dict(all_scores[month])


def reset_month_scores():
    all_scores = load_scores()
    month = get_current_month_key()
    all_scores[month] = {}
    save_scores(all_scores)


def reset_all_historical_data():
    save_scores({})


def load_settings() -> dict:
    path = _settings_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            settings = json.load(f)
            if "min_shifts" not in settings:
                settings["min_shifts"] = DEFAULT_MIN_SHIFTS
            if "max_consecutive_days" not in settings:
                settings["max_consecutive_days"] = DEFAULT_MAX_CONSECUTIVE_DAYS
            return settings

    return {
        "sheet_url": "",
        "excluded_employees": [],
        "last_saturday_shifts": {},
        "last_saturday_by_employee": {},
        "work_streaks": {},
        "min_shifts": DEFAULT_MIN_SHIFTS,
        "max_consecutive_days": DEFAULT_MAX_CONSECUTIVE_DAYS,
    }


def save_settings(settings: dict):
    with open(_settings_path(), "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def save_last_week_data(assignments: dict, num_days: int, employees: list):
    last_day_idx = num_days - 1
    last_by_emp: dict = {}
    for k, emp in assignments.items():
        if not emp:
            continue
        d, s, _ = normalize_assignment_key(k)
        if d == last_day_idx and s in REGULAR_SHIFTS:
            last_by_emp[emp] = s

    streaks = {}
    for emp in employees:
        count = 0
        for d in range(num_days - 1, -1, -1):
            worked = False
            for k, emp_assign in assignments.items():
                dd, s, _ = normalize_assignment_key(k)
                if dd == d and emp_assign == emp and s in REGULAR_SHIFTS:
                    worked = True
                    break
            if worked:
                count += 1
            else:
                break
        streaks[emp] = count

    settings = load_settings()
    settings["last_saturday_by_employee"] = last_by_emp
    settings.pop("last_saturday_shifts", None)
    settings["work_streaks"] = streaks
    save_settings(settings)


def get_prev_week_data() -> tuple:
    settings = load_settings()
    shifts = dict(settings.get("last_saturday_by_employee", {}))
    if not shifts:
        legacy = settings.get("last_saturday_shifts", {})
        shifts = {emp: s for s, emp in legacy.items() if emp}
    streaks = settings.get("work_streaks", {})
    return shifts, streaks


def get_historical_stats() -> dict:
    raw = load_scores()
    out = {}
    for month, emap in raw.items():
        out[month] = {emp: _parse_month_entry(v) for emp, v in emap.items()}
    return out
