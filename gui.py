"""NOC Shift Scheduler - GUI built with CustomTkinter."""

import threading
import customtkinter as ctk
from tkinter import messagebox, filedialog
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

from config import (
    APP_TITLE, APP_WIDTH, APP_HEIGHT,
    SHIFT_TYPES, REGULAR_SHIFTS, SHIFT_LABELS, DAY_NAMES_HEB,
)
from sheets_reader import fetch_and_parse
from data_store import (
    load_settings, save_settings,
    get_current_month_scores, update_month_scores, reset_month_scores,
)
from scheduler import schedule_shifts, calculate_week_scores, get_shift_weight

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

EMPTY_LABEL = "-- ריק --"
COLOR_MANUAL = "#42A5F5"
COLOR_AUTO = "#66BB6A"
COLOR_UNFILLED = "#EF5350"
COLOR_DEFAULT = "#3B8ED0"
COLOR_WARNING = "#FFA726"


class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, employees: list, excluded: list):
        super().__init__(parent)
        self.title("הגדרות - Settings")
        self.geometry("420x520")
        self.resizable(False, False)
        self.grab_set()

        self.result_excluded = list(excluded)
        self.check_vars = {}

        ctk.CTkLabel(self, text="עובדים מוחרגים מאיזון", font=("Arial", 16, "bold")).pack(
            pady=(15, 5)
        )
        ctk.CTkLabel(
            self,
            text="עובדים מסומנים לא ישתתפו בחישוב ההוגנות",
            font=("Arial", 12),
            text_color="gray",
        ).pack(pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(self, width=360, height=300)
        scroll.pack(padx=20, pady=5, fill="both", expand=True)

        for emp in employees:
            var = ctk.BooleanVar(value=emp in excluded)
            self.check_vars[emp] = var
            ctk.CTkCheckBox(scroll, text=emp, variable=var, font=("Arial", 13)).pack(
                anchor="e", padx=10, pady=3
            )

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=15)

        ctk.CTkButton(btn_frame, text="שמור", width=120, command=self._save).pack(
            side="right", padx=10
        )
        ctk.CTkButton(
            btn_frame, text="איפוס ניקוד חודשי", width=160, fg_color="#FF7043",
            command=self._reset_scores,
        ).pack(side="right", padx=10)

    def _save(self):
        self.result_excluded = [e for e, v in self.check_vars.items() if v.get()]
        self.destroy()

    def _reset_scores(self):
        if messagebox.askyesno("איפוס", "לאפס את הניקוד החודשי של כל העובדים?", parent=self):
            reset_month_scores()
            messagebox.showinfo("בוצע", "הניקוד החודשי אופס.", parent=self)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(f"{APP_WIDTH}x{APP_HEIGHT}")
        self.minsize(1100, 700)

        self.week_data = None
        self.manual_flags: dict[tuple, bool] = {}
        self.current_assignments: dict[tuple, str] = {}
        self.schedule_menus: dict[tuple, ctk.CTkOptionMenu] = {}
        self.settings = load_settings()

        self._build_ui()
        self._load_saved_url()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        # Top bar
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(top, text="כתובת Google Sheet:", font=("Arial", 13)).pack(
            side="left", padx=(8, 4)
        )
        self.url_entry = ctk.CTkEntry(top, width=560, font=("Arial", 12))
        self.url_entry.pack(side="left", padx=4)

        self.import_btn = ctk.CTkButton(
            top, text="ייבוא נתונים", width=130, command=self._import_clicked
        )
        self.import_btn.pack(side="left", padx=8)

        self.status_label = ctk.CTkLabel(
            self, text="יש להזין כתובת גיליון וללחוץ ייבוא", font=("Arial", 12),
            text_color="gray",
        )
        self.status_label.pack(fill="x", padx=16, pady=2)

        # Schedule table wrapper
        self.table_outer = ctk.CTkFrame(self)
        self.table_outer.pack(fill="both", expand=True, padx=12, pady=4)

        self.table_frame = ctk.CTkFrame(self.table_outer, fg_color="transparent")
        self.table_frame.pack(anchor="center", pady=10, padx=10)

        # Action buttons
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=6)

        ctk.CTkButton(
            actions, text="⚙  הגדרות", width=130, fg_color="#78909C",
            command=self._open_settings,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            actions, text="▶  שבץ אוטומטי", width=160, fg_color="#43A047",
            command=self._run_scheduler_clicked,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            actions, text="✓  אשר ושמור", width=140, fg_color="#1E88E5",
            command=self._confirm_save,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            actions, text="ייצוא Excel", width=130, fg_color="#8E24AA",
            command=self._export_excel,
        ).pack(side="left", padx=6)

        # Scores section
        scores_label = ctk.CTkLabel(
            self, text="טבלת הוגנות (ניקוד)", font=("Arial", 14, "bold")
        )
        scores_label.pack(padx=16, pady=(8, 2), anchor="w")

        self.scores_frame = ctk.CTkScrollableFrame(self, height=180)
        self.scores_frame.pack(fill="x", padx=12, pady=(0, 10))

    def _load_saved_url(self):
        url = self.settings.get("sheet_url", "")
        if url:
            self.url_entry.insert(0, url)

    # -------------------------------------------------------------- Import
    def _import_clicked(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("שגיאה", "יש להזין כתובת גיליון")
            return
        self.import_btn.configure(state="disabled")
        self._set_status("מייבא נתונים מ-Google Sheets…", "orange")
        threading.Thread(target=self._import_thread, args=(url,), daemon=True).start()

    def _import_thread(self, url):
        try:
            data = fetch_and_parse(url)
            self.after(0, lambda: self._import_done(url, data))
        except Exception as exc:
            self.after(0, lambda: self._import_error(exc))

    def _import_done(self, url, data):
        self.week_data = data
        self.settings["sheet_url"] = url
        save_settings(self.settings)
        self.current_assignments.clear()
        self.manual_flags.clear()
        self._build_schedule_table()
        n_emp = len(data["employees"])
        n_days = data["num_days"]
        self._set_status(f"ייבוא הצליח!  {n_emp} עובדים · {n_days} ימים", "green")
        self.import_btn.configure(state="normal")

    def _import_error(self, exc):
        self._set_status(f"שגיאת ייבוא: {exc}", "red")
        self.import_btn.configure(state="normal")
        messagebox.showerror("שגיאת ייבוא", str(exc))

    # -------------------------------------------------------- Schedule Table
    def _build_schedule_table(self):
        for w in self.table_frame.winfo_children():
            w.destroy()
        self.schedule_menus.clear()

        data = self.week_data
        if not data:
            return

        num_days = data["num_days"]
        employees = data["employees"]
        all_values = [EMPTY_LABEL] + employees

        # Headers
        ctk.CTkLabel(
            self.table_frame, text="", width=130
        ).grid(row=0, column=0, padx=4, pady=4)

        for d in range(num_days):
            date_str = data["dates"][d] if d < len(data["dates"]) else ""
            day_name = data["day_names"][d] if d < len(data["day_names"]) else ""
            header = f"{day_name}\n{date_str}"
            lbl = ctk.CTkLabel(
                self.table_frame, text=header, font=("Arial", 12, "bold"),
                width=130, justify="center",
            )
            lbl.grid(row=0, column=d + 1, padx=2, pady=4)

        # Shift rows
        for s_idx, stype in enumerate(SHIFT_TYPES):
            row = s_idx + 1
            ctk.CTkLabel(
                self.table_frame, text=SHIFT_LABELS.get(stype, stype),
                font=("Arial", 12, "bold"), width=130, anchor="e",
            ).grid(row=row, column=0, padx=(4, 8), pady=4, sticky="e")

            for d in range(num_days):
                avail_emps = [
                    e for e in employees
                    if data["availability"].get(e, {}).get(d, {}).get(stype, False)
                ]
                tooltip = ", ".join(avail_emps) if avail_emps else "אין זמינים"

                menu = ctk.CTkOptionMenu(
                    self.table_frame,
                    values=all_values,
                    width=125, height=32,
                    font=("Arial", 11),
                    command=lambda val, dd=d, ss=stype: self._on_cell_change(dd, ss, val),
                )
                menu.set(EMPTY_LABEL)
                menu.grid(row=row, column=d + 1, padx=2, pady=4)
                self.schedule_menus[(d, stype)] = menu

        # Availability summary row
        summary_row = len(SHIFT_TYPES) + 1
        ctk.CTkLabel(
            self.table_frame, text="", height=6
        ).grid(row=summary_row, column=0)

        self._update_cell_colors()

    def _on_cell_change(self, day, shift, value):
        if value == EMPTY_LABEL:
            self.current_assignments.pop((day, shift), None)
            self.manual_flags.pop((day, shift), None)
        else:
            self.current_assignments[(day, shift)] = value
            self.manual_flags[(day, shift)] = True
        self._update_cell_colors()
        self._update_scores_display()

    def _update_cell_colors(self):
        for (d, s), menu in self.schedule_menus.items():
            if (d, s) in self.current_assignments:
                emp = self.current_assignments[(d, s)]
                is_available = (
                    self.week_data
                    and self.week_data["availability"].get(emp, {}).get(d, {}).get(s, False)
                )
                if self.manual_flags.get((d, s)):
                    menu.configure(fg_color=COLOR_MANUAL if is_available else COLOR_WARNING)
                else:
                    menu.configure(fg_color=COLOR_AUTO)
            else:
                menu.configure(fg_color=COLOR_UNFILLED)

    # ----------------------------------------------------------- Scheduler
    def _run_scheduler_clicked(self):
        if not self.week_data:
            messagebox.showerror("שגיאה", "יש לייבא נתונים תחילה")
            return
        self._set_status("מריץ אלגוריתם שיבוץ…", "orange")
        threading.Thread(target=self._scheduler_thread, daemon=True).start()

    def _scheduler_thread(self):
        try:
            manual = {
                k: v for k, v in self.current_assignments.items()
                if self.manual_flags.get(k)
            }
            historical = get_current_month_scores()
            excluded = self.settings.get("excluded_employees", [])

            result = schedule_shifts(
                availability=self.week_data["availability"],
                day_names=self.week_data["day_names"],
                employees=self.week_data["employees"],
                manual_assignments=manual,
                historical_scores=historical,
                excluded_employees=excluded,
            )
            self.after(0, lambda: self._scheduler_done(result, manual))
        except Exception as exc:
            self.after(0, lambda: self._scheduler_error(exc))

    def _scheduler_done(self, result, manual):
        new_assignments = dict(manual)
        new_flags = {k: True for k in manual}

        for (d, s), emp in result["assignments"].items():
            if (d, s) not in manual:
                new_assignments[(d, s)] = emp
                new_flags[(d, s)] = False

        self.current_assignments = new_assignments
        self.manual_flags = new_flags

        for (d, s), menu in self.schedule_menus.items():
            emp = self.current_assignments.get((d, s))
            menu.set(emp if emp else EMPTY_LABEL)

        self._update_cell_colors()
        self._update_scores_display()

        n_unfilled = len(result.get("unfilled", []))
        status_map = {
            "optimal": ("שיבוץ הושלם בהצלחה!", "green"),
            "partial": (f"שיבוץ חלקי – {n_unfilled} משבצות לא מולאו", "orange"),
            "infeasible": ("לא ניתן לשבץ אוטומטית – יש למלא ידנית", "red"),
        }
        msg, color = status_map.get(result["status"], ("", "gray"))
        self._set_status(msg, color)

    def _scheduler_error(self, exc):
        self._set_status(f"שגיאה באלגוריתם: {exc}", "red")
        messagebox.showerror("שגיאת שיבוץ", str(exc))

    # -------------------------------------------------------------- Scores
    def _update_scores_display(self):
        for w in self.scores_frame.winfo_children():
            w.destroy()

        if not self.week_data:
            return

        day_names = self.week_data["day_names"]
        week_scores = calculate_week_scores(self.current_assignments, day_names)
        historical = get_current_month_scores()
        excluded = self.settings.get("excluded_employees", [])

        # Header
        cols = ["עובד", "השבוע", "חודשי מצטבר", "מצב", ""]
        for c_idx, col in enumerate(cols):
            ctk.CTkLabel(
                self.scores_frame, text=col, font=("Arial", 12, "bold"), width=120,
            ).grid(row=0, column=c_idx, padx=6, pady=4)

        all_employees = self.week_data["employees"]
        totals = {}
        for e in all_employees:
            ws = week_scores.get(e, 0)
            hs = historical.get(e, 0)
            totals[e] = round(ws + hs, 2)

        active_totals = [totals[e] for e in all_employees if e not in excluded]
        max_total = max(active_totals) if active_totals else 1
        min_total = min(active_totals) if active_totals else 0

        for r, emp in enumerate(all_employees, start=1):
            ws = week_scores.get(emp, 0)
            total = totals[emp]
            is_excluded = emp in excluded

            ctk.CTkLabel(
                self.scores_frame, text=emp, font=("Arial", 12), width=120,
            ).grid(row=r, column=0, padx=6, pady=2)

            ctk.CTkLabel(
                self.scores_frame, text=f"{ws:.1f}", font=("Arial", 12), width=120,
            ).grid(row=r, column=1, padx=6, pady=2)

            ctk.CTkLabel(
                self.scores_frame, text=f"{total:.1f}", font=("Arial", 12), width=120,
            ).grid(row=r, column=2, padx=6, pady=2)

            if is_excluded:
                tag = "מוחרג"
                tag_color = "gray"
            elif max_total > min_total:
                ratio = (total - min_total) / (max_total - min_total)
                if ratio > 0.7:
                    tag = "ניקוד גבוה ↑"
                    tag_color = "#E53935"
                elif ratio < 0.3:
                    tag = "ניקוד נמוך ↓"
                    tag_color = "#43A047"
                else:
                    tag = "מאוזן"
                    tag_color = "#1E88E5"
            else:
                tag = "מאוזן"
                tag_color = "#1E88E5"

            ctk.CTkLabel(
                self.scores_frame, text=tag, font=("Arial", 11),
                text_color=tag_color, width=120,
            ).grid(row=r, column=3, padx=6, pady=2)

            # Visual bar
            bar_width = 200
            if max_total > 0:
                fill_pct = min(total / max_total, 1.0)
            else:
                fill_pct = 0
            bar_frame = ctk.CTkFrame(self.scores_frame, width=bar_width, height=16, fg_color="#E0E0E0")
            bar_frame.grid(row=r, column=4, padx=6, pady=2, sticky="w")
            bar_frame.pack_propagate(False)
            bar_inner = ctk.CTkFrame(
                bar_frame, width=max(int(bar_width * fill_pct), 2), height=16,
                fg_color=tag_color,
            )
            bar_inner.place(x=0, y=0)

    # -------------------------------------------------------- Confirm/Save
    def _confirm_save(self):
        if not self.week_data:
            messagebox.showerror("שגיאה", "אין נתונים לשמור")
            return

        day_names = self.week_data["day_names"]
        week_scores = calculate_week_scores(self.current_assignments, day_names)

        if not week_scores:
            messagebox.showwarning("אזהרה", "אין שיבוצים לשמור")
            return

        new_monthly = update_month_scores(week_scores)

        summary_lines = ["הניקוד נשמר בהצלחה!\n", "ניקוד שבועי:"]
        for emp, sc in sorted(week_scores.items(), key=lambda x: -x[1]):
            monthly = new_monthly.get(emp, sc)
            summary_lines.append(f"  {emp}: {sc:.1f}  (חודשי: {monthly:.1f})")

        messagebox.showinfo("נשמר", "\n".join(summary_lines))
        self._update_scores_display()
        self._set_status("הניקוד נשמר בהצלחה", "green")

    # -------------------------------------------------------- Settings
    def _open_settings(self):
        employees = self.week_data["employees"] if self.week_data else []
        excluded = self.settings.get("excluded_employees", [])
        dialog = SettingsDialog(self, employees, excluded)
        self.wait_window(dialog)
        self.settings["excluded_employees"] = dialog.result_excluded
        save_settings(self.settings)
        self._update_scores_display()

    # -------------------------------------------------------- Export
    def _export_excel(self):
        if not self.week_data:
            messagebox.showerror("שגיאה", "אין נתונים לייצוא")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            title="שמור לוח משמרות",
            initialfile="schedule.xlsx",
        )
        if not path:
            return

        try:
            self._write_excel(path)
            messagebox.showinfo("ייצוא", f"הקובץ נשמר בהצלחה:\n{path}")
        except Exception as exc:
            messagebox.showerror("שגיאת ייצוא", str(exc))

    def _write_excel(self, path: str):
        wb = Workbook()
        ws = wb.active
        ws.title = "לוח משמרות"
        ws.sheet_view.rightToLeft = True

        data = self.week_data
        num_days = data["num_days"]

        header_fill = PatternFill(start_color="1E88E5", end_color="1E88E5", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=12)
        cell_font = Font(size=11)
        center = Alignment(horizontal="center", vertical="center")
        thin_border = Border(
            left=Side(style="thin"), right=Side(style="thin"),
            top=Side(style="thin"), bottom=Side(style="thin"),
        )

        # Header row
        ws.cell(row=1, column=1, value="משמרת").font = header_font
        ws.cell(row=1, column=1).fill = header_fill
        ws.cell(row=1, column=1).alignment = center
        ws.cell(row=1, column=1).border = thin_border
        ws.column_dimensions["A"].width = 20

        for d in range(num_days):
            day_name = data["day_names"][d] if d < len(data["day_names"]) else ""
            date_str = data["dates"][d] if d < len(data["dates"]) else ""
            cell = ws.cell(row=1, column=d + 2, value=f"{day_name} {date_str}")
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center
            cell.border = thin_border
            ws.column_dimensions[cell.column_letter].width = 18

        # Data rows
        auto_fill = PatternFill(start_color="C8E6C9", end_color="C8E6C9", fill_type="solid")
        manual_fill = PatternFill(start_color="BBDEFB", end_color="BBDEFB", fill_type="solid")
        empty_fill = PatternFill(start_color="FFCDD2", end_color="FFCDD2", fill_type="solid")

        for s_idx, stype in enumerate(SHIFT_TYPES):
            row = s_idx + 2
            label_cell = ws.cell(row=row, column=1, value=SHIFT_LABELS.get(stype, stype))
            label_cell.font = Font(bold=True, size=11)
            label_cell.alignment = center
            label_cell.border = thin_border

            for d in range(num_days):
                emp = self.current_assignments.get((d, stype), "")
                cell = ws.cell(row=row, column=d + 2, value=emp)
                cell.font = cell_font
                cell.alignment = center
                cell.border = thin_border
                if emp:
                    if self.manual_flags.get((d, stype)):
                        cell.fill = manual_fill
                    else:
                        cell.fill = auto_fill
                else:
                    cell.fill = empty_fill

        # Scores sheet
        ws2 = wb.create_sheet("ניקוד הוגנות")
        ws2.sheet_view.rightToLeft = True
        day_names = data["day_names"]
        week_scores = calculate_week_scores(self.current_assignments, day_names)
        historical = get_current_month_scores()

        headers2 = ["עובד", "ניקוד שבועי", "ניקוד חודשי מצטבר"]
        for c, h in enumerate(headers2, 1):
            cell = ws2.cell(row=1, column=c, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center
            cell.border = thin_border

        for r, emp in enumerate(data["employees"], 2):
            ws2.cell(row=r, column=1, value=emp).font = cell_font
            ws2.cell(row=r, column=1).border = thin_border
            ws = week_scores.get(emp, 0)
            total = round(ws + historical.get(emp, 0), 2)
            ws2.cell(row=r, column=2, value=ws).font = cell_font
            ws2.cell(row=r, column=2).border = thin_border
            ws2.cell(row=r, column=3, value=total).font = cell_font
            ws2.cell(row=r, column=3).border = thin_border

        ws2.column_dimensions["A"].width = 15
        ws2.column_dimensions["B"].width = 15
        ws2.column_dimensions["C"].width = 22

        wb.save(path)

    # -------------------------------------------------------- Helpers
    def _set_status(self, text: str, color: str = "gray"):
        self.status_label.configure(text=text, text_color=color)
