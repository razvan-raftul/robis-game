; Program de instalare pentru Robi's game (Inno Setup)
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6B1E4C2A-9F3D-4E7B-A5C8-2D7F1B9E3A41}
AppName=Robi's game
AppVersion={#AppVersion}
AppPublisher=razvan-raftul
DefaultDirName={autopf}\Robi's game
DefaultGroupName=Robi's game
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=RobisGameSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\RobisGame.exe
CloseApplications=yes

[Languages]
#if FileExists(AddBackslash(SourcePath) + "Romanian.isl")
Name: "ro"; MessagesFile: "Romanian.isl"
#else
Name: "en"; MessagesFile: "compiler:Default.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "Creează o scurtătură pe desktop"; GroupDescription: "Scurtături:"

[Files]
Source: "dist\RobisGame.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Robi's game"; Filename: "{app}\RobisGame.exe"
Name: "{group}\Dezinstalează Robi's game"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Robi's game"; Filename: "{app}\RobisGame.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\RobisGame.exe"; Description: "Pornește Robi's game"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\RobisGame.exe.old"
Type: files; Name: "{app}\RobisGame.exe.new"
