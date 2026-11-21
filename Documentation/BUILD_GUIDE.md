# SKYBOUND — Build Guide

## Verified environment gap

The machine this project was scaffolded on has: Windows 11, 32 GB RAM, Intel
Core i7-1185G7, **Intel Iris Xe integrated graphics (2 GB shared)**, 129 GB free,
Python 3.12, Node 26, Git — and **no Unreal Engine, no Visual Studio, no .NET
SDK, no C++ compiler**.

Consequences, stated plainly:

* `Source/`, `Plugins/`, `Config/` have **never been compiled**.
* A Lumen/Nanite target cannot be validated on an Iris Xe iGPU even once compiled.
* The Python tooling and tests run fine and are the current verification evidence.

## Required toolchain

| Requirement | Version | Notes |
|---|---|---|
| Unreal Engine | **5.6** | Cesium for Unreal v2.31 supports 5.6/5.7/5.8 only; 5.6 is the oldest supported, chosen for plugin compatibility |
| Visual Studio | 2022 (17.x) | Workloads: *Game development with C++*, *.NET desktop*, Windows 10/11 SDK |
| Cesium for Unreal | 2.31 | Install into UE 5.6, enable in the project |
| Python | 3.10+ | Tooling only |
| Inno Setup | 6 | `winget install JRSoftware.InnoSetup` |
| Disk | ~140 GB | UE 5.6 + VS + DDC |

**Do not** pick UE 5.5 or older: Cesium for Unreal dropped 5.5 at v2.29.

## Build steps

```powershell
# 1. Generate the project files
"C:\Program Files\Epic Games\UE_5.6\Engine\Build\BatchFiles\GenerateProjectFiles.bat" -project="$PWD\SKYBOUND.uproject" -game -engine

# 2. Compile (Development Editor first)
"C:\Program Files\Epic Games\UE_5.6\Engine\Build\BatchFiles\Build.bat" SKYBOUNDEditor Win64 Development -project="$PWD\SKYBOUND.uproject" -waitmutex

# 3. Open the editor and confirm the modules load
"C:\Program Files\Epic Games\UE_5.6\Engine\Binaries\Win64\UnrealEditor.exe" "$PWD\SKYBOUND.uproject"

# 4. Package a Shipping build
"C:\Program Files\Epic Games\UE_5.6\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun `
  -project="$PWD\SKYBOUND.uproject" -noP4 -platform=Win64 -clientconfig=Shipping `
  -cook -allmaps -build -stage -pak -archive -archivedirectory="$PWD\Build\Packaged"
```

## JSBSim shim

JSBSim must be built as a DLL and wrapped by the C-ABI shim:

```powershell
.\Scripts\build_jsbsim_shim.ps1 -JsbsimSource C:\src\jsbsim
```

Output goes to `Binaries\Win64\` (`jsbsim.dll` + `SkbJsbsimShim.dll`). Until that
exists, the game reports flight dynamics as unavailable — by design.

## Expected first-run work

The C++ has never been compiled, so expect to fix:

* include paths and module names for Cesium (`CesiumRuntime`),
* `FTickableGameObject` + `UGameInstanceSubsystem` multiple-inheritance details,
* any API drift between UE 5.6 and what the scaffold assumes.

This is normal first-compile work, not a sign the design is wrong.

## Package + installer

```powershell
.\Scripts\package.ps1 -PackagedBuild Build\Packaged\Windows -BuildInstaller
```

Produces `Build\Output\SKYBOUND-Setup-0.1.0.exe`.

## Continuous checks (run before every commit)

```bash
python Tools/FlightDynamics/validate.py
python Tests/test_jsbsim_models.py
python Tests/run_all.py
```
