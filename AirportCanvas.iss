#define AppVersion "1.1.0"

[Setup]
AppId=AirportCanvas.Desktop
AppName=Airport Canvas
AppPublisher=刃下狼血
AppPublisherURL=https://github.com/RXLX-CHINA
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\Airport Canvas
DefaultGroupName=Airport Canvas
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes
SetupIconFile=src\airport_canvas\AirportCanvas.ico
LicenseFile=COPYING
UninstallDisplayIcon={app}\AirportCanvas.exe
OutputDir=release
OutputBaseFilename=AirportCanvas_{#AppVersion}_Windows_x64_Setup
Compression=lzma2
SolidCompression=yes

[Files]
Source: "build\gui.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Airport Canvas"; Filename: "{app}\AirportCanvas.exe"; WorkingDir: "{app}"

[Registry]
Root: HKCU; Subkey: "Software\Classes\AirportCanvas.Project"; ValueType: string; ValueData: "Airport Canvas Project"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\AirportCanvas.Project\DefaultIcon"; ValueType: string; ValueData: """{app}\AirportCanvasProject.ico"",0"
Root: HKCU; Subkey: "Software\Classes\AirportCanvas.Project\shell\open\command"; ValueType: string; ValueData: """{app}\AirportCanvas.exe"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\.acp\OpenWithProgids"; ValueType: string; ValueName: "AirportCanvas.Project"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Airport Canvas\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "Airport Canvas"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Airport Canvas\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Airport project editor"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Airport Canvas\Capabilities\FileAssociations"; ValueType: string; ValueName: ".acp"; ValueData: "AirportCanvas.Project"
Root: HKCU; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "Airport Canvas"; ValueData: "Software\Airport Canvas\Capabilities"; Flags: uninsdeletevalue
