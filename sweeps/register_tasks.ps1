[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$PythonExe = "python",
    [string]$ProjectRoot = "C:\Users\bmoor\Local_AI",
    [string]$CoreTime = "07:00",
    [string]$ExtendedTime = "13:00"
)

$ErrorActionPreference = "Stop"

$runner = Join-Path $ProjectRoot "sweeps\run_workflow.py"

if (-not (Test-Path -LiteralPath $runner)) {
    throw "Runner not found: $runner"
}

$pythonPath = & $PythonExe -c "import sys; print(sys.executable)"
if (-not $pythonPath) {
    throw "Could not resolve Python executable path from: $PythonExe"
}
$pythonPath = $pythonPath.Trim()

$coreTaskName = "SovereignNodeSweepCore"
$extendedTaskName = "SovereignNodeSweepExtended"

$coreCmd = "`"$pythonPath`" `"$runner`" --profile core"
$extendedCmd = "`"$pythonPath`" `"$runner`" --profile extended"

if ($PSCmdlet.ShouldProcess($coreTaskName, "Create or update scheduled task")) {
    schtasks /Create /TN $coreTaskName /SC DAILY /ST $CoreTime /TR $coreCmd /RL LIMITED /F | Out-Null
}

if ($PSCmdlet.ShouldProcess($extendedTaskName, "Create or update scheduled task")) {
    schtasks /Create /TN $extendedTaskName /SC DAILY /ST $ExtendedTime /TR $extendedCmd /RL LIMITED /F | Out-Null
}

Write-Output "Created tasks:"
Write-Output " - $coreTaskName at $CoreTime"
Write-Output " - $extendedTaskName at $ExtendedTime"
Write-Output ""
Write-Output "Review:"
Write-Output " - schtasks /Query /TN $coreTaskName /V /FO LIST"
Write-Output " - schtasks /Query /TN $extendedTaskName /V /FO LIST"
