# Stakeholder Analysis

*Fictional engagement; interests are plausible assumptions to be validated in workshops.*

## 1. Stakeholder register
| Stakeholder | Role in project | Key questions | What they need from the solution | Influence | Interest | Engagement approach |
|---|---|---|---|:-:|:-:|---|
| **Hospital CEO / Management** | Sponsor, decision-maker | Is the hospital efficient? Where is pressure? Are we improving? | Executive page, monthly pack, comparisons vs previous period, clear recommendations | High | High | Monthly review; one-page summary; decision log |
| **Operations Manager** | Business owner, daily user | When is demand highest? Which departments constrain flow? | Admission/discharge trends, occupancy, discharge-day pattern, resource alignment | High | High | Weekly working session; co-design Pages 2-3 |
| **Department Heads** | Consumers; accountable for department KPIs | How do we compare, fairly? | Department matrix with context (case-mix, denominators), doctor load | Medium-High | High | Pre-read of definitions; agree interpretation guardrails |
| **Doctors** | Subjects of utilisation measures | Will this be used against me? | Transparent definitions; workload fairness; no individual league tables in shared views | Medium | Medium | Communicate purpose; aggregate by department by default |
| **Nursing Staff** | Operate wards | How full will my ward be? | Occupancy by ward, surge warnings, discharge timing | Medium | Medium | Ward-level view; feedback loop |
| **Bed Management Team** | Daily bed allocation | Where are free beds? When will beds free up? | Census, high-occupancy periods, peak days, discharge pattern | Medium | High | Daily huddle use; Page 3 owner |
| **Emergency Department Manager** | Owner of ED KPIs | Which hours/triage categories need staff? Is boarding my problem or the wards'? | Hourly arrivals, waits by triage, LWBS, turnaround of admitted patients | High | High | Co-design Page 5; staffing scenarios |
| **Data / Business Analyst** | Builder/maintainer | Is the data right and reproducible? | Pipeline, documentation, validation, reconciliation | Medium | High | Own backlog and definitions |
| IT / Data owner (assumed) | Source systems | Data extracts, refresh | Clear extract specs, nightly schedule | Medium | Low | Technical handover |
| Compliance / Privacy officer (assumed) | Governance | Patient privacy | Pseudonymised data, RLS, small-cell rules | High | Low-Medium | Review before go-live |

## 2. Power / interest grid
- **Manage closely:** CEO, Operations Manager, ED Manager.
- **Keep satisfied:** Compliance officer, IT.
- **Keep informed:** Department heads, Bed Management, Nursing, Doctors (but doctors are high-sensitivity - engage early).

## 3. Requirements by stakeholder (traceability)
| Stakeholder | Requirements |
|---|---|
| CEO | FR-01, FR-04, FR-08, FR-14, FR-16, FR-19 |
| Operations Manager | FR-01-FR-07, FR-16, FR-17 |
| Department Heads | FR-07, FR-11-FR-14, FR-17 |
| Doctors | FR-11 (workload fairness), NFR privacy |
| Nursing | FR-04, FR-05, FR-06 |
| Bed Management | FR-04-FR-06, FR-16 (weekday/discharge) |
| ED Manager | FR-08-FR-10, FR-15 |
| Analyst | FR-02, BR-01..BR-10, validation suite |

## 4. Potential conflicts and how to handle them
| Conflict | Handling |
|---|---|
| Management wants rankings; department heads fear unfair comparison | Matrix shows relative position with context, denominators and case-mix notes; no "worst department" labels |
| ED sees boarding as a ward problem; wards see ED as over-admitting | Shared metric: consultation-to-ward time by admitting department (Q41) as neutral evidence |
| Doctors vs management on utilisation | Utilisation framed as capacity planning, aggregated at department/shift level; consultation hours excluded from performance appraisal |
| Bed managers want real-time; project is batch | State refresh latency on every page; roadmap item for daily refresh |

## 5. Communication plan
Weekly: Operations Manager + Bed Management (Pages 2-3). Monthly: management pack (CEO), KPI deep-dive per department. Ad hoc: ED staffing review (Page 5). All reports carry the data-freshness stamp and the actual/proxy KPI tags.
