$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopPath "Agente Studio.lnk"
$TargetVBS = "c:\Users\uwu\Documents\agente\launch.vbs"

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = "`"$TargetVBS`""
$Shortcut.WorkingDirectory = "c:\Users\uwu\Documents\agente"
$Shortcut.Description = "Agente Autónomo de Oficina y Sistema para Windows"
$Shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,220" # Modern icon
$Shortcut.Save()

Write-Host "Acceso directo creado exitosamente en el Escritorio: $ShortcutPath"
