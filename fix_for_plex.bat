@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ---- Input handling (space-safe) ----
REM Always quote the input path when calling this script.
REM You can also drag-and-drop a file onto the .cmd.

if "%~1"=="" (
  echo Usage: %~nx0 "full\path\to\input.mkv" [audio_index]
  echo Example: %~nx0 "S:\TV Shows\Pluribus\Pluribus S01E07 ....mkv" 0
  exit /b 1
)

set "IN=%~1"
set "AIDX=%~2"
if "%AIDX%"=="" set "AIDX=0"

REM ---- Build output path safely ----
set "OUT=%~dpn1_plex.mkv"

echo Input : "%IN%"
echo Audio : index %AIDX%
echo Output: "%OUT%"
echo.

REM ---- ffmpeg ----
ffmpeg -hide_banner -y -fflags +genpts -i "%IN%" ^
  -map 0:v:0 ^
  -map 0:a:%AIDX%? ^
  -map 0:s? ^
  -map -0:d? ^
  -c:v copy ^
  -c:a aac -b:a 192k -ac 2 ^
  -c:s srt ^
  -max_interleave_delta 0 ^
  "%OUT%"

if errorlevel 1 (
  echo.
  echo ERROR: ffmpeg failed.
  echo Try a different audio_index: 0 or 1 are most common.
  exit /b 1
)

echo.
echo Done.
endlocal
