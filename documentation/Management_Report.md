# Hospital Operations: Performance Assessment & Optimization Opportunities
*Management report | Reporting period Jan 2023 - Dec 2025 | Prepared by the Business Analytics team*

> **Portfolio disclaimer:** the hospital and all data are synthetic; operational scenarios were injected to demonstrate analysis. Figures are real outputs of the reconciled SQL analysis on that data. Evidence is separated from hypothesis throughout; no causal claim is made. Detailed evidence: `Business_Insights_Report.md`.

## 1. Executive summary
Over three years the hospital admitted **15,865** patients (12,311 individuals) and ran at an average **70.7%** bed occupancy, with a median ED wait of **41 minutes** and a 30-day unplanned readmission rate of **8.6%**. Averages are comfortable; **the distribution is not**:

1. **Pressure is concentrated.** General Medicine (86% occupancy; full on 46% of days), ICU, Cardiology and Pulmonology (82-84%) run at or near capacity, while Pediatrics (52%), OB/GYN (56%), Oncology (60%) and General Surgery (61%) have the spare beds.
2. **Demand is rising, stays are not lengthening.** Admissions grew 8.7% in two years and occupancy rose from 67.4% to 74.4% with a flat ALOS (4.98 days) - growth is eating the remaining slack.
3. **The ED's biggest issue is at the back door.** Front-door waits are stable (mean ~50 min; evening peak 60 min), but admitted patients spend **11 hours** in the ED on average (P90 35 h) and ED turnaround rose **26%** from 2023 to 2025 as occupancy rose.
4. **Discharge timing and ED peaks are mismatched with demand:** 22.5% of discharges happen on Mondays (Sunday 9.5%), and 32% of ED arrivals come between 17:00 and 21:00 when waits double versus night.
5. **Quality and workload are uneven, not uniformly poor:** readmissions are 15-17% in Cardiology/Pulmonology/Oncology (chronic case-mix) but 3-5% in surgical/obstetric services; doctor utilisation ranges from 63% (Oncology) to 86% (Pulmonology, 3 doctors).

**Recommendation in one line:** fix *flow and allocation* before adding capacity - weekend/early discharge, a bed-pressure protocol for Medicine and ICU, ED evening staffing and boarding management - then plan targeted capacity (Medicine, Cardiology, Pulmonology) for the next 24 months.

## 2. Key findings
| Area | Finding (fact) | Evidence |
|---|---|---|
| Volume | 5,031 / 5,365 / 5,469 admissions in 2023 / 2024 / 2025; 61.7% emergency; 14.5 admissions per day | Q05, Q38 |
| Efficiency | ALOS 4.98 days overall; ICU and Neurology 6.9 vs Pediatrics 3.1; 3-10% of stays > 14 days in GM/ICU/Neurology | Q12 |
| Capacity | BOR 70.7%; GM 86.1%, Cardiology 83.8%, ICU 83.4%, Pulmonology 82.1% | Q17 |
| ED | Median wait 41.2 min; evening 60 min; triage 3 within target only 28.5% (illustrative target) | Q22-Q24 |
| Flow | Admitted ED patients: 666 min mean turnaround; consult-to-ward 553 -> 798 min as occupancy rises | Q25, Q28 |
| Quality | 30-day readmission 8.6%; 16.6% Cardiology; LAMA 18.1% | Q33-Q35 |
| Resources | Utilisation 63-86% by department; GM: beds full, doctors have headroom | Q30, Q39 |

## 3. Department performance (context before judgement)
| Department | Admissions | ALOS (d) | Occupancy | 30-d readmit | Doctor util. | Context |
|---|---:|---:|---:|---:|---:|---|
| General Medicine | 2,582 | 5.9 | **86%** | 10.2% | 78% | 78% emergency; seasonal Jul-Sep peak 94-97% |
| General Surgery | 2,386 | 3.9 | 61% | 4.8% | 84% | 41% elective; spare beds, busy surgeons |
| Cardiology | 2,270 | 4.9 | **84%** | **16.6%** | 83% | chronic heart disease case-mix |
| OB/GYN | 1,867 | 3.3 | 56% | 3.4% | 75% | scheduled/delivery pathway; short stays |
| Pediatrics | 1,832 | 3.1 | 52% | 5.4% | 76% | strong Aug peak (73%) |
| Orthopedics | 1,255 | 6.3 | 65% | 3.7% | 81% | 46% elective |
| ICU | 1,054 | 6.9 | **83%** | 5.6% | 83% | 84% via ED; 13.9% mortality (case-mix) |
| Pulmonology | 984 | 6.4 | **82%** | **15.5%** | **86%** | 3 doctors, 1 closed bed |
| Oncology | 821 | 5.6 | 60% | 14.5% | 63% | 29% referral; light doctor load |
| Neurology | 814 | 6.9 | 74% | 10.2% | 69% | long stays; 1 closed bed |
*(Rates are not risk-adjusted; a high readmission rate or volume is not by itself evidence of poor performance. Source: `vw_department_performance`, Q11, Q12, Q17, Q30, Q34.)*

## 4. Capacity constraints
- **At capacity:** ICU, Pulmonology, General Medicine and Cardiology are at 100% on 44-49% of days. In 7-12 bed units a single patient decides whether the unit is "full".
- **Closed beds:** four of 106 beds are unstaffed; on the *same* demand, reopening Pulmonology's closed bed would lower its occupancy from 82% to 72%, and Neurology's from 74% to 64% (arithmetic, not a forecast).
- **Spare capacity:** ~17 average free beds in Pediatrics, OB/GYN, Surgery and Oncology versus ~2 in General Medicine - but ward-type rules limit flexibility.
- **Trajectory:** +4 occupancy points per year; hospital-wide average occupancy would approach 80% in about a year at the same slope (illustration only).

## 5. Emergency department bottlenecks
- **Peak:** 17-21h = 32% of arrivals, average wait 60 min vs 32 min at night; LWBS 3.0-3.6% in the evening vs 1.1-1.8% mornings.
- **Handover dip:** waits rise at 14-15h although arrivals dip.
- **Monday:** +27% visits vs other days and the longest waits (57.9 min).
- **Triage 2-3** miss illustrative targets most (48% / 28% on target).
- **Sep-Nov 2024 spike:** waits +25% while visits were lower than in September - a capacity, not demand, signature.
- **Boarding:** 20% of admitted patients spend > 12 h in the ED (13% > 24 h); worst for ICU, Medicine, Pulmonology and Cardiology admissions (850-935 min vs ~300 min for surgery/obstetrics).

## 6. Resource utilisation
Doctor utilisation 79.5% overall; Pulmonology 86% (49% of doctor-days saturated) and the ED 83% (66% saturated) vs Oncology 63% and Neurology 69%. General Medicine is a *flow* constraint (beds 86%, doctors 78%), Pulmonology a *staffing* constraint. Utilisation counts consultation hours only (proxy).

## 7. Recommendations
| # | Recommendation | Owner | Evidence | Metric to monitor |
|---|---|---|---|---|
| R1 | Weekend discharge cover + discharge-before-noon target + Monday early huddle | Ops Manager | Insight 5 | Weekend discharge share; % discharges before noon |
| R2 | Bed-pressure protocol (surge triggers at 90% for medicine/ICU; governed outlying to surgical beds) | Ops Manager / Bed Mgmt | Insights 1, 2, 4 | Days >= 90%; outlier safety indicators |
| R3 | Review and re-open the closed Pulmonology isolation bed; record closure reasons | CEO / Nursing | Insight 3 | Staffed beds; days at capacity |
| R4 | ED: staggered evening shift (16:30-23:00), overlap at handover, early diagnostics for triage 2-3 | ED Manager | Insights 6, 7 | Median wait 17-21h; % within target; LWBS |
| R5 | ED boarding KPI shared with wards; > 4 h boarding triggers bed huddle | ED + Ops Managers | Insight 9 | % admitted out of ED in 4/12 h |
| R6 | Transitional care for Cardiology/Pulmonology/Oncology (72-h call, 7-day clinic), LAMA counselling | Dept Heads / Quality | Insight 10 | 7- and 30-day readmission (pilot vs control) |
| R7 | Rebalance doctor rosters: Pulmonology cross-cover/4th doctor; Oncology/Neurology spare capacity to clinics | Dept Heads | Insight 11 | Utilisation; saturated doctor-days |
| R8 | 24-month capacity plan by department; schedule planned downtime in low-demand windows | CEO / Ops | Insights 12, 13 | Rolling growth, BOR by dept |
| R9 | Case management for patients with >= 3 admissions | Quality | Insight 14 | Cohort bed-days |
| R10 | Data: closure reasons, step-down readiness, discharge time-of-day, planned/unplanned flag | Analytics / IT | Limitations | Data completeness |

## 8. Suggested implementation roadmap
| Phase | Timing | Actions | Gate / success check |
|---|---|---|---|
| 0 Foundation | Weeks 0-4 | Sign off KPI definitions; deploy dashboard and monthly pack; add missing data fields (R10) | KPIs reconciled; stakeholders trained |
| 1 Quick wins | Months 1-3 | R1 discharge process; R4 ED shift stagger; R5 boarding huddle; R3 bed review | Weekend discharge share up; evening median wait down vs same-weekday baseline |
| 2 Pilots | Months 3-6 | R6 transitional-care pilot (with control cohort); R2 outlying policy pilot on one ward; R7 roster changes | Pilot metrics vs baseline; safety indicators unchanged |
| 3 Scale | Months 6-12 | Roll out successful pilots; surge plan before Jul-Sep | Full-days in GM/ICU reduced; boarding minutes reduced |
| 4 Plan | Months 9-24 | Department capacity plan; forecasting; cost per bed-day | Board decision on capacity |
Improvements are claimed only after monitoring metrics show change against a baseline or control; seasonality (Jul-Sep) must be controlled for.

## 9. Risks and caveats
Synthetic data; illustrative thresholds; unplanned readmission proxied by admission type; staffed beds assumed constant; no cost or nursing data; correlation is not causation.
