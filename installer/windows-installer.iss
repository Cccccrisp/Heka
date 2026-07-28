#define MyAppName "Heka"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Heka"
#define MyAppExeName "Heka.exe"

[Setup]
AppId={{4D25CF67-2D1F-4D36-BD74-5D5C98DCA701}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Heka
DefaultGroupName=Heka
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=Heka-Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern

[Files]
Source: "..\dist\Heka.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Heka"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Heka"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "在桌面创建 Heka 图标"; GroupDescription: "额外选项："

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "打开 Heka"; Flags: nowait postinstall skipifsilent
