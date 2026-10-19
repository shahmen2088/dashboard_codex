param(
  [ValidateRange(5, 1440)]
  [int]$EveryMinutes = 15,
  [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
  [string]$TaskName = 'Codex History Organizer - Refresh'
)

$ErrorActionPreference = 'Stop'

$refreshScript = Join-Path $ProjectRoot 'codex-history-organizer\maintenance\refresh_audit.py'
if (-not (Test-Path -LiteralPath $refreshScript -PathType Leaf)) {
  throw "Audit refresh script was not found: $refreshScript"
}

$python = Get-Command python.exe -ErrorAction Stop
$action = New-ScheduledTaskAction -Execute $python.Source -Argument "-u `"$refreshScript`""
$trigger = New-ScheduledTaskTrigger `
  -Once `
  -At (Get-Date).AddMinutes(1) `
  -RepetitionInterval (New-TimeSpan -Minutes $EveryMinutes) `
  -RepetitionDuration (New-TimeSpan -Days 3650)
$principal = New-ScheduledTaskPrincipal `
  -UserId "$env:USERDOMAIN\$env:USERNAME" `
  -LogonType Interactive `
  -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $action `
  -Trigger $trigger `
  -Principal $principal `
  -Settings $settings `
  -Description 'Read-only refresh of the local CodexChatAudit export.' `
  -Force | Out-Null

Write-Host "Task '$TaskName' configured: every $EveryMinutes minutes."
Write-Host 'It reads local history and updates only CodexChatAudit.'
