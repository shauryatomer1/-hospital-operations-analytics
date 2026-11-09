#!/usr/bin/env python3
"""Generates documentation/SQL_Analysis_Documentation.md from database/analytical_queries.sql and the executed results."""
import csv
import glob
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
text = (ROOT / "database" / "analytical_queries.sql").read_text(encoding="utf-8")
parts = re.split(r"(?m)^-- @(Q\d+)\s*\|\s*(.*)$", text)
TECH = [("CTE", r"\bWITH\b"), ("Window function", r"\bOVER\s*\("), ("CASE", r"\bCASE\b"), ("Conditional aggregation", r"\bFILTER\s*\(\s*WHERE"),
        ("Subquery", r"\(\s*SELECT\b"), ("JOIN", r"\bJOIN\b"), ("Date functions", r"MAKE_DATE|EXTRACT\(|DATE_TRUNC|INTERVAL"),
        ("Percentile", r"PERCENTILE_CONT"), ("UNION ALL", r"UNION ALL"), ("ROLLUP", r"ROLLUP"), ("Gaps-and-islands", r"ROW_NUMBER\(\) OVER \(ORDER BY census_date\)")]
SECTIONS = {"Q01": "A. Patient analysis", "Q06": "B. Admission and discharge analysis", "Q16": "C. Bed utilisation", "Q22": "D. Emergency operations",
            "Q29": "E. Doctor utilisation", "Q33": "F. Readmissions", "Q38": "G. Cross-functional / root-cause"}
out = ["# SQL Analysis Documentation", "",
       "41 queries in `database/analytical_queries.sql`, executed on PostgreSQL 16 against the cleaned dataset (all run without error; results saved in `analysis/sql_results/`). Every query lists its **business purpose** and the **decision it supports**.",
       "", "Run: `python scripts/load_database.py --steps queries` (embedded PostgreSQL) or paste any block into psql/pgAdmin. Views used: `vw_patient_admission_summary`, `vw_bed_occupancy`, `vw_readmission_analysis`, `vw_emergency_performance`, `vw_doctor_utilization`, `vw_department_performance`, `vw_monthly_hospital_kpis`.", "",
       "## Techniques coverage", ""]
body, counts = [], {t: 0 for t, _ in TECH}
for i in range(1, len(parts), 3):
    qid, title, blk = parts[i], parts[i + 1].strip(), parts[i + 2]
    if qid in SECTIONS: body += ["", f"## {SECTIONS[qid]}", ""]
    purpose = re.search(r"-- Purpose : (.*)", blk); decision = re.search(r"-- Decision: (.*)", blk)
    sql = "\n".join(l for l in blk.splitlines() if not l.startswith("--")).strip()
    tech = [t for t, rx in TECH if re.search(rx, sql, re.I)]
    for t in tech: counts[t] += 1
    body += [f"### {qid} - {title}", f"- **Business purpose:** {purpose.group(1) if purpose else ''}", f"- **Decision supported:** {decision.group(1) if decision else ''}",
             f"- **SQL techniques:** {', '.join(tech)}"]
    f = glob.glob(str(ROOT / "analysis" / "sql_results" / f"{qid}_*.csv"))
    if f:
        rows = list(csv.reader(open(f[0], encoding="utf-8")))
        hdr, data = rows[0][:8], rows[1:5]
        body += [f"- **Result preview** ({len(rows) - 1} rows):", "", "| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
        body += ["| " + " | ".join(c[:28] for c in r[:8]) + " |" for r in data]
    body += ["", "```sql", sql, "```", ""]
out += ["| Technique | Queries using it |", "|---|---|"] + [f"| {t} | {n} |" for t, n in counts.items()]
out += body
out += ["", "## Reading guide / pitfalls handled", "",
        "- **Occupancy** is always occupied bed-days / staffed bed-days from admission/discharge intervals - never admissions / beds, never `bed_status`.",
        "- **ALOS/discharges** use `Discharged` status only; open stays and cancelled requests are separated.",
        "- **Readmission** uses eligible discharges with a complete 30-day window; denominators are shown.",
        "- **Calendar spine** (`dim_date`) used wherever zero-count days/months must stay visible.",
        "- **No fact-to-fact joins that multiply rows** (ED, activity and admissions are aggregated separately before comparison)."]
(ROOT / "documentation" / "SQL_Analysis_Documentation.md").write_text("\n".join(out) + "\n", encoding="utf-8")
print("wrote documentation/SQL_Analysis_Documentation.md", counts)
