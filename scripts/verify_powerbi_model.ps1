<#
Verifies the DAX measures of the open Power BI model against analysis/kpi_checkpoints.csv.

Usage (Power BI Desktop must have powerbi\HospitalOperations.pbip open):
    powershell -ExecutionPolicy Bypass -File scripts\verify_powerbi_model.ps1 [-Refresh]

It finds the local Analysis Services instance that Desktop started, optionally refreshes the data,
evaluates each KPI measure for 4 scopes (all / 2023 / 2024 / 2025, with the report-level filter
InReportingWindow = TRUE applied) and writes analysis/powerbi_verification.md.
#>
param([switch]$Refresh, [string]$Tolerance = "0.00005")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dll = "C:\Program Files\Microsoft Power BI Desktop\bin\Microsoft.PowerBI.AdomdClient.dll"
Add-Type -Path $dll

$ms = Get-Process msmdsrv -ErrorAction SilentlyContinue
if (-not $ms) { throw "No Power BI Desktop engine running. Open powerbi\HospitalOperations.pbip first." }
$port = $null
foreach ($p in $ms) {
    $line = netstat -ano | Select-String "127.0.0.1:(\d+)\s+0.0.0.0:0\s+LISTENING\s+$($p.Id)" | Select-Object -First 1
    if ($line) { $port = [regex]::Match($line.ToString(), "127.0.0.1:(\d+)").Groups[1].Value }
}
if (-not $port) { throw "Could not find the engine port." }

$conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port")
$conn.Open()
function Run-Dax([string]$q) {
    $cmd = $conn.CreateCommand(); $cmd.CommandText = $q
    $r = $cmd.ExecuteReader()
    $names = 0..($r.FieldCount - 1) | ForEach-Object { $r.GetName($_) }
    $row = @{}
    if ($r.Read()) { for ($i = 0; $i -lt $r.FieldCount; $i++) { $row[$names[$i]] = $r.GetValue($i) } }
    $r.Close(); $row
}
if ($Refresh) {
    $cat = (Run-Dax "SELECT [CATALOG_NAME] FROM `$SYSTEM.DBSCHEMA_CATALOGS") 2>$null
    $cmd = $conn.CreateCommand(); $cmd.CommandText = "SELECT [CATALOG_NAME] FROM `$SYSTEM.DBSCHEMA_CATALOGS"
    $r = $cmd.ExecuteReader(); $r.Read() | Out-Null; $db = $r.GetValue(0); $r.Close()
    $x = $conn.CreateCommand()
    $x.CommandText = '{"refresh":{"type":"full","objects":[{"database":"' + $db + '"}]}}'
    $x.ExecuteNonQuery() | Out-Null
}

# checkpoint KPI name -> DAX measure
$map = [ordered]@{
    "Total Admissions" = "Total Admissions"; "Total Unique Patients" = "Total Unique Patients"; "Total Discharges" = "Total Discharges"
    "ALOS (days)" = "ALOS"; "Bed Occupancy Rate" = "Bed Occupancy Rate"; "Occupied Bed-Days" = "Occupied Bed-Days"
    "Staffed Bed-Days" = "Available Bed-Days"; "Avg ED Wait (min)" = "Avg ED Wait (min)"; "Median ED Wait (min)" = "Median ED Wait (min)"
    "ED Turnaround (min)" = "ED Turnaround (min)"; "30-Day Readmission Rate" = "30-Day Readmission Rate"
    "Eligible Discharges" = "Eligible Discharges"; "Doctor Utilization" = "Doctor Utilization Rate"
    "Avg Daily Admissions" = "Avg Daily Admissions"; "Emergency Admission %" = "Emergency Admission %"; "Patients per Doctor" = "Patients per Doctor"
}
$scopes = [ordered]@{ "All (2023-2025)" = ""; "2023" = ", DimDate[Year] = 2023"; "2024" = ", DimDate[Year] = 2024"; "2025" = ", DimDate[Year] = 2025" }
$cp = Import-Csv (Join-Path $root "analysis\kpi_checkpoints.csv")
$rows = @(); $pass = 0; $fail = 0
foreach ($s in $scopes.Keys) {
    $cols = ($map.GetEnumerator() | ForEach-Object { '"{0}", [{1}]' -f $_.Key, $_.Value }) -join ", "
    $q = "EVALUATE CALCULATETABLE ( ROW ( $cols ), DimDate[InReportingWindow] = TRUE () $($scopes[$s]) )"
    $res = Run-Dax $q
    foreach ($k in $map.Keys) {
        $exp = $cp | Where-Object { $_.Scope -eq $s -and $_.KPI -eq $k } | Select-Object -First 1
        if (-not $exp) { continue }
        $got = $res["[$k]"]
        $sql = [double]$exp.SQL
        $ok = $false
        if ($null -ne $got) { $ok = ([math]::Abs([double]$got - $sql) -le [double]$Tolerance * [math]::Max(1, [math]::Abs($sql))) }
        if ($ok) { $pass++ } else { $fail++ }
        $rows += [pscustomobject]@{ Scope = $s; KPI = $k; DAX_in_PowerBI = $got; SQL_checkpoint = $sql; Match = $(if ($ok) { "PASS" } else { "FAIL" }) }
    }
}
$conn.Close()

$md = @("# Power BI model verification", "",
    "Measures evaluated in the **real Power BI Desktop engine** (Analysis Services, port $port) with the report-level filter ``DimDate[InReportingWindow] = TRUE`` and compared with ``analysis/kpi_checkpoints.csv`` (SQL results).",
    "", "**Result: $pass PASS / $fail FAIL** (tolerance $Tolerance, relative).", "",
    "| Scope | KPI | DAX (Power BI) | SQL checkpoint | Match |", "|---|---|---:|---:|:--:|")
foreach ($r in $rows) { $md += "| $($r.Scope) | $($r.KPI) | $([math]::Round([double]$r.DAX_in_PowerBI,6)) | $($r.SQL_checkpoint) | $($r.Match) |" }
$md | Set-Content (Join-Path $root "analysis\powerbi_verification.md") -Encoding utf8
$rows | Format-Table -AutoSize | Out-String -Width 200
"PASS=$pass FAIL=$fail"
