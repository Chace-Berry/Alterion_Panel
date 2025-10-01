; Inno Setup Script for Alterion Panel
; Requires Inno Setup 6.0 or later: https://jrsoftware.org/isinfo.php

#define MyAppName "Alterion Panel"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Chace Berry"
#define MyAppURL "https://github.com/yourusername/alterion_panel"
#define MyAppExeName "AlterionPanel.exe"

[Setup]
; Basic setup information
AppId={A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation directories
DefaultDirName={autopf}\chace_berry\Alterion\AlterionPanel
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Output
OutputDir=installer_output
OutputBaseFilename=AlterionPanel_Setup_{#MyAppVersion}
SetupIconFile=frontend\public\favicon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

; Privileges
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; License and info
LicenseFile=LICENSE
InfoBeforeFile=README.md

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenuicon"; Description: "Create Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startup"; Description: "Run {#MyAppName} at Windows startup"; GroupDescription: "Startup Options"; Flags: unchecked

[Files]
; Main application files
Source: "dist\AlterionPanel\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
; Start Menu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

; Desktop icon (optional)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

; Startup (optional)
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: startup

[Run]
; Ask to run after installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up data on uninstall (be careful with this)
Type: filesandordirs; Name: "{app}\backend\backend\dashboard\serverid.dat"
Type: filesandordirs; Name: "{app}\backend\backend\services\*.pem"
Type: filesandordirs; Name: "{app}\backend\backend\db.sqlite3"

[Code]
var
  DataDirPage: TInputDirWizardPage;
  KeepDataCheckbox: TNewCheckBox;

procedure InitializeWizard;
begin
  { Create a custom page for data directory selection }
  DataDirPage := CreateInputDirPage(wpSelectDir,
    'Select Data Directory', 'Where should {#MyAppName} store its data?',
    'Select the folder where {#MyAppName} should store its database, keys, and configuration files.',
    False, '');
  DataDirPage.Add('');
  DataDirPage.Values[0] := ExpandConstant('{userappdata}\{#MyAppName}');
end;

function GetDataDir(Param: String): String;
begin
  Result := DataDirPage.Values[0];
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  DataDir: String;
begin
  if CurStep = ssPostInstall then
  begin
    { Create data directory }
    DataDir := DataDirPage.Values[0];
    if not DirExists(DataDir) then
      CreateDir(DataDir);
    
    { You could run initial setup here }
    { Exec(ExpandConstant('{app}\{#MyAppExeName}'), '--setup', '', SW_SHOW, ewWaitUntilTerminated, ResultCode); }
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
  Response: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    Response := MsgBox('Do you want to keep your data files (database, configurations, keys)?', mbConfirmation, MB_YESNO);
    if Response = IDNO then
    begin
      { Delete data directory }
      DataDir := ExpandConstant('{userappdata}\{#MyAppName}');
      if DirExists(DataDir) then
        DelTree(DataDir, True, True, True);
    end;
  end;
end;
