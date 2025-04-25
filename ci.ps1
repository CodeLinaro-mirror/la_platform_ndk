$EntryPoint = Join-Path -Path $PSScriptRoot -ChildPath ci.py
$PythonPath = Join-Path -Path $PSScriptRoot -ChildPath ..\prebuilts\python\windows-x86\python.exe
& $PythonPath $EntryPoint $args
