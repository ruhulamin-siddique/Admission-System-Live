Set FSO = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

' Wait up to 30 seconds for Google Drive D:\ to mount after boot
For i = 1 To 15
    If FSO.DriveExists("D") Then Exit For
    WScript.Sleep 2000
Next

If FSO.FolderExists("D:\My Drive\1-Python\1-Admission") Then
    WshShell.CurrentDirectory = "D:\My Drive\1-Python\1-Admission"
    WshShell.Run "cmd.exe /c run_server.bat", 0, False
End If
