' MarketPulse 每日任务启动器
' 放在 Startup 文件夹，每次登录自动执行一次
Set WshShell = CreateObject("WScript.Shell")
' 将此脚本放在 MarketPulse 根目录，双击即可
' 获取脚本所在目录的上级（即项目根目录）
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "cmd /c """ & scriptDir & "\scripts\daily_task.bat""", 0, False
