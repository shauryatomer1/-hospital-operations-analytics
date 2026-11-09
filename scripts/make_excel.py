#!/usr/bin/env python3
"""Builds analysis/excel_data_inspection.xlsx - the Excel layer of the project (inspection, cleaning log, preliminary
analysis and KPI validation). Growth, rate and PASS/FAIL cells are live Excel formulas, not pasted values."""
import glob
from pathlib import Path
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import CellIsRule

ROOT = Path(__file__).resolve().parent.parent
RAW, PROC, RES = ROOT / "data" / "raw", ROOT / "data" / "processed", ROOT / "analysis" / "sql_results"
HDR = PatternFill("solid", fgColor="1F5FA8"); HF = Font(bold=True, color="FFFFFF")
TABLES = ["patients", "admissions", "departments", "doctors", "beds", "emergency_visits", "doctor_activity", "readmissions"]


def header(ws, row=1):
    for c in ws[row]:
        c.fill, c.font, c.alignment = HDR, HF, Alignment(wrap_text=True, vertical="center")


def widths(ws, w=None):
    for i, col in enumerate(ws.columns, 1):
        ws.column_dimensions[get_column_letter(i)].width = (w or {}).get(i, min(48, max(10, max(len(str(c.value or "")) for c in col) + 2)))


def sheet_from_df(wb, name, df):
    ws = wb.create_sheet(name); ws.append(list(df.columns))
    for r in df.itertuples(index=False): ws.append(list(r))
    header(ws); ws.freeze_panes = "A2"; widths(ws); return ws


wb = Workbook(); ws = wb.active; ws.title = "README"
for line in ["Hospital Operations Analytics - Excel inspection workbook",
             "Sheets: Data_Profile (raw vs processed row counts, nulls) | Cleaning_Log | Monthly_KPIs (formulas) | Dept_Scorecard (formulas) | KPI_Validation (formula PASS/FAIL)",
             "Synthetic data (seed 42). Values come from the PostgreSQL views / reconciliation script; the ratio, growth and PASS/FAIL columns are Excel formulas.",
             "Excel is used for inspection and sanity checks; SQL and Power BI remain the system of record."]:
    ws.append([line])
ws["A1"].font = Font(bold=True, size=14); ws.column_dimensions["A"].width = 150

# --- Data_Profile
rows = []
for t in TABLES:
    raw, pro = pd.read_csv(RAW / f"{t}.csv"), pd.read_csv(PROC / f"{t}.csv")
    rows.append(dict(table=t, raw_rows=len(raw), processed_rows=len(pro), rows_removed=None, columns=pro.shape[1],
                     raw_null_cells=int(raw.isna().sum().sum()), processed_null_cells=int(pro.isna().sum().sum()),
                     expected_null_reason={"admissions": "bed/discharge null for cancelled & open stays", "emergency_visits": "consultation null for LWBS; admission_id null if not admitted"}.get(t, "none expected")))
ws = sheet_from_df(wb, "Data_Profile", pd.DataFrame(rows))
for r in range(2, ws.max_row + 1): ws[f"D{r}"] = f"=B{r}-C{r}"

sheet_from_df(wb, "Cleaning_Log", pd.read_csv(PROC / "cleaning_log.csv"))

# --- Monthly KPIs with formulas
m = pd.read_csv(glob.glob(str(RES / "Q38_*.csv"))[0])[["year_month", "admissions", "discharges", "alos_days", "bed_occupancy_rate", "median_wait_min", "avg_turnaround_min", "readmission_rate_30d", "doctor_utilization_rate"]]
ws = sheet_from_df(wb, "Monthly_KPIs", m)
ws["J1"], ws["K1"], ws["L1"] = "Admission growth MoM", "Net flow (adm - dis)", "Cumulative net flow"; header(ws)
for r in range(2, ws.max_row + 1):
    ws[f"J{r}"] = f'=IF(ROW()=2,"",B{r}/B{r-1}-1)' if r > 2 else ""
    ws[f"K{r}"] = f"=B{r}-C{r}"; ws[f"L{r}"] = f"=SUM(K$2:K{r})"
    ws[f"J{r}"].number_format = "0.0%"; ws[f"E{r}"].number_format = "0.0%"; ws[f"H{r}"].number_format = "0.0%"; ws[f"I{r}"].number_format = "0.0%"
last = ws.max_row + 2
ws[f"A{last}"], ws[f"B{last}"], ws[f"C{last}"] = "Total / average", f"=SUM(B2:B{ws.max_row-2})", f"=SUM(C2:C{ws.max_row-2})"
ws[f"E{last}"] = f"=AVERAGE(E2:E{ws.max_row-2})"; ws[f"E{last}"].number_format = "0.0%"; widths(ws)

# --- Dept scorecard with formulas (inputs from SQL, ratios as formulas)
b = pd.read_csv(glob.glob(str(RES / "Q17_*.csv"))[0])[["department_name", "occupied_bed_days", "staffed_bed_days"]]
d = pd.read_csv(glob.glob(str(RES / "Q30_*.csv"))[0])[["department_name", "scheduled_hours", "consultation_hours"]]
rd = pd.read_csv(glob.glob(str(RES / "Q34_*.csv"))[0])[["department_name", "eligible_discharges", "readmissions_30d"]]
x = b.merge(d, on="department_name", how="left").merge(rd, on="department_name", how="left")
ws = sheet_from_df(wb, "Dept_Scorecard", x)
for col, t in zip("HIJK", ["Bed occupancy rate", "Occupancy band", "Doctor utilisation", "30-day readmission rate"]):
    ws[f"{col}1"] = t
ws["M1"], ws["N1"] = "BOR high threshold (illustrative)", 0.85
ws["M2"], ws["N2"] = "BOR critical threshold (illustrative)", 0.95
for r in range(2, ws.max_row + 1):
    ws[f"H{r}"] = f"=B{r}/C{r}"; ws[f"I{r}"] = f'=IF(H{r}>=$N$2,"Critical",IF(H{r}>=$N$1,"High","Normal"))'
    ws[f"J{r}"] = f'=IFERROR(E{r}/D{r},"")'; ws[f"K{r}"] = f'=IFERROR(G{r}/F{r},"")'
    for c in "HJK": ws[f"{c}{r}"].number_format = "0.0%"
header(ws); widths(ws)
ws.conditional_formatting.add(f"H2:H{ws.max_row}", CellIsRule(operator="greaterThanOrEqual", formula=["$N$1"], fill=PatternFill("solid", bgColor="F8D49A")))

# --- KPI validation (formula-based)
k = pd.read_csv(ROOT / "analysis" / "kpi_checkpoints.csv")
ws = sheet_from_df(wb, "KPI_Validation", k[["Scope", "KPI", "Pandas_DAX_logic", "SQL"]])
ws["E1"], ws["F1"] = "Abs. difference", "Match"; header(ws)
for r in range(2, ws.max_row + 1):
    ws[f"E{r}"] = f"=ABS(C{r}-D{r})"; ws[f"F{r}"] = f'=IF(E{r}<=MAX(0.000000001,0.000001*ABS(D{r})),"PASS","FAIL")'
ws[f"H1"], ws["I1"] = "Passed", f'=COUNTIF(F2:F{ws.max_row},"PASS")&" / "&COUNTA(F2:F{ws.max_row})'
widths(ws)

out = ROOT / "analysis" / "excel_data_inspection.xlsx"
wb.save(out); print("wrote", out)
