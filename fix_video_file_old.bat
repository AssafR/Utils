@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem === Usage: triage_remux.bat "input.ts" ===

if "%~1"=="" (
  echo Usage: %~nx0 "input_file"
  exit /b 1
)

set "IN=%~1"
if not exist "%IN%" (
  echo ERROR: Input not found: "%IN%"
  exit /b 2
)

rem --- Build output name ---
set "DIR=%~dp1"
set "BASE=%~n1"
set "EXT=%~x1"

if /I "%EXT%"==".mkv" (
  set "OUT=%DIR%%BASE%_.mkv"
) else (
  set "OUT=%DIR%%BASE%.mkv"
)

rem --- Post-mortem verification log ---
set "LOG=%OUT:~0,-4%.log" 

rem --- Choose if we need AAC ADTS -> ASC bitstream filter ---
rem We detect AAC audio in MPEG-TS / M2TS / TS-ish inputs and apply the filter,
rem because it commonly prevents "malformed AAC" issues when remuxing.
set "NEED_AAC_BSF=0"

for %%E in (.ts .m2ts .mts .trp .tp .vob) do (
  if /I "%EXT%"=="%%E" set "MAYBE_TS=1"
)

if defined MAYBE_TS (
  for /f "usebackq delims=" %%A in (`
    ffprobe -v error -select_streams a:0 -show_entries stream^=codec_name -of default^=nokey^=1:noprint_wrappers^=1 "%IN%"
  `) do (
    if /I "%%A"=="aac" set "NEED_AAC_BSF=1"
  )
)

echo.
echo Input : "%IN%"
echo Output: "%OUT%"
if "%NEED_AAC_BSF%"=="1" (
  echo Mode  : TS + AAC ^(using -bsf:a aac_adtstoasc^)
) else (
  echo Mode  : Generic remux ^(no audio bitstream filter^)
)
echo.


rem --- Core triage remux command (NO RE-ENCODE) ---
rem +genpts: regenerate missing PTS
rem -err_detect ignore_err: keep going through minor corruption
rem -start_at_zero: normalize start timestamps
rem -map 0: keep all streams
rem -max_interleave_delta 0: reduces weird A/V interleave issues in some captures
rem -ignore_unknown: don't fail on odd private streams
rem -copy_unknown: keep unknown streams if possible
rem -map_metadata 0: preserve metadata
rem -map_chapters 0: preserve chapters if present
rem -c copy: stream copy (no recode)

if "%NEED_AAC_BSF%"=="1" (
  ffmpeg -hide_banner -y ^
    -fflags +genpts ^
    -err_detect ignore_err ^
    -probesize 100M -analyzeduration 100M ^
    -ignore_unknown -copy_unknown ^
    -i "%IN%" ^
    -map 0 -map_metadata 0 -map_chapters 0 ^
    -c copy ^
    -start_at_zero ^
    -max_interleave_delta 0 ^
    -bsf:a aac_adtstoasc ^
    "%OUT%"
) else (
  ffmpeg -hide_banner -y ^
    -fflags +genpts ^
    -err_detect ignore_err ^
    -ignore_unknown -copy_unknown ^
    -i "%IN%" ^
    -map 0 -map_metadata 0 -map_chapters 0 ^
    -c copy ^
    -start_at_zero ^
    -max_interleave_delta 0 ^
    "%OUT%"
)

set "RC=%ERRORLEVEL%"
echo.

if not "%RC%"=="0" (
  echo FAILED with exit code %RC%
  exit /b %RC%
)

echo SUCCESS.
echo.


REM -----------------------

rem --- Post-mortem verification (single pass, progress bar, warnings-only log) ---
echo Running post-mortem verification pass...

rem Get duration in seconds (for percentage). Might be empty for some files.
set "DUR="
for /f "usebackq delims=" %%D in (`
  ffprobe -v error -show_entries format^=duration -of default^=nokey^=1:noprint_wrappers^=1 "%OUT%"
`) do set "DUR=%%D"

type nul > "%LOG%"

set "PS1=%TEMP%\ff_verify_progress_%RANDOM%%RANDOM%.ps1"

rem Force echo off (grouped blocks can behave weirdly)
@echo off

> "%PS1%" (
  echo param([double]$DurSec^)
  echo $durUs = 0
  echo if ($DurSec -gt 0) ^{ $durUs = [int64]($DurSec * 1000000) ^}
  echo $out = 0
  echo $speed = ''
  echo $lastPct = -1
  echo while (($l = [Console]::In.ReadLine()) -ne $null) ^{
  echo   if ($l -match '^(?<k>[^=]+)=(?<v>.*)$') ^{
  echo     $k = $Matches['k']; $v = $Matches['v']
  echo     if ($k -eq 'out_time_ms') ^{ [void][int64]::TryParse($v, [ref]$out) ^}
  echo     elseif ($k -eq 'speed') ^{ $speed = $v ^}
  echo     elseif ($k -eq 'progress' -and $v -eq 'end') ^{ break ^}
  echo   ^}
  echo   if ($durUs -gt 0) ^{
  echo     $pct = [math]::Max(0, [math]::Min(100, [math]::Floor(($out / $durUs) * 100)))
  echo     if ($pct -ne $lastPct) ^{
  echo       Write-Progress -Activity 'Verifying (decode-only)' -Status ("$pct%%  speed $speed") -PercentComplete $pct
  echo       $lastPct = $pct
  echo     ^}
  echo   ^} else ^{
  echo     Write-Progress -Activity 'Verifying (decode-only)' -Status ("speed $speed") -PercentComplete 0
  echo   ^}
  echo ^}
  echo Write-Progress -Activity 'Verifying (decode-only)' -Completed
)




rem ffmpeg: progress to stdout, warnings/errors to stderr -> log
ffmpeg -hide_banner -nostats -loglevel warning ^
  -i "%OUT%" -f null - ^
  -progress pipe:1 ^
  2> "%LOG%" ^
| powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" "%DUR%"


del "%PS1%" >nul 2>&1


REM ---------------

echo Verification log saved to "%LOG%"


for %%Z in ("%LOG%") do set "LOGSIZE=%%~zZ"

if "%LOGSIZE%"=="0" (
  echo The file seems perfect: no warnings/errors during verification.
) else (
  echo Note: verification produced warnings/errors. See "%LOG%".
)



exit /b 0
