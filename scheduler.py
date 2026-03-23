"""Shift scheduling algorithm using PuLP linear programming."""

import os
import sys
from pulp import LpProblem, LpMaximize, LpVariable, lpSum, value, PULP_CBC_CMD, COIN_CMD
from config import SHIFT_WEIGHTS, REGULAR_SHIFTS, SHIFT_TYPES, FORBIDDEN_CONSECUTIVE, MIN_SHIFTS_PER_EMPLOYEE


def _get_solver():
    """Return a configured CBC solver, handling PyInstaller bundling."""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
        cbc = os.path.join(base, "cbc.exe")
        if not os.path.isfile(cbc):
            for root, _, files in os.walk(base):
                if "cbc.exe" in files:
                    cbc = os.path.join(root, "cbc.exe")
                    break
        if os.path.isfile(cbc):
            return COIN_CMD(path=cbc, msg=0, timeLimit=30, gapRel=0.05)
    return PULP_CBC_CMD(msg=0, timeLimit=30, gapRel=0.05)


def get_day_type(day_name: str) -> str:
    if day_name == "שישי":
        return "friday"
    if day_name == "שבת":
        return "saturday"
    return "weekday"


def get_shift_weight(day_name: str, shift_type: str) -> float:
    return SHIFT_WEIGHTS[get_day_type(day_name)].get(shift_type, 1.0)


def _safe_name(text: str, idx: int) -> str:
    """Create a safe LP variable name from Hebrew text."""
    return f"e{idx}"


def schedule_shifts(
    availability: dict,
    day_names: list,
    employees: list,
    manual_assignments: dict,
    historical_scores: dict,
    excluded_employees: list,
) -> dict:
    """
    Run the scheduling algorithm.

    Parameters
    ----------
    availability : {employee: {day_idx(int): {shift_type: bool}}}
    day_names    : list of Hebrew day names, length = num_days
    employees    : list of employee name strings
    manual_assignments : {(day_idx, shift_type): employee_name}
    historical_scores  : {employee: float} cumulative monthly scores so far
    excluded_employees : list of employee names excluded from balancing

    Returns
    -------
    dict with keys: assignments, week_scores, total_scores, status, unfilled
    """
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
    result = _solve(
        active, emp_idx, availability, day_names, num_days,
        manual_assignments, historical_scores, excluded_employees,
        enforce_min_shifts=True,
    )

    if result is None:
        result = _solve(
            active, emp_idx, availability, day_names, num_days,
            manual_assignments, historical_scores, excluded_employees,
            enforce_min_shifts=False,
        )

    if result is None:
        return _empty_result(num_days, manual_assignments, historical_scores)

    return result


def _solve(
    active, emp_idx, availability, day_names, num_days,
    manual_assignments, historical_scores, excluded_employees,
    enforce_min_shifts,
):
    prob = LpProblem("NOC_Schedule", LpMaximize)

    x = {}
    for e in active:
        ei = emp_idx[e]
        for d in range(num_days):
            for s in SHIFT_TYPES:
                x[e, d, s] = LpVariable(f"x_{ei}_{d}_{s}", cat="Binary")

    fill = {}
    for d in range(num_days):
        for s in SHIFT_TYPES:
            fill[d, s] = LpVariable(f"fill_{d}_{s}", cat="Binary")

    # --- Constraints ---

    # Each slot filled by at most one employee
    for d in range(num_days):
        for s in SHIFT_TYPES:
            prob += lpSum(x[e, d, s] for e in active) == fill[d, s]

    # Availability
    for e in active:
        for d in range(num_days):
            for s in SHIFT_TYPES:
                if not availability.get(e, {}).get(d, {}).get(s, False):
                    if (d, s) not in manual_assignments or manual_assignments[(d, s)] != e:
                        prob += x[e, d, s] == 0

    # Manual assignments are locked
    for (d, s), emp in manual_assignments.items():
        if emp in active:
            prob += x[emp, d, s] == 1

    # One regular shift per employee per day
    for e in active:
        for d in range(num_days):
            prob += lpSum(x[e, d, s] for s in REGULAR_SHIFTS) <= 1

    # 8-hour gap: forbidden consecutive-day pairs
    for e in active:
        for d in range(num_days - 1):
            for s1, s2 in FORBIDDEN_CONSECUTIVE:
                prob += x[e, d, s1] + x[e, d + 1, s2] <= 1

    # On-call only with morning or no shift
    for e in active:
        for d in range(num_days):
            prob += x[e, d, "כונן"] + x[e, d, "ערב"] <= 1
            prob += x[e, d, "כונן"] + x[e, d, "לילה"] <= 1

    # Minimum shifts per employee who submitted enough availability
    if enforce_min_shifts:
        for e in active:
            avail_count = sum(
                1 for d in range(num_days) for s in REGULAR_SHIFTS
                if availability.get(e, {}).get(d, {}).get(s, False)
            )
            if avail_count >= MIN_SHIFTS_PER_EMPLOYEE:
                already_manual = sum(
                    1 for (d, s), emp in manual_assignments.items()
                    if emp == e and s in REGULAR_SHIFTS
                )
                needed = max(0, MIN_SHIFTS_PER_EMPLOYEE - already_manual)
                if needed > 0:
                    free_slots = lpSum(
                        x[e, d, s]
                        for d in range(num_days) for s in REGULAR_SHIFTS
                        if (d, s) not in manual_assignments
                    )
                    prob += free_slots + already_manual >= MIN_SHIFTS_PER_EMPLOYEE

    # --- Objective ---
    total_fill = lpSum(fill[d, s] for d in range(num_days) for s in SHIFT_TYPES)

    balancing = [e for e in active if e not in excluded_employees]
    if balancing:
        score_expr = {}
        for e in balancing:
            week = lpSum(
                x[e, d, s] * get_shift_weight(day_names[d], s)
                for d in range(num_days) for s in SHIFT_TYPES
            )
            score_expr[e] = week + historical_scores.get(e, 0)

        max_score = LpVariable("max_score")
        min_score = LpVariable("min_score")
        for e in balancing:
            prob += max_score >= score_expr[e]
            prob += min_score <= score_expr[e]

        prob += 1000 * total_fill - (max_score - min_score)
    else:
        prob += total_fill

    # --- Solve ---
    solver = _get_solver()
    status = prob.solve(solver)

    if status != 1:
        return None

    # --- Extract ---
    assignments = {}
    for d in range(num_days):
        for s in SHIFT_TYPES:
            for e in active:
                v = value(x[e, d, s])
                if v is not None and v > 0.5:
                    assignments[(d, s)] = e
                    break

    week_scores = {}
    total_scores = {}
    for e in active:
        ws = sum(
            get_shift_weight(day_names[d], s)
            for d in range(num_days) for s in SHIFT_TYPES
            if assignments.get((d, s)) == e
        )
        week_scores[e] = round(ws, 2)
        total_scores[e] = round(historical_scores.get(e, 0) + ws, 2)

    unfilled = [
        (d, s) for d in range(num_days) for s in SHIFT_TYPES
        if (d, s) not in assignments
    ]

    return {
        "assignments": assignments,
        "week_scores": week_scores,
        "total_scores": total_scores,
        "status": "optimal" if not unfilled else "partial",
        "unfilled": unfilled,
    }


def _empty_result(num_days, manual_assignments, historical_scores):
    return {
        "assignments": dict(manual_assignments),
        "week_scores": {},
        "total_scores": dict(historical_scores),
        "status": "infeasible",
        "unfilled": [
            (d, s) for d in range(num_days) for s in SHIFT_TYPES
            if (d, s) not in manual_assignments
        ],
    }


def calculate_week_scores(assignments: dict, day_names: list) -> dict:
    """Calculate per-employee scores from a set of assignments."""
    scores = {}
    for (d, s), emp in assignments.items():
        if emp and d < len(day_names):
            w = get_shift_weight(day_names[d], s)
            scores[emp] = scores.get(emp, 0) + w
    return {e: round(v, 2) for e, v in scores.items()}
