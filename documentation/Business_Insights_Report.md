# Business Insights Report

> **Read this first.** The dataset is **synthetic** and several operational scenarios were injected on purpose (surges, an OT shutdown, an ED staffing gap, a weekend discharge dip - see `data/data_dictionary.md`). The insights below are real *outputs of the analysis on that data* and demonstrate the method; they are **not** findings about a real hospital.
> Every number is from the reconciled SQL results (`analysis/sql_results/Qnn`, cited per insight). **Observation/Evidence = fact in the data. Root cause = hypothesis** (the data cannot prove causation). No claim is made that any action *caused* an improvement - benefits are expectations to be verified by the monitoring metric.
> Illustrative thresholds: occupancy High >= 85%, Critical >= 95%; ED wait targets 5/15/30/60/120 min by triage. Window 2023-01..2025-12.

**Headline KPIs (2023-25):** 15,865 admissions · 12,311 unique patients · ALOS 4.98 days · bed occupancy 70.7% · ED median wait 41.2 min (mean 50.8) · ED turnaround 308 min · 30-day readmission 8.6% · doctor utilisation 79.5%.

| # | Insight (one line) | Domain |
|---|---|---|
| 1 | General Medicine is chronically full and peaks hard in Jul-Sep | Capacity |
| 2 | Four small units run at or near 100% on ~half of all days | Capacity |
| 3 | Closed beds explain a large part of the pressure in two units | Capacity |
| 4 | Pediatrics, OB/GYN, Surgery, Oncology carry the spare beds | Resource allocation |
| 5 | Discharges bunch on Mondays while Monday demand is highest | Flow |
| 6 | ED arrivals peak 17-21h and waits double vs night; handover dip at 14-16h | ED |
| 7 | Triage 2 and 3 miss the (illustrative) targets most | ED |
| 8 | A waiting-time spike in Sep-Nov 2024 happened while volume was *lower* | ED |
| 9 | The ED "back door" is the problem: boarding of admitted patients, rising with occupancy | ED / inpatient flow |
| 10 | Readmissions concentrate in three departments, LAMA discharges and ages 45-74 | Quality |
| 11 | Doctor workload is uneven: Pulmonology/ED saturated, Oncology/Neurology light; GM has beds pressure but doctor headroom | Staffing |
| 12 | Demand grew 8.7% in two years, occupancy +7 pts, ALOS flat | Trend |
| 13 | Planned OT downtime (Mar 2024) removed ~30% of surgical/ortho admissions, then rebounded | Planning |
| 14 | 6% of patients use 17% of bed-days | Care management |

---

## Insight 1 - General Medicine is chronically full and peaks sharply in Jul-Sep
| | |
|---|---|
| **1. Observation (fact)** | General Medicine has the highest occupancy of any department and spends most days above the High band. |
| **2. Supporting data** | BOR **86.1%** (15,103 / 17,536 bed-days); **64.1%** of days >= 85% and **45.9%** of days at 100% (16/16 beds) (Q17, `vw_bed_occupancy`). Monthly BOR: Jan 73%, Jun 88%, **Jul 94%, Aug 93%, Sep 96.5%** (Q19). Avg free beds 2.2. |
| **3. Business impact** | Little buffer for emergency arrivals (77.8% of GM admissions are emergencies, Q9, so load cannot be scheduled away); GM admissions boarded **~895 min** in the ED (Insight 9). |
| **4. Root-cause hypothesis** | Seasonal infectious/monsoon demand (Q19 shape) on a 16-bed unit with ALOS 5.9 days (above the hospital 4.98) and weekend discharge delays (Insight 5). Not tested: staffing/nursing constraints, delays to diagnostics. |
| **5. Recommended action** | (a) Monsoon surge plan triggered when GM occupancy exceeds 90% for 2 days; (b) discharge-before-noon target and weekend discharge cover for GM; (c) review of the >14-day long stays (3.1% of GM stays, Q12) for avoidable delay; (d) agree outlying rules for GM overflow to other adult wards. |
| **6. Expected benefit** | Fewer days at 100% and shorter ED boarding for medical patients - to be measured, not assumed. |
| **7. Monitor** | % days >= 90% occupancy (GM); GM discharges before noon; GM consult-to-ward minutes; ALOS and long-stay share. |

## Insight 2 - Four small units are completely full on roughly half of all days
| | |
|---|---|
| **1. Observation** | ICU, Pulmonology, General Medicine and Cardiology hit 100% occupancy on 44-49% of days. |
| **2. Supporting data** | Days at 100% (Q17-derived, `vw_bed_occupancy`): Critical Care **48.5%**, Pulmonology **48.0%**, General Medicine 45.9%, Cardiology 44.3%. BOR: GM 86.1%, Cardiology 83.8%, ICU 83.4%, Pulmonology 82.1%. ICU/Pulmonology have 8 staffed beds (7 for Pulmonology), Cardiology 12. |
| **3. Business impact** | In 7-12 bed units one extra patient flips the unit to "full": surge absorption depends on single beds; ICU is 84% emergency-sourced (Q41) so cannot defer admissions. |
| **4. Hypothesis** | Small-unit arithmetic (granularity) plus emergency dependence; an ICU step-down bottleneck is plausible - ICU ALOS 6.9 days (median 5, P90 15, 10.3% > 14 days, Q12) but the data has no step-down/transfer-readiness field to confirm. |
| **5. Action** | Add a step-down readiness flag to the data; daily "ready-to-move" review for ICU stays > 7 days; define surge-bed rules for ICU/Pulmonology; report occupancy for units <= 10 beds as "days at capacity", not only a percentage. |
| **6. Benefit** | Earlier release of ICU beds; fewer capacity-driven diversions (ED 'Transferred' disposition 3.3% of visits includes diversions - cannot be separated in this data). |
| **7. Monitor** | % days at capacity; ICU stays > 7 days with a ready-to-move flag; ICU refusals/diversions (new field). |

## Insight 3 - Closed (unstaffed) beds account for much of the pressure in Pulmonology and Neurology
| | |
|---|---|
| **1. Observation** | Four beds are `Closed`: Pulmonology 1 (isolation), Neurology 1, Oncology 1, Orthopedics 1 (private) - the capacity denominator for occupancy excludes them. |
| **2. Data** | Pulmonology BOR 82.1% on 7 staffed beds; on all 8 physical beds the *same* demand would be **71.9%** (6,300 / 8,768 bed-days). Neurology 73.6% -> **64.4%** with its 8th bed (5,646 / 8,768). Arithmetic on identical bed-days - not a forecast. |
| **3. Impact** | Two of the four units with the most 100% days (Pulmonology) or highest LOS (Neurology) operate one bed short. |
| **4. Hypothesis** | Closures reflect staffing/maintenance decisions made when demand was lower (2023 BOR 67%); no closure-reason data to confirm. |
| **5. Action** | Re-evaluate the closed Pulmonology isolation bed first. Add a *closure reason / date* field to `beds`; review staffing cost vs boarding cost. |
| **6. Benefit** | Reduced full-days in Pulmonology if the extra bed is staffed (to be verified). |
| **7. Monitor** | Staffed vs physical beds per unit; % days at capacity; ED boarding for Pulmonology admissions. |

## Insight 4 - Spare capacity sits in Pediatrics, OB/GYN, General Surgery and Oncology
| | |
|---|---|
| **1. Observation** | Four departments average well under 65% occupancy. |
| **2. Data** | BOR: Pediatrics **52.3%** (avg 4.8 free beds), OB/GYN **56.4%** (4.4 free), Oncology **59.5%**, General Surgery **60.6%** (5.5 free), Orthopedics 65.3% (3.8 free) (Q17, avg free beds from `vw_bed_occupancy`). Only 11-12% of Pediatrics/OB/GYN days are >= 85%. Pediatrics does peak at **72.9% in Aug** (Q19; Aug-2024 surge z = +2.9, Q40). |
| **3. Impact** | Fixed capacity (and staff) is idle while medical units are full; the hospital-wide average of ~30 free beds is misleading because the free beds are in the wrong specialities. |
| **4. Hypothesis** | Capacity was sized for peak/seasonality or historical case-mix; ward type constraints (maternity/paediatric beds cannot be used by adults) limit flexibility. |
| **5. Action** | Surgical/orthopaedic ward beds are adult beds: consider a governed "medical outlier" policy using surgical beds when GM > 90%; evaluate converting some Pediatric beds to flexible/overflow use outside Jul-Sep (clinical governance and nurse competency required); do not reduce capacity without reviewing peaks. |
| **6. Benefit** | Lower GM full-days and ED boarding without new beds (to be tested in a pilot). |
| **7. Monitor** | GM days >= 90%; number of medical outliers; outlier patient LOS and safety indicators (falls, readmissions); surgical elective cancellations (must not rise). |

## Insight 5 - Discharges bunch on Mondays while Monday is the busiest day for demand
| | |
|---|---|
| **1. Observation** | Monday carries 22.5% of all discharges (index 1.57 vs average); Sunday 9.5% (0.66) and Saturday 12.2% (0.85) (Q14). Monday is also the peak for admissions (3,059 vs 2,394-2,575 on Tue-Fri, Q8; Mon-Fri elective admissions 544-830) and ED visits (6,214, +27% vs the Tue-Sun average of ~4,910; avg wait 57.9 min vs 46.5-51.4, Q-ED weekday). Monday has the **lowest** end-of-day occupancy (66.3% vs 73.5% Thursday, Q20). |
| **2. Data** | Q8, Q14, Q20 as above. |
| **3. Impact** | Beds are released *during* Monday while the demand surge arrives *early Monday*: supply lags demand; ED waits and LWBS (2.7% vs 1.9-2.4%) are worst on Monday. |
| **4. Hypothesis** | Reduced weekend discharge capacity (pharmacy, transport, senior review) pushes discharges to Monday - known mechanism, **injected in this simulation**; in real data a test would be discharge time-of-day and reasons. |
| **5. Action** | Weekend discharge coordinator, weekend pharmacy/TTO cover, "weekend ready" discharge planning on Fridays; Monday early-discharge huddle. |
| **6. Benefit** | Flatter discharge profile; more free beds on Monday morning (to be measured). |
| **7. Monitor** | Discharge share by weekday (target: Sat/Sun >= 85% of weekday average); % discharges before noon; Monday ED boarding minutes. |

## Insight 6 - ED arrivals peak 17-21h; waits double vs night; shift-handover dip
| | |
|---|---|
| **1. Observation** | 31.8% of arrivals come in 17-21h. |
| **2. Data** | Average wait **60.0 min** in 17-21h vs **32.1 min** at 0-6h (Q24). Arrivals peak at 19h (2,529 visits, 7.1%). A second wait bump at 14-15h (57 min vs 46.7 at 13h) although arrivals dip. LWBS rate 3.0-3.6% at 18-21h vs 1.1-1.8% at 8-9h. |
| **3. Impact** | Longer waits and patients leaving unseen in the evening - a safety and reputation risk. |
| **4. Hypothesis** | Staffing not aligned to the evening peak; the 14-16h bump is consistent with handover/lunch gaps (injected in simulation; real cause needs rota data). |
| **5. Action** | Shift start staggering: add a clinician from 16:30-23:00; protect handover with overlapping shifts; consider an evening fast-track for triage 4-5. |
| **6. Benefit** | Lower evening median wait and LWBS (measure vs same weekdays pre-change). |
| **7. Monitor** | Median wait by hour block; LWBS % by hour; % seen within target in 17-21h. |

## Insight 7 - Triage 2 and 3 miss the illustrative targets most often
| | |
|---|---|
| **1. Observation** | Urgent (3) patients are far from the target; emergent (2) patients often just miss it. |
| **2. Data** | Seen within target (illustrative): L1 **81.9%** (5 min), **L2 48.3%** (15 min), **L3 28.5%** (30 min), L4 52.5% (60 min), L5 85.2% (120 min); L3 avg 49.6 min, P90 88 min; L3 = 40% of visits (Q23). |
| **3. Impact** | The largest, clinically meaningful group (L3) waits longest relative to target; targets are illustrative - the pattern (L2/L3 worst) is the point. |
| **4. Hypothesis** | Single-stream flow; L3 patients queue behind sicker patients and wait for cubicle/investigations. |
| **5. Action** | Review whether the L3 target is realistic; introduce early diagnostics (point-of-care tests/X-ray ordered at triage), a rapid-assessment area for L2/L3. |
| **6. Benefit** | Higher share seen within target for L2/L3 (to be measured). |
| **7. Monitor** | % within target by triage; P90 wait L2/L3. |

## Insight 8 - Sep-Nov 2024 waiting-time spike occurred while volume was lower
| | |
|---|---|
| **1. Observation** | Average wait rose ~25% for three months and then returned to baseline in Dec 2024. |
| **2. Data** | Avg wait Sep **61.3**, Oct **62.7**, Nov **62.3** min vs 49-51 in adjacent months; P90 121-125 vs ~100 (Q22). Seen visits fell in Oct (956) and Nov (921) from 1,087 in Sep - lower volume, higher waits. |
| **3. Impact** | Access deteriorated without a demand explanation. |
| **4. Hypothesis** | A temporary capacity/staffing shock in the ED (vacancies, leave, locums) - **injected as scenario S4**; with real data you would test rota fill rate and clinician-hours per visit. Demand surge is *not* supported by the data. |
| **5. Action** | Track clinician hours per 100 visits as a leading indicator; trigger agency/locum cover when median wait exceeds baseline +15% for 2 weeks. |
| **6. Benefit** | Faster detection/response to capacity shocks. |
| **7. Monitor** | Median wait vs 12-month baseline; clinician hours per 100 visits; vacancy rate. |

## Insight 9 - The ED's problem is the "back door": boarding of admitted patients
| | |
|---|---|
| **1. Observation** | Admitted patients spend far longer in the ED than anyone else, and the gap widens as the hospital fills. |
| **2. Data** | Avg turnaround **666 min (11.1 h)** for admitted vs 171 min for discharged-home (Q25); P90 **35 h**; 19.7% of admitted patients stay > 12 h, 13.4% > 24 h. Consultation-to-ward time by hospital-occupancy band: <70% **553 min** -> 70-79% 674 -> 80-84% 714 -> 85%+ **798** (+44%) (Q28). By admitting dept (Q41): ICU 935, GM 895, Pulmonology 870, Cardiology 854 min vs OB/GYN 291, Surgery 316. Year trend: ED turnaround **270 -> 308 -> 340 min** (2023-25, +26%) while the *mean wait* stayed 49.7 / 53.0 / 49.7 and occupancy rose 67.4% -> 74.4%. |
| **3. Impact** | ED crowding and patient-experience risk even though front-door waits look stable; ED staff and cubicles are tied up by inpatients. |
| **4. Hypothesis** | Inpatient bed availability in the full units (Insights 1-3) drives boarding; ED process is not the main lever. Correlation of daily occupancy with boarding is weak (r = 0.10, Q28) - the effect is in the high-occupancy tail. |
| **5. Action** | Hospital-wide flow: ED boarding > 4 h triggers a bed huddle; reserve ICU/medical beds each morning from planned discharges; report boarding by admitting department monthly (shared KPI between ED and wards). |
| **6. Benefit** | Shorter ED stay for admitted patients; freed ED capacity (measure). |
| **7. Monitor** | % admitted patients out of ED within 4/12 h; consult-to-ward minutes by department; ED turnaround (admitted). |

## Insight 10 - Readmissions concentrate in three departments, LAMA discharges and ages 45-74
| | |
|---|---|
| **1. Observation** | Hospital 30-day unplanned readmission **8.6%** (1,264 / 14,655), but 4x variation by department. |
| **2. Data** | Cardiology **16.6%** (n = 2,088), Pulmonology **15.5%** (895), Oncology **14.5%** (709), vs surgical/obstetric 3.4-4.8% (Q34). *Left Against Medical Advice* **18.1%** vs 8.3% routine home (Q35, n = 310). Ages 45-74: 10.8-11.8% vs 4.9-6.8% under 45. 41% of readmissions occur within 7 days, 75% within 14 days (Q35). About 75-80% return to the same department; Cardiology -> General Medicine 10.5% (Q36). |
| **3. Impact** | Repeat admissions consume bed-days in already-full units (Cardiology, Pulmonology). |
| **4. Hypothesis** | Chronic-disease case-mix (heart failure, COPD, cancer complications) rather than poor care - **do not rank these departments as poor performers**; early-week return suggests transition-of-care gaps; LAMA patients leave before stabilisation. |
| **5. Action** | 72-hour post-discharge call and 7-day clinic slot for Cardiology/Pulmonology/Oncology; LAMA counselling and safety-net plan; case-mix-adjust before external comparison. |
| **6. Benefit** | Fewer early readmissions (to be tested via pilot vs control). |
| **7. Monitor** | 7-day and 30-day readmission rate for the pilot cohort vs matched baseline; LAMA rate; share of readmissions to GM. |

## Insight 11 - Doctor workload is uneven; GM has bed pressure but doctor headroom
| | |
|---|---|
| **1. Observation** | Utilisation ranges from 63% to 86% across departments. |
| **2. Data** | Pulmonology **86.4%** (3 doctors; 49% of doctor-days saturated; >= 85% in 26 of 36 months), General Surgery 84.2%, Cardiology 82.8%, ICU 82.8%, Emergency Medicine 82.7% (65.8% of doctor-days saturated) vs Neurology 69.1%, **Oncology 62.9%** (Q30, Q32). Resource-alignment (Q39): GM has the highest bed pressure (86%) but doctor utilisation only 78.1% -> classed 'bed pressure, doctors have headroom' (a *flow/discharge* problem, not a doctor-shortage problem); Pulmonology is the opposite ('doctor pressure', 86.4% utilisation, BOR 82%). |
| **3. Impact** | Overload risk in a 3-doctor unit (single-point-of-failure on leave); under-use elsewhere. |
| **4. Hypothesis** | Roster sized to historical, not current, workload; small pools amplify absence (5% absence assumed in data). Consultation hours exclude non-clinical work, so true loads are higher; utilisation is a proxy. |
| **5. Action** | Cross-cover pool between Pulmonology and General Medicine; review Pulmonology to 4 doctors or add a visiting-consultant session; do not reassign across specialties without competency review; Oncology/Neurology spare capacity -> outpatient clinics. |
| **6. Benefit** | More balanced utilisation and resilience (to be measured). |
| **7. Monitor** | Utilisation by department/month; saturated doctor-days %; leave-cover incidents. |

## Insight 12 - Demand grows, stays are not longer: occupancy is rising
| | |
|---|---|
| **1. Observation** | Volume and occupancy rise while ALOS is flat. |
| **2. Data** | Admissions **5,031 -> 5,365 -> 5,469** (2023-25; +6.6%, +1.9%; +8.7% over two years); occupancy **67.4% -> 70.3% -> 74.4%**; ALOS 4.98 / 4.90 / 5.08; ED visits 11,155 -> 11,978 -> 12,546 (Q38, `vw_monthly_hospital_kpis`). |
| **3. Impact** | Growth is absorbing the remaining slack - at the same slope (+4 pts/year; an illustration, not a forecast) occupancy would approach 80% within roughly a year and critical units would have even less buffer. |
| **4. Hypothesis** | Volume (not stay length) is driving bed-days: growth is demand-led. |
| **5. Action** | 24-month capacity plan by department (Medicine, Cardiology first), including closed-bed reopening and discharge-flow actions before building beds. |
| **6. Benefit** | Capacity added where demand is, not hospital-wide. |
| **7. Monitor** | Rolling 12-month admissions growth; BOR by department; forecast vs actual. |

## Insight 13 - Planned OT downtime removed ~30% of surgical admissions, then a rebound followed
| | |
|---|---|
| **1. Observation** | March 2024 admissions fell sharply in the two surgical departments only. |
| **2. Data** | General Surgery **52** vs ~72 average of Jan-Feb/Apr-May 2024 (-28%); Orthopedics **26** vs ~37 (-30%); the cancellation rate itself is unremarkable (2.95%, within a 1.5-3.9% monthly range in 2024, Q15) - the effect shows in *volume*, not cancellations; the next month shows a catch-up (General Surgery z = +2.3 in Apr 2024, Q40). No other department changed. |
| **3. Impact** | Lost/deferred activity during a 2-week downtime; the rebound loads wards in April (hospital BOR 75.8% in Apr 2024, the highest month of 2024). |
| **4. Hypothesis** | Deferred electives re-booked into April (injected scenario S3). |
| **5. Action** | Schedule maintenance in low-demand windows; staged re-booking plan to avoid rebound peaks; track elective backlog. |
| **6. Benefit** | Less lost activity and smoother occupancy after planned downtime. |
| **7. Monitor** | Elective cancellations and backlog; occupancy in the 4 weeks after downtime. |

## Insight 14 - A small group of patients drives a large share of bed-days
| | |
|---|---|
| **1. Observation** | Repeat admitters are few but heavy users. |
| **2. Data** | 720 patients (5.8%) with >= 3 admissions use **17.0%** of bed-days (13,369); 1,727 patients with exactly two admissions use 22.6% (Q37). Frequent patients average age 49-55 and use ~2-3 different departments. |
| **3. Impact** | Fragmented care across departments for the same patients. |
| **4. Hypothesis** | Chronic multi-morbidity; no single owner of the pathway. |
| **5. Action** | Case-management for patients with 3+ admissions in 12 months; cross-department care plans. |
| **6. Benefit** | Fewer avoidable admissions (measure via cohort comparison). |
| **7. Monitor** | Admissions per frequent patient; bed-days of the cohort; 30-day readmission within the cohort. |

---

## Facts vs hypotheses - summary
| Established by the data | Hypotheses needing further evidence |
|---|---|
| Occupancy by department/day/month; days at capacity | Why GM/Pulmonology are full (staffing, discharge delays, diagnostics) |
| ED waits by hour, triage, month; boarding minutes by department/occupancy | Whether the Sep-Nov 2024 spike was staffing/vacancies |
| Discharge profile by weekday | Why discharges bunch on Mondays (process vs. clinical) |
| Readmission rates, gaps, flows | Whether readmissions are avoidable; case-mix effect |
| Utilisation (consultation / scheduled hours) | True workload incl. non-clinical work |

## Limitations of these insights
Synthetic data with injected scenarios; one hospital; no cost, nurse, theatre or OPD data; illustrative thresholds; unplanned readmission proxied by Emergency admission type; staffed beds assumed constant; correlations are descriptive.
