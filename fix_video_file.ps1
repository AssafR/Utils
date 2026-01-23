param(
  [Parameter(Mandatory=$true, Position=0)]
  [string]$InputFile
)

# --- Resolve paths ---
$inPath = (Resolve-Path -Path $InputFile).Path
$dir    = Split-Path -Path $inPath -Parent
$base   = [IO.Path]::GetFileNameWithoutExtension($inPath)
$ext    = [IO.Path]::GetExtension($inPath)

if ($ext -ieq ".mkv") { $outPath = Join-Path $dir ($base + "_.mkv") }
else                  { $outPath = Join-Path $dir ($base + ".mkv")  }

$logPath = [IO.Path]::ChangeExtension($outPath, ".log")

# --- Detect whether we should apply AAC ADTS->ASC bitstream filter ---
$tsLikeExt = @(".ts",".m2ts",".mts",".trp",".tp",".vob")
$needAacBsf = $false

if ($tsLikeExt -contains $ext.ToLowerInvariant()) {
  try {
    $aCodec = & ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of default=nokey=1:noprint_wrappers=1 -- $inPath
    if ($aCodec.Trim().ToLowerInvariant() -eq "aac") { $needAacBsf = $true }
  } catch { $needAacBsf = $false }
}

Write-Host ""
Write-Host "Input : `"$inPath`""
Write-Host "Output: `"$outPath`""
if ($needAacBsf) { Write-Host "Mode  : TS + AAC (using -bsf:a aac_adtstoasc)" }
else             { Write-Host "Mode  : Generic remux (no audio bitstream filter)" }
Write-Host ""

# Hardware encode selection
function Get-FfmpegHwaccels {
  try {
    $out = & ffmpeg -hide_banner -hwaccels 2>$null
    return ($out | ForEach-Object { $_.Trim() }) | Where-Object { $_ -and $_ -notmatch 'Hardware acceleration methods:' }
  } catch {
    return @()
  }
}


$available = Get-FfmpegHwaccels

# Preferred order for Windows verification
$candidates = @()

if ($available -contains "d3d11va") { $candidates += @(@("d3d11va","d3d11")) }
if ($available -contains "cuda")    { $candidates += @(@("cuda","cuda")) }   # NVDEC/NV12 path if supported
if ($available -contains "qsv")     { $candidates += @(@("qsv",$null)) }     # Intel QuickSync

# Always end with CPU fallback
$candidates += @(@($null,$null))






# --- TRIAGE REMUX (no re-encode) ---
$ffArgs = @(
  "-hide_banner","-y",
  "-fflags","+genpts",
  "-err_detect","ignore_err",
  "-probesize","100M","-analyzeduration","100M",
  "-ignore_unknown","-copy_unknown",
  "-i", $inPath,
  "-map","0","-map_metadata","0","-map_chapters","0",
  "-c","copy",
  "-start_at_zero",
  "-max_interleave_delta","0"
)

if ($needAacBsf) { $ffArgs += @("-bsf:a","aac_adtstoasc") }
$ffArgs += $outPath

$LASTEXITCODE = 0
& ffmpeg @ffArgs
$exit = $LASTEXITCODE

if ($exit -ne 0) {
  throw "Triage remux failed with exit code $exit."
}



Write-Host ""
Write-Host "SUCCESS."
Write-Host ""

# --- Get duration for progress percent (may be empty) ---
$durSec = 0.0
try {
  $d = & ffprobe -v error -show_entries format=duration -of default=nokey=1:noprint_wrappers=1 -- "$outPath"
  [void][double]::TryParse($d.Trim(), [ref]$durSec)
} catch { $durSec = 0.0 }

# --- POST-MORTEM VERIFY (single pass, progress bar, warnings-only log) ---
Write-Host "Running post-mortem verification pass..."
New-Item -Path $logPath -ItemType File -Force | Out-Null

$durUs = if ($durSec -gt 0) { [int64]($durSec * 1000000) } else { 0 }

# Start ffmpeg verify and read its progress from stdout
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "ffmpeg"
$psi.Arguments = @(
  "-hide_banner","-nostats","-loglevel","warning",
  "-i", "`"$outPath`"",
  "-f","null","-",
  "-progress","pipe:1"
) -join " "
$psi.RedirectStandardOutput = $true   # progress key=value
$psi.RedirectStandardError  = $true   # warnings/errors
$psi.UseShellExecute        = $false
$psi.CreateNoWindow         = $true

$p = New-Object System.Diagnostics.Process
$p.StartInfo = $psi
[void]$p.Start()

# async stderr -> log file
$logWriter = New-Object System.IO.StreamWriter($logPath, $false, [System.Text.Encoding]::UTF8)

$stderrJob = [System.Threading.Tasks.Task]::Factory.StartNew(
  {
    param($state)
    $proc   = $state.proc
    $writer = $state.writer
    try {
      while (-not $proc.StandardError.EndOfStream) {
        $line = $proc.StandardError.ReadLine()
        if ($null -eq $line) { break }
        $writer.WriteLine($line)
      }
    } catch {
      # swallow logging thread errors; verification result is still valid
    }
  },
  @{ proc = $p; writer = $logWriter }
)




$outTimeUs = [int64]0
$speed = ""
$lastPct = -1

$sw = [System.Diagnostics.Stopwatch]::StartNew()
$eta = "??:??"

# ----- RENDER BLOCK

$lastRender = [datetime]::UtcNow
$eta = "??:??:??"

while (-not $p.StandardOutput.EndOfStream) {
  $line = $p.StandardOutput.ReadLine()
  if ($line -match "^(?<k>[^=]+)=(?<v>.*)$") {
    $k = $Matches.k; $v = $Matches.v
    if ($k -eq "out_time_ms") { [void][int64]::TryParse($v, [ref]$outTimeUs) }
    elseif ($k -eq "speed") { $speed = $v }
    elseif ($k -eq "progress" -and $v -eq "end") { break }
  }

  if ($durUs -gt 0) {
    $pct = [math]::Max([double]0, [math]::Min([double]100, [math]::Floor((($outTimeUs / [double]$durUs) * 100))))
	$pct = [int]$pct


    $now = [datetime]::UtcNow
    $shouldRender = ($pct -ne $lastPct) -or (($now - $lastRender).TotalSeconds -ge 0.5)

    if ($shouldRender) {
      # estimate remaining time (ETA)
      $eta = "??:??:??"
      $elapsedSec = [math]::Max(0.001, $sw.Elapsed.TotalSeconds)
      $rateUsPerSec = $outTimeUs / $elapsedSec

      if ($rateUsPerSec -gt 0) {
        $remainUs  = [math]::Max([int64]0, ($durUs - $outTimeUs))
        $remainSec = [math]::Floor($remainUs / $rateUsPerSec)
        $eta = ([TimeSpan]::FromSeconds($remainSec)).ToString("hh\:mm\:ss")
      }

      Write-Host ("`rVerifying: {0,3}%  ETA {1}  speed {2,-8}" -f $pct, $eta, $speed) -NoNewline
      $lastPct = $pct
      $lastRender = $now
    }
  } else {
    # duration unknown: show speed only (still refresh occasionally)
    $now = [datetime]::UtcNow
    if ((($now - $lastRender).TotalSeconds -ge 0.5)) {
      Write-Host ("`rVerifying: speed {0,-8}" -f $speed) -NoNewline
      $lastRender = $now
    }
  }
}

$sw.Stop()
Write-Host ""




$p.WaitForExit()

try {
  $stderrJob.Wait()
} catch {
  # Ignore logging task failures (verification already completed)
}

try {
  $logWriter.Flush()
  $logWriter.Dispose()
} catch { }



Write-Host "Verification log saved to `"$logPath`""

$logText = ""
try {
  $logText = Get-Content -LiteralPath $logPath -Raw -ErrorAction Stop
} catch { }


$baseLog = [System.IO.Path]::ChangeExtension($logPath, $null)

$logText = ""
try {
  $logText = Get-Content -LiteralPath $logPath -Raw -ErrorAction Stop
} catch { }

# Log Evaluation:

# --- Known harmless warnings (regex patterns, case-insensitive) ---
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



$baseLog = [System.IO.Path]::ChangeExtension($logPath, $null)

$logLines = @()
try {
  $logLines = Get-Content -LiteralPath $logPath -ErrorAction Stop
} catch { }

# Remove harmless warnings
$meaningfulLines = $logLines | Where-Object {
  $line = $_
  -not ($harmlessPatterns | Where-Object { $line -match $_ })
}

if ($meaningfulLines.Count -eq 0) {

  $newLog = "${baseLog}_NOERRORS.log"
  Move-Item -LiteralPath $logPath -Destination $newLog -Force

  Write-Host "The file seems clean (only harmless warnings, if any)."
  Write-Host "Log renamed to: `"$newLog`""

} else {

  $newLog = "${baseLog}_WITHERRORS.log"
  Move-Item -LiteralPath $logPath -Destination $newLog -Force

  Write-Host "Verification produced meaningful warnings/errors."
  Write-Host "Log renamed to: `"$newLog`""

  # Optional: show first few real problems
  Write-Host ""
  Write-Host "First issues detected:"
  $meaningfulLines | Select-Object -First 5 | ForEach-Object {
    Write-Host "  $_"
  }
}





exit 0
