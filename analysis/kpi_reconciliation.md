# KPI Reconciliation: SQL vs DAX-logic (pandas)

Independent recomputation of every core KPI. **SQL** = queries on the PostgreSQL *base tables*; **Pandas** = a line-by-line replica of the DAX measure logic running on the Power BI import CSVs (`data/processed/powerbi`).  The DAX itself was verified in the Power BI Desktop engine (64/64, `analysis/powerbi_verification.md`); in any rebuilt report compare each card to the `Pandas_DAX_logic` column below (same values as `analysis/kpi_checkpoints.csv`).

**Result: 64 / 64 comparisons match** (tolerance 1e-6 relative).


### Scope: All (2023-2025)

| KPI | Pandas / DAX logic | SQL | Match |
|---|---:|---:|:---:|
| Total Admissions | 15,865.0000 | 15,865.0000 | ✅ |
| Total Unique Patients | 12,311.0000 | 12,311.0000 | ✅ |
| Total Discharges | 15,843.0000 | 15,843.0000 | ✅ |
| ALOS (days) | 4.9839 | 4.9839 | ✅ |
| Bed Occupancy Rate | 0.7069 | 0.7069 | ✅ |
| Occupied Bed-Days | 79,025.0000 | 79,025.0000 | ✅ |
| Staffed Bed-Days | 111,792.0000 | 111,792.0000 | ✅ |
| Avg ED Wait (min) | 50.8102 | 50.8102 | ✅ |
| Median ED Wait (min) | 41.2000 | 41.2000 | ✅ |
| ED Turnaround (min) | 308.1941 | 308.1941 | ✅ |
| 30-Day Readmission Rate | 0.0862 | 0.0862 | ✅ |
| Eligible Discharges | 14,655.0000 | 14,655.0000 | ✅ |
| Doctor Utilization | 0.7947 | 0.7947 | ✅ |
| Avg Daily Admissions | 14.4754 | 14.4754 | ✅ |
| Emergency Admission % | 0.6173 | 0.6173 | ✅ |
| Patients per Doctor | 212.2586 | 212.2586 | ✅ |

### Scope: 2023

| KPI | Pandas / DAX logic | SQL | Match |
|---|---:|---:|:---:|
| Total Admissions | 5,031.0000 | 5,031.0000 | ✅ |
| Total Unique Patients | 4,139.0000 | 4,139.0000 | ✅ |
| Total Discharges | 5,022.0000 | 5,022.0000 | ✅ |
| ALOS (days) | 4.9827 | 4.9827 | ✅ |
| Bed Occupancy Rate | 0.6736 | 0.6736 | ✅ |
| Occupied Bed-Days | 25,078.0000 | 25,078.0000 | ✅ |
| Staffed Bed-Days | 37,230.0000 | 37,230.0000 | ✅ |
| Avg ED Wait (min) | 49.6926 | 49.6926 | ✅ |
| Median ED Wait (min) | 40.3083 | 40.3083 | ✅ |
| ED Turnaround (min) | 269.8406 | 269.8406 | ✅ |
| 30-Day Readmission Rate | 0.0904 | 0.0904 | ✅ |
| Eligible Discharges | 4,791.0000 | 4,791.0000 | ✅ |
| Doctor Utilization | 0.7912 | 0.7912 | ✅ |
| Avg Daily Admissions | 13.7836 | 13.7836 | ✅ |
| Emergency Admission % | 0.6126 | 0.6126 | ✅ |
| Patients per Doctor | 71.3621 | 71.3621 | ✅ |

### Scope: 2024

| KPI | Pandas / DAX logic | SQL | Match |
|---|---:|---:|:---:|
| Total Admissions | 5,365.0000 | 5,365.0000 | ✅ |
| Total Unique Patients | 4,595.0000 | 4,595.0000 | ✅ |
| Total Discharges | 5,366.0000 | 5,366.0000 | ✅ |
| ALOS (days) | 4.8962 | 4.8962 | ✅ |
| Bed Occupancy Rate | 0.7033 | 0.7033 | ✅ |
| Occupied Bed-Days | 26,254.0000 | 26,254.0000 | ✅ |
| Staffed Bed-Days | 37,332.0000 | 37,332.0000 | ✅ |
| Avg ED Wait (min) | 53.0477 | 53.0477 | ✅ |
| Median ED Wait (min) | 43.1416 | 43.1417 | ✅ |
| ED Turnaround (min) | 309.4054 | 309.4054 | ✅ |
| 30-Day Readmission Rate | 0.0806 | 0.0806 | ✅ |
| Eligible Discharges | 5,076.0000 | 5,076.0000 | ✅ |
| Doctor Utilization | 0.7943 | 0.7943 | ✅ |
| Avg Daily Admissions | 14.6585 | 14.6585 | ✅ |
| Emergency Admission % | 0.6183 | 0.6183 | ✅ |
| Patients per Doctor | 79.2241 | 79.2241 | ✅ |

### Scope: 2025

| KPI | Pandas / DAX logic | SQL | Match |
|---|---:|---:|:---:|
| Total Admissions | 5,469.0000 | 5,469.0000 | ✅ |
| Total Unique Patients | 4,727.0000 | 4,727.0000 | ✅ |
| Total Discharges | 5,455.0000 | 5,455.0000 | ✅ |
| ALOS (days) | 5.0713 | 5.0713 | ✅ |
| Bed Occupancy Rate | 0.7438 | 0.7438 | ✅ |
| Occupied Bed-Days | 27,693.0000 | 27,693.0000 | ✅ |
| Staffed Bed-Days | 37,230.0000 | 37,230.0000 | ✅ |
| Avg ED Wait (min) | 49.6744 | 49.6744 | ✅ |
| Median ED Wait (min) | 40.2500 | 40.2500 | ✅ |
| ED Turnaround (min) | 341.1387 | 341.1387 | ✅ |
| 30-Day Readmission Rate | 0.0881 | 0.0881 | ✅ |
| Eligible Discharges | 4,788.0000 | 4,788.0000 | ✅ |
| Doctor Utilization | 0.7986 | 0.7986 | ✅ |
| Avg Daily Admissions | 14.9836 | 14.9836 | ✅ |
| Emergency Admission % | 0.6206 | 0.6206 | ✅ |
| Patients per Doctor | 81.5000 | 81.5000 | ✅ |
