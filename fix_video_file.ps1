param(
  [Parameter(Mandatory=$true, Position=0)]
  [string]$InputFile
)

Set-StrictMode -Version 2

function Assert-True([bool]$Condition, [string]$Message) {
  if (-not $Condition) { throw "ASSERT: $Message" }
}

function Assert-NonEmptyString([string]$Value, [string]$Name) {
  if ([string]::IsNullOrWhiteSpace($Value)) {
    throw "Invalid ${Name}: value is empty."
  }
}

function Ensure-ExistingPath([string]$Path, [string]$Name) {
  Assert-NonEmptyString $Path $Name
  if (-not (Test-Path -LiteralPath $Path)) {
    throw "Invalid ${Name}: path not found: $Path"
  }
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

function Calculate-ProgressPercent([int64]$OutTimeUs, [int64]$DurUs) {
  Assert-True ($DurUs -gt 0) "Duration must be > 0 to compute progress percent."
  Assert-True ($OutTimeUs -ge 0) "outTimeUs must be >= 0."
  $pct = [math]::Floor(($OutTimeUs / [double]$DurUs) * 100)
  $pct = [math]::Max([double]0, [math]::Min([double]100, $pct))
  return [int]$pct
}

function Calculate-EtaString([int64]$OutTimeUs, [int64]$DurUs, [double]$ElapsedSec) {
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

function Should-RenderProgress([int]$Percent, [int]$LastPercent, [datetime]$Now, [datetime]$LastRender) {
  Assert-True ($Percent -ge 0 -and $Percent -le 100) "Percent must be 0..100."
  $delta = ($Now - $LastRender).TotalSeconds
  return ($Percent -ne $LastPercent) -or ($delta -ge 0.5)
}

function Get-ProgressSnapshot([int64]$DurUs, [int64]$OutTimeUs, [double]$ElapsedSec) {
  $pct = Calculate-ProgressPercent -OutTimeUs $OutTimeUs -DurUs $DurUs
  $eta = Calculate-EtaString -OutTimeUs $OutTimeUs -DurUs $DurUs -ElapsedSec $ElapsedSec
  return @{ Percent = $pct; Eta = $eta }
}

function Try-UpdateProgressStateFromLine([string]$Line) {
  if ($null -eq $Line) { return $false }
  if ($Line -notmatch '^(?<k>[^=]+)=(?<v>.*)$') { return $false }

  $k = $Matches.k
  $v = $Matches.v

  switch ($k) {
    'out_time_us' {
      $tmp = [int64]0
      if ([int64]::TryParse($v, [ref]$tmp)) {
        Assert-True ($tmp -ge 0) "out_time_us must be >= 0."
        $script:outTimeUs = $tmp
      }
      return $true
    }
    'out_time_ms' {
      $tmp = [int64]0
      if ([int64]::TryParse($v, [ref]$tmp)) {
        $script:outTimeUs = Convert-MsToUs $tmp
      }
      return $true
    }
    'out_time' {
      $ts = [TimeSpan]::Zero
      if ([TimeSpan]::TryParse($v, [ref]$ts)) {
        $script:outTimeUs = Convert-TimeSpanToUs $ts
      }
      return $true
    }
    'speed' {
      $script:speed = if ($v) { $v } else { '?' }
      return $true
    }
    'progress' {
      return $true
    }
    default { return $false }
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
  Ensure-ExistingPath $InputPath 'Input file'
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
  $tsLikeExt = @('.ts','.m2ts','.mts','.trp','.tp','.vob')
  if ($tsLikeExt -notcontains $Extension.ToLowerInvariant()) { return $false }

  try {
    $aCodec = & ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of default=nokey=1:noprint_wrappers=1 -- $InputPath
    return ($aCodec.Trim().ToLowerInvariant() -eq 'aac')
  } catch {
    Write-Warning "Failed to detect audio codec; defaulting to no AAC bitstream filter. $($_.Exception.Message)"
    return $false
  }
}

function Quote-Arg([string]$s) {
  if ($null -eq $s) { return '' }
  if ($s -match '[\s"]') {
    return '"' + ($s -replace '"','\\"') + '"'
  }
  return $s
}

function Get-FfmpegHwaccels {
  try {
    $out = & ffmpeg -hide_banner -hwaccels 2>$null
    return ($out | ForEach-Object { $_.Trim() }) | Where-Object { $_ -and ($_ -notmatch '^Hardware acceleration methods') }
  } catch {
    return @()
  }
}

function Get-FormatDurationSec([string]$Path) {
  Ensure-ExistingPath $Path 'Media file'
  $durSec = 0.0

  try {
    $d = & ffprobe -v error -show_entries format=duration -of default=nokey=1:noprint_wrappers=1 -- $Path
    $ci = [System.Globalization.CultureInfo]::InvariantCulture
    if (-not [double]::TryParse($d.Trim(), [System.Globalization.NumberStyles]::Float, $ci, [ref]$durSec)) {
      Write-Warning "Unable to parse duration from ffprobe output: '$d'"
      $durSec = 0.0
    }
  } catch {
    Write-Warning "ffprobe failed to read duration: $($_.Exception.Message)"
    $durSec = 0.0
  }

  if ($durSec -lt 0) {
    Write-Warning "Duration is negative ($durSec). Using 0."
    $durSec = 0.0
  }

  return $durSec
}

function Get-FormatDurationUs([string]$Path) {
  $durSec = Get-FormatDurationSec $Path
  if ($durSec -le 0) { return [int64]0 }
  return Convert-SecondsToUs $durSec
}

function Get-VerifyCandidates([string[]]$AvailableHw) {
  if ($null -eq $AvailableHw) { $AvailableHw = @() }

  $candidates = @()
  if ($AvailableHw -contains 'd3d11va') { $candidates += ,@('d3d11va', $null) }
  if ($AvailableHw -contains 'cuda')    { $candidates += ,@('cuda',    'cuda') }
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
    return Get-Content -LiteralPath $LogPath -ErrorAction Stop
  } catch {
    Write-Warning "Failed reading log file: $LogPath. $($_.Exception.Message)"
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
  Ensure-ExistingPath $InputPath 'Input file'
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
  & ffmpeg @ffArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Triage remux failed with exit code $LASTEXITCODE."
  }
}

function Invoke-Verification([string]$OutPath, [string]$LogPath, [int64]$DurUs) {
  Ensure-ExistingPath $OutPath 'Output file'
  Assert-NonEmptyString $LogPath 'Log path'
  Assert-True ($DurUs -ge 0) "Duration microseconds must be >= 0."

  $availableHw = Get-FfmpegHwaccels
  $verifyCandidates = Get-VerifyCandidates $availableHw

  $verifyExit = $null
  $used = 'CPU'

  foreach ($c in $verifyCandidates) {
    $hw  = $c[0]
    $fmt = $c[1]

    if ($hw) { Write-Host "Verify decode: trying hwaccel=$hw" }
    else     { Write-Host 'Verify decode: trying CPU' }

    $verifyExit = Run-Verify -outPath $OutPath -logPath $LogPath -durUs $DurUs -hwaccel $hw -hwoutfmt $fmt

    if ($verifyExit -eq 0) {
      $used = if ($hw) { $hw } else { 'CPU' }
      break
    }

    if ($hw) {
      Remove-Item -LiteralPath $LogPath -Force -ErrorAction SilentlyContinue
      Start-Sleep -Milliseconds 100
      continue
    } else {
      break
    }
  }

  Assert-True ($null -ne $verifyExit) 'Verification did not produce an exit code.'
  return @{ ExitCode = $verifyExit; Used = $used }
}

function Finalize-VerificationLog(
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
  $meaningfulLines = Get-MeaningfulLogLines -LogLines $logLines -HarmlessPatterns $HarmlessPatterns

  if ($VerifyExit -ne 0) {
    $newLog = "${baseLog}_WITHERRORS.log"
    Rename-Log -LogPath $LogPath -NewLog $newLog
    Write-Host "Verification failed (exit $VerifyExit)."
    Write-Host "Log renamed to: `"$newLog`""
    exit $VerifyExit
  }

  if ($meaningfulLines.Count -eq 0) {
    $newLog = "${baseLog}_NOERRORS.log"
    Rename-Log -LogPath $LogPath -NewLog $newLog
    Write-Host 'The file seems clean (only harmless warnings, if any).'
    Write-Host "Log renamed to: `"$newLog`""
  } else {
    $newLog = "${baseLog}_WITHERRORS.log"
    Rename-Log -LogPath $LogPath -NewLog $newLog
    Write-Host 'Verification produced meaningful warnings/errors.'
    Write-Host "Log renamed to: `"$newLog`""
    Write-Host ''
    Write-Host 'First issues detected:'
    $meaningfulLines | Select-Object -First 8 | ForEach-Object { Write-Host "  $_" }
  }
}

function Run-Verify(
  [string]$outPath,
  [string]$logPath,
  [int64]$durUs,
  [string]$hwaccel,
  [string]$hwoutfmt
) {
  Assert-NonEmptyString $outPath 'Output path'
  Assert-NonEmptyString $logPath 'Log path'
  Assert-True ($durUs -ge 0) "Duration microseconds must be >= 0."

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

  $argString = ($argList | ForEach-Object { Quote-Arg $_ }) -join ' '

  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = 'ffmpeg'
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

  [void]$p.Start()

  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  $lastPct = -1
  $lastRender = [datetime]::UtcNow

  while (-not $p.HasExited) {
    while ($p.StandardOutput.Peek() -ge 0) {
      $line = $p.StandardOutput.ReadLine()
      if ($null -eq $line) { break }
      [void](Try-UpdateProgressStateFromLine $line)
    }

    while ($p.StandardError.Peek() -ge 0) {
      $eLine = $p.StandardError.ReadLine()
      if ($null -eq $eLine) { break }
      if (Try-UpdateProgressStateFromLine $eLine) { continue }
      try { $logWriter.WriteLine($eLine) } catch { }
    }

    if ($durUs -gt 0) {
      $snapshot = Get-ProgressSnapshot -DurUs $durUs -OutTimeUs $script:outTimeUs -ElapsedSec $sw.Elapsed.TotalSeconds
      $now = [datetime]::UtcNow

      if (Should-RenderProgress -Percent $snapshot.Percent -LastPercent $lastPct -Now $now -LastRender $lastRender) {
        Write-Host ("`rVerifying: {0,3}%  ETA {1}  speed {2,-8}" -f $snapshot.Percent, $snapshot.Eta, $script:speed) -NoNewline
        $lastPct = $snapshot.Percent
        $lastRender = $now
      }
    } else {
      $now = [datetime]::UtcNow
      if ((($now - $lastRender).TotalSeconds -ge 0.5)) {
        Write-Host ("`rVerifying: speed {0,-8}" -f $script:speed) -NoNewline
        $lastRender = $now
      }
    }

    Start-Sleep -Milliseconds 100
  }

  $sw.Stop()
  Write-Host ''

  try {
    while (-not $p.StandardError.EndOfStream) {
      $eLine = $p.StandardError.ReadLine()
      if ($null -eq $eLine) { break }
      if (Try-UpdateProgressStateFromLine $eLine) { continue }
      try { $logWriter.WriteLine($eLine) } catch { }
    }
  } catch { }

  try { $logWriter.Flush() } catch { }
  try { $logWriter.Dispose() } catch { }

  return $p.ExitCode
}

# ----------------------
# Main flow
# ----------------------
$paths = Get-OutputPaths -InputPath (Get-ResolvedInputPath $InputFile)
$inPath  = $paths.InPath
$outPath = $paths.OutPath
$logPath = $paths.LogPath
$ext     = $paths.Ext

$needAacBsf = Get-AacBsfNeeded -InputPath $inPath -Extension $ext

Write-Host ''
Write-Host "Input : `"$inPath`""
Write-Host "Output: `"$outPath`""
if ($needAacBsf) { Write-Host 'Mode  : TS + AAC (using -bsf:a aac_adtstoasc)' }
else             { Write-Host 'Mode  : Generic remux (no audio bitstream filter)' }
Write-Host ''

Invoke-TriageRemux -InputPath $inPath -OutputPath $outPath -NeedAacBsf $needAacBsf

Write-Host ''
Write-Host 'SUCCESS.'
Write-Host ''

Write-Host 'Running post-mortem verification pass...'
$durUs = Get-FormatDurationUs $outPath

$verifyResult = Invoke-Verification -OutPath $outPath -LogPath $logPath -DurUs $durUs

Write-Host "Verification completed using: $($verifyResult.Used)"
Write-Host "Verification log saved to `"$logPath`""

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

Finalize-VerificationLog -VerifyExit $verifyResult.ExitCode -LogPath $logPath -OutPath $outPath -HarmlessPatterns $harmlessPatterns

exit 0
