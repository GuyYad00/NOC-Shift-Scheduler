"""Persistent data storage for fairness scores and application settings."""

import json
import os
import sys
from datetime import datetime


def get_data_dir() -> str:
    if getattr(sys, 'frozen', False):
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


def get_current_month_scores() -> dict:
    all_scores = load_scores()
    return dict(all_scores.get(get_current_month_key(), {}))


def update_month_scores(employee_week_scores: dict):
    """Add this week's scores to the monthly cumulative scores."""
    all_scores = load_scores()
    month = get_current_month_key()
    if month not in all_scores:
        all_scores[month] = {}

    for emp, week_score in employee_week_scores.items():
        all_scores[month][emp] = all_scores[month].get(emp, 0) + week_score

    save_scores(all_scores)
    return dict(all_scores[month])


def reset_month_scores():
    all_scores = load_scores()
    month = get_current_month_key()
    all_scores[month] = {}
    save_scores(all_scores)


def load_settings() -> dict:
    path = _settings_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"sheet_url": "", "excluded_employees": []}


def save_settings(settings: dict):
    with open(_settings_path(), "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
