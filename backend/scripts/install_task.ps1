param(
    [string]$TaskName = "JLU Notice Monitor",
    [string]$DailyAt = "08:00"
)

$ErrorActionPreference = "Stop"
$BackendDir = Split-Path -Parent $PSScriptRoot
$CrawlerScript = Join-Path $PSScriptRoot "run_crawler.ps1"
$PowerShell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$StartTime = [DateTime]::ParseExact($DailyAt, "HH:mm", $null)

$Action = New-ScheduledTaskAction `
    -Execute $PowerShell `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$CrawlerScript`"" `
    -WorkingDirectory $BackendDir
$Trigger = New-ScheduledTaskTrigger -Daily -At $StartTime
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Daily crawl for JLU Notice Monitor" `
    -RunLevel Limited `
    -Force

Write-Host "Scheduled task '$TaskName' installed for $DailyAt every day."

