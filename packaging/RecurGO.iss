#ifndef BuildSourceDir
  #error BuildSourceDir must point to the curated RecurGO stage directory.
#endif
#ifndef AppVersion
  #error AppVersion must be supplied by the release builder.
#endif

[Setup]
AppId={{D68E0D17-61C0-4F1D-9AD0-73377206F1EA}
AppName=RecurGO
AppVersion={#AppVersion}
AppPublisher=izaak
DefaultDirName={localappdata}\Programs\RecurGO
DisableDirPage=no
DefaultGroupName=RecurGO
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
MinVersion=10.0
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\RecurGO.exe
LicenseFile={#BuildSourceDir}\INSTALLER_LICENSE.txt
InfoBeforeFile={#BuildSourceDir}\INSTALLER_NOTICE.txt
OutputBaseFilename=RecurGO-{#AppVersion}-Windows-x64-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinese"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#BuildSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\RecurGO"; Filename: "{app}\RecurGO.exe"
Name: "{group}\Analysis Environment Check"; Filename: "{app}\check_analysis_environment.cmd"; WorkingDir: "{app}"
Name: "{group}\Start Optional Ollama"; Filename: "{app}\start_optional_ollama.cmd"; WorkingDir: "{app}"
Name: "{group}\Download Ollama Model"; Filename: "{app}\download_ollama_model.cmd"; WorkingDir: "{app}"
Name: "{group}\Installation Guide"; Filename: "{sys}\notepad.exe"; Parameters: """{app}\docs\INSTALL_WINDOWS.en.md"""
Name: "{group}\User Manual"; Filename: "{sys}\notepad.exe"; Parameters: """{app}\docs\USER_GUIDE.en.md"""
Name: "{group}\安装指南"; Filename: "{sys}\notepad.exe"; Parameters: """{app}\docs\INSTALL_WINDOWS.md"""
Name: "{group}\用户说明书"; Filename: "{sys}\notepad.exe"; Parameters: """{app}\docs\USER_GUIDE.md"""
Name: "{autodesktop}\RecurGO"; Filename: "{app}\RecurGO.exe"; IconFilename: "{app}\assets\recurgo.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\RecurGO.exe"; Description: "{cm:LaunchProgram,RecurGO}"; Flags: nowait postinstall skipifsilent
