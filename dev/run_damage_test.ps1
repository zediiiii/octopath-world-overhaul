# End-to-end combat test. Requires an unlocked screen (capture fails against the lock screen;
# on this machine the lock happens when the remote desktop session drops).
#
#   1. python damage_test.py                                      set up
#   2. powershell -ExecutionPolicy Bypass -File run_damage_test.ps1
#   3. look through %TEMP%\octotest\
#   4. python damage_test.py --restore                            undo
#
# Turn model (corrected): each character's command resolves IMMEDIATELY after it is
# confirmed - the party does not queue all four and then execute. So the capture has to
# start on the confirm keypress, not after the whole party has input. That mistake is why
# earlier runs kept photographing the menu instead of the damage.
param(
    [string]$Out = "$env:TEMP\octotest",
    [int]$WeaponCycles = 2     # presses of D to move Attack onto the sword
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
New-Item -ItemType Directory -Force -Path $Out | Out-Null
Get-ChildItem $Out -Filter *.png -ErrorAction SilentlyContinue | Remove-Item -Force
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$script:n = 0

function Grab($label) {
    $script:n++
    $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
    $bmp.Save((Join-Path $Out ("{0:d3}-{1}.png" -f $script:n, $label)),
              [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
}
function Key($k, $r = 1) { & powershell -ExecutionPolicy Bypass -File "$here\input.ps1" -Key $k -Repeat $r | Out-Null }
function Hold($k, $ms)   { & powershell -ExecutionPolicy Bypass -File "$here\input.ps1" -Hold $k -HoldMs $ms | Out-Null }
# confirm, then immediately photograph the resolution that follows it
function ConfirmAndCapture($label, $frames = 12, $gap = 110) {
    Key E
    for ($f = 0; $f -lt $frames; $f++) { Grab $label; Start-Sleep -Milliseconds $gap }
}

if (Get-Process -Name LogonUI -ErrorAction SilentlyContinue) {
    Write-Output "ABORT: the workstation is locked - capture cannot see the game."
    exit 2
}

Write-Output "launching..."
Get-Process | Where-Object { $_.ProcessName -like '*ctopath*' } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Start-Process 'steam://rungameid/921570'
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt 180) {
    if (Get-Process | Where-Object { $_.ProcessName -like '*Shipping*' }) { break }
    Start-Sleep -Seconds 2
}
if (-not (Get-Process | Where-Object { $_.ProcessName -like '*Shipping*' })) {
    Write-Output "ABORT: game never started"; exit 1
}
Start-Sleep -Seconds 30

Write-Output "title -> continue -> slot 7"
Key RETURN; Start-Sleep -Seconds 3
Key RETURN; Start-Sleep -Seconds 4
Key E;      Start-Sleep -Seconds 3
Key W;      Start-Sleep -Seconds 1     # the confirm dialog starts with NOTHING selected
Key E;      Start-Sleep -Seconds 45
Grab "loaded"

Write-Output "walking (test builds drop EncountStepMin to 4, so this is quick)"
for ($i = 0; $i -lt 6; $i++) {
    Hold 'A' 1500
    Start-Sleep -Seconds 2
    Grab "walk"
}

# The leader's Attack defaults to whichever weapon the game picked - for H'aanit that is the
# bow, not the test sword. Cycle it and photograph the icon so the choice is auditable.
Write-Output "selecting the sword"
for ($c = 0; $c -lt $WeaponCycles; $c++) {
    Key D
    Start-Sleep -Milliseconds 500
    Grab "weapon"
}

Write-Output "attacking, capturing each confirm"
for ($t = 0; $t -lt 8; $t++) { ConfirmAndCapture "hit$t" }

Write-Output ""
Write-Output "done - review $Out"
Write-Output "  a number above 9,999 from a character WITHOUT 'Surpassing Power' means the"
Write-Output "  global damage cap patch is live."
