; Installer Windows (Inno Setup 6) per QEMU-3dfx Manager.
; Compilazione:  iscc /DAppVersion=0.2.0 packaging\windows\installer.iss
; Richiede la build PyInstaller in dist\QEMU-3dfx Manager\

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "QEMU-3dfx Manager"
#define AppExe "QEMU-3dfx Manager.exe"

[Setup]
; AppId identifica l'app per aggiornamenti e disinstallazione: non cambiarlo.
AppId={{6B1E0F3A-4C2D-4E8B-9A7F-3D5C1B2E9F40}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=QEMU-3dfx Manager
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Installazione per l'utente corrente: non servono privilegi di amministratore.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist
OutputBaseFilename=QEMU-3dfx-Manager-{#AppVersion}-Setup
SetupIconFile=..\icons\app.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\..\dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

; Le VM dell'utente e QEMU-3dfx scaricato (in %APPDATA%) non vengono
; toccati dalla disinstallazione.
