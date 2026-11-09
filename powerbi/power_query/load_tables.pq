// =====================================================================================
// Power Query (M) - loads the 9 star-schema tables from data/processed/powerbi/*.csv
// HOW TO USE
//   1. Home > Transform data > Manage Parameters > New:  Name = DataFolder, Type = Text,
//      Current value = C:\...\hospital-operations-analytics\data\processed\powerbi\   (trailing backslash!)
//   2. New Source > Blank Query > Advanced Editor. Create ONE query named  fnLoadCsv  (code A below).
//   3. Create one blank query per table (code B..J) and paste the code, naming the query exactly as the title.
//   NOTE: the same queries are embedded in the generated project (powerbi/HospitalOperations.pbip) and load successfully in Power BI Desktop.
// =====================================================================================


// ---------- A. fnLoadCsv (function query) -------------------------------------------
(fileName as text) as table =>
let
    Source   = Csv.Document(File.Contents(DataFolder & fileName), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
in
    Promoted


// ---------- B. DimDate --------------------------------------------------------------
let
    Source = fnLoadCsv("DimDate.csv"),
    Typed  = Table.TransformColumnTypes(Source, {
        {"Date", type date}, {"DateKey", Int64.Type}, {"Year", Int64.Type}, {"Quarter", Int64.Type}, {"QuarterLabel", type text},
        {"MonthNumber", Int64.Type}, {"MonthName", type text}, {"MonthShort", type text}, {"YearMonth", type text},
        {"YearMonthSort", Int64.Type}, {"MonthStart", type date}, {"WeekStart", type date}, {"ISOWeek", Int64.Type},
        {"DayOfMonth", Int64.Type}, {"DayOfWeekNumber", Int64.Type}, {"DayName", type text}, {"DayShort", type text},
        {"IsWeekend", type logical}, {"InReportingWindow", type logical}}, "en-US")
in
    Typed


// ---------- C. DimPatients ----------------------------------------------------------
let
    Source = fnLoadCsv("DimPatients.csv"),
    Typed  = Table.TransformColumnTypes(Source, {
        {"PatientID", type text}, {"Age", Int64.Type}, {"AgeGroup", type text}, {"Gender", type text}, {"City", type text},
        {"PatientType", type text}, {"RegistrationDate", type date}}, "en-US")
in
    Typed


// ---------- D. DimDepartments -------------------------------------------------------
let
    Source = fnLoadCsv("DimDepartments.csv"),
    Typed  = Table.TransformColumnTypes(Source, {
        {"DepartmentID", type text}, {"DepartmentName", type text}, {"DepartmentCategory", type text},
        {"DepartmentCapacity", Int64.Type}, {"StaffedBeds", Int64.Type}, {"HasInpatientBeds", type logical}}, "en-US")
in
    Typed


// ---------- E. DimDoctors -----------------------------------------------------------
let
    Source = fnLoadCsv("DimDoctors.csv"),
    Typed  = Table.TransformColumnTypes(Source, {
        {"DoctorID", type text}, {"DoctorName", type text}, {"DepartmentID", type text}, {"Specialization", type text},
        {"EmploymentType", type text}, {"Shift", type text}}, "en-US")
in
    Typed


// ---------- F. DimBeds --------------------------------------------------------------
let
    Source = fnLoadCsv("DimBeds.csv"),
    Typed  = Table.TransformColumnTypes(Source, {
        {"BedID", type text}, {"DepartmentID", type text}, {"BedType", type text}, {"BedStatus", type text}, {"IsStaffed", type logical}}, "en-US")
in
    Typed


// ---------- G. FactAdmissions -------------------------------------------------------
let
    Source = fnLoadCsv("FactAdmissions.csv"),
    Typed  = Table.TransformColumnTypes(Source, {
        {"AdmissionID", type text}, {"PatientID", type text}, {"AdmissionDate", type date}, {"DischargeDate", type date},
        {"AdmissionType", type text}, {"DepartmentID", type text}, {"DoctorID", type text}, {"BedID", type text},
        {"DiagnosisCategory", type text}, {"AdmissionStatus", type text}, {"DischargeType", type text},
        {"IsCompleted", type logical}, {"IsCancelled", type logical}, {"IsOpenStay", type logical}, {"IsAdmission", type logical},
        {"LOSDays", Int64.Type}, {"BedReleaseDate", type date}, {"InReportingWindow", type logical}, {"AdmissionSeq", Int64.Type},
        {"IsReadmissionEligible", type logical}, {"FollowupComplete", type logical}, {"BedType", type text},
        {"Readmitted30d", type logical}, {"IsUnplannedReadmission30d", type logical}, {"FromED", type logical}}, "en-US")
in
    Typed


// ---------- H. FactEmergencyVisits --------------------------------------------------
let
    Source = fnLoadCsv("FactEmergencyVisits.csv"),
    Typed  = Table.TransformColumnTypes(Source, {
        {"EmergencyVisitID", type text}, {"PatientID", type text}, {"ArrivalDateTime", type datetime}, {"ArrivalDate", type date},
        {"ArrivalHour", Int64.Type}, {"TriageLevel", Int64.Type}, {"TriageLabel", type text}, {"TargetWaitMin", Int64.Type},
        {"ConsultationDateTime", type datetime}, {"DispositionDateTime", type datetime}, {"DispositionType", type text},
        {"DepartmentID", type text}, {"AdmissionID", type text}, {"WaitMinutes", type number}, {"TurnaroundMinutes", type number},
        {"ConsultToDispositionMinutes", type number}, {"IsLWBS", type logical}, {"IsAdmitted", type logical},
        {"MetWaitTarget", Int64.Type}, {"InReportingWindow", type logical}}, "en-US")
in
    Typed


// ---------- I. FactDoctorActivity ---------------------------------------------------
let
    Source = fnLoadCsv("FactDoctorActivity.csv"),
    Typed  = Table.TransformColumnTypes(Source, {
        {"ActivityID", type text}, {"DoctorID", type text}, {"DepartmentID", type text}, {"ActivityDate", type date},
        {"ScheduledHours", type number}, {"ConsultationHours", type number}, {"PatientsAttended", Int64.Type},
        {"InReportingWindow", type logical}}, "en-US")
in
    Typed


// ---------- J. FactReadmissions -----------------------------------------------------
let
    Source = fnLoadCsv("FactReadmissions.csv"),
    Typed  = Table.TransformColumnTypes(Source, {
        {"ReadmissionID", type text}, {"PatientID", type text}, {"OriginalAdmissionID", type text}, {"ReadmissionAdmissionID", type text},
        {"DaysBetweenAdmissions", Int64.Type}, {"IndexDepartmentID", type text}, {"ReadmitDepartmentID", type text},
        {"IndexDischargeDate", type date}, {"ReadmitAdmissionDate", type date}, {"Within30Days", type logical}}, "en-US")
in
    Typed


// ---------- K. (alternative source) PostgreSQL ---------------------------------------
// Replace the CSV step of any table with a database navigation, e.g. the departments dimension:
//   let
//       Source = PostgreSQL.Database("localhost:5432", "hospital"),
//       Tbl    = Source{[Schema = "hospital", Item = "departments"]}[Data]
//   in  Tbl
// The star-schema derived columns (flags, minutes, BedReleaseDate, ...) are built by scripts/build_star_schema.py;
// to load straight from PostgreSQL either re-create them as SQL views over hospital.vw_patient_admission_summary /
// vw_emergency_performance (they already contain los_days, wait_minutes, turnaround_minutes, is_lwbs, ...) or keep
// the CSV path above, which is the tested route.
