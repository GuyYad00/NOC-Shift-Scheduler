# pyre-ignore-all-errors
"""Shift scheduling — night spacing, night/oncall/day fairness, multi-slot mornings."""
# type: ignore[reportOperatorIssue]
# pyright: reportGeneralTypeIssues=false, reportUnknownMemberType=false, reportUnknownVariableType=false
import os
import sys
from typing import Optional
from pulp import LpProblem, LpMaximize, LpVariable, lpSum, value, PULP_CBC_CMD, COIN_CMD
from config import (
    SHIFT_WEIGHTS,
    REGULAR_SHIFTS,
    SHIFT_TYPES,
    FORBIDDEN_CONSECUTIVE,
    PREFERENCE_BONUS,
    ONCALL_BALANCE_WEIGHT,
    slots_for_day_shift,
    iter_all_slot_keys,
    normalize_assignment_key,
)


def _get_solver():
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", "")
        cbc = os.path.join(base, "cbc.exe")
        if not os.path.isfile(cbc):
            for root, _, files in os.walk(base):
                if "cbc.exe" in files:
                    cbc = os.path.join(root, "cbc.exe")
                    break
        if os.path.isfile(cbc):
            return COIN_CMD(path=cbc, msg=0, timeLimit=60, gapRel=0.02)
    return PULP_CBC_CMD(msg=0, timeLimit=60, gapRel=0.02)


def get_day_type(day_name: str) -> str:
    if day_name == "שישי":
        return "friday"
    if day_name == "שבת":
        return "saturday"
    return "weekday"


def get_shift_weight(day_name: str, shift_type: str) -> float:
    return SHIFT_WEIGHTS[get_day_type(day_name)].get(shift_type, 1.0)


def _normalize_manual(manual: dict) -> dict:
    return {normalize_assignment_key(k): v for k, v in manual.items()}


def _night_counts(assignments: dict, active: list) -> dict:
    nc = {e: 0 for e in active}
    for k, emp in assignments.items():
        _, s, _ = normalize_assignment_key(k)
        if s == "לילה" and emp in nc:
            nc[emp] += 1
    return nc


# ───────────────────────── Main entry point ─────────────────────────

def schedule_shifts(
    availability: dict,
    preferences: dict,
    day_names: list,
    employees: list,
    manual_assignments: dict,
    historical_scores: dict,
    excluded_employees: list,
    prev_week_shifts: Optional[dict] = None,
    prev_work_streaks: Optional[dict] = None,
    min_shifts_val: int = 3,
    max_days_val: int = 6,
) -> dict:
    num_days = len(day_names)
    active = [
        e for e in employees
        if any(
            availability.get(e, {}).get(d, {}).get(s, False)
            for d in range(num_days) for s in SHIFT_TYPES
        )
    ]
    if not active:
        return _empty_result(num_days, manual_assignments, historical_scores)

    emp_idx = {e: i for i, e in enumerate(active)}
    streaks = prev_work_streaks or {e: 0 for e in active}
    manual_n = _normalize_manual(manual_assignments)

    def _try_all(max_n):
        for reset_fat in (False, True):
            su = {e: 0 for e in active} if reset_fat else streaks
            pu = None if reset_fat else prev_week_shifts
            for enf in (True, False):
                for oh in (True, False):
                    r = _solve(
                        active, emp_idx, availability, preferences,
                        day_names, num_days, manual_n, historical_scores,
                        excluded_employees,
                        enforce_min=enf, max_nights_per_emp=max_n,
                        prev_shifts=pu, streaks=su,
                        min_shifts_val=min_shifts_val,
                        max_days_val=max_days_val, oncall_hard=oh,
                    )
                    if r is not None:
                        return r
        return None

    # Phase 1: max 1 night per employee — if optimal, use it immediately
    r1 = _try_all(1)
    if r1 and r1["status"] == "optimal":
        return _tag_nights(r1, active)

    # Phase 2: max 2 nights — if covers more slots, prefer it (with approval)
    r2 = _try_all(2)
    best = r1
    if r2:
        r1_filled = len(r1["assignments"]) if r1 else 0
        r2_filled = len(r2["assignments"])
        if r2_filled > r1_filled:
            best = r2
    if best:
        return _tag_nights(best, active)

    return _empty_result(num_days, manual_n, historical_scores)


def _tag_nights(result, active):
    nc = _night_counts(result["assignments"], active)
    multi = [e for e, c in nc.items() if c > 1]
    result["night_counts"] = nc
    result["needs_night_approval"] = bool(multi)
    result["multi_night_employees"] = multi
    return result


# ───────────────────────── Solver core ─────────────────────────

def _solve(
    active, emp_idx, availability, preferences,
    day_names, num_days, manual, history, excluded,
    enforce_min, max_nights_per_emp, prev_shifts, streaks,
    min_shifts_val, max_days_val, oncall_hard,
):
    prob = LpProblem("NOC_Schedule", LpMaximize)

    # ──── Decision variables ────
    x: dict = {}
    fill: dict = {}
    for d in range(num_days):
        for s in SHIFT_TYPES:
            for slot in slots_for_day_shift(d, s):
                fill[d, s, slot] = LpVariable(f"fill_{d}_{s}_{slot}", cat="Binary")
                for e in active:
                    x[e, d, s, slot] = LpVariable(f"x_{emp_idx[e]}_{d}_{s}_{slot}", cat="Binary")

    # ──── Coverage: exactly one employee per filled slot ────
    for d in range(num_days):
        for s in SHIFT_TYPES:
            for slot in slots_for_day_shift(d, s):
                prob += lpSum(x[e, d, s, slot] for e in active) == fill[d, s, slot]

    # ──── Availability (force 0 if not available, unless manually locked) ────
    for e in active:
        for d in range(num_days):
            for s in SHIFT_TYPES:
                for slot in slots_for_day_shift(d, s):
                    if not availability.get(e, {}).get(d, {}).get(s, False):
                        if manual.get((d, s, slot)) != e:
                            prob += x[e, d, s, slot] == 0

    # ──── Manual locks ────
    for (d, s, slot), emp in manual.items():
        if emp in active:
            prob += x[emp, d, s, slot] == 1

    # ──── Max 1 regular shift per employee per day ────
    for e in active:
        for d in range(num_days):
            prob += lpSum(
                x[e, d, s, slot]
                for s in REGULAR_SHIFTS for slot in slots_for_day_shift(d, s)
            ) <= 1

    # ──── 8-hour rest (forbidden consecutive shift pairs across days) ────
    for e in active:
        for d in range(num_days - 1):
            for s1, s2 in FORBIDDEN_CONSECUTIVE:
                for slot2 in slots_for_day_shift(d + 1, s2):
                    prob += x[e, d, s1, 0] + x[e, d + 1, s2, slot2] <= 1

    # ──── NO consecutive nights (core requirement) ────
    for e in active:
        for d in range(num_days - 1):
            prob += x[e, d, "לילה", 0] + x[e, d + 1, "לילה", 0] <= 1

    # ──── Cross-week rest from previous Saturday ────
    if prev_shifts:
        for e in active:
            if e not in prev_shifts:
                continue
            last = prev_shifts[e]
            for s1, s2 in FORBIDDEN_CONSECUTIVE:
                if last == s1:
                    for slot2 in slots_for_day_shift(0, s2):
                        prob += x[e, 0, s2, slot2] == 0
            if last == "לילה":
                prob += x[e, 0, "לילה", 0] == 0

    # ──── Fatigue: max consecutive working days ────
    for e in active:
        initial = streaks.get(e, 0)
        window = max_days_val + 1
        for start in range(-initial, num_days):
            if start + window <= num_days:
                days_range = range(max(0, start), start + window)
                past = max(0, -start)
                prob += lpSum(
                    x[e, d, s, slot]
                    for d in days_range for s in REGULAR_SHIFTS
                    for slot in slots_for_day_shift(d, s)
                ) + past <= max_days_val

    # ──── On-call: cannot be on-call same day as ערב or לילה ────
    for e in active:
        for d in range(num_days):
            prob += x[e, d, "כונן", 0] + x[e, d, "ערב", 0] <= 1
            prob += x[e, d, "כונן", 0] + x[e, d, "לילה", 0] <= 1

    # ──── Max nights per employee ────
    for e in active:
        prob += lpSum(x[e, d, "לילה", 0] for d in range(num_days)) <= max_nights_per_emp

    # ──── Minimum shifts per employee ────
    if enforce_min:
        for e in active:
            avail_count = sum(
                1 for d in range(num_days) for s in REGULAR_SHIFTS
                if availability.get(e, {}).get(d, {}).get(s, False)
            )
            if avail_count >= min_shifts_val:
                prob += lpSum(
                    x[e, d, s, slot]
                    for d in range(num_days) for s in REGULAR_SHIFTS
                    for slot in slots_for_day_shift(d, s)
                ) >= min_shifts_val

    # ══════════════════════ OBJECTIVE ══════════════════════

    total_fill = lpSum(
        fill[d, s, slot]
        for d in range(num_days) for s in SHIFT_TYPES
        for slot in slots_for_day_shift(d, s)
    )

    pref_terms = [
        x[e, d, s, slot] * PREFERENCE_BONUS
        for e in active for d in range(num_days) for s in SHIFT_TYPES
        for slot in slots_for_day_shift(d, s)
        if preferences.get(e, {}).get(d, {}).get(s, False)
    ]
    pref_score = lpSum(pref_terms) if pref_terms else 0

    balancing = [e for e in active if e not in excluded]

    # Who signed up for night?
    night_volunteers = [
        e for e in balancing
        if any(availability.get(e, {}).get(d, {}).get("לילה", False) for d in range(num_days))
    ]
    # Who signed up for on-call?
    oncall_volunteers = [
        e for e in balancing
        if any(availability.get(e, {}).get(d, {}).get("כונן", False) for d in range(num_days))
    ]

    objective = 10000 * total_fill + pref_score

    # ── Night fairness: minimize gap in night count among night volunteers ──
    if len(night_volunteers) >= 2:
        nc_expr = {
            e: lpSum(x[e, d, "לילה", 0] for d in range(num_days))
            for e in night_volunteers
        }
        max_nc = LpVariable("max_night_count")
        min_nc = LpVariable("min_night_count")
        for e in night_volunteers:
            prob += max_nc >= nc_expr[e]
            prob += min_nc <= nc_expr[e]
        objective -= 500 * (max_nc - min_nc)

    # ── On-call fairness: minimize gap in oncall count ──
    if len(oncall_volunteers) >= 2:
        kon_expr = {
            e: lpSum(x[e, d, "כונן", 0] for d in range(num_days))
            for e in oncall_volunteers
        }
        max_kon = LpVariable("max_kon_count")
        min_kon = LpVariable("min_kon_count")
        for e in oncall_volunteers:
            prob += max_kon >= kon_expr[e]
            prob += min_kon <= kon_expr[e]
        objective -= ONCALL_BALANCE_WEIGHT * (max_kon - min_kon)
        if oncall_hard:
            for e1 in oncall_volunteers:
                for e2 in oncall_volunteers:
                    prob += kon_expr[e1] - kon_expr[e2] <= 1

    # ── Day-score fairness (בוקר+ערב+כונן weighted) ──
    if balancing:
        day_expr = {}
        for e in balancing:
            day_expr[e] = lpSum(
                x[e, d, s, slot] * get_shift_weight(day_names[d], s)
                for d in range(num_days) for s in SHIFT_TYPES
                for slot in slots_for_day_shift(d, s)
            ) + history.get(e, 0)
        max_ds = LpVariable("max_day_score")
        min_ds = LpVariable("min_day_score")
        for e in balancing:
            prob += max_ds >= day_expr[e]
            prob += min_ds <= day_expr[e]
        objective -= 5 * (max_ds - min_ds)

    # ── Night spacing: penalize close nights for same employee ──
    # Gap of 1 day (e.g., Sun+Tue) gets penalty 3; gap of 2 (Sun+Wed) gets 1
    for e in active:
        for d in range(num_days - 2):
            objective -= 3 * (x[e, d, "לילה", 0] + x[e, d + 2, "לילה", 0] - 1)
        for d in range(num_days - 3):
            objective -= 1 * (x[e, d, "לילה", 0] + x[e, d + 3, "לילה", 0] - 1)

    prob += objective

    # ──── Solve ────
    solver = _get_solver()
    status = prob.solve(solver)
    if status != 1:
        return None

    # ──── Extract results ────
    assignments: dict = {}
    for d in range(num_days):
        for s in SHIFT_TYPES:
            for slot in slots_for_day_shift(d, s):
                for e in active:
                    if value(x[e, d, s, slot]) and value(x[e, d, s, slot]) > 0.5:
                        assignments[(d, s, slot)] = e
                        break

    week_scores = {
        e: round(float(sum(
            get_shift_weight(day_names[d], s)
            for (d, s, sl), emp in assignments.items() if emp == e
        )), 2)
        for e in active
    }
    total_scores = {
        e: round(history.get(e, 0) + week_scores.get(e, 0), 2) for e in active
    }
    unfilled = [
        (d, s, slot) for d, s, slot in iter_all_slot_keys(num_days)
        if (d, s, slot) not in assignments
    ]

    return {
        "assignments": assignments,
        "week_scores": week_scores,
        "total_scores": total_scores,
        "status": "optimal" if not unfilled else "partial",
        "unfilled": unfilled,
    }


# ───────────────────────── Helpers ─────────────────────────

def _empty_result(num_days, manual, history):
    man = _normalize_manual(manual)
    return {
        "assignments": dict(man),
        "week_scores": {},
        "total_scores": dict(history),
        "status": "infeasible",
        "unfilled": [k for k in iter_all_slot_keys(num_days) if k not in man],
        "night_counts": {},
        "needs_night_approval": False,
        "multi_night_employees": [],
    }


def calculate_week_scores(assignments: dict, day_names: list) -> dict:
    scores = {}
    for k, emp in assignments.items():
        if not emp:
            continue
        d, s, _ = normalize_assignment_key(k)
        if d < len(day_names):
            scores[emp] = scores.get(emp, 0.0) + get_shift_weight(day_names[d], s)
    return {e: round(v, 2) for e, v in scores.items()}


def calculate_split_week_scores(assignments: dict, day_names: list) -> dict:
    """Night count (int) vs weighted day score (בוקר+ערב+כונן)."""
    out: dict = {}
    for k, emp in assignments.items():
        if not emp:
            continue
        d, s, _ = normalize_assignment_key(k)
        if d >= len(day_names):
            continue
        if emp not in out:
            out[emp] = {"לילה": 0, "יום": 0.0}
        if s == "לילה":
            out[emp]["לילה"] += 1
        elif s in ("בוקר", "ערב", "כונן"):
            out[emp]["יום"] += get_shift_weight(day_names[d], s)
    for emp in out:
        out[emp]["יום"] = round(out[emp]["יום"], 2)
    return out
