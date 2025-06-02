$EntryPoint = Join-Path -Path $PSScriptRoot -ChildPath ci.py
$PythonPath = C:\python312\python.exe
& $PythonPath $EntryPoint $args
