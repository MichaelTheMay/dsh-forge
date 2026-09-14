#ifndef AppVersion
  #error AppVersion must be provided with /DAppVersion=x.y.z
#endif
#ifndef SourceDir
  #error SourceDir must point to the PyInstaller application directory
#endif
#ifndef OutputDir
  #error OutputDir must point to the installer output directory
#endif
#ifndef IconPath
  #error IconPath must point to the application icon
#endif

[Setup]
AppId={{D70F4E6D-1B17-4BD5-964A-A2267F68B85F}
AppName=DSH Forge
AppVersion={#AppVersion}
AppPublisher=DSH Forge contributors
AppPublisherURL=https://github.com/MichaelTheMay/dsh-forge
AppSupportURL=https://github.com/MichaelTheMay/dsh-forge/issues
AppUpdatesURL=https://github.com/MichaelTheMay/dsh-forge/releases/latest
DefaultDirName={localappdata}\Programs\DSH Forge
DefaultGroupName=DSH Forge
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=DSH-Forge-{#AppVersion}-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile={#IconPath}
CloseApplications=yes
RestartApplications=no
AppMutex=Local\MichaelTheMay.DSHForge
UninstallDisplayIcon={app}\DSH Forge.exe
VersionInfoCompany=DSH Forge contributors
VersionInfoDescription=DSH Forge desktop launcher
VersionInfoProductName=DSH Forge

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\DSH Forge"; Filename: "{app}\DSH Forge.exe"
Name: "{autodesktop}\DSH Forge"; Filename: "{app}\DSH Forge.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\DSH Forge.exe"; Description: "Open DSH Forge"; Flags: nowait postinstall skipifsilent
