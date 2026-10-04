# Build the release: dist\OctopathWorldOverhaul\ and dist\OctopathWorldOverhaul-<version>.zip
#   powershell -ExecutionPolicy Bypass -File build_release.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$version = (Get-Content src\version.py | Select-String 'VERSION = "(.+)"').Matches[0].Groups[1].Value

python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name OctopathWorldOverhaul `
    --paths src `
    --hidden-import config --hidden-import build_all --hidden-import validate `
    --hidden-import build_fasttravel_mod --hidden-import steam_setup `
    --hidden-import blueprint_patch --hidden-import kismet `
    src\launch_octopath.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$out = Join-Path $root "dist\OctopathWorldOverhaul"
if (Test-Path $out) { Remove-Item -Recurse -Force $out }
New-Item -ItemType Directory -Force "$out\data" | Out-Null
Copy-Item dist\OctopathWorldOverhaul.exe $out
Copy-Item src\data\item_registry.json "$out\data"
Copy-Item README.md, LICENSE, CHANGELOG.md $out
$zip = Join-Path $root "dist\OctopathWorldOverhaul-$version.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path "$out\*" -DestinationPath $zip
Write-Output "built $zip"
