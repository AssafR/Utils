@echo off
setlocal

echo %date% %time% >> "%~dp0pp_test.log"
whoami >> "%~dp0pp_test.log"
dir E:\ >> "%~dp0pp_test.log" 2>&1
dir "E:\DriveE\ASSAF\program\Utils" >> "%~dp0pp_test.log" 2>&1


set "IN=%~1"

call "E:\DriveE\ASSAF\program\Utils\fix_video_file.bat" "%IN%"

endlocal