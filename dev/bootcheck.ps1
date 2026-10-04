# Launch the game through Steam and report whether it actually comes up.
#
# Steam can take anywhere from ~20s to well over a minute to spawn the shipping exe, so a
# fixed sleep gives false "NOT RUNNING" answers by sampling too early. Poll instead, then
# confirm the process stays alive and responsive rather than crashing straight back out.
param(
    [int]$StartTimeoutSec = 180,   # how long to wait for the process to appear
    [int]$StableSec = 25,          # how long it must then keep running
    [switch]$KeepOpen
)

$ErrorActionPreference = 'Stop'
$proc = { Get-Process | Where-Object { $_.ProcessName -like '*Shipping*' } | Select-Object -First 1 }

if (& $proc) { Write-Output 'NOTE: a game process was already running; closing it first'
    Get-Process | Where-Object { $_.ProcessName -like '*ctopath*' } | Stop-Process -Force
    Start-Sleep -Seconds 3 }

Write-Output 'launching via Steam...'
Start-Process 'steam://rungameid/921570'

$sw = [Diagnostics.Stopwatch]::StartNew()
$p = $null
while ($sw.Elapsed.TotalSeconds -lt $StartTimeoutSec) {
    $p = & $proc
    if ($p) { break }
    Start-Sleep -Seconds 2
}
if (-not $p) {
    Write-Output "RESULT: FAIL - no game process within ${StartTimeoutSec}s"
    exit 1
}
Write-Output ("process appeared after {0:N0}s (pid {1})" -f $sw.Elapsed.TotalSeconds, $p.Id)

Start-Sleep -Seconds $StableSec
$p2 = & $proc
if (-not $p2) {
    Write-Output "RESULT: FAIL - process exited within ${StableSec}s of starting (likely a bad pak)"
    exit 1
}
$mb = [math]::Round($p2.WorkingSet64 / 1MB)
Write-Output "RESULT: PASS - alive ${mb}MB responding=$($p2.Responding)"
if (-not $KeepOpen) {
    Get-Process | Where-Object { $_.ProcessName -like '*ctopath*' } | Stop-Process -Force
    Write-Output 'closed'
}
exit 0
