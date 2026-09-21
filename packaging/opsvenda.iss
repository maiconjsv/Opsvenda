; Inno Setup script for OpsVenda's standalone Windows installer.
; Compiled by packaging/build_windows.ps1 (via ISCC.exe) against the
; already-assembled dist\windows\runtime\ folder (embedded Python +
; dependencies + app code - see build_windows.ps1 for how that's built).
;
; Produces dist\OpsVenda-Setup.exe: a normal Windows installer wizard
; (Avançar/Concluir, barra de progresso, aparece em "Adicionar ou remover
; programas" com desinstalador). Installs per-user (no admin/UAC prompt)
; and lets Inno Setup's own shell APIs resolve the real Desktop/Start Menu
; folders - this avoids the "$Home\Desktop" bug that breaks when OneDrive
; redirects Desktop elsewhere.

#define MyAppName "OpsVenda"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "OpsVenda"

[Setup]
AppId={{6F3B9C2A-6E9B-4B7B-9B1E-6C6C8B2E3A11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\OpsVenda
DisableProgramGroupPage=yes
DisableDirPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=OpsVenda-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
UninstallDisplayName={#MyAppName}
SetupLogging=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"; Flags: checkedonce

[Files]
Source: "..\dist\windows\runtime\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "install-windows.ps1"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\run_desktop.py"""; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\run_desktop.py"""; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\run_desktop.py"""; Description: "Abrir o OpsVenda agora"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; The app stores its database/backups outside {app} (in %LOCALAPPDATA%\OpsVenda\..
; via OPSVENDA_DATA_DIR default) so a normal uninstall never touches user data.
