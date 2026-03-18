' Start the PrintForge Auto-Slicer minimized (for Windows Startup folder)
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "pythonw """ & Replace(WScript.ScriptFullName, "start_watcher.vbs", "auto_slice.py") & """", 0, False
