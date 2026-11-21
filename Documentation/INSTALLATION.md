# SKYBOUND — Installation

## Installer technology: Inno Setup 6

Chosen over WiX/MSI because it produces a single signed-capable `.exe` with a
full wizard, per-machine/per-user installs, prerequisite checks, a registered
uninstaller and silent/unattended modes — without requiring the .NET SDK on the
build machine. WiX remains a documented fallback if an enterprise deployment
requires an MSI.

Script: `Build/Installer/SKYBOUND.iss` · Build: `Scripts/package.ps1 -BuildInstaller`

## What the wizard does

1. Welcome, with SKYBOUND branding and application icon
2. Licence and third-party notices (`Build/Assets/LICENSE.txt`)
3. System requirements before committing (`Build/Assets/SYSTEM_REQUIREMENTS.txt`)
4. Install location (`C:\Program Files\SKYBOUND` by default, user-changeable)
5. Disk-space check (Inno computes it from the staged payload)
6. Progress
7. Shortcut options: Start Menu always, desktop shortcut optional
8. Optional "launch after install"
9. Completion

## Prerequisites

Detected and installed if missing: **Microsoft Visual C++ 2015–2022 x64 runtime**
(presence probed via `VCRUNTIME140_1.dll`). The installer does **not** require or
install Unreal Engine, Visual Studio or any development tool.

Windows version: 10 build 17763+ or Windows 11, x64. Enforced by `MinVersion` and
`ArchitecturesAllowed`.

## Directory policy

| Path | Contents | Survives update | Survives uninstall |
|---|---|---|---|
| `C:\Program Files\SKYBOUND` | binaries, content, engine | replaced | removed |
| `%LOCALAPPDATA%\SKYBOUND` | settings, saves, control profiles, favourites, downloaded content, logs, cache | **yes** | only if the user says yes |

User data is deliberately outside the install tree. An ordinary update or
uninstall never touches flight saves or settings silently (spec 31.3, 31.7).

## Validation and failure behaviour

After files are written, the installer verifies `SKYBOUND.exe` exists and raises
a clear error with the log path if not. It does not leave a broken install
registered as successful.

## Repair

Run the installer again and choose **Repair** (Inno's default behaviour when the
same `AppId` is detected). It re-verifies and rewrites application files and
leaves `%LOCALAPPDATA%\SKYBOUND` untouched.

## Uninstall

**Settings → Apps → Installed apps → SKYBOUND → Uninstall**, or the Start Menu
entry. Removes binaries, shortcuts and registration. If user data exists you are
asked once: *"Also delete your settings, saved flights and downloaded content?"*
Declining is safe and keeps everything.

## Updates

The installer supports in-place upgrade over an older version (same `AppId`,
`UsePreviousAppDir=yes`). An auto-update channel is designed but **not
implemented**: it must verify signatures and never overwrite user content
(spec 31.8). Until it exists, updates are a manual installer run.

## Current limitation

`SKYBOUND.iss` has not yet produced a playable installer, because no packaged
Unreal build exists on this machine. `Scripts/package.ps1` without
`-PackagedBuild` stages documentation only and prints a warning that the result
is **not** a game payload.
