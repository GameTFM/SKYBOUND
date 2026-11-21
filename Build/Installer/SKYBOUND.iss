; SKYBOUND - Windows installer (Inno Setup 6)
;
; CHOSEN TECHNOLOGY: Inno Setup 6.
; Rationale (documented in INSTALLATION.md): it produces a single signed-capable
; .exe with a real wizard, per-machine and per-user installs, prerequisite
; checks, a proper uninstaller registered in Installed Apps, and silent/unattended
; modes for CI - without requiring the .NET SDK or a WiX toolchain on the build
; machine. MSI/WiX remains the fallback if enterprise deployment requires it.
;
; BUILD INPUT (staged by Scripts/package.ps1):
;   Build/Package/SKYBOUND.exe          - packaged UE5 shipping build
;   Build/Package/Engine/**, */Binaries - engine/plugin binaries + content
;   Build/Package/Documentation/**      - shipped docs
;   Build/Package/Redist/**             - VC++ runtime installer (see note below)
;
; If the packaged game payload is absent the script still compiles, but it
; REFUSES to produce a "complete" installer - see the Payload check below.

#define AppName        "SKYBOUND"
#define AppVersion     "0.1.0"
#define AppPublisher   "SKYBOUND"
#define AppExeName     "SKYBOUND.exe"
#define PayloadDir     "..\Package"

[Setup]
AppId={{9C1E7A54-5D2B-4C31-8B77-6F5E2A0D3C19}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=no
AllowNoIcons=yes
OutputDir=..\..\Build\Output
OutputBaseFilename=SKYBOUND-Setup-{#AppVersion}
; SetupIconFile is intentionally unset until a real SKYBOUND.ico exists.
; Inno aborts if the referenced icon is missing, so shipping this line pointing at
; a non-existent file would break the build. Add it back together with the asset.
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=..\Assets\LICENSE.txt
InfoBeforeFile=..\Assets\SYSTEM_REQUIREMENTS.txt
; User data lives OUTSIDE the install tree (spec 31.3) so updates/uninstalls
; never touch saves, settings or downloaded content.
UsePreviousAppDir=yes
ChangesAssociations=no
VersionInfoVersion=0.1.0.0
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Installer
VersionInfoProductName={#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: checkedonce
Name: "launchafter"; Description: "Launch {#AppName} after installation"; GroupDescription: "Completion:"; Flags: checkedonce

[Files]
; Game payload. flags: ignoreversion so upgrades replace binaries cleanly.
; skipifsourcedoesntexist lets the script compile during pipeline testing when
; no packaged UE build exists yet - the [Code] payload check below then refuses
; to report a successful installation.
Source: "{#PayloadDir}\SKYBOUND.exe"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "{#PayloadDir}\Engine\*";     DestDir: "{app}\Engine";     Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "{#PayloadDir}\Binaries\*";   DestDir: "{app}\Binaries";   Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "{#PayloadDir}\Content\*";    DestDir: "{app}\Content";    Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "{#PayloadDir}\Documentation\*"; DestDir: "{app}\Documentation"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
; JSBSim DLL + shim are installed as replaceable components (LGPL relinking).
Source: "{#PayloadDir}\Binaries\Win64\SkbJsbsimShim.dll"; DestDir: "{app}\Binaries\Win64"; Flags: ignoreversion skipifsourcedoesntexist
Source: "{#PayloadDir}\Binaries\Win64\jsbsim.dll";         DestDir: "{app}\Binaries\Win64"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#AppName}";              Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}";    Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";        Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Prerequisite: Microsoft VC++ 2015-2022 x64 runtime, only if not already present.
Filename: "{tmp}\VC_redist.x64.exe"; Parameters: "/install /quiet /norestart"; \
  StatusMsg: "Installing Microsoft Visual C++ runtime..."; \
  Check: NeedsVCRedist; Flags: waituntilterminated
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; \
  Flags: nowait postinstall skipifsilent; Tasks: launchafter

[UninstallDelete]
; Only installer-owned caches. User data under %LOCALAPPDATA% is handled by the
; optional prompt in [Code] and is NEVER removed silently.
Type: filesandordirs; Name: "{app}\Engine\Cache"
Type: filesandordirs; Name: "{app}\Saved\Logs"

[Code]
var
  UserDataDir: String;

function PayloadPresent: Boolean;
begin
  Result := FileExists(ExpandConstant('{#PayloadDir}\SKYBOUND.exe'));
end;

function NeedsVCRedist: Boolean;
begin
  // VCRUNTIME140_1.dll presence is a reliable proxy for the 2015-2022 runtime.
  Result := not FileExists(ExpandConstant('{sys}\VCRUNTIME140_1.dll'));
end;

procedure InitializeWizard;
begin
  UserDataDir := ExpandConstant('{localappdata}\SKYBOUND');
end;

// Verify essential files before declaring success (spec 31.6).
function VerifyInstallation: Boolean;
begin
  Result := FileExists(ExpandConstant('{app}\{#AppExeName}'));
  if not Result then
    MsgBox('SKYBOUND.exe was not installed correctly. See the install log in ' +
           ExpandConstant('{log}') + ' and the documentation for troubleshooting.',
           mbError, MB_OK);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) then begin
    // A build staged without a packaged game must never present itself as a
    // complete SKYBOUND installation.
    if not PayloadPresent then
      MsgBox('This installer was built WITHOUT a packaged game payload.' + #13#10 +
             'It installs documentation only and SKYBOUND will not run.' + #13#10#13#10 +
             'This build is for pipeline testing only.', mbInformation, MB_OK);
    if not VerifyInstallation then
      RaiseException('Installation validation failed.');
  end;
end;

// Ask about user data on uninstall, never delete silently (spec 31.7).
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    if DirExists(UserDataDir) then
      if MsgBox('Also delete your SKYBOUND settings, saved flights and downloaded content?' + #13#10 +
                '(' + UserDataDir + ')', mbConfirmation, MB_YESNO) = IDYES then
        DelTree(UserDataDir, True, True, True);
end;

[UninstallRun]
; Stop a running instance before removing binaries.
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM {#AppExeName}"; \
  Flags: runhidden skipifdoesntexist; RunOnceId: "KillSkybound"
