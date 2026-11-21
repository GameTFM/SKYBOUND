# SKYBOUND - build jsbsim.dll and the C-ABI shim.
#
#   .\Scripts\build_jsbsim_shim.ps1 -JsbsimSource C:\src\jsbsim [-Configuration Release]
#
# WHY THIS EXISTS
# ---------------
# JSBSim is LGPL-2.1 and the Unreal Engine EULA does not permit statically linked
# LGPL code in a packaged product. JSBSim is therefore built as a standalone DLL
# and reached through a SKYBOUND-owned C-ABI shim, so that:
#   * only the shim includes JSBSim headers,
#   * the user can replace jsbsim.dll with their own build (LGPL relinking),
#   * the game module has no LGPL compile dependency.
#
# Requires: Visual Studio 2022 (C++ workload) and a JSBSim source checkout
# (https://github.com/JSBSim-Team/jsbsim). CMake is bundled with VS.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$JsbsimSource,
    [string]$Configuration = 'Release',
    [string]$OutDir = ""
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $OutDir) { $OutDir = Join-Path $root 'Binaries\Win64' }

if (-not (Test-Path (Join-Path $JsbsimSource 'CMakeLists.txt'))) {
    throw "JsbsimSource '$JsbsimSource' does not look like a JSBSim checkout (no CMakeLists.txt)."
}
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

$cmake = (Get-Command cmake -ErrorAction SilentlyContinue).Source
if (-not $cmake) { $cmake = 'C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe' }
if (-not (Test-Path $cmake)) { throw "cmake.exe not found. Install Visual Studio 2022 with the C++ workload." }

# --- 1. JSBSim as a shared library ----------------------------------------
$build = Join-Path $root 'Build\jsbsim-build'
Write-Host "Configuring JSBSim (shared) -> $build"
& $cmake -S $JsbsimSource -B $build -G 'Visual Studio 17 2022' -A x64 `
    -DBUILD_SHARED_LIBS=ON -DCMAKE_BUILD_TYPE=$Configuration
if ($LASTEXITCODE -ne 0) { throw "CMake configure failed ($LASTEXITCODE)" }

& $cmake --build $build --config $Configuration --target JSBSim
if ($LASTEXITCODE -ne 0) { throw "JSBSim build failed ($LASTEXITCODE)" }

$dll = Get-ChildItem $build -Recurse -Filter 'JSBSim.dll' -ErrorAction SilentlyContinue |
       Select-Object -First 1
if (-not $dll) { throw "JSBSim.dll not produced - check the CMake output above." }
Copy-Item $dll.FullName (Join-Path $OutDir 'jsbsim.dll') -Force
Write-Host "  jsbsim.dll -> $OutDir"

# --- 2. The SKYBOUND shim -------------------------------------------------
# The shim source lives with the plugin so its ABI stays next to its consumer.
$shimSrc = Join-Path $root 'Tools\JSBSimShim'
if (-not (Test-Path $shimSrc)) {
    Write-Warning "Tools\JSBSimShim not found - cannot build SkbJsbsimShim.dll."
    Write-Warning "The game will report flight dynamics as unavailable until it exists."
    exit 0
}
$shimBuild = Join-Path $root 'Build\shim-build'
Write-Host "Building shim -> $shimBuild"
& $cmake -S $shimSrc -B $shimBuild -G 'Visual Studio 17 2022' -A x64 `
    -DJSBSIM_SOURCE=$JsbsimSource -DCMAKE_BUILD_TYPE=$Configuration
if ($LASTEXITCODE -ne 0) { throw "Shim configure failed ($LASTEXITCODE)" }
& $cmake --build $shimBuild --config $Configuration
if ($LASTEXITCODE -ne 0) { throw "Shim build failed ($LASTEXITCODE)" }

Get-ChildItem $shimBuild -Recurse -Filter 'SkbJsbsimShim.dll' |
    Select-Object -First 1 |
    ForEach-Object { Copy-Item $_.FullName (Join-Path $OutDir 'SkbJsbsimShim.dll') -Force }

Write-Host "Done. Files in ${OutDir}:"
Get-ChildItem $OutDir -Filter '*.dll' | Format-Table Name, Length
