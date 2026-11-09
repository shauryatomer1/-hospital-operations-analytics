# Interview Preparation Pack

*Honesty note for interviews: say the data is synthetic, that you injected scenarios to test the method, and that the DAX was verified against SQL in the Power BI engine (64/64) and that the report was generated as a Power BI Project and reviewed in Desktop.*

## A. Resume bullets (ATS-friendly; no invented business outcomes)
1. **Healthcare operations analytics:** Designed an end-to-end hospital operations analytics solution (BRD, FRD, 18-KPI dictionary, user stories) on a 16,000-admission synthetic dataset covering admissions, bed occupancy, ED waiting times, doctor utilisation and 30-day readmissions; separated actual KPIs from proxy metrics and documented every assumption.
2. **SQL / data quality:** Built a normalised PostgreSQL schema with constraints, 7 reusable analytical views and 41 business-driven SQL queries (CTEs, window functions, conditional aggregation, percentiles, gaps-and-islands); automated 72 pandas and 37 SQL data-quality checks and reconciled 64 KPI comparisons between independent SQL and DAX-logic implementations.
3. **Power BI / recommendations:** Specified a star-schema Power BI model (4 facts, 5 dimensions, role-playing dates), 18 DAX measures with interval-based bed occupancy and a five-page executive-to-operational dashboard; translated findings into 10 prioritised, evidence-labelled recommendations with monitoring metrics for hospital management.

## B. Two-minute project explanation
"I built a hospital operations analytics project end to end. The business problem: a multi-specialty hospital had no single, trusted view of patient flow, bed capacity, ED waits, doctor workload and readmissions. I started as a BA - wrote the BRD, stakeholder analysis, user stories and a KPI dictionary, being strict about definitions: occupancy is occupied bed-days over staffed bed-days, not admissions over beds; ALOS uses completed stays only; readmission uses an eligible-discharge denominator.
Because I couldn't use real patient data, I built a simulation where beds are a finite resource, emergency admissions come from ED visits, and readmissions are derived - so relationships can't be impossible - and I injected realistic bottlenecks. I validated it with 72 automated tests, loaded it to PostgreSQL with constraints, wrote 41 SQL analyses and views, and designed a star-schema Power BI model with DAX measures. I reconciled each KPI between SQL and an independent replica of the DAX logic.
The analysis showed that averages hide the problem: 71% average occupancy, but General Medicine, ICU, Cardiology and Pulmonology are full on nearly half of all days while paediatrics and surgery have spare beds; ED waits are stable but admitted patients board for about 11 hours, rising as occupancy rises; discharges bunch on Mondays. I recommended flow actions first - weekend discharge, a bed-pressure protocol, ED evening staffing - before capacity, each with a metric to monitor. The limits: synthetic data, illustrative thresholds, and the Power BI file still needs building in Desktop."

## C. Detailed explanation (use for deeper rounds)
- **Problem:** fragmented data, wrong occupancy measure, no ED-to-ward visibility, averages hiding department differences.
- **Method:** requirements -> KPI definitions (actual vs proxy) -> simulation (finite beds, ED-linked emergency admissions, derived readmissions, seeded) -> cleaning with logged remediation -> PostgreSQL (PK/FK/CHECK/indexes) -> transformations (date dimension, department-day census) -> views -> 41 queries -> star schema + DAX -> reconciliation -> insights -> report.
- **Findings:** see `Business_Insights_Report.md` (14 insights, each with observation, data, impact, hypothesis, action, benefit, monitor).
- **Recommendations:** R1-R10 in `Management_Report.md` with owners, metrics, a phased roadmap, and pilots with controls.
- **What I'd do next:** build and verify the PBIX, add forecasting and richer data (closure reasons, discharge times).

---

## D. 15 Business Analyst questions
1. **How did you gather/define requirements without stakeholders?** Wrote assumed pain points as a hypothesis, derived requirements per stakeholder, mapped them to FR-IDs and KPIs, listed assumptions and risks - and would validate each in workshops.
2. **Why isn't occupancy admissions / beds?** Flow vs stock - unit mismatch, ignores stay length; correct is occupied bed-days / available staffed bed-days. Example: 15,865 admissions vs 106 beds would give "150" - meaningless.
3. **How did you treat cancelled and open admissions?** Cancelled: no bed, excluded from volume, ALOS, occupancy, reported separately. Open: counted in admissions and occupancy, excluded from ALOS/discharges/readmission cohort.
4. **What is an "eligible" readmission?** Discharged alive, not transferred out, full 30-day follow-up; unplanned = Emergency type (proxy). Right-censoring handled.
5. **Actual vs proxy KPIs?** Actual: recorded events (admissions, waits). Proxy: BOR (constant staffed beds), utilisation (consultation hours only), readmission (type-based), patients per doctor.
6. **How would you prevent KPI misuse?** Context panels, denominators, relative-position colours, aggregated doctor views, "illustrative" labels.
7. **A department head disputes the readmission rate. What do you do?** Show definition, denominator, case-mix (chronic diseases), cohort drill-through; propose risk adjustment; agree on a pilot.
8. **How did you prioritise recommendations?** Evidence strength, operational impact, effort, risk; quick wins first (discharge process, ED shift stagger), pilots with controls next.
9. **How do you separate facts from hypotheses?** Dedicated fields in every insight; summary table of established vs unproven.
10. **What data quality issues did you find and how handled?** 9 failing raw tests; fixed, quarantined or documented; 72/72 final; cleaning log.
11. **What is the biggest insight and why does it matter?** Averages hide concentrated pressure; ED boarding is an inpatient flow issue.
12. **How would you measure success of the discharge initiative?** Weekend discharge share, % before noon, GM full-days, boarding minutes; baseline same season; control ward.
13. **What are the limitations?** Synthetic, illustrative thresholds, no cost/nursing data, proxies; no causation.
14. **How would you handle privacy?** Pseudonymised IDs, no names, RLS by department, small-cell suppression, access logging, compliance review.
15. **How would you scale to real data?** Source-system extracts, nightly ETL, data contracts, incremental refresh, KPI governance board.

## E. 10 SQL questions (based on this project)
1. **Compute bed occupancy by department.** Join admissions to a date table on `date >= admission_date AND date < COALESCE(discharge_date, snapshot+1)`, group by department/date, divide sum of occupied by sum of staffed beds (Q17, `fact_dept_daily_census`).
2. **Why half-open interval `[admit, discharge)`?** Same-day turnover without double-counting; matches midnight census.
3. **Median ED wait?** `PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY wait)`; excludes NULL (LWBS).
4. **Find consecutive high-occupancy streaks.** Gaps-and-islands: `date - ROW_NUMBER() OVER (ORDER BY date)` as group key (Q18).
5. **30-day readmission rate with correct denominator.** Eligible index discharges LEFT JOIN readmissions; `AVG((days<=30)::int)` filtered by `followup_complete` (Q33/34).
6. **Month-over-month growth and moving average.** `LAG()` and `AVG() OVER (ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)` (Q5).
7. **Top 3 peak-occupancy days per department.** `ROW_NUMBER() OVER (PARTITION BY dept ORDER BY occupancy DESC)` then filter (Q21).
8. **Pivot months into columns.** Conditional aggregation `SUM(x) FILTER (WHERE month = 1)` (Q19).
9. **Detect overlapping stays in a bed.** `LAG(discharge) OVER (PARTITION BY bed ORDER BY admit)`; overlap where `admit < prev_end` (DQ-31).
10. **Avoid row multiplication when combining ED, admissions, and activity.** Aggregate each fact to the common grain (month, department) in CTEs, then join the aggregates (`vw_department_performance`).

## F. 10 Power BI / DAX questions
1. **Why a star schema with four facts?** Different grains; joining facts multiplies rows; shared dimensions give consistent filtering.
2. **How do you use admission and discharge dates with one calendar?** Active relationship on admission date, inactive on discharge date, `USERELATIONSHIP` in discharge measures.
3. **Write the occupied bed-days measure.** `SUMX(VALUES(DimDate[Date]), VAR d = DimDate[Date] RETURN CALCULATE(COUNTROWS(FactAdmissions), AdmissionDate <= d, BedReleaseDate > d, REMOVEFILTERS(DimDate)))`.
4. **Why `REMOVEFILTERS(DimDate)` inside the iterator?** Context transition would filter the fact to that single date through the relationship; we need the interval test instead.
5. **Why not bi-directional filtering?** Ambiguity and performance risks; not needed with dim->fact flow; use visual filters.
6. **How did you avoid ambiguous paths?** No dim-to-dim links; denormalised `DepartmentID` on activity and `BedType` on admissions.
7. **Median vs average in DAX?** `MEDIAN` ignores blanks; never average medians; ratio KPIs as ratio of sums.
8. **How is "vs previous period" computed?** `DATESBETWEEN` on equal-length preceding window with `REMOVEFILTERS(DimDate)` and the reporting-window flag; DATEADD alternative for fixed months.
9. **Configurable traffic-light thresholds?** What-if parameters + SWITCH measure returning hex codes used in conditional formatting.
10. **How do you validate DAX?** Independent pandas/SQL replicas and a checkpoint table; tolerance 1e-6.

## G. 5 business case questions
1. **ED waits are highest 5-9 pm. What do you do?** Check volume vs staffing by hour, stagger shifts, fast-track triage 4-5, early diagnostics; monitor median wait by hour and LWBS; compare to same weekdays.
2. **General Medicine is full 46% of days. Add beds?** First flow: discharge timing, outlying, long-stay review, surge triggers; check doctor headroom (78%); quantify closed-bed arithmetic; add beds only if demand growth persists.
3. **Cardiology readmission is 16.6%. Is it the worst department?** Not necessarily - chronic case-mix, not risk-adjusted; look at gap distribution, discharge type, follow-up pathways; pilot 72-hour calls with a control group.
4. **A surgeon asks why doctor utilisation is 84%.** Explain definition, proxy nature, saturated days; use for rostering, not appraisal; examine OT/clinic pattern.
5. **Management wants a 10% waiting-time reduction target.** Baseline by triage/hour, define denominators, separate demand effects (seasonality), pilot, set targets by triage, review monthly; avoid gaming (LWBS, reclassification).

## H. Likely follow-ups and honest answers
- *"Is this real data?"* No; simulated with documented injected scenarios.
- *"Did you build the Power BI file?"* Yes as a Power BI Project (TMDL model + 5-page report generated by script); I verified every KPI measure in the Desktop engine against SQL (64/64). Real Power BI screenshots of all five pages are in the repo; the `.pbix` (`powerbi/hospital_operations_dashboard.pbix`) is saved from Desktop.
- *"What would you change?"* Add forecasting and real closure/discharge-time data; risk-adjust readmissions.
