@echo off
setlocal
set "HERE=%~dp0"
set "IN=%~1"

rem Log so you can see failures
set "LOG=%HERE%fix_video_file_run.log"
echo ==== %date% %time% ==== >> "%LOG%"
echo whoami: >> "%LOG%"
whoami >> "%LOG%"
echo IN=%IN% >> "%LOG%"

rem Run the ps1 using an absolute path
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%HERE%fix_video_file.ps1" "%IN%" >> "%LOG%" 2>&1
echo exitcode=%errorlevel% >> "%LOG%"

endlocal
exit /b %errorlevel%
