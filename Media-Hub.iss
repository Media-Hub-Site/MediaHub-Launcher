[Setup]
; Información básica
AppName=Media Hub
AppVersion=1.5
AppPublisher=Alan Dave
DefaultDirName={autopf}\Media Hub
DefaultGroupName=Media Hub
SetupIconFile=assets\hub\Media-Hub.ico
Compression=lzma
SolidCompression=yes
OutputDir=Output
OutputBaseFilename=MediaHubInstaller

; --- MEJORAS DE RUTA Y UX ---
; Permite que el usuario cambie la ruta (esto es por defecto, pero se asegura con DisableDirPage=no)
DisableDirPage=no
; Si el usuario ya lo instaló antes, recordará la ruta anterior
UsePreviousAppDir=yes
; Evita que se instale en la raíz de una unidad (ej: C:\) sin una subcarpeta
AppendDefaultDirName=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Usamos ignoreversion para que siempre sobrescriba archivos viejos en actualizaciones
Source: "dist\Media Hub\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Media Hub"; Filename: "{app}\Media Hub.exe"
Name: "{autodesktop}\Media Hub"; Filename: "{app}\Media Hub.exe"; Tasks: desktopicon

[Run]
; Flags recomendados para evitar problemas de permisos al lanzar la app tras instalar
Filename: "{app}\Media Hub.exe"; Description: "{cm:LaunchProgram,Media Hub}"; Flags: nowait postinstall skipifsilent runasoriginaluser
