# Examples:
#   .\fix_video_file.ps1 file.ts
#   .\fix_video_file.ps1 file.ts -SkipRemux
#   .\fix_video_file.ps1 file.ts -SkipRemux -EchoVerifyStderr
#   .\fix_video_file.ps1 file.ts -VerifyNoProgressTimeoutSec 120 -VerifyNoProgressAfterProgressSec 300 -VerifyMaxRuntimeSec 1200
#   .\fix_video_file.ps1 file.ts -VerifyCaptureLogInInteractive
#   .\fix_video_file.ps1 file.ts -ForceProgress


param(
  [Parameter(Mandatory=$true, Position=0)]
  [Alias("i")]
  [string]$InputFile,

  [switch]$SkipRemux,
  [switch]$NoProgress,
  [switch]$ForceProgress,
  [switch]$EchoVerifyStderr,
  [switch]$VerifyCaptureLogInInteractive,

  [int]$VerifyNoProgressTimeoutSec,
  [int]$VerifyNoProgressAfterProgressSec,
  [int]$VerifyMaxRuntimeSec
)

Set-StrictMode -Version 2

# ======================
# Output policy
#   - When run interactively (ConsoleHost) and NOT redirected: show live progress ticker.
#   - When run via PostProcessing.bat / redirected: suppress ticker and write normal logs.
#   - -ForceProgress overrides -NoProgress and redirection checks.
# ======================
$script:IsConsoleHost = ($Host.Name -eq 'ConsoleHost')
$script:IsRedirected  = [Console]::IsOutputRedirected -or [Console]::IsErrorRedirected
$script:ShowProgress  = $ForceProgress -or ($script:IsConsoleHost -and (-not $script:IsRedirected) -and (-not $NoProgress))

function Get-ProgressModeReason {
  if ($ForceProgress) { return 'forced by -ForceProgress switch' }
  if ($NoProgress) { return 'disabled by -NoProgress switch' }
  if (-not $script:IsConsoleHost) { return "host '$($Host.Name)' is not ConsoleHost" }
  if ($script:IsRedirected) { return 'output/error is redirected (no TTY)' }
  return 'enabled'
}

function Write-Info([string]$Message) { Write-Host $Message }
function Write-Warn([string]$Message) { Write-Warning $Message }
function Write-Err([string]$Message)  { Write-Error $Message }

$script:_LastProgress = $null
function Write-ProgressLine([string]$Message) {
  if (-not $script:ShowProgress) { return }
  if ($Message -eq $script:_LastProgress) { return }
  $script:_LastProgress = $Message
  Write-Host ("`r" + $Message) -NoNewline
}
function Write-ProgressDone() {
  if (-not $script:ShowProgress) { return }
  $script:_LastProgress = $null
  Write-Host ""
}

# ======================
# Settings
# ======================

# ---- Tools ----
# ---- Tools (self-contained discovery; works under SYSTEM) ----
function Resolve-ExePath([string]$ExeName, [string[]]$Candidates) {
  # 1) If it's on PATH, use it
  $cmd = Get-Command $ExeName -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Path -and (Test-Path -LiteralPath $cmd.Path)) {
    return $cmd.Path
  }

  # 2) Otherwise, scan candidate absolute paths
  foreach ($p in $Candidates) {
    if ([string]::IsNullOrWhiteSpace($p)) { continue }
    if (Test-Path -LiteralPath $p) { return $p }
  }

  throw "Missing tool: $ExeName. Not found on PATH and not found in candidate paths."
}

function Get-ExeCandidates([string]$ExeName, [string[]]$RootDirs) {
  $list = New-Object System.Collections.Generic.List[string]
  foreach ($root in $RootDirs) {
    if ([string]::IsNullOrWhiteSpace($root)) { continue }
    $list.Add((Join-Path $root $ExeName))
  }
  # De-dup (case-insensitive) while preserving order
  return $list | Select-Object -Unique
}

# Candidate roots (add/remove as you like)
$FFMPEG_ROOTS = @(
  # WinGet user shims (works for normal user; SYSTEM usually won't have these)
  (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links"),
  "C:\ffmpeg\bin",
  "C:\ProgramData\chocolatey\bin",
  "C:\Program Files\ffmpeg\bin",
  "E:\ffmpeg\bin"
)

$FFMPEG  = Resolve-ExePath "ffmpeg.exe"  (Get-ExeCandidates "ffmpeg.exe"  $FFMPEG_ROOTS)
$FFPROBE = Resolve-ExePath "ffprobe.exe" (Get-ExeCandidates "ffprobe.exe" $FFMPEG_ROOTS)

Write-Info "Using ffmpeg : $FFMPEG"
Write-Info "Using ffprobe: $FFPROBE"


$Settings = [ordered]@{
  # Toggle: set to $true to skip remux and only run post-mortem verification.
  SkipRemux = $false # $true

  # Verification watchdogs (seconds). If no progress or total runtime exceeds limit, abort attempt.
  VerifyNoProgressTimeoutSec = 60
  VerifyNoProgressAfterProgressSec = 180
  VerifyMaxRuntimeSec        = 600

  # Echo non-progress ffmpeg stderr lines during verification (helps debugging stalls).
  EchoVerifyStderr = $true

  # When interactive, capture verify logs using internal progress (not native ffmpeg stats).
  VerifyCaptureLogInInteractive = $true
}

# ======================
# Helpers
# ======================
function Assert-True([bool]$Condition, [string]$Message) {
  if (-not $Condition) { throw "ASSERT: $Message" }
}

function Assert-NonEmptyString([string]$Value, [string]$Name) {
  if ([string]::IsNullOrWhiteSpace($Value)) {
    throw "Invalid ${Name}: value is empty."
  }
}

function Test-ExistingPath([string]$Path, [string]$Name) {
  Assert-NonEmptyString $Path $Name
  if (-not (Test-Path -LiteralPath $Path)) {
    throw "Invalid ${Name}: path not found: $Path"
  }
}

function Strip-Ansi([string]$Text) {
  if ([string]::IsNullOrEmpty($Text)) { return $Text }
  return ($Text -replace "`e\[[0-9;]*[A-Za-z]", '')
}

function Assert-Settings([hashtable]$Settings) {
  Assert-True ($Settings.SkipRemux -is [bool]) "Settings.SkipRemux must be boolean."
  Assert-True ($Settings.EchoVerifyStderr -is [bool]) "Settings.EchoVerifyStderr must be boolean."
  Assert-True ($Settings.VerifyNoProgressTimeoutSec -is [int]) "Settings.VerifyNoProgressTimeoutSec must be int."
  Assert-True ($Settings.VerifyNoProgressAfterProgressSec -is [int]) "Settings.VerifyNoProgressAfterProgressSec must be int."
  Assert-True ($Settings.VerifyMaxRuntimeSec -is [int]) "Settings.VerifyMaxRuntimeSec must be int."
  Assert-True ($Settings.VerifyCaptureLogInInteractive -is [bool]) "Settings.VerifyCaptureLogInInteractive must be boolean."
  Assert-True ($Settings.VerifyNoProgressTimeoutSec -gt 0) "Settings.VerifyNoProgressTimeoutSec must be > 0."
  Assert-True ($Settings.VerifyNoProgressAfterProgressSec -gt 0) "Settings.VerifyNoProgressAfterProgressSec must be > 0."
  Assert-True ($Settings.VerifyMaxRuntimeSec -gt 0) "Settings.VerifyMaxRuntimeSec must be > 0."
}

function Convert-MsToUs([int64]$Ms) {
  Assert-True ($Ms -ge 0) "Milliseconds must be >= 0."
  return $Ms * 1000
}

function Convert-TimeSpanToUs([TimeSpan]$Ts) {
  Assert-True ($Ts -ge [TimeSpan]::Zero) "Timespan must be non-negative."
  return [int64]($Ts.TotalSeconds * 1000000.0)
}

function Convert-SecondsToUs([double]$Sec) {
  if ([double]::IsNaN($Sec) -or [double]::IsInfinity($Sec)) {
    throw "Duration seconds is not finite: $Sec"
  }
  Assert-True ($Sec -ge 0) "Duration seconds must be >= 0."
  if ($Sec -gt 3155760000) {
    throw "Duration seconds is unrealistically large: $Sec"
  }
  return [int64]($Sec * 1000000.0)
}

function Format-SecondsAsHms([int64]$Seconds) {
  Assert-True ($Seconds -ge 0) "Seconds must be non-negative."
  $hrs  = [int]($Seconds / 3600)
  $mins = [int](($Seconds % 3600) / 60)
  $secs = [int]($Seconds % 60)
  return ("{0:00}:{1:00}:{2:00}" -f $hrs, $mins, $secs)
}

function Get-ProgressPercent([int64]$OutTimeUs, [int64]$DurUs) {
  Assert-True ($DurUs -gt 0) "Duration must be > 0 to compute progress percent."
  Assert-True ($OutTimeUs -ge 0) "outTimeUs must be >= 0."
  $pct = [math]::Floor(($OutTimeUs / [double]$DurUs) * 100)
  $pct = [math]::Max([double]0, [math]::Min([double]100, $pct))
  return [int]$pct
}

function Get-EtaString([int64]$OutTimeUs, [int64]$DurUs, [double]$ElapsedSec) {
  Assert-True ($DurUs -gt 0) "Duration must be > 0 to compute ETA."
  Assert-True ($OutTimeUs -ge 0) "outTimeUs must be >= 0."

  $elapsed = [math]::Max(0.001, $ElapsedSec)
  $rateUsPerSec = $OutTimeUs / $elapsed
  if ($rateUsPerSec -le 0) { return '??:??:??' }

  $remainUs  = [math]::Max([int64]0, ($DurUs - $OutTimeUs))
  $remainSec = [math]::Floor($remainUs / $rateUsPerSec)
  if ($remainSec -lt 0 -or $remainSec -ge 3155760000) { return '??:??:??' }

  return Format-SecondsAsHms $remainSec
}

function Test-RenderProgress([int]$Percent, [int]$LastPercent, [datetime]$Now, [datetime]$LastRender) {
  Assert-True ($Percent -ge 0 -and $Percent -le 100) "Percent must be 0..100."
  $delta = ($Now - $LastRender).TotalSeconds
  return ($Percent -ne $LastPercent) -or ($delta -ge 0.5)
}

function Get-ProgressSnapshot([int64]$DurUs, [int64]$OutTimeUs, [double]$ElapsedSec) {
  $pct = Get-ProgressPercent -OutTimeUs $OutTimeUs -DurUs $DurUs
  $eta = Get-EtaString -OutTimeUs $OutTimeUs -DurUs $DurUs -ElapsedSec $ElapsedSec
  return @{ Percent = $pct; Eta = $eta }
}

function Update-ProgressStateFromLine([string]$Line) {
  if ($null -eq $Line) { return $null }
  if ($Line -notmatch '^(?<k>[^=]+)=(?<v>.*)$') { return $null }

  $k = $Matches.k
  $v = $Matches.v

  switch ($k) {
    'out_time_us' {
      $tmp = [int64]0
      if ([int64]::TryParse($v, [ref]$tmp)) {
        Assert-True ($tmp -ge 0) "out_time_us must be >= 0."
        $script:outTimeUs = $tmp
      }
      return $k
    }
    'out_time_ms' {
      $tmp = [int64]0
      if ([int64]::TryParse($v, [ref]$tmp)) {
        $script:outTimeUs = Convert-MsToUs $tmp
      }
      return $k
    }
    'out_time' {
      $ts = [TimeSpan]::Zero
      if ([TimeSpan]::TryParse($v, [ref]$ts)) {
        $script:outTimeUs = Convert-TimeSpanToUs $ts
      }
      return $k
    }
    'speed' {
      $script:speed = if ($v) { $v } else { '?' }
      return $k
    }
    'progress' {
      return $k
    }
    default { return $null }
  }
}

function Get-ResolvedInputPath([string]$InputFile) {
  Assert-NonEmptyString $InputFile 'InputFile'
  try {
    return (Resolve-Path -Path $InputFile -ErrorAction Stop).Path
  } catch {
    throw "Input file not found: $InputFile"
  }
}

function Get-OutputPaths([string]$InputPath) {
  Test-ExistingPath $InputPath 'Input file'
  $dir  = Split-Path -Path $InputPath -Parent
  $base = [IO.Path]::GetFileNameWithoutExtension($InputPath)
  $ext  = [IO.Path]::GetExtension($InputPath)

  Assert-NonEmptyString $base 'Input base name'
  Assert-NonEmptyString $ext 'Input extension'

  if ($ext -ieq '.mkv') { $outPath = Join-Path $dir ($base + '_.mkv') }
  else                  { $outPath = Join-Path $dir ($base + '.mkv')  }

  $logPath  = [IO.Path]::ChangeExtension($outPath, '.log')
  $baseLog  = [IO.Path]::Combine(
    [IO.Path]::GetDirectoryName($outPath),
    [IO.Path]::GetFileNameWithoutExtension($outPath)
  )

  return @{
    InPath  = $InputPath
    Dir     = $dir
    Base    = $base
    Ext     = $ext
    OutPath = $outPath
    LogPath = $logPath
    BaseLog = $baseLog
  }
}

function Get-AacBsfNeeded([string]$InputPath, [string]$Extension) {
  Test-ExistingPath $InputPath 'Input file'
  Assert-NonEmptyString $Extension 'Input extension'
  $tsLikeExt = @('.ts','.m2ts','.mts','.trp','.tp','.vob')
  if ($tsLikeExt -notcontains $Extension.ToLowerInvariant()) { return $false }

  try {
    $aCodecLine = & $FFPROBE -v error -select_streams a:0 -show_entries stream=codec_name -of default=nokey=1:noprint_wrappers=1 -- $InputPath |
      Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($aCodecLine)) { return $false }
    $codec = $aCodecLine.Trim().ToLowerInvariant()
    $isAac = [bool]($codec -eq 'aac')
    return $isAac
  } catch {
    Write-Warn "Failed to detect audio codec; defaulting to no AAC bitstream filter. $($_.Exception.Message)"
    return $false
  }
}

function Format-Arg([string]$s) {
  if ($null -eq $s) { return '' }
  if ($s -match '[\s"]') {
    return '"' + ($s -replace '"','\\"') + '"'
  }
  return $s
}

function Get-FfmpegHwaccels {
  try {
    $out = & $FFMPEG -hide_banner -hwaccels 2>$null
    return ($out | ForEach-Object { $_.Trim() }) | Where-Object { $_ -and ($_ -notmatch '^Hardware acceleration methods') }
  } catch {
    return @()
  }
}

function Get-FormatDurationSec([string]$Path) {
  Test-ExistingPath $Path 'Media file'
  $durSec = 0.0

  try {
    $d = & $FFPROBE -v error -show_entries format=duration -of default=nokey=1:noprint_wrappers=1 -- $Path
    $ci = [System.Globalization.CultureInfo]::InvariantCulture
    if (-not [double]::TryParse($d.Trim(), [System.Globalization.NumberStyles]::Float, $ci, [ref]$durSec)) {
      Write-Warn "Unable to parse duration from ffprobe output: '$d'"
      $durSec = 0.0
    }
  } catch {
    Write-Warn "ffprobe failed to read duration: $($_.Exception.Message)"
    $durSec = 0.0
  }

  if ($durSec -lt 0) {
    Write-Warn "Duration is negative ($durSec). Using 0."
    $durSec = 0.0
  }

  return $durSec
}

function Get-FormatDurationUs([string]$Path) {
  $durSec = Get-FormatDurationSec $Path
  if ($durSec -le 0) { return [int64]0 }
  return Convert-SecondsToUs $durSec
}

function Get-VerificationDurationUs([string]$OutPath, [string]$InPath, [bool]$SkipRemux) {
  $durUs = Get-FormatDurationUs $OutPath
  if ($durUs -gt 0) { return $durUs }

  if ($SkipRemux) {
    Write-Warn "Output duration unavailable; falling back to input duration for ETA."
    $durUs = Get-FormatDurationUs $InPath
    if ($durUs -gt 0) { return $durUs }
  }

  Write-Warn "Duration unavailable; progress will show speed only."
  return [int64]0
}

function Stop-ProcessTree([int]$ProcessId) {
  if ($ProcessId -le 0) { return }
  try { Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue } catch { }
  Start-Sleep -Milliseconds 200
  try {
    $still = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($null -ne $still) {
      & taskkill /PID $ProcessId /T /F | Out-Null
    }
  } catch { }
}

function Get-VerifyCandidates([string[]]$AvailableHw) {
  if ($null -eq $AvailableHw) { $AvailableHw = @() }

  $candidates = @()
  if ($AvailableHw -contains 'cuda')    { $candidates += ,@('cuda',    'cuda') }
  if ($AvailableHw -contains 'd3d12va') { $candidates += ,@('d3d12va', $null) }
  if ($AvailableHw -contains 'd3d11va') { $candidates += ,@('d3d11va', $null) }
  if ($AvailableHw -contains 'qsv')     { $candidates += ,@('qsv',     $null) }

  $candidates += ,@($null, $null)

  foreach ($c in $candidates) {
    Assert-True ($c -is [System.Array] -and $c.Count -ge 2) "Verify candidate must be a 2-item array."
  }

  return $candidates
}

function Get-LogLinesSafe([string]$LogPath) {
  if (-not (Test-Path -LiteralPath $LogPath)) { return @() }
  try {
    $lines = Get-Content -LiteralPath $LogPath -ErrorAction Stop
    return @($lines)
  } catch {
    Write-Warn "Failed reading log file: $LogPath. $($_.Exception.Message)"
    return @()
  }
}

function Get-MeaningfulLogLines([string[]]$LogLines, [string[]]$HarmlessPatterns) {
  if ($null -eq $LogLines) { return @() }
  if ($null -eq $HarmlessPatterns -or $HarmlessPatterns.Count -eq 0) { return @($LogLines) }

  return @($LogLines | Where-Object {
    $line = $_
    -not ($HarmlessPatterns | Where-Object { $line -match $_ })
  })
}

function Rename-Log([string]$LogPath, [string]$NewLog) {
  Assert-NonEmptyString $NewLog 'New log path'
  if (Test-Path -LiteralPath $LogPath) {
    Move-Item -LiteralPath $LogPath -Destination $NewLog -Force
  } else {
    New-Item -Path $NewLog -ItemType File -Force | Out-Null
  }
}

function Invoke-TriageRemux([string]$InputPath, [string]$OutputPath, [bool]$NeedAacBsf) {
  Test-ExistingPath $InputPath 'Input file'
  Assert-NonEmptyString $OutputPath 'Output path'

  $ffArgs = @(
    '-hide_banner','-y',
    '-fflags','+genpts',
    '-err_detect','ignore_err',
    '-probesize','100M','-analyzeduration','100M',
    '-ignore_unknown','-copy_unknown',
    '-i', $InputPath,
    '-map','0','-map_metadata','0','-map_chapters','0',
    '-c','copy',
    '-start_at_zero',
    '-max_interleave_delta','0'
  )

  if ($NeedAacBsf) { $ffArgs += @('-bsf:a','aac_adtstoasc') }
  $ffArgs += $OutputPath

  $LASTEXITCODE = 0
  & $FFMPEG @ffArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Triage remux failed with exit code $LASTEXITCODE."
  }
}

function Invoke-Verification([string]$OutPath, [string]$LogPath, [int64]$DurUs) {
  Test-ExistingPath $OutPath 'Output file'
  Assert-NonEmptyString $LogPath 'Log path'
  Assert-True ($DurUs -ge 0) "Duration microseconds must be >= 0."

  $availableHw = Get-FfmpegHwaccels
  $verifyCandidates = Get-VerifyCandidates $availableHw

  $verifyExit = $null
  $used = 'CPU'

  $attempt = 0
  foreach ($c in $verifyCandidates) {
    $hw  = $c[0]
    $fmt = $c[1]
    $attempt++
    $label = if ($hw) { "hw=$hw" } else { "CPU" }

    Write-Info ''
    if ($hw) { Write-Info "Verify decode: trying hwaccel=$hw" }
    else     { Write-Info 'Verify decode: trying CPU' }

    $verifyExit = Invoke-Verify -outPath $OutPath -logPath $LogPath -durUs $DurUs -hwaccel $hw -hwoutfmt $fmt -NoProgressTimeoutSec $Settings.VerifyNoProgressTimeoutSec -NoProgressAfterProgressSec $Settings.VerifyNoProgressAfterProgressSec -MaxRuntimeSec $Settings.VerifyMaxRuntimeSec -EchoStderr $Settings.EchoVerifyStderr -DisplayTag $label -Interactive:$script:ShowProgress -CaptureLogInInteractive:$Settings.VerifyCaptureLogInInteractive
    Write-Info "Verify decode: attempt $attempt exit code = $verifyExit"

    if ($verifyExit -eq 0) {
      $used = if ($hw) { $hw } else { 'CPU' }
      break
    }

    if ($hw) {
      Write-Warn "Verify decode: hwaccel=$hw failed (exit $verifyExit). Trying next candidate..."
      Remove-Item -LiteralPath $LogPath -Force -ErrorAction SilentlyContinue
      Start-Sleep -Milliseconds 100
      continue
    } else {
      break
    }
  }

  Assert-True ($null -ne $verifyExit) 'Verification did not produce an exit code.'
  return [pscustomobject]@{
    ExitCode = [int]$verifyExit
    Used     = [string]$used
  }
}

function Complete-VerificationLog(
  [int]$VerifyExit,
  [string]$LogPath,
  [string]$OutPath,
  [string[]]$HarmlessPatterns
) {
  $baseLog = [System.IO.Path]::Combine(
    [System.IO.Path]::GetDirectoryName($OutPath),
    [System.IO.Path]::GetFileNameWithoutExtension($OutPath)
  )

  Assert-NonEmptyString $baseLog 'Base log path'

  $logLines = Get-LogLinesSafe $LogPath
  $meaningfulLines = @(Get-MeaningfulLogLines -LogLines $logLines -HarmlessPatterns $HarmlessPatterns | Where-Object { $_ -ne $null })

  if ($VerifyExit -ne 0) {
    $newLog = "${baseLog}_WITHERRORS.log"
    Rename-Log -LogPath $LogPath -NewLog $newLog
    Write-Info "Verification failed (exit $VerifyExit)."
    Write-Info "Log renamed to: `"$newLog`""
    exit $VerifyExit
  }

  if ($meaningfulLines.Count -eq 0) {
    $newLog = "${baseLog}_NOERRORS.log"
    Rename-Log -LogPath $LogPath -NewLog $newLog
    Write-Info 'The file seems clean (only harmless warnings, if any).'
    Write-Info "Log renamed to: `"$newLog`""
  } else {
    $newLog = "${baseLog}_WITHERRORS.log"
    Rename-Log -LogPath $LogPath -NewLog $newLog
    Write-Info 'Verification produced meaningful warnings/errors.'
    Write-Info "Log renamed to: `"$newLog`""
    Write-Info ''
    Write-Info 'First issues detected:'
    $meaningfulLines | Select-Object -First 8 | ForEach-Object { Write-Info "  $_" }
  }
}

function Invoke-Verify(
  [string]$outPath,
  [string]$logPath,
  [int64]$durUs,
  [string]$hwaccel,
  [string]$hwoutfmt,
  [int]$NoProgressTimeoutSec = 60,
  [int]$NoProgressAfterProgressSec = 180,
  [int]$MaxRuntimeSec = 600,
  [bool]$EchoStderr = $false,
  [string]$DisplayTag = '',
  [switch]$Interactive,
  [switch]$CaptureLogInInteractive
) {
  Assert-NonEmptyString $outPath 'Output path'
  Assert-NonEmptyString $logPath 'Log path'
  Assert-True ($durUs -ge 0) "Duration microseconds must be >= 0."
  Assert-True ($NoProgressTimeoutSec -gt 0) "NoProgressTimeoutSec must be > 0."
  Assert-True ($NoProgressAfterProgressSec -gt 0) "NoProgressAfterProgressSec must be > 0."
  Assert-True ($MaxRuntimeSec -gt 0) "MaxRuntimeSec must be > 0."

  New-Item -Path $logPath -ItemType File -Force | Out-Null

  $argList = @()
  if ($hwaccel) { $argList += @('-hwaccel', $hwaccel) }
  if ($hwoutfmt) { $argList += @('-hwaccel_output_format', $hwoutfmt) }

  $argList += @(
    '-hide_banner','-nostats','-loglevel','warning',
    '-i', $outPath,
    '-map','0:v','-map','0:a','-sn','-dn',
    '-f','null','-',
    '-progress','pipe:1'
  )

  $argString = ($argList | ForEach-Object { Format-Arg $_ }) -join ' '
# If we're interactive and not capturing logs, preserve ffmpeg's native console behavior.
# Remove -progress (key=value spam) and enable -stats.
if ($Interactive.IsPresent -and (-not $CaptureLogInInteractive)) {

  $argListInteractive = @()
  for ($i = 0; $i -lt $argList.Count; $i++) {
    $item = $argList[$i]
    if ($item -eq '-progress') { $i++; continue }
    if ($item -eq '-nostats') { continue }
    $argListInteractive += $item
  }
  $argListInteractive += '-stats'

  $global:LASTEXITCODE = 0
  & $FFMPEG @argListInteractive
  return [int]$global:LASTEXITCODE
}



  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $FFMPEG
  $psi.Arguments = $argString
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError  = $true
  $psi.UseShellExecute        = $false
  $psi.CreateNoWindow         = $true

  $p = New-Object System.Diagnostics.Process
  $p.StartInfo = $psi

  $logWriter = New-Object System.IO.StreamWriter($logPath, $false, [System.Text.Encoding]::UTF8)
  $logWriter.AutoFlush = $true

  $script:outTimeUs = [int64]0
  $script:speed = '?'
  $script:verifyLastProgressUpdate = [datetime]::UtcNow
  $script:verifyLogWriter = $logWriter
  $script:verifyEchoStderr = $EchoStderr

  [void]$p.Start()

  # Async capture to avoid blocking on partial lines.
  $outId = "verify-out-$($p.Id)"
  $errId = "verify-err-$($p.Id)"

  Register-ObjectEvent -InputObject $p -EventName OutputDataReceived -SourceIdentifier $outId -Action {
    if ($null -eq $eventArgs.Data) { return }
    $k = Update-ProgressStateFromLine $eventArgs.Data
    if ($k -in @('out_time_us','out_time_ms','out_time','speed')) {
      $script:verifyLastProgressUpdate = [datetime]::UtcNow
    }
  } | Out-Null

  Register-ObjectEvent -InputObject $p -EventName ErrorDataReceived -SourceIdentifier $errId -Action {
    if ($null -eq $eventArgs.Data) { return }
    $k = Update-ProgressStateFromLine $eventArgs.Data
    if ($k -in @('out_time_us','out_time_ms','out_time','speed')) {
      $script:verifyLastProgressUpdate = [datetime]::UtcNow
      return
    }
    if ($k) { return }
    $line = $eventArgs.Data
    try { $script:verifyLogWriter.WriteLine((Strip-Ansi $line)) } catch { }
    if ($script:verifyEchoStderr) { [Console]::WriteLine($line) }
  } | Out-Null

  $p.BeginOutputReadLine()
  $p.BeginErrorReadLine()

  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  $totalSw = [System.Diagnostics.Stopwatch]::StartNew()
  $lastPct = -1
  $lastRender = [datetime]::UtcNow
  $stalled = $false
  $displayOutTimeUs = [int64]0
  $maxOutTimeUs = if ($durUs -gt 0) { [int64]([math]::Ceiling($durUs * 1.10)) } else { [int64]0 }

  while (-not $p.HasExited) {

    if ($durUs -gt 0) {
      $currentOutTimeUs = $script:outTimeUs
      if ($maxOutTimeUs -gt 0 -and $currentOutTimeUs -gt $maxOutTimeUs) {
        # Ignore spikes beyond 110% of duration to avoid false 100% jumps.
        $currentOutTimeUs = $displayOutTimeUs
      } elseif ($currentOutTimeUs -lt $displayOutTimeUs) {
        # Handle time resets/discontinuities by allowing progress to restart.
        $displayOutTimeUs = $currentOutTimeUs
        $lastPct = -1
      } else {
        $displayOutTimeUs = $currentOutTimeUs
      }

      $snapshot = Get-ProgressSnapshot -DurUs $durUs -OutTimeUs $displayOutTimeUs -ElapsedSec $sw.Elapsed.TotalSeconds
      $now = [datetime]::UtcNow

      if (Test-RenderProgress -Percent $snapshot.Percent -LastPercent $lastPct -Now $now -LastRender $lastRender) {
        $tag = if ($DisplayTag) { "[$DisplayTag] " } else { '' }
        Write-ProgressLine ("Verifying {0}{1,3}%  ETA {2}  speed {3,-8}" -f $tag, $snapshot.Percent, $snapshot.Eta, $script:speed)
        $lastPct = $snapshot.Percent
        $lastRender = $now
      }
    } else {
      $now = [datetime]::UtcNow
      if ((($now - $lastRender).TotalSeconds -ge 0.5)) {
        if ($script:speed -eq '?') {
          $tag = if ($DisplayTag) { "[$DisplayTag] " } else { '' }
          Write-ProgressLine ("Verifying {0}waiting for progress..." -f $tag)
        } else {
          $tag = if ($DisplayTag) { "[$DisplayTag] " } else { '' }
          Write-ProgressLine ("Verifying {0}speed {1,-8}" -f $tag, $script:speed)
        }
        $lastRender = $now
      }
    }

    $timeoutSec = if ($script:outTimeUs -gt 0) { $NoProgressAfterProgressSec } else { $NoProgressTimeoutSec }
    if (([datetime]::UtcNow - $script:verifyLastProgressUpdate).TotalSeconds -ge $timeoutSec) {
      $stalled = $true
      Stop-ProcessTree -ProcessId $p.Id
      Write-Warn "Verification stalled (no progress for ${timeoutSec}s)."
      break
    }

    if ($totalSw.Elapsed.TotalSeconds -ge $MaxRuntimeSec) {
      $stalled = $true
      Stop-ProcessTree -ProcessId $p.Id
      Write-Warn "Verification timed out after ${MaxRuntimeSec}s."
      break
    }

    Start-Sleep -Milliseconds 100
  }

  $sw.Stop()
  Write-ProgressDone

  try { $p.CancelOutputReadLine() } catch { }
  try { $p.CancelErrorReadLine() } catch { }
  try { Unregister-Event -SourceIdentifier $outId -ErrorAction SilentlyContinue } catch { }
  try { Unregister-Event -SourceIdentifier $errId -ErrorAction SilentlyContinue } catch { }
  try { Remove-Event -SourceIdentifier $outId -ErrorAction SilentlyContinue } catch { }
  try { Remove-Event -SourceIdentifier $errId -ErrorAction SilentlyContinue } catch { }

  try { $logWriter.Flush() } catch { }
  try { $logWriter.Dispose() } catch { }

  if ($stalled) { return 124 }
  return $p.ExitCode
}

# Harmless verification patterns (used in log evaluation)
$harmlessPatterns = @(
  'timestamp discontinuity',
  'non-monotonous dts',
  'non-monotonous pts',
  'Application provided invalid, non monotonically increasing dts',
  'invalid dropping',
  'Packet corrupt.*dropping',
  'Estimating duration from bitrate',
  'start time .* not set'
)

# ----------------------
# Main flow
# ----------------------
# Apply CLI overrides (only when explicitly provided).
if ($PSBoundParameters.ContainsKey('SkipRemux')) { $Settings.SkipRemux = [bool]$SkipRemux }
if ($PSBoundParameters.ContainsKey('EchoVerifyStderr')) { $Settings.EchoVerifyStderr = [bool]$EchoVerifyStderr }
if ($PSBoundParameters.ContainsKey('VerifyCaptureLogInInteractive')) { $Settings.VerifyCaptureLogInInteractive = [bool]$VerifyCaptureLogInInteractive }
if ($PSBoundParameters.ContainsKey('VerifyNoProgressTimeoutSec')) { $Settings.VerifyNoProgressTimeoutSec = $VerifyNoProgressTimeoutSec }
if ($PSBoundParameters.ContainsKey('VerifyNoProgressAfterProgressSec')) { $Settings.VerifyNoProgressAfterProgressSec = $VerifyNoProgressAfterProgressSec }
if ($PSBoundParameters.ContainsKey('VerifyMaxRuntimeSec')) { $Settings.VerifyMaxRuntimeSec = $VerifyMaxRuntimeSec }

# Validate settings early to fail fast with clear errors.
Assert-Settings $Settings

# Resolve input/output paths and derived naming.
$paths = Get-OutputPaths -InputPath (Get-ResolvedInputPath $InputFile)
$inPath  = $paths.InPath
$outPath = $paths.OutPath
$logPath = $paths.LogPath
$ext     = $paths.Ext

# Decide whether to apply AAC ADTS->ASC bitstream filter for TS-like inputs.
$needAacBsf = Get-AacBsfNeeded -InputPath $inPath -Extension $ext
Assert-True ($needAacBsf -is [bool]) "Expected boolean from Get-AacBsfNeeded, got '$($needAacBsf.GetType().FullName)'."

# Print a concise summary of the planned operation.
$modeLabel = if ($needAacBsf) { 'TS + AAC (using -bsf:a aac_adtstoasc)' } else { 'Generic remux (no audio bitstream filter)' }
Write-Info ("`nInput : `"{0}`"`nOutput: `"{1}`"`nMode  : {2}`n" -f $inPath, $outPath, $modeLabel)

# Perform the remux (no re-encode).
if (-not $Settings.SkipRemux) {
  Invoke-TriageRemux -InputPath $inPath -OutputPath $outPath -NeedAacBsf $needAacBsf
  Write-Info "`nSUCCESS.`n"
} else {
  Write-Info "`nSKIP: remux disabled; verifying existing output only.`n"
  Test-ExistingPath $outPath 'Output file'
}

# Validate the output with decode+audio checks (hwaccel fallback where available).
Write-Info 'Running post-mortem verification pass...'
if (-not $script:ShowProgress) {
  Write-Info ("Progress ticker is disabled: {0}" -f (Get-ProgressModeReason))
}
$durUs = Get-VerificationDurationUs -OutPath $outPath -InPath $inPath -SkipRemux $Settings.SkipRemux

# Try hardware decode first (if available), then CPU fallback.
$verifyResult = Invoke-Verification -OutPath $outPath -LogPath $logPath -DurUs $durUs

# Report verification method and log location.
Write-Info "Verification completed using: $($verifyResult.Used)"
Write-Info "Verification log saved to `"$logPath`""

# Classify log contents, rename log accordingly, and surface first issues if any.
Complete-VerificationLog -VerifyExit $verifyResult.ExitCode -LogPath $logPath -OutPath $outPath -HarmlessPatterns $harmlessPatterns

exit 0
