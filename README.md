<p align="center">
  <img src="docs/hero.png" alt="NOC Shift Scheduler" width="280" />
</p>

<h1 align="center">NOC Shift Scheduler</h1>

<p align="center">
  <b>מערכת שיבוץ משמרות ל־NOC</b><br/>
  Optimal weekly shifts · Hebrew RTL desktop app · MILP solver
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Solver-PuLP%20%2B%20CBC-0D47A1" alt="PuLP CBC" />
  <img src="https://img.shields.io/badge/UI-Hebrew%20RTL-1565C0" alt="Hebrew RTL" />
  <img src="https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white" alt="Windows" />
</p>

---

Desktop app that turns a public **Google Sheet** of availability into a fair weekly NOC schedule — then lets you lock cells, export to Excel, or send it on WhatsApp.

## Stack

| | |
|---|---|
| **Language** | Python 3.10+ |
| **UI** | [customtkinter](https://github.com/TomSchimansky/CustomTkinter) · Hebrew RTL |
| **Solver** | [PuLP](https://github.com/coin-or/pulp) + CBC (MILP) |
| **Input** | Google Sheets CSV (`gviz`, no OAuth) |
| **Export** | openpyxl · WhatsApp Web |
| **State** | local JSON (`noc_settings.json`, `noc_scores.json`) |
| **Packaging** | PyInstaller → one-file `.exe` |

No server, no database, no login. One operator, one machine.

## Architecture

```mermaid
flowchart LR
  Sheet[Google Sheets] --> GUI[gui.py]
  GUI --> Reader[sheets_reader]
  GUI --> Solver[scheduler · PuLP/CBC]
  GUI --> Store[data_store · JSON]
  GUI --> Out[Excel / WhatsApp]
```

`main.py` launches the GUI. Everything else is pure logic: parse the sheet, solve the week, persist fairness scores.

## What it enforces

- Coverage first, then fairness (nights, on-call, weighted day score)
- 8-hour rest · no consecutive nights · max consecutive work days
- On-call cannot overlap evening/night
- Manual locks are hard constraints
- Last Saturday + work streaks carry into the next week
- ⭐ in the sheet is a preference bonus

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Starter sheet (import into Google Sheets, share as *Anyone with the link can view*):  
[`templates/NOC_Availability_Template.xlsx`](templates/NOC_Availability_Template.xlsx)

1. Paste the sheet URL → **ייבוא נתונים**
2. Optionally lock cells
3. **שבץ אוטומטי** → **אשר ושמור**
4. Export Excel or send via WhatsApp

Build a standalone exe: `.\build.bat`

## Layout

```
main.py            entry
gui.py             RTL UI, export, WhatsApp
scheduler.py       MILP model
sheets_reader.py   Google Sheet → availability
data_store.py      JSON persistence
config.py          shifts, weights, constraints
templates/         starter Google Sheet
```

---

<p align="center">
  <sub>Built by <a href="https://github.com/GuyYad00">Guy Yad Shalom</a> · <a href="https://github.com/Elilevy52">Eli Levy</a></sub>
</p>
