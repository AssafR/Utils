@echo off
setlocal
set "HERE=%~dp0"

if "%~1"=="" (
  echo Usage: %~nx0 "input.ts" [extra ps args...]
  exit /b 2
)

set "IN=%~1"
shift

rem Build remaining args manually, since %* doesn't change after SHIFT
set "REST_ARGS="
:args_loop
if "%~1"=="" goto args_done
set "REST_ARGS=%REST_ARGS% "%~1""
shift
goto args_loop
:args_done

echo IN="%IN%"
echo REST=%REST_ARGS%

powershell.exe -NoProfile -ExecutionPolicy Bypass ^
  -File "%HERE%fix_video_file.ps1" -InputFile "%IN%" %REST_ARGS%

set "EC=%errorlevel%"
endlocal
exit /b %EC%
