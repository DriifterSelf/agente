$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
$ShortcutPath = Join-Path -Path $DesktopPath -ChildPath "Agente Studio.lnk"
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Shortcut.TargetPath = "wscript.exe"
$Shortcut.Arguments = "`"$ScriptDir\launch.vbs`""
$Shortcut.WorkingDirectory = $ScriptDir
$Shortcut.Description = "Agente Autónomo de Oficina y Sistema"
$Shortcut.Save()
Write-Host "Acceso directo creado exitosamente en el Escritorio." -ForegroundColor Green
