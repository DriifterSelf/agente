Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c npm start", 0
Set WshShell = Nothing
