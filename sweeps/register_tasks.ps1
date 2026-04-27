[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$PythonExe = "python",
    [string]$ProjectRoot = "C:\Users\bmoor\Local_AI",
    [string]$CoreTime = "07:00",
    [string]$ExtendedTime = "13:00",
    [string]$WeeklyTime = "08:30",
    [switch]$DisallowBatteryStart
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
$weeklyTaskName = "SovereignNodeSweepWeekly"

function New-SweepTaskAction {
    param(
        [string]$Arguments
    )

    return New-ScheduledTaskAction -Execute $pythonPath -Argument $Arguments -WorkingDirectory $ProjectRoot
}

function New-SweepTaskSettings {
    $params = @{
        StartWhenAvailable    = $true
        ExecutionTimeLimit    = (New-TimeSpan -Hours 72)
        AllowStartIfOnBatteries = (-not $DisallowBatteryStart.IsPresent)
        DontStopIfGoingOnBatteries = (-not $DisallowBatteryStart.IsPresent)
    }

    return New-ScheduledTaskSettingsSet @params
}

function Register-SweepTask {
    param(
        [string]$TaskName,
        [Microsoft.Management.Infrastructure.CimInstance]$Trigger,
        [string]$Arguments
    )

    $action = New-SweepTaskAction -Arguments $Arguments
    $settings = New-SweepTaskSettings

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $Trigger `
        -Settings $settings `
        -User $env:USERNAME `
        -RunLevel Limited `
        -Force | Out-Null
}

if ($PSCmdlet.ShouldProcess($coreTaskName, "Create or update scheduled task")) {
    $coreTrigger = New-ScheduledTaskTrigger -Daily -At $CoreTime
    Register-SweepTask -TaskName $coreTaskName -Trigger $coreTrigger -Arguments "`"$runner`" --profile core"
}

if ($PSCmdlet.ShouldProcess($extendedTaskName, "Create or update scheduled task")) {
    $extendedTrigger = New-ScheduledTaskTrigger -Daily -At $ExtendedTime
    Register-SweepTask -TaskName $extendedTaskName -Trigger $extendedTrigger -Arguments "`"$runner`" --profile extended"
}

if ($PSCmdlet.ShouldProcess($weeklyTaskName, "Create or update scheduled task")) {
    $weeklyTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At $WeeklyTime
    Register-SweepTask -TaskName $weeklyTaskName -Trigger $weeklyTrigger -Arguments "`"$runner`" --profile all --weekly --skip-email"
}

Write-Output "Created tasks:"
Write-Output " - $coreTaskName at $CoreTime"
Write-Output " - $extendedTaskName at $ExtendedTime"
Write-Output " - $weeklyTaskName Sundays at $WeeklyTime"
Write-Output ""
Write-Output "Review:"
Write-Output " - schtasks /Query /TN $coreTaskName /V /FO LIST"
Write-Output " - schtasks /Query /TN $extendedTaskName /V /FO LIST"
Write-Output " - schtasks /Query /TN $weeklyTaskName /V /FO LIST"
