# SKYBOUND - packaging script.
#
# Stages the installer payload from a packaged Unreal build and (optionally)
# compiles the installer with Inno Setup.
#
#   .\Scripts\package.ps1                 # stage only
#   .\Scripts\package.ps1 -BuildInstaller # stage + compile SKYBOUND-Setup-*.exe
#
# The Unreal packaging step itself requires a UE 5.6 installation and is
# documented in BUILD_GUIDE.md. This script does NOT pretend to build the game;
# if the packaged build is missing it stages documentation/tools only and says so.

[CmdletBinding()]
param(
    [string]$PackagedBuild = "",
    [switch]$BuildInstaller
)

$ErrorActionPreference = 'Stop'
$root    = Split-Path -Parent $PSScriptRoot
$payload = Join-Path $root 'Build\Package'
$assets  = Join-Path $root 'Build\Assets'
$output  = Join-Path $root 'Build\Output'

Write-Host "SKYBOUND packaging"
Write-Host "  project : $root"
Write-Host "  payload : $payload"

# --- clean staging ---------------------------------------------------------
if (Test-Path $payload) { Remove-Item $payload -Recurse -Force }
New-Item -ItemType Directory -Path $payload -Force | Out-Null
New-Item -ItemType Directory -Path $assets  -Force | Out-Null
New-Item -ItemType Directory -Path $output  -Force | Out-Null

# --- assets required by the installer --------------------------------------
$sysReq = @"
SKYBOUND system requirements
============================
OS           : Windows 10 64-bit (build 17763+) or Windows 11
CPU          : 6-core x64, 3.0 GHz or faster (8-core recommended)
GPU          : DirectX 12 Ultimate, 8 GB VRAM (12 GB+ for Ultra)
RAM          : 16 GB minimum, 32 GB recommended
Storage      : 60 GB available (SSD strongly recommended)
Runtime      : Microsoft Visual C++ 2015-2022 x64 (installed by setup if missing)
Network      : required for streaming world data (Cesium ion token needed)
"@
Set-Content -Path (Join-Path $assets 'SYSTEM_REQUIREMENTS.txt') -Value $sysReq -Encoding UTF8
if (-not (Test-Path (Join-Path $assets 'LICENSE.txt'))) {
    Set-Content -Path (Join-Path $assets 'LICENSE.txt') -Encoding UTF8 -Value @"
SKYBOUND - license and third-party notices
See Documentation/LICENSES_AND_ATTRIBUTION.md in the application folder.
This build bundles JSBSim (LGPL-2.1) as a separately replaceable DLL.
"@
}
if (-not (Test-Path (Join-Path $assets 'skybound.ico'))) {
    Write-Warning "Build\Assets\skybound.ico missing - installer will use the Inno Setup default icon."
}

# --- payload ---------------------------------------------------------------
if ($PackagedBuild -and (Test-Path $PackagedBuild)) {
    Write-Host "  staging packaged build from $PackagedBuild"
    Copy-Item -Path (Join-Path $PackagedBuild '*') -Destination $payload -Recurse -Force
    $exe = Join-Path $payload 'SKYBOUND.exe'
    if (-not (Test-Path $exe)) {
        throw "Packaged build did not contain SKYBOUND.exe - check the Unreal packaging log."
    }
    Write-Host "  payload staged: $((Get-ChildItem $payload -Recurse -File | Measure-Object).Count) files"
} else {
    Write-Warning "No packaged Unreal build supplied (-PackagedBuild)."
    Write-Warning "Staging DOCUMENTATION ONLY. This is NOT a playable game payload;"
    Write-Warning "the installer produced from this staging is for pipeline testing only."
    $docs = Join-Path $payload 'Documentation'
    New-Item -ItemType Directory -Path $docs -Force | Out-Null
    Copy-Item (Join-Path $root 'Documentation\*.md') $docs -Force
    Copy-Item (Join-Path $root 'README.md') $docs -Force -ErrorAction SilentlyContinue
}

# --- installer -------------------------------------------------------------
if ($BuildInstaller) {
    # winget installs Inno Setup per-user on this machine, so all three
    # locations are probed rather than assuming Program Files.
    $iscc = @(
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        'C:\Program Files\Inno Setup 6\ISCC.exe',
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $iscc) {
        throw "Inno Setup 6 not found. Install with: winget install JRSoftware.InnoSetup"
    }
    Write-Host "  compiling installer with $iscc"
    & $iscc (Join-Path $root 'Build\Installer\SKYBOUND.iss')
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed with exit code $LASTEXITCODE" }
    Get-ChildItem $output -Filter '*.exe' | ForEach-Object {
        Write-Host ("  built {0} ({1:N1} MB)" -f $_.Name, ($_.Length / 1MB))
    }
}
