param(
  [Parameter(Mandatory=$true, Position=0)]
  [string]$InputFile
)

Set-StrictMode -Version 2

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

function Get-FormatDurationSec([string]$path) {
  $durSec = 0.0
  try {
    $d = & ffprobe -v error -show_entries format=duration -of default=nokey=1:noprint_wrappers=1 -- $path
    # Locale-safe parse (handles decimal dot even on comma-decimal locales)
    $ci = [System.Globalization.CultureInfo]::InvariantCulture
    [void][double]::TryParse($d.Trim(), [System.Globalization.NumberStyles]::Float, $ci, [ref]$durSec)
  } catch { $durSec = 0.0 }
  return $durSec
}

function Run-Verify(
  [string]$outPath,
  [string]$logPath,
  [int64]$durUs,
  [string]$hwaccel,
  [string]$hwoutfmt
) {
  # Clear log for this attempt
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

  # shared state (updated by parsing -progress output)
  $script:outTimeUs = [int64]0
  $script:speed = '?'

  [void]$p.Start()

  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  $lastPct = -1
  $lastRender = [datetime]::UtcNow
  $eta = '??:??:??'

  $sawEnd = $false
  while (-not $p.HasExited) {
    # Drain stdout (ffmpeg -progress pipe:1)
    while ($p.StandardOutput.Peek() -ge 0) {
      $line = $p.StandardOutput.ReadLine()
      if ($null -eq $line) { break }
      if ($line -match '^(?<k>[^=]+)=(?<v>.*)$') {
        $k = $Matches.k; $v = $Matches.v
        if ($k -eq 'out_time_us') {
          [void][int64]::TryParse($v, [ref]$script:outTimeUs)
        } elseif ($k -eq 'out_time_ms') {
          $tmp = [int64]0
          if ([int64]::TryParse($v, [ref]$tmp)) { $script:outTimeUs = $tmp * 1000 }
        } elseif ($k -eq 'out_time') {
          $ts = [TimeSpan]::Zero
          if ([TimeSpan]::TryParse($v, [ref]$ts)) {
            $script:outTimeUs = [int64]($ts.TotalSeconds * 1000000.0)
          }
        } elseif ($k -eq 'speed') {
          if ($v) { $script:speed = $v } else { $script:speed = '?' }
        } elseif ($k -eq 'progress' -and $v -eq 'end') {
          $sawEnd = $true
        }
      }
    }

    # Drain stderr (warnings/errors) into log.
    # Some ffmpeg builds may emit -progress lines to stderr; parse them too.
    while ($p.StandardError.Peek() -ge 0) {
      $eLine = $p.StandardError.ReadLine()
      if ($null -eq $eLine) { break }

      # If this looks like a progress line, update state and do not log it.
      if ($eLine -match '^(?<k>[^=]+)=(?<v>.*)$') {
        $k2 = $Matches.k; $v2 = $Matches.v
        if ($k2 -eq 'out_time_us') {
          [void][int64]::TryParse($v2, [ref]$script:outTimeUs)
          continue
        } elseif ($k2 -eq 'out_time_ms') {
          $tmp2 = [int64]0
          if ([int64]::TryParse($v2, [ref]$tmp2)) { $script:outTimeUs = $tmp2 * 1000 }
          continue
        } elseif ($k2 -eq 'out_time') {
          $ts2 = [TimeSpan]::Zero
          if ([TimeSpan]::TryParse($v2, [ref]$ts2)) { $script:outTimeUs = [int64]($ts2.TotalSeconds * 1000000.0) }
          continue
        } elseif ($k2 -eq 'speed') {
          if ($v2) { $script:speed = $v2 } else { $script:speed = '?' }
          continue
        } elseif ($k2 -eq 'progress') {
          continue
        }
      }

      try { $logWriter.WriteLine($eLine) } catch { }
    }

    if ($durUs -gt 0) {
      $pctD = [math]::Max([double]0, [math]::Min([double]100, [math]::Floor((($script:outTimeUs / [double]$durUs) * 100))))
      $pct = [int]$pctD

      $now = [datetime]::UtcNow
      $shouldRender = ($pct -ne $lastPct) -or (($now - $lastRender).TotalSeconds -ge 0.5)

      if ($shouldRender) {
        $eta = '??:??:??'
        $elapsedSec = [math]::Max(0.001, $sw.Elapsed.TotalSeconds)
        $rateUsPerSec = $script:outTimeUs / $elapsedSec

        if ($rateUsPerSec -gt 0) {
          $remainUs  = [math]::Max([int64]0, ($durUs - $script:outTimeUs))
          $remainSec = [math]::Floor($remainUs / $rateUsPerSec)
		if ($remainSec -ge 0 -and $remainSec -lt 3155760000) {  # < ~100 years, sanity guard
		  $hrs = [int]($remainSec / 3600)
		  $mins = [int](($remainSec % 3600) / 60)
		  $secs = [int]($remainSec % 60)
		  $eta = ("{0:00}:{1:00}:{2:00}" -f $hrs, $mins, $secs)
		} else {
		  $eta = "??:??:??"
		}
        }

        Write-Host ("`rVerifying: {0,3}%  ETA {1}  speed {2,-8}" -f $pct, $eta, $script:speed) -NoNewline
        $lastPct = $pct
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

  # one last drain after exit
  try {
    while (-not $p.StandardError.EndOfStream) {
      $eLine = $p.StandardError.ReadLine()
      if ($null -eq $eLine) { break }

      if ($eLine -match '^(?<k>[^=]+)=(?<v>.*)$') {
        $k2 = $Matches.k; $v2 = $Matches.v
        if ($k2 -eq 'out_time_us') {
          [void][int64]::TryParse($v2, [ref]$script:outTimeUs)
          continue
        } elseif ($k2 -eq 'out_time_ms') {
          $tmp2 = [int64]0
          if ([int64]::TryParse($v2, [ref]$tmp2)) { $script:outTimeUs = $tmp2 * 1000 }
          continue
        } elseif ($k2 -eq 'out_time') {
          $ts2 = [TimeSpan]::Zero
          if ([TimeSpan]::TryParse($v2, [ref]$ts2)) { $script:outTimeUs = [int64]($ts2.TotalSeconds * 1000000.0) }
          continue
        } elseif ($k2 -eq 'speed') {
          if ($v2) { $script:speed = $v2 } else { $script:speed = '?' }
          continue
        } elseif ($k2 -eq 'progress') {
          continue
        }
      }

      try { $logWriter.WriteLine($eLine) } catch { }
    }
  } catch { }

  try { $logWriter.Flush() } catch { }
  try { $logWriter.Dispose() } catch { }

  return $p.ExitCode
}

# ----------------------
# Resolve paths & output naming
# ----------------------
$inPath = (Resolve-Path -Path $InputFile).Path
$dir    = Split-Path -Path $inPath -Parent
$base   = [IO.Path]::GetFileNameWithoutExtension($inPath)
$ext    = [IO.Path]::GetExtension($inPath)

if ($ext -ieq '.mkv') { $outPath = Join-Path $dir ($base + '_.mkv') }
else                  { $outPath = Join-Path $dir ($base + '.mkv')  }

$logPath = [IO.Path]::ChangeExtension($outPath, '.log')

# Detect AAC ADTS->ASC need for TS-like inputs
$tsLikeExt = @('.ts','.m2ts','.mts','.trp','.tp','.vob')
$needAacBsf = $false

if ($tsLikeExt -contains $ext.ToLowerInvariant()) {
  try {
    $aCodec = & ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of default=nokey=1:noprint_wrappers=1 -- $inPath
    if ($aCodec.Trim().ToLowerInvariant() -eq 'aac') { $needAacBsf = $true }
  } catch { $needAacBsf = $false }
}

Write-Host ''
Write-Host "Input : `"$inPath`""
Write-Host "Output: `"$outPath`""
if ($needAacBsf) { Write-Host 'Mode  : TS + AAC (using -bsf:a aac_adtstoasc)' }
else             { Write-Host 'Mode  : Generic remux (no audio bitstream filter)' }
Write-Host ''

# TRIAGE REMUX (no re-encode)
$ffArgs = @(
  '-hide_banner','-y',
  '-fflags','+genpts',
  '-err_detect','ignore_err',
  '-probesize','100M','-analyzeduration','100M',
  '-ignore_unknown','-copy_unknown',
  '-i', $inPath,
  '-map','0','-map_metadata','0','-map_chapters','0',
  '-c','copy',
  '-start_at_zero',
  '-max_interleave_delta','0'
)

if ($needAacBsf) { $ffArgs += @('-bsf:a','aac_adtstoasc') }
$ffArgs += $outPath

$LASTEXITCODE = 0
& ffmpeg @ffArgs
if ($LASTEXITCODE -ne 0) { throw "Triage remux failed with exit code $LASTEXITCODE." }

Write-Host ''
Write-Host 'SUCCESS.'
Write-Host ''

# POST-MORTEM VERIFY with hwaccel fallback (keep audio validation)
Write-Host 'Running post-mortem verification pass...'

$durSec = Get-FormatDurationSec $outPath
$durUs  = if ($durSec -gt 0) { [int64]($durSec * 1000000) } else { 0 }

# Check hardware

# --- Determine available hardware acceleration methods ---
$availableHw = Get-FfmpegHwaccels

# IMPORTANT: each entry must be a 2-item array: @($hwaccel, $outputFormat)
$verifyCandidates = @()

if ($availableHw -contains "d3d11va") { $verifyCandidates += ,@("d3d11va", $null) }
if ($availableHw -contains "cuda")    { $verifyCandidates += ,@("cuda",    "cuda") }
if ($availableHw -contains "qsv")     { $verifyCandidates += ,@("qsv",     $null) }

# Always add CPU fallback as a *pair*
$verifyCandidates += ,@($null, $null)



$verifyExit = $null
$used = 'CPU'

foreach ($c in $verifyCandidates) {
  if ($null -eq $c -or $c.Count -lt 2) { continue }

  $hw  = $c[0]
  $fmt = $c[1]

  if ($hw) { Write-Host "Verify decode: trying hwaccel=$hw" }
  else     { Write-Host 'Verify decode: trying CPU' }

  $verifyExit = Run-Verify -outPath $outPath -logPath $logPath -durUs $durUs -hwaccel $hw -hwoutfmt $fmt

  if ($verifyExit -eq 0) {
    $used = if ($hw) { $hw } else { 'CPU' }
    break
  }

  if ($hw) {
    # hwaccel attempt failed; discard this attempt's log and try next
    Remove-Item -LiteralPath $logPath -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 100
    continue
  } else {
    break
  }
}

Write-Host "Verification completed using: $used"
Write-Host "Verification log saved to `"$logPath`""

# Log evaluation & rename verdict
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

$baseLog = [System.IO.Path]::Combine(
  [System.IO.Path]::GetDirectoryName($outPath),
  [System.IO.Path]::GetFileNameWithoutExtension($outPath)
)


$logLines = @()
try {
  if (Test-Path -LiteralPath $logPath) {
    $logLines = Get-Content -LiteralPath $logPath -ErrorAction Stop
  }
} catch { $logLines = @() }

$meaningfulLines = @($logLines | Where-Object {
  $line = $_
  -not ($harmlessPatterns | Where-Object { $line -match $_ })
})

if ($verifyExit -ne 0) {
  $newLog = "${baseLog}_WITHERRORS.log"
  if (Test-Path -LiteralPath $logPath) {
    Move-Item -LiteralPath $logPath -Destination $newLog -Force
  } else {
    New-Item -Path $newLog -ItemType File -Force | Out-Null
  }
  Write-Host "Verification failed (exit $verifyExit)."
  Write-Host "Log renamed to: `"$newLog`""
  exit $verifyExit
}

if ($meaningfulLines.Count -eq 0) {
  $newLog = "${baseLog}_NOERRORS.log"
  Move-Item -LiteralPath $logPath -Destination $newLog -Force
  Write-Host 'The file seems clean (only harmless warnings, if any).'
  Write-Host "Log renamed to: `"$newLog`""
} else {
  $newLog = "${baseLog}_WITHERRORS.log"
  Move-Item -LiteralPath $logPath -Destination $newLog -Force
  Write-Host 'Verification produced meaningful warnings/errors.'
  Write-Host "Log renamed to: `"$newLog`""
  Write-Host ''
  Write-Host 'First issues detected:'
  $meaningfulLines | Select-Object -First 8 | ForEach-Object { Write-Host "  $_" }
}

exit 0
