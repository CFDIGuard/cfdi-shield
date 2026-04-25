#define MyAppName "CFDI Shield"
#define MyAppVersion "1.0 RC"
#define MyAppPublisher "CFDI Shield"
#define MyAppExeName "CFDIShield.exe"
#define MyServiceName "CFDIShield"

[Setup]
AppId={{D3B2E8A1-A2A7-4F4A-B547-2A6FC35CE880}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName=C:\CFDIShield
DefaultGroupName={#MyAppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=CFDIShieldSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Dirs]
Name: "{app}\run"

[Files]
Source: "..\dist\CFDIShield\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "C:\nssm\win64\nssm.exe"; DestDir: "{app}"; DestName: "nssm.exe"; Flags: ignoreversion

[Run]
Filename: "{cmd}"; Parameters: "/C if not exist ""{app}\.env"" copy /Y ""{app}\_internal\.env.example"" ""{app}\.env"""; Flags: runhidden
Filename: "{cmd}"; Parameters: "/C ""{app}\nssm.exe"" stop {#MyServiceName} >nul 2>&1 & exit /b 0"; Flags: runhidden
Filename: "{cmd}"; Parameters: "/C ""{app}\nssm.exe"" remove {#MyServiceName} confirm >nul 2>&1 & exit /b 0"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "install {#MyServiceName} ""{app}\{#MyAppExeName}"""; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set {#MyServiceName} AppDirectory ""{app}"""; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set {#MyServiceName} Start SERVICE_AUTO_START"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set {#MyServiceName} AppStdout ""{app}\run\service-stdout.log"""; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set {#MyServiceName} AppStderr ""{app}\run\service-stderr.log"""; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "start {#MyServiceName}"; Flags: runhidden

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C ""{app}\nssm.exe"" stop {#MyServiceName} >nul 2>&1 & exit /b 0"; Flags: runhidden; RunOnceId: "StopCFDIShieldService"
Filename: "{cmd}"; Parameters: "/C ""{app}\nssm.exe"" remove {#MyServiceName} confirm >nul 2>&1 & exit /b 0"; Flags: runhidden; RunOnceId: "RemoveCFDIShieldService"

[INI]
Filename: "{commondesktop}\CFDI Shield.url"; Section: "InternetShortcut"; Key: "URL"; String: "http://127.0.0.1:8000"; Flags: uninsdeleteentry
Filename: "{commondesktop}\CFDI Shield.url"; Section: "InternetShortcut"; Key: "IconFile"; String: "{app}\{#MyAppExeName}"; Flags: uninsdeleteentry
Filename: "{commondesktop}\CFDI Shield.url"; Section: "InternetShortcut"; Key: "IconIndex"; String: "0"; Flags: uninsdeleteentry

[UninstallDelete]
Type: files; Name: "{commondesktop}\CFDI Shield.url"
