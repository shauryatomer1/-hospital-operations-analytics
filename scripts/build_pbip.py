"""Generate the Power BI Project (PBIP) for the Hospital Operations dashboard.

Writes powerbi/HospitalOperations.pbip + .SemanticModel (TMDL) + .Report (PBIR).
Open the .pbip in Power BI Desktop, then File > Save as to produce a .pbix.

The model (tables, M queries, relationships, 18 KPI measures) is generated from the
specs in powerbi/*.md.  Visuals follow powerbi/dashboard_build_guide.md.
"""
from __future__ import annotations
import json, shutil, sys, hashlib
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
PBI = ROOT / "powerbi"
NAME = "HospitalOperations"
SM = PBI / f"{NAME}.SemanticModel"
RP = PBI / f"{NAME}.Report"
DATA = ROOT / "data" / "processed" / "powerbi"
BASE_THEME_SRC = Path(r"C:\Program Files\Microsoft Power BI Desktop\bin\WebView2Resources\minerva\sharedresources\BaseThemes\CY26SU10.json")
BASE_THEME = "CY26SU10"


def w(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def j(path: Path, obj):
    w(path, json.dumps(obj, indent=2))


# ------------------------------------------------------------------ tables
# (name, M type, tmdl dataType, options)
T, N, I, D, B, DT = "type text", "type number", "Int64.Type", "type date", "type logical", "type datetime"
tm = {T: "string", N: "double", I: "int64", D: "dateTime", B: "boolean", DT: "dateTime"}

TABLES = {
    "DimDate": ("DimDate.csv", [
        ("Date", D), ("DateKey", I), ("Year", I), ("Quarter", I), ("QuarterLabel", T), ("MonthNumber", I),
        ("MonthName", T), ("MonthShort", T), ("YearMonth", T), ("YearMonthSort", I), ("MonthStart", D),
        ("WeekStart", D), ("ISOWeek", I), ("DayOfMonth", I), ("DayOfWeekNumber", I), ("DayName", T),
        ("DayShort", T), ("IsWeekend", B), ("InReportingWindow", B)]),
    "DimPatients": ("DimPatients.csv", [
        ("PatientID", T), ("Age", I), ("AgeGroup", T), ("Gender", T), ("City", T), ("PatientType", T),
        ("RegistrationDate", D)]),
    "DimDepartments": ("DimDepartments.csv", [
        ("DepartmentID", T), ("DepartmentName", T), ("DepartmentCategory", T), ("DepartmentCapacity", I),
        ("StaffedBeds", I), ("HasInpatientBeds", B)]),
    "DimDoctors": ("DimDoctors.csv", [
        ("DoctorID", T), ("DoctorName", T), ("DepartmentID", T), ("Specialization", T), ("EmploymentType", T),
        ("Shift", T)]),
    "DimBeds": ("DimBeds.csv", [
        ("BedID", T), ("DepartmentID", T), ("BedType", T), ("BedStatus", T), ("IsStaffed", B)]),
    "FactAdmissions": ("FactAdmissions.csv", [
        ("AdmissionID", T), ("PatientID", T), ("AdmissionDate", D), ("DischargeDate", D), ("AdmissionType", T),
        ("DepartmentID", T), ("DoctorID", T), ("BedID", T), ("DiagnosisCategory", T), ("AdmissionStatus", T),
        ("DischargeType", T), ("IsCompleted", B), ("IsCancelled", B), ("IsOpenStay", B), ("IsAdmission", B),
        ("LOSDays", I), ("BedReleaseDate", D), ("InReportingWindow", B), ("AdmissionSeq", I),
        ("IsReadmissionEligible", B), ("FollowupComplete", B), ("BedType", T), ("Readmitted30d", B),
        ("IsUnplannedReadmission30d", B), ("FromED", B)]),
    "FactEmergencyVisits": ("FactEmergencyVisits.csv", [
        ("EmergencyVisitID", T), ("PatientID", T), ("ArrivalDateTime", DT), ("ArrivalDate", D), ("ArrivalHour", I),
        ("TriageLevel", I), ("TriageLabel", T), ("TargetWaitMin", I), ("ConsultationDateTime", DT),
        ("DispositionDateTime", DT), ("DispositionType", T), ("DepartmentID", T), ("AdmissionID", T),
        ("WaitMinutes", N), ("TurnaroundMinutes", N), ("ConsultToDispositionMinutes", N), ("IsLWBS", B),
        ("IsAdmitted", B), ("MetWaitTarget", I), ("InReportingWindow", B)]),
    "FactDoctorActivity": ("FactDoctorActivity.csv", [
        ("ActivityID", T), ("DoctorID", T), ("DepartmentID", T), ("ActivityDate", D), ("ScheduledHours", N),
        ("ConsultationHours", N), ("PatientsAttended", I), ("InReportingWindow", B)]),
    "FactReadmissions": ("FactReadmissions.csv", [
        ("ReadmissionID", T), ("PatientID", T), ("OriginalAdmissionID", T), ("ReadmissionAdmissionID", T),
        ("DaysBetweenAdmissions", I), ("IndexDepartmentID", T), ("ReadmitDepartmentID", T),
        ("IndexDischargeDate", D), ("ReadmitAdmissionDate", D), ("Within30Days", B)]),
}

KEYS = {"DimDate": "Date", "DimPatients": "PatientID", "DimDepartments": "DepartmentID",
        "DimDoctors": "DoctorID", "DimBeds": "BedID", "FactAdmissions": "AdmissionID",
        "FactEmergencyVisits": "EmergencyVisitID", "FactDoctorActivity": "ActivityID",
        "FactReadmissions": "ReadmissionID"}
SORT_BY = {("DimDate", "MonthName"): "MonthNumber", ("DimDate", "MonthShort"): "MonthNumber",
           ("DimDate", "YearMonth"): "YearMonthSort", ("DimDate", "DayName"): "DayOfWeekNumber",
           ("DimDate", "DayShort"): "DayOfWeekNumber"}
HIDDEN = {  # technical columns hidden in report view
    "DimDate": {"DateKey", "YearMonthSort", "MonthNumber", "DayOfWeekNumber", "MonthStart", "ISOWeek", "InReportingWindow", "DayOfMonth"},
    "DimPatients": {"PatientID", "RegistrationDate"},
    "DimDepartments": {"DepartmentID", "DepartmentCapacity", "StaffedBeds"},
    "DimDoctors": {"DoctorID", "DepartmentID"},
    "DimBeds": {"BedID", "DepartmentID", "IsStaffed"},
    "FactAdmissions": {"AdmissionID", "PatientID", "DepartmentID", "DoctorID", "BedID", "IsCompleted", "IsCancelled",
                       "IsOpenStay", "IsAdmission", "BedReleaseDate", "InReportingWindow", "AdmissionSeq",
                       "IsReadmissionEligible", "FollowupComplete", "Readmitted30d", "IsUnplannedReadmission30d"},
    "FactEmergencyVisits": {"EmergencyVisitID", "PatientID", "DepartmentID", "AdmissionID", "InReportingWindow",
                            "ConsultationDateTime", "DispositionDateTime", "IsLWBS", "IsAdmitted", "MetWaitTarget"},
    "FactDoctorActivity": {"ActivityID", "DoctorID", "DepartmentID", "InReportingWindow"},
    "FactReadmissions": {"ReadmissionID", "PatientID", "OriginalAdmissionID", "ReadmissionAdmissionID",
                         "IndexDepartmentID", "ReadmitDepartmentID"},
}
FMT = {D: "dd-mmm-yyyy", DT: "dd-mmm-yyyy hh:nn", I: "0", N: "0.0"}


def table_tmdl(tname: str) -> str:
    csv, cols = TABLES[tname]
    out = [f"table {tname}", ""]
    if tname == "DimDate":
        out.append("\tdataCategory: Time")
        out.append("")
    for cname, ctype in cols:
        out.append(f"\tcolumn {cname}")
        out.append(f"\t\tdataType: {tm[ctype]}")
        if ctype in FMT and not (cname.endswith("Key") or cname in ("Year", "Quarter", "ArrivalHour", "ISOWeek", "DayOfMonth")):
            out.append(f"\t\tformatString: {FMT[ctype]}")
        if KEYS.get(tname) == cname:
            out.append("\t\tisKey")
        if cname in HIDDEN.get(tname, ()):
            out.append("\t\tisHidden")
        out.append(f"\t\tsummarizeBy: none")
        out.append(f"\t\tsourceColumn: {cname}")
        if (tname, cname) in SORT_BY:
            out.append(f"\t\tsortByColumn: {SORT_BY[(tname, cname)]}")
        out.append("")
    typed = ", ".join('{"%s", %s}' % (c, t) for c, t in cols)
    out += [f"\tpartition {tname} = m", "\t\tmode: import", "\t\tsource =", "\t\t\t\tlet",
            f'\t\t\t\t    Source = Csv.Document(File.Contents(DataFolder & "{csv}"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
            "\t\t\t\t    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
            f'\t\t\t\t    Typed = Table.TransformColumnTypes(Promoted, {{{typed}}}, "en-US")',
            "\t\t\t\tin", "\t\t\t\t    Typed", ""]
    return "\n".join(out)


# ------------------------------------------------------------------ measures
INT, PCT, DEC1, DEC2 = "#,0", "0.0%", "0.0", "0.00"
M = []  # (name, folder, format, expr)


def m(name, folder, fmt, expr):
    M.append((name, folder, fmt, expr.strip("\n")))


m("Days in Period", "0 Support", INT, "COUNTROWS ( DimDate )")
m("Staffed Beds", "0 Support", INT, "CALCULATE ( COUNTROWS ( DimBeds ), DimBeds[IsStaffed] = TRUE () )")
m("Active Doctors", "0 Support", INT, "DISTINCTCOUNT ( FactDoctorActivity[DoctorID] )")
m("Total Admissions", "1 Volume", INT, "CALCULATE ( COUNTROWS ( FactAdmissions ), FactAdmissions[IsAdmission] = TRUE () )")
m("Cancelled Admission Requests", "1 Volume", INT, "CALCULATE ( COUNTROWS ( FactAdmissions ), FactAdmissions[IsCancelled] = TRUE () )")
m("Total Unique Patients", "1 Volume", INT, "CALCULATE ( DISTINCTCOUNT ( FactAdmissions[PatientID] ), FactAdmissions[IsAdmission] = TRUE () )")
m("Total Discharges", "1 Volume", INT, """
CALCULATE (
    COUNTROWS ( FactAdmissions ),
    FactAdmissions[IsCompleted] = TRUE (),
    USERELATIONSHIP ( DimDate[Date], FactAdmissions[DischargeDate] )
)""")
m("ALOS", "2 Efficiency", DEC2, """
CALCULATE (
    AVERAGE ( FactAdmissions[LOSDays] ),
    FactAdmissions[IsCompleted] = TRUE (),
    USERELATIONSHIP ( DimDate[Date], FactAdmissions[DischargeDate] )
)""")
m("Open Stays at Snapshot", "2 Efficiency", INT, "CALCULATE ( COUNTROWS ( FactAdmissions ), FactAdmissions[IsOpenStay] = TRUE () )")
m("Occupied Bed-Days", "3 Beds", INT, """
SUMX (
    VALUES ( DimDate[Date] ),
    VAR _d = DimDate[Date]
    RETURN
        CALCULATE (
            COUNTROWS ( FactAdmissions ),
            FactAdmissions[IsAdmission] = TRUE (),
            FactAdmissions[AdmissionDate] <= _d,
            FactAdmissions[BedReleaseDate] > _d,
            REMOVEFILTERS ( DimDate )
        )
)""")
m("Available Bed-Days", "3 Beds", INT, "[Staffed Beds] * [Days in Period]")
m("Bed Occupancy Rate", "3 Beds", PCT, "DIVIDE ( [Occupied Bed-Days], [Available Bed-Days] )")
m("Avg Daily Census", "3 Beds", DEC1, "DIVIDE ( [Occupied Bed-Days], [Days in Period] )")
m("Available Bed Count", "3 Beds", DEC1, "[Staffed Beds] - [Avg Daily Census]")
m("Beds Available Now (snapshot)", "3 Beds", INT, 'CALCULATE ( COUNTROWS ( DimBeds ), DimBeds[BedStatus] = "Available" )')
m("ED Visits", "4 Emergency", INT, "COUNTROWS ( FactEmergencyVisits )")
m("Avg ED Wait (min)", "4 Emergency", DEC1, "AVERAGE ( FactEmergencyVisits[WaitMinutes] )")
m("Median ED Wait (min)", "4 Emergency", DEC1, "MEDIAN ( FactEmergencyVisits[WaitMinutes] )")
m("ED Turnaround (min)", "4 Emergency", DEC1, "AVERAGE ( FactEmergencyVisits[TurnaroundMinutes] )")
m("ED Turnaround - Admitted (min)", "4 Emergency", DEC1,
  "CALCULATE ( AVERAGE ( FactEmergencyVisits[TurnaroundMinutes] ), FactEmergencyVisits[IsAdmitted] = TRUE () )")
m("LWBS Rate", "4 Emergency", PCT, "DIVIDE ( CALCULATE ( COUNTROWS ( FactEmergencyVisits ), FactEmergencyVisits[IsLWBS] = TRUE () ), [ED Visits] )")
m("ED Admit Rate", "4 Emergency", PCT, "DIVIDE ( CALCULATE ( [ED Visits], FactEmergencyVisits[IsAdmitted] = TRUE () ), [ED Visits] )")
m("% Seen within Target", "4 Emergency", PCT, """
DIVIDE (
    CALCULATE ( COUNTROWS ( FactEmergencyVisits ), FactEmergencyVisits[MetWaitTarget] = 1 ),
    CALCULATE ( COUNTROWS ( FactEmergencyVisits ), NOT ISBLANK ( FactEmergencyVisits[MetWaitTarget] ) )
)""")
m("Avg Wait Hour Index", "4 Emergency", DEC2,
  "DIVIDE ( [Avg ED Wait (min)], CALCULATE ( [Avg ED Wait (min)], REMOVEFILTERS ( FactEmergencyVisits[ArrivalHour] ) ) )")
m("Eligible Discharges", "5 Quality", INT, """
CALCULATE (
    COUNTROWS ( FactAdmissions ),
    FactAdmissions[IsReadmissionEligible] = TRUE (),
    FactAdmissions[FollowupComplete] = TRUE (),
    USERELATIONSHIP ( DimDate[Date], FactAdmissions[DischargeDate] )
)""")
m("Readmissions 30d", "5 Quality", INT, "CALCULATE ( [Eligible Discharges], FactAdmissions[Readmitted30d] = TRUE () )")
m("30-Day Readmission Rate", "5 Quality", PCT, "DIVIDE ( [Readmissions 30d], [Eligible Discharges] )")
m("Readmission Flow Count", "5 Quality", INT, "CALCULATE ( COUNTROWS ( FactReadmissions ), FactReadmissions[Within30Days] = TRUE () )")
m("Readmission Flow Count (to dept)", "5 Quality", INT, """
CALCULATE (
    COUNTROWS ( FactReadmissions ),
    FactReadmissions[Within30Days] = TRUE (),
    USERELATIONSHIP ( DimDepartments[DepartmentID], FactReadmissions[ReadmitDepartmentID] )
)""")
m("Doctor Utilization Rate", "6 Resources", PCT, "DIVIDE ( SUM ( FactDoctorActivity[ConsultationHours] ), SUM ( FactDoctorActivity[ScheduledHours] ) )")
m("Saturated Doctor-Days %", "6 Resources", PCT, """
DIVIDE (
    COUNTROWS ( FILTER ( FactDoctorActivity, FactDoctorActivity[ConsultationHours] >= 0.95 * FactDoctorActivity[ScheduledHours] ) ),
    COUNTROWS ( FactDoctorActivity )
)""")
m("Patients per Doctor", "6 Resources", DEC1, "DIVIDE ( [Total Unique Patients], [Active Doctors] )")
m("Patients Attended per Doctor-Day", "6 Resources", DEC1,
  "DIVIDE ( SUM ( FactDoctorActivity[PatientsAttended] ), COUNTROWS ( FactDoctorActivity ) )")
m("Prev Period Admissions", "7 Growth", INT, """
VAR _min = MIN ( DimDate[Date] )
VAR _max = MAX ( DimDate[Date] )
VAR _len = _max - _min + 1
RETURN
    CALCULATE (
        [Total Admissions],
        REMOVEFILTERS ( DimDate ),
        DATESBETWEEN ( DimDate[Date], _min - _len, _max - _len ),
        DimDate[InReportingWindow] = TRUE ()
    )""")
m("Admission Growth Rate", "7 Growth", PCT, "DIVIDE ( [Total Admissions] - [Prev Period Admissions], [Prev Period Admissions] )")
m("Prev Period Discharges", "7 Growth", INT, """
VAR _min = MIN ( DimDate[Date] )
VAR _max = MAX ( DimDate[Date] )
VAR _len = _max - _min + 1
RETURN
    CALCULATE (
        [Total Discharges],
        REMOVEFILTERS ( DimDate ),
        DATESBETWEEN ( DimDate[Date], _min - _len, _max - _len ),
        DimDate[InReportingWindow] = TRUE ()
    )""")
m("Discharge Growth Rate", "7 Growth", PCT, "DIVIDE ( [Total Discharges] - [Prev Period Discharges], [Prev Period Discharges] )")
m("Discharges Net Flow", "7 Growth", INT, "[Total Admissions] - [Total Discharges]")
m("Cancellation Rate", "7 Growth", PCT, "DIVIDE ( [Cancelled Admission Requests], [Total Admissions] + [Cancelled Admission Requests] )")
m("Peak Admission Day", "8 Peaks", "dd-mmm-yyyy", """
VAR _t = ADDCOLUMNS ( VALUES ( DimDate[Date] ), "Adm", [Total Admissions] )
VAR _mx = MAXX ( _t, [Adm] )
RETURN
    MINX ( FILTER ( _t, [Adm] = _mx ), DimDate[Date] )""")
m("Peak Day Admissions", "8 Peaks", INT, 'MAXX ( ADDCOLUMNS ( VALUES ( DimDate[Date] ), "Adm", [Total Admissions] ), [Adm] )')
m("Peak Weekday", "8 Peaks", "@", """
VAR _t = ADDCOLUMNS ( VALUES ( DimDate[DayName] ), "Adm", [Total Admissions] )
RETURN
    MAXX ( TOPN ( 1, _t, [Adm], DESC ), DimDate[DayName] )""")
m("Dept Load Share %", "9 Department", PCT, "DIVIDE ( [Occupied Bed-Days], CALCULATE ( [Occupied Bed-Days], ALLSELECTED ( DimDepartments ) ) )")
m("Dept Admission Share %", "9 Department", PCT, "DIVIDE ( [Total Admissions], CALCULATE ( [Total Admissions], ALLSELECTED ( DimDepartments ) ) )")
m("Avg Daily Admissions", "1 Volume", DEC1, "DIVIDE ( [Total Admissions], [Days in Period] )")
m("Emergency Admission %", "1 Volume", PCT,
  'DIVIDE ( CALCULATE ( [Total Admissions], FactAdmissions[AdmissionType] = "Emergency" ), [Total Admissions] )')
m("BOR High Threshold Value", "A Thresholds", PCT, "SELECTEDVALUE ( 'BOR High Threshold'[BOR High Threshold], 0.85 )")
m("BOR Critical Threshold Value", "A Thresholds", PCT, "SELECTEDVALUE ( 'BOR Critical Threshold'[BOR Critical Threshold], 0.95 )")
m("BOR Status", "A Thresholds", "@", """
SWITCH (
    TRUE (),
    ISBLANK ( [Bed Occupancy Rate] ), BLANK (),
    [Bed Occupancy Rate] >= [BOR Critical Threshold Value], "Critical",
    [Bed Occupancy Rate] >= [BOR High Threshold Value], "High",
    "Normal"
)""")
m("BOR Color", "A Thresholds", "@", """
SWITCH ( [BOR Status], "Critical", "#C0392B", "High", "#E6A117", "Normal", "#2E8B57", "#B8C2CC" )""")
m("Doctor Util Color", "A Thresholds", "@", """
VAR u = [Doctor Utilization Rate]
RETURN
    SWITCH ( TRUE (), ISBLANK ( u ), "#B8C2CC", u >= 0.95, "#C0392B", u >= 0.85, "#E6A117", u < 0.55, "#7FB3D5", "#2E8B57" )""")
m("KPI Delta Color", "A Thresholds", "@", 'IF ( [Admission Growth Rate] >= 0, "#1A9E9A", "#1F5FA8" )')
m("Reporting Note", "A Thresholds", "@",
  '"Synthetic data. Thresholds are illustrative operational thresholds - set by hospital policy."')


def measures_table_tmdl() -> str:
    out = ["table _Measures", ""]
    for name, folder, fmt, expr in M:
        nm = f"'{name}'" if not name.replace("_", "").isalnum() else name
        out.append(f"\tmeasure {nm} = ```")
        for line in expr.split("\n"):
            out.append("\t\t\t" + line)
        out.append("\t\t\t```")
        if fmt != "@":
            out.append(f"\t\tformatString: {fmt}")
        out.append(f"\t\tdisplayFolder: {folder}")
        out.append("")
    out += ["\tcolumn Dummy", "\t\tdataType: int64", "\t\tisHidden", "\t\tsummarizeBy: none", "\t\tsourceColumn: [Dummy]", "",
            "\tpartition _Measures = calculated", "\t\tmode: import", "\t\tsource = ROW ( \"Dummy\", 1 )", ""]
    return "\n".join(out)


def threshold_table(name: str) -> str:
    return "\n".join([
        f"table '{name}'", "",
        f"\tcolumn '{name}'", "\t\tdataType: double", "\t\tformatString: 0%", "\t\tsummarizeBy: none",
        f"\t\tsourceColumn: [{name}]", "",
        f"\tpartition '{name}' = calculated", "\t\tmode: import",
        f"\t\tsource = SELECTCOLUMNS ( GENERATESERIES ( 0.5, 1, 0.01 ), \"{name}\", [Value] )", ""])


REL = [  # (many col, one col, active)
    ("FactAdmissions.AdmissionDate", "DimDate.Date", True),
    ("FactAdmissions.DischargeDate", "DimDate.Date", False),
    ("FactEmergencyVisits.ArrivalDate", "DimDate.Date", True),
    ("FactDoctorActivity.ActivityDate", "DimDate.Date", True),
    ("FactReadmissions.ReadmitAdmissionDate", "DimDate.Date", True),
    ("FactReadmissions.IndexDischargeDate", "DimDate.Date", False),
    ("FactAdmissions.DepartmentID", "DimDepartments.DepartmentID", True),
    ("FactEmergencyVisits.DepartmentID", "DimDepartments.DepartmentID", True),
    ("FactDoctorActivity.DepartmentID", "DimDepartments.DepartmentID", True),
    ("FactReadmissions.IndexDepartmentID", "DimDepartments.DepartmentID", True),
    ("FactReadmissions.ReadmitDepartmentID", "DimDepartments.DepartmentID", False),
    ("DimBeds.DepartmentID", "DimDepartments.DepartmentID", True),
    ("FactAdmissions.DoctorID", "DimDoctors.DoctorID", True),
    ("FactDoctorActivity.DoctorID", "DimDoctors.DoctorID", True),
    ("FactAdmissions.PatientID", "DimPatients.PatientID", True),
    ("FactEmergencyVisits.PatientID", "DimPatients.PatientID", True),
    ("FactReadmissions.PatientID", "DimPatients.PatientID", True),
]


def uid(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()[:20]


def build_model():
    j(SM / "definition.pbism", {"version": "4.0", "settings": {}})
    w(SM / "definition" / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n")
    tables = list(TABLES) + ["_Measures", "BOR High Threshold", "BOR Critical Threshold"]
    refs = "\n".join(f"ref table {('' if t.replace('_','').isalnum() else chr(39))}{t}{('' if t.replace('_','').isalnum() else chr(39))}" for t in tables)
    w(SM / "definition" / "model.tmdl",
      "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n\tdiscourageImplicitMeasures\n"
      "\tsourceQueryCulture: en-US\n\n" + refs + "\n\nref expression DataFolder\n")
    folder = str(DATA) + "\\"
    w(SM / "definition" / "expressions.tmdl",
      'expression DataFolder = "%s" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n'
      "\tlineageTag: %s\n" % (folder.replace("\\", "\\\\") if False else folder, "2f1d0c1e-0000-4000-8000-000000000001"))
    out = []
    for i, (mc, oc, act) in enumerate(REL):
        out += [f"relationship {uid(mc + oc)}", f"\tfromColumn: {mc}", f"\ttoColumn: {oc}"]
        if not act:
            out.append("\tisActive: false")
        out.append("")
    w(SM / "definition" / "relationships.tmdl", "\n".join(out))
    for t in TABLES:
        w(SM / "definition" / "tables" / f"{t}.tmdl", table_tmdl(t))
    w(SM / "definition" / "tables" / "_Measures.tmdl", measures_table_tmdl())
    w(SM / "definition" / "tables" / "BOR High Threshold.tmdl", threshold_table("BOR High Threshold"))
    w(SM / "definition" / "tables" / "BOR Critical Threshold.tmdl", threshold_table("BOR Critical Threshold"))


# ------------------------------------------------------------------ report
SCH = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
INK, MUTED, BLUE, TEAL = "#1B2A3A", "#51606F", "#1F5FA8", "#1A9E9A"


def col(entity, prop):
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def meas(prop, entity="_Measures"):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def proj(field, active=True):
    kind = "Column" if "Column" in field else "Measure"
    ent = field[kind]["Expression"]["SourceRef"]["Entity"]
    prop = field[kind]["Property"]
    p = {"field": field, "queryRef": f"{ent}.{prop}", "nativeQueryRef": prop}
    if active:
        p["active"] = True
    return p


def lit(s):
    return {"expr": {"Literal": {"Value": s}}}


class Page:
    def __init__(self, pid, title):
        self.id, self.title, self.visuals, self.z = pid, title, [], 0

    def add(self, vtype, x, y, wd, ht, roles, title=None, objects=None, sort=None, extra=None, title_size=None):
        self.z += 1
        vid = uid(f"{self.id}-{self.z}")
        qs = {r: {"projections": [proj(f) for f in fs]} for r, fs in roles.items()}
        query = {"queryState": qs}
        if sort:
            query["sortDefinition"] = {"sort": [{"field": sort[0], "direction": sort[1]}], "isDefaultSort": True}
        visual = {"visualType": vtype, "query": query, "drillFilterOtherVisuals": True}
        if objects:
            visual["objects"] = objects
        if title:
            visual["visualContainerObjects"] = {"title": [{"properties": {
                "show": lit("true"), "text": lit("'" + title.replace("'", "''") + "'"),
                **({"fontSize": lit(title_size)} if title_size else {})}}]}
        obj = {"$schema": f"{SCH}/visualContainer/2.14.0/schema.json", "name": vid,
               "position": {"x": x, "y": y, "width": wd, "height": ht, "z": self.z * 100, "tabOrder": self.z * 100},
               "visual": visual}
        self.visuals.append((vid, obj))

    def text(self, x, y, wd, ht, runs, size="11pt", color=MUTED, bold=False, framed=False):
        self.z += 1
        vid = uid(f"{self.id}-t{self.z}")
        style = {"fontSize": size, "color": color}
        if bold:
            style["fontWeight"] = "bold"
        obj = {"$schema": f"{SCH}/visualContainer/2.14.0/schema.json", "name": vid,
               "position": {"x": x, "y": y, "width": wd, "height": ht, "z": self.z * 100, "tabOrder": self.z * 100},
               "visual": {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": [
                   {"textRuns": [{"value": runs, "textStyle": style}]}]}}]},
                   "visualContainerObjects": ({} if framed else {
                       "background": [{"properties": {"show": lit("false")}}],
                       "border": [{"properties": {"show": lit("false")}}]}),
                   "drillFilterOtherVisuals": True}}
        self.visuals.append((vid, obj))


def slicer(p, x, y, wd, ht, ent, prop, title, mode="Dropdown"):
    p.add("slicer", x, y, wd, ht, {"Values": [col(ent, prop)]}, title=title, title_size="9D",
          objects={"data": [{"properties": {"mode": lit(f"'{mode}'")}}],
                   "header": [{"properties": {"show": lit("false")}}]})


def card(p, x, y, wd, ht, measure, title):
    p.add("card", x, y, wd, ht, {"Values": [meas(measure)]}, title=title,
          objects={"labels": [{"properties": {"fontSize": lit("20D")}}],
                   "categoryLabels": [{"properties": {"show": lit("false")}}]})


def fill_by(measure_name):
    return {"dataPoint": [{"properties": {"fill": {"solid": {"color": {"expr": {
        "Measure": {"Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": measure_name}}}}}},
        "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}]}


def sortdesc(measure_name):
    return (meas(measure_name), "Descending")


def sortasc_col(ent, prop):
    return (col(ent, prop), "Ascending")


DEPT = col("DimDepartments", "DepartmentName")
YM = col("DimDate", "YearMonth")
PAGES = []


def header(p, subtitle):
    p.text(16, 2, 900, 44, p.title, size="20pt", color=INK, bold=True)
    p.text(16, 42, 1240, 30, subtitle, size="10pt", color=MUTED)
    p.text(780, 690, 484, 30, "Synthetic data (2023-2025). Thresholds are illustrative.", size="9pt", color=MUTED)


# ---- Page 1: Executive overview
p = Page("p1_exec", "Executive Overview"); PAGES.append(p)
header(p, "Are we efficient? Are admissions rising? Which departments are under pressure? Are occupancy and waits improving?")
slicer(p, 16, 70, 220, 58, "DimDate", "Year", "Year")
slicer(p, 248, 70, 220, 58, "DimDepartments", "DepartmentName", "Department")
slicer(p, 480, 70, 220, 58, "FactAdmissions", "AdmissionType", "Admission type")
for i, (mn, t) in enumerate([("Total Admissions", "Total admissions"), ("Total Discharges", "Total discharges"),
                             ("Total Unique Patients", "Unique patients"), ("ALOS", "ALOS (days)"),
                             ("Bed Occupancy Rate", "Bed occupancy rate"), ("30-Day Readmission Rate", "30-day readmission rate")]):
    card(p, 16 + i * 207, 132, 195, 80, mn, t)
p.add("lineChart", 16, 222, 500, 220, {"Category": [YM], "Y": [meas("Total Admissions"), meas("Total Discharges")]},
      title="Monthly admissions and discharges")
p.add("clusteredBarChart", 528, 222, 400, 460, {"Category": [DEPT], "Y": [meas("Total Admissions")]},
      title="Admissions by department", sort=sortdesc("Total Admissions"))
p.add("donutChart", 940, 222, 324, 220, {"Category": [col("FactAdmissions", "AdmissionType")], "Y": [meas("Total Admissions")]},
      title="Admission type mix")
p.add("lineChart", 16, 454, 500, 228, {"Category": [YM], "Y": [meas("Bed Occupancy Rate")]},
      title="Bed occupancy trend (occupied / staffed bed-days)")
p.add("lineChart", 940, 454, 324, 228, {"Category": [YM], "Y": [meas("Avg ED Wait (min)"), meas("Median ED Wait (min)")]},
      title="ED waiting time (arrival to consultation, min)")

# ---- Page 2: Admissions & discharges
p = Page("p2_adm", "Admissions & Discharges"); PAGES.append(p)
header(p, "When is demand highest? Which categories grow? Which departments hold patients longest?")
slicer(p, 16, 70, 220, 58, "DimDate", "Year", "Year")
slicer(p, 248, 70, 220, 58, "DimDepartments", "DepartmentName", "Department")
slicer(p, 480, 70, 220, 58, "FactAdmissions", "AdmissionType", "Admission type")
p.add("lineChart", 16, 126, 628, 220, {"Category": [col("DimDate", "WeekStart")], "Y": [meas("Total Admissions")]},
      title="Weekly admissions")
p.add("clusteredColumnChart", 656, 126, 608, 220, {"Category": [YM], "Y": [meas("Total Admissions"), meas("Total Discharges")]},
      title="Admissions vs discharges by month")
p.add("hundredPercentStackedColumnChart", 16, 358, 280, 324, {"Category": [col("DimDate", "Year")], "Y": [meas("Total Admissions")],
      "Series": [col("FactAdmissions", "AdmissionType")]}, title="Admission type by year (%)")
p.add("clusteredBarChart", 308, 358, 300, 324, {"Category": [DEPT], "Y": [meas("ALOS")]}, title="ALOS by department (days)",
      sort=sortdesc("ALOS"))
p.add("clusteredBarChart", 620, 358, 300, 324, {"Category": [col("FactAdmissions", "DischargeType")], "Y": [meas("Total Discharges")]},
      title="Discharge type", sort=sortdesc("Total Discharges"))
p.add("pivotTable", 932, 358, 332, 324, {"Rows": [col("DimDate", "DayName")], "Columns": [col("FactAdmissions", "AdmissionType")],
      "Values": [meas("Total Admissions")]}, title="Weekday profile (admissions)")

# ---- Page 3: Bed occupancy
p = Page("p3_beds", "Bed Occupancy & Resources"); PAGES.append(p)
header(p, "Which departments are at capacity and where are beds under-used? Thresholds are illustrative and adjustable.")
slicer(p, 16, 70, 220, 58, "DimDate", "Year", "Year")
slicer(p, 248, 70, 220, 58, "DimDepartments", "DepartmentName", "Department")
slicer(p, 480, 70, 150, 58, "BOR High Threshold", "BOR High Threshold", "BOR high threshold")
slicer(p, 640, 70, 150, 58, "BOR Critical Threshold", "BOR Critical Threshold", "BOR critical threshold")
for i, (mn, t) in enumerate([("Staffed Beds", "Staffed beds"), ("Avg Daily Census", "Avg daily census"),
                             ("Available Bed Count", "Avg free staffed beds"), ("Bed Occupancy Rate", "Bed occupancy rate")]):
    card(p, 16 + i * 207, 132, 195, 80, mn, t)
p.add("clusteredBarChart", 16, 222, 408, 460, {"Category": [DEPT], "Y": [meas("Bed Occupancy Rate")]},
      title="Occupancy by department (colour = status vs thresholds)", objects=fill_by("BOR Color"),
      sort=sortdesc("Bed Occupancy Rate"))
p.add("clusteredBarChart", 436, 222, 408, 460, {"Category": [DEPT], "Y": [meas("Staffed Beds"), meas("Avg Daily Census")]},
      title="Staffed beds vs average census")
p.add("pivotTable", 856, 222, 408, 230, {"Rows": [DEPT], "Columns": [col("DimDate", "MonthShort")], "Values": [meas("Bed Occupancy Rate")]},
      title="Occupancy by department and month")
p.add("scatterChart", 856, 464, 408, 218, {"Category": [DEPT], "X": [meas("Bed Occupancy Rate")], "Y": [meas("Doctor Utilization Rate")],
      "Size": [meas("Total Admissions")]}, title="Bed pressure vs doctor utilisation",
      objects={"categoryLabels": [{"properties": {"show": lit("true"), "fontSize": lit("8D")}}]})

# ---- Page 4: Department performance
p = Page("p4_dept", "Department Performance"); PAGES.append(p)
header(p, "How does my department compare - in context? Colours/ranks show relative position, not a verdict.")
slicer(p, 16, 70, 220, 58, "DimDate", "Year", "Year")
slicer(p, 248, 70, 220, 58, "FactAdmissions", "AdmissionType", "Admission type")
p.add("tableEx", 16, 126, 1248, 280, {"Values": [DEPT, meas("Total Admissions"), meas("Total Discharges"), meas("ALOS"),
      meas("Bed Occupancy Rate"), meas("30-Day Readmission Rate"), meas("Eligible Discharges"), meas("Doctor Utilization Rate"),
      meas("Patients per Doctor"), meas("Avg ED Wait (min)")]}, title="Department comparison matrix",
      objects={"values": [{"properties": {"fontSize": lit("9D")}}], "columnHeaders": [{"properties": {"fontSize": lit("9D")}}],
               "grid": [{"properties": {"rowPadding": lit("0D")}}]})
p.add("clusteredBarChart", 16, 414, 408, 268, {"Category": [DEPT], "Y": [meas("30-Day Readmission Rate")]},
      title="30-day readmission rate (not risk-adjusted)", sort=sortdesc("30-Day Readmission Rate"))
p.add("clusteredBarChart", 436, 414, 408, 268, {"Category": [DEPT], "Y": [meas("Doctor Utilization Rate")]},
      title="Doctor utilisation (consultation / scheduled hours)", objects=fill_by("Doctor Util Color"),
      sort=sortdesc("Doctor Utilization Rate"))
p.text(856, 414, 408, 268, "Context: high readmission may reflect chronic case-mix (cardiology, pulmonology, oncology); "
       "high volume is demand, not inefficiency. Utilisation counts consultation hours only (a proxy) and must not be used "
       "for individual appraisal. Use the denominators (Eligible Discharges) before comparing rates.", size="11pt", color=MUTED, framed=True)

# ---- Page 5: ED
p = Page("p5_ed", "Waiting Time & Patient Flow"); PAGES.append(p)
header(p, "Which hours and triage groups wait longest? Where does flow break?")
slicer(p, 16, 70, 220, 58, "DimDate", "Year", "Year")
slicer(p, 248, 70, 220, 58, "FactEmergencyVisits", "TriageLabel", "Triage level")
slicer(p, 480, 70, 220, 58, "DimDepartments", "DepartmentName", "Department")
for i, (mn, t) in enumerate([("Avg ED Wait (min)", "Avg wait (min)"), ("Median ED Wait (min)", "Median wait (min)"),
                             ("ED Turnaround (min)", "Avg turnaround (min)"), ("ED Visits", "ED visits"), ("LWBS Rate", "Left without being seen")]):
    card(p, 16 + i * 248, 132, 236, 80, mn, t)
p.add("clusteredColumnChart", 16, 222, 408, 230, {"Category": [col("FactEmergencyVisits", "ArrivalHour")], "Y": [meas("ED Visits")]},
      title="Arrivals by hour")
p.add("lineChart", 436, 222, 408, 230, {"Category": [col("FactEmergencyVisits", "ArrivalHour")], "Y": [meas("Avg ED Wait (min)")]},
      title="Average wait by arrival hour (min)")
p.add("clusteredBarChart", 856, 222, 408, 230,
      {"Category": [col("FactEmergencyVisits", "TriageLabel")], "Y": [meas("Avg ED Wait (min)")]}, title="Wait by triage level (min)")
p.add("clusteredBarChart", 16, 464, 408, 218, {"Category": [col("FactEmergencyVisits", "DispositionType")], "Y": [meas("ED Visits")]},
      title="Disposition", sort=sortdesc("ED Visits"))
p.add("clusteredColumnChart", 436, 464, 408, 218, {"Category": [col("DimDate", "DayName")], "Y": [meas("ED Visits")]}, title="ED visits by weekday")
p.add("lineChart", 856, 464, 408, 218, {"Category": [YM], "Y": [meas("ED Turnaround - Admitted (min)"), meas("ED Turnaround (min)")]},
      title="ED turnaround: admitted vs all (min)")


def build_report():
    j(RP / "definition.pbir", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
                               "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}})
    rd = RP / "definition"
    j(rd / "version.json", {"$schema": f"{SCH}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    (RP / "StaticResources" / "RegisteredResources").mkdir(parents=True, exist_ok=True)
    shutil.copy(PBI / "theme" / "hospital_theme.json", RP / "StaticResources" / "RegisteredResources" / "hospital_theme.json")
    (RP / "StaticResources" / "SharedResources" / "BaseThemes").mkdir(parents=True, exist_ok=True)
    if BASE_THEME_SRC.exists():
        shutil.copy(BASE_THEME_SRC, RP / "StaticResources" / "SharedResources" / "BaseThemes" / f"{BASE_THEME}.json")
    flt = {"name": "rptWindow", "field": col("DimDate", "InReportingWindow"), "type": "Categorical",
           "filter": {"Version": 2, "From": [{"Name": "d", "Entity": "DimDate", "Type": 0}],
                      "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "InReportingWindow"}}],
                                                      "Values": [[{"Literal": {"Value": "true"}}]]}}}]}}
    j(rd / "report.json", {
        "$schema": f"{SCH}/report/3.3.0/schema.json",
        "themeCollection": {"baseTheme": {"name": BASE_THEME, "reportVersionAtImport": {"visual": "2.9.0", "report": "3.3.0", "page": "2.1.0"}, "type": "SharedResources"},
                            "customTheme": {"name": "hospital_theme.json", "reportVersionAtImport": {"visual": "2.9.0", "report": "3.3.0", "page": "2.1.0"}, "type": "RegisteredResources"}},
        "filterConfig": {"filters": [flt]},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources", "items": [{"name": BASE_THEME, "path": f"BaseThemes/{BASE_THEME}.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources", "items": [{"name": "hospital_theme.json", "path": "hospital_theme.json", "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized", "defaultDrillFilterOtherVisuals": True}})
    j(rd / "pages" / "pages.json", {"$schema": f"{SCH}/pagesMetadata/1.1.0/schema.json",
                                    "pageOrder": [pg.id for pg in PAGES], "activePageName": PAGES[0].id})
    for pg in PAGES:
        pd = rd / "pages" / pg.id
        j(pd / "page.json", {"$schema": f"{SCH}/page/2.1.0/schema.json", "name": pg.id, "displayName": pg.title,
                             "displayOption": "FitToPage", "height": 720, "width": 1280})
        for vid, obj in pg.visuals:
            j(pd / "visuals" / vid / "visual.json", obj)


def main():
    for d in (SM, RP):
        if d.exists():
            shutil.rmtree(d)
    build_model()
    build_report()
    j(PBI / f"{NAME}.pbip", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
                             "version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
                             "settings": {"enableAutoRecovery": True}})
    n = sum(len(pg.visuals) for pg in PAGES)
    print(f"PBIP written: {len(TABLES)+3} tables, {len(M)} measures, {len(REL)} relationships, {len(PAGES)} pages, {n} visuals")


if __name__ == "__main__":
    main()
