#!/usr/bin/env python3
"""Builds analysis/exploratory_analysis.ipynb (then execute it with: jupyter nbconvert --to notebook --execute --inplace)."""
from pathlib import Path
import nbformat as nbf

nb = nbf.v4.new_notebook()
C = lambda s: nbf.v4.new_code_cell(s.strip("\n"))
M = lambda s: nbf.v4.new_markdown_cell(s.strip("\n"))
nb.cells = [
M("""# Hospital Operations Analytics - Exploratory Analysis
Excel-style inspection, profiling and preliminary analysis of the **cleaned** synthetic dataset (`data/processed`), done *before* the SQL/Power BI work to understand shape, quality and the first signals. All numbers are computed live from the CSVs.

> **Data note:** the dataset is synthetic (seed 42). Operational patterns and scenarios were injected deliberately by `scripts/generate_dataset.py`; findings demonstrate the analytical method, not real hospital performance."""),
C("""
import pandas as pd, numpy as np, matplotlib.pyplot as plt
from pathlib import Path
pd.options.display.float_format = '{:,.2f}'.format
plt.rcParams.update({'axes.spines.top': False, 'axes.spines.right': False, 'figure.dpi': 100, 'axes.titleweight': 'bold', 'axes.titlelocation': 'left'})
BLUE, TEAL, GREY, AMBER = '#1F5FA8', '#1A9E9A', '#B8C2CC', '#E6A117'
P = Path('..') / 'data' / 'processed'
T = {n: pd.read_csv(P / f'{n}.csv') for n in ['patients','admissions','departments','doctors','beds','emergency_visits','doctor_activity','readmissions']}
pd.DataFrame({'rows': {k: len(v) for k, v in T.items()}, 'columns': {k: v.shape[1] for k, v in T.items()}})
"""),
M("## 1. Profiling: nulls and domains\nNulls are expected only where the business logic says so (cancelled admissions have no bed/discharge; open stays have no discharge; LWBS visits have no consultation; ED-to-admission link is optional)."),
C("""
nulls = pd.concat({k: v.isna().sum()[v.isna().sum() > 0] for k, v in T.items()})
nulls.to_frame('null_count')
"""),
C("""
a = T['admissions']
print(a.admission_status.value_counts().to_string()); print()
print(pd.crosstab(a.admission_status, a.discharge_type.fillna('(none)')))
"""),
M("## 2. Referential and logical sanity (spot checks - the full 72-test suite is `scripts/validate_data.py`)"),
C("""
a['admission_date'] = pd.to_datetime(a.admission_date); a['discharge_date'] = pd.to_datetime(a.discharge_date)
bd = a[a.bed_id.notna()].merge(T['beds'], on='bed_id', suffixes=('', '_b'))
dd = a.merge(T['doctors'], on='doctor_id', suffixes=('', '_d'))
chk = {
 'admissions with unknown patient': (~a.patient_id.isin(T['patients'].patient_id)).sum(),
 'discharge before admission': (a.discharge_date < a.admission_date).sum(),
 'bed dept != admission dept': (bd.department_id != bd.department_id_b).sum(),
 'doctor dept != admission dept': (dd.department_id != dd.department_id_d).sum(),
 'readmissions with unknown admission': (~T['readmissions'].readmission_admission_id.isin(a.admission_id)).sum(),
}
pd.Series(chk, name='violations')
"""),
M("## 3. Admissions: volume, type, seasonality (reporting window 2023-2025)"),
C("""
w = a[(a.admission_status != 'Cancelled') & (a.admission_date >= '2023-01-01')]
m = w.groupby(w.admission_date.dt.to_period('M')).size()
fig, ax = plt.subplots(1, 2, figsize=(13, 3.6))
ax[0].plot(m.index.to_timestamp(), m.values, color=BLUE, lw=2); ax[0].set_title('Monthly admissions')
t = w.groupby([w.admission_date.dt.dayofweek, 'admission_type']).size().unstack().reindex(range(7)); t.index = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
t.plot.bar(stacked=True, ax=ax[1], color=[BLUE, TEAL, GREY]); ax[1].set_title('Weekday demand by admission type'); ax[1].legend(frameon=False); plt.xticks(rotation=0); plt.tight_layout(); plt.show()
print(w.admission_type.value_counts(normalize=True).round(3).to_dict())
"""),
M("## 4. Length of stay (completed stays only)"),
C("""
d = a[a.admission_status == 'Discharged'].copy(); d['los'] = (d.discharge_date - d.admission_date).dt.days
d = d.merge(T['departments'][['department_id','department_name']], on='department_id')
s = d.groupby('department_name').los.agg(['count','mean','median', lambda x: x.quantile(.9), 'max']); s.columns = ['stays','ALOS','median','P90','max']
s.sort_values('ALOS', ascending=False)
"""),
M("## 5. Bed occupancy - interval based (never admissions / beds)\nOccupied on day D when `admission_date <= D < discharge_date` (open stays run to the snapshot date). Staffed beds exclude `Closed` beds."),
C("""
days = pd.date_range('2023-01-01', '2025-12-31'); snap = pd.Timestamp('2026-01-01')
nc = a[a.admission_status != 'Cancelled'].copy(); nc['end'] = nc.discharge_date.fillna(snap)
staffed = T['beds'][T['beds'].bed_status != 'Closed'].groupby('department_id').size()
d64 = days.values.astype('datetime64[D]'); rows = []
for dep, g in nc.groupby('department_id'):
    ad, en = g.admission_date.values.astype('datetime64[D]'), g.end.values.astype('datetime64[D]')
    rows.append(pd.Series(((ad[None, :] <= d64[:, None]) & (en[None, :] > d64[:, None])).sum(1), index=days, name=dep))
occ = pd.concat(rows, axis=1)
bor = (occ.sum() / (staffed * len(days))).rename('BOR').to_frame().join(T['departments'].set_index('department_id').department_name)
bor['share_of_days_>=85%'] = ((occ / staffed) >= .85).mean().round(3)
print('Hospital BOR =', round(occ.values.sum() / (staffed.sum() * len(days)), 4))
bor.sort_values('BOR', ascending=False)
"""),
C("""
hosp = occ.sum(axis=1) / staffed.sum()
fig, ax = plt.subplots(figsize=(13, 3.2)); ax.plot(hosp.index, hosp.values, color=BLUE, lw=.9); ax.axhline(.85, color=AMBER, ls='--')
ax.set_title('Daily hospital occupancy (amber = illustrative 85% High threshold)'); plt.show()
print('Weekday occupancy (0=Mon):', hosp.groupby(hosp.index.dayofweek).mean().round(3).to_dict())
"""),
M("## 6. Emergency department"),
C("""
e = T['emergency_visits']
for c in ['arrival_datetime', 'consultation_datetime', 'disposition_datetime']: e[c] = pd.to_datetime(e[c])
e = e[e.arrival_datetime >= '2023-01-01'].copy()
e['wait'] = (e.consultation_datetime - e.arrival_datetime).dt.total_seconds() / 60; e['tat'] = (e.disposition_datetime - e.arrival_datetime).dt.total_seconds() / 60
print(f"visits={len(e):,}  mean wait={e.wait.mean():.1f}  median={e.wait.median():.1f}  turnaround={e.tat.mean():.0f}  LWBS={(e.disposition_type == 'Left Without Being Seen').mean():.1%}")
fig, ax = plt.subplots(1, 3, figsize=(14, 3.4))
h = e.groupby(e.arrival_datetime.dt.hour).agg(v=('wait', 'size'), w=('wait', 'mean'))
ax[0].bar(h.index, h.v, color=BLUE); ax[0].set_title('Arrivals by hour')
ax[1].plot(h.index, h.w, color=TEAL, lw=2); ax[1].set_title('Avg wait (min) by hour')
e.groupby('triage_level').wait.mean().plot.bar(ax=ax[2], color=BLUE); ax[2].set_title('Avg wait by triage'); plt.tight_layout(); plt.show()
e.groupby('disposition_type').tat.agg(['count', 'mean', 'median']).sort_values('count', ascending=False)
"""),
M("## 7. Readmissions (30-day, eligible discharges only)"),
C("""
r = T['readmissions']
elig = d[~d.discharge_type.isin(['Deceased', 'Transferred to Another Facility']) & (d.discharge_date >= '2023-01-01') & (d.discharge_date + pd.Timedelta(days=30) <= '2025-12-31')].copy()
back = set(r[r.days_between_admissions <= 30].original_admission_id); elig['r30'] = elig.admission_id.isin(back)
print(f"eligible discharges={len(elig):,}  30-day readmissions={elig.r30.sum():,}  rate={elig.r30.mean():.2%}")
elig.groupby('department_name').r30.agg(['size', 'sum', 'mean']).rename(columns={'size': 'eligible', 'sum': 'readmitted', 'mean': 'rate'}).sort_values('rate', ascending=False)
"""),
M("## 8. Doctor utilisation"),
C("""
da = T['doctor_activity'].merge(T['doctors'], on='doctor_id').merge(T['departments'][['department_id', 'department_name']], on='department_id')
da = da[da.activity_date >= '2023-01-01']
u = da.groupby('department_name')[['patient_consultation_hours', 'scheduled_hours']].sum(); u['utilisation'] = u.iloc[:, 0] / u.iloc[:, 1]
print('Hospital utilisation =', round(u.iloc[:, 0].sum() / u.iloc[:, 1].sum(), 4)); u.sort_values('utilisation', ascending=False)
"""),
M("""## 9. What this tells us / next steps
* Bed pressure is concentrated in a handful of departments (section 5) while others run well below capacity - a *distribution* problem rather than a hospital-wide shortage.
* ED waits are shaped by hour of day and triage level; turnaround of **admitted** patients is dominated by waiting for a ward bed.
* Readmission rates vary strongly by department and must always be read with their denominators (section 7).
* The formal, reconciled KPIs and the 41 SQL analyses are in `database/` and `analysis/sql_results/`; insights are in `documentation/Business_Insights_Report.md`."""),
]
nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
out = Path(__file__).resolve().parent.parent / "analysis" / "exploratory_analysis.ipynb"
nbf.write(nb, out)
print("wrote", out)
