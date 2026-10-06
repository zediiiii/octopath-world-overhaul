# Build the release: dist\OrsterraUnbound\ and dist\OrsterraUnbound-<version>.zip
#   powershell -ExecutionPolicy Bypass -File build_release.ps1
# (a wrapper for dev\package_release.py, which documents the layout)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
python dev\package_release.py
if ($LASTEXITCODE -ne 0) { throw "packaging failed" }
