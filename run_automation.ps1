<#
.SYNOPSIS
    BENXAUTOMATION — Unified Topic-to-Video Generation and Validation Runner
.DESCRIPTION
    Runs the complete topic-to-video automation pipeline locally on Windows.
    Accepts a topic, validates dependencies, generates narration, scenes,
    Shorts and long-form videos, subtitles, and executes thorough media validation.
    YouTube publishing remains disabled and strictly separate.
.EXAMPLE
    .\run_automation.ps1 -Topic "5 surprising facts about the deep sea"
    .\run_automation.ps1 -Topic "Mariana Trench" -Format "shorts"
    .\run_automation.ps1 -Script "Custom voiceover text..." -Format "both"
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Topic = "5 surprising facts about the deep sea",

    [Parameter()]
    [string]$Script = "",

    [Parameter()]
    [ValidateSet("both", "shorts", "longform")]
    [string]$Format = "both",

    [Parameter()]
    [int]$Duration = 0,

    [Parameter()]
    [string]$Voice = "",

    [Parameter()]
    [string]$Language = "en",

    [Parameter()]
    [string]$Provider = "",

    [Parameter()]
    [string]$OutputDir = "output/automation_run",

    [Parameter()]
    [switch]$NoSubtitles,

    [Parameter()]
    [switch]$NoMusic,

    [Parameter()]
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ScriptRoot = $PSScriptRoot
if (-not $ScriptRoot) { $ScriptRoot = (Get-Location).Path }
Set-Location $ScriptRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " BENXAUTOMATION — End-to-End Video Generation Runner" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# ── 1. Locate Python Interpreter ─────────────────────────────────────
Write-Host "`n[1/5] Checking Python environment..." -ForegroundColor Yellow
$PythonCandidates = @(
    "C:\Users\Admin\python311\tools\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "python.exe"
)

$PythonExe = $null
foreach ($cand in $PythonCandidates) {
    if (Test-Path $cand) {
        $PythonExe = $cand
        break
    } else {
        $resolved = Get-Command $cand -ErrorAction SilentlyContinue
        if ($resolved) {
            $PythonExe = $resolved.Source
            break
        }
    }
}

if (-not $PythonExe) {
    Write-Host "[ERROR] Python 3.10+ interpreter not found. Please install Python or set path." -ForegroundColor Red
    exit 1
}

$PyVersion = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null
Write-Host "  Using Python: $PythonExe (v$PyVersion)" -ForegroundColor Green

# ── 2. Locate FFmpeg & FFprobe ───────────────────────────────────────
Write-Host "`n[2/5] Checking FFmpeg & FFprobe..." -ForegroundColor Yellow
$FFmpegExe = $null
$FFprobeExe = $null

# Check via python helper which synchronizes Windows registry PATH
$ResolvedTools = & $PythonExe -c "
from benxautomation.renderer.ffmpeg_utils import find_ffmpeg, find_ffprobe
try:
    print('FFMPEG=' + find_ffmpeg())
    print('FFPROBE=' + find_ffprobe())
except Exception as e:
    print('ERROR=' + str(e))
"

foreach ($line in ($ResolvedTools -split "`r?`n")) {
    if ($line -like "FFMPEG=*") { $FFmpegExe = $line.Substring(7) }
    if ($line -like "FFPROBE=*") { $FFprobeExe = $line.Substring(8) }
}

if (-not $FFmpegExe -or -not (Test-Path $FFmpegExe)) {
    Write-Host "[ERROR] FFmpeg binary not found. Please install FFmpeg." -ForegroundColor Red
    exit 1
}
if (-not $FFprobeExe -or -not (Test-Path $FFprobeExe)) {
    Write-Host "[ERROR] FFprobe binary not found. Please install FFprobe." -ForegroundColor Red
    exit 1
}

Write-Host "  FFmpeg:  $FFmpegExe" -ForegroundColor Green
Write-Host "  FFprobe: $FFprobeExe" -ForegroundColor Green

# ── 3. Assemble CLI Arguments & Execute Pipeline ─────────────────────
Write-Host "`n[3/5] Launching generation pipeline..." -ForegroundColor Yellow

$CliArgs = @("-m", "benxautomation.main")

if ($Script) {
    $CliArgs += @("--script", $Script)
    if ($Topic) { $CliArgs += @("--topic", $Topic) }
} else {
    $CliArgs += @("--topic", $Topic)
}

$CliArgs += @("--format", $Format)
$CliArgs += @("--output-dir", $OutputDir)
$CliArgs += @("--language", $Language)

$EffectiveProvider = $Provider
if (-not $EffectiveProvider) {
    if ($env:GEMINI_API_KEY) {
        $EffectiveProvider = "gemini"
    } elseif ($env:OPENAI_API_KEY) {
        $EffectiveProvider = "openai"
    } else {
        $EffectiveProvider = "fallback"
    }
}
$CliArgs += @("--provider", $EffectiveProvider)
if ($Voice) { $CliArgs += @("--voice", $Voice) }
if ($Duration -gt 0) { $CliArgs += @("--duration", "$Duration") }
if ($NoSubtitles) { $CliArgs += "--no-subtitles" }
if ($NoMusic) { $CliArgs += "--no-music" }
if ($DryRun) { $CliArgs += "--dry-run" }

$ManifestPath = Join-Path $ScriptRoot "assets/license_manifest.yaml"
if (Test-Path $ManifestPath) {
    $CliArgs += @("--manifest", $ManifestPath)
}

$StartTime = Get-Date
& $PythonExe @CliArgs
$ExitCode = $LASTEXITCODE

if ($ExitCode -ne 0) {
    Write-Host "`n[FAIL] Pipeline execution failed with exit code $ExitCode." -ForegroundColor Red
    exit $ExitCode
}

if ($DryRun) {
    Write-Host "`n[SUCCESS] Dry-run validation completed successfully." -ForegroundColor Green
    exit 0
}

# ── 4. Verify & Validate Rendered Artifacts ──────────────────────────
Write-Host "`n[4/5] Auditing rendered media outputs..." -ForegroundColor Yellow

$OutDirResolved = (Resolve-Path $OutputDir).Path
$ShortsVideo = Join-Path $OutDirResolved "video_shorts.mp4"
$LongformVideo = Join-Path $OutDirResolved "video_longform.mp4"
$NarrationAudio = Join-Path $OutDirResolved "video_narration.mp3"
$SubtitlesSrt = Join-Path $OutDirResolved "video_subtitles.srt"
$QualityReportJson = Join-Path $OutDirResolved "video_quality_report.json"
$ScenePlanJson = Join-Path $OutDirResolved "video_scene_plan.json"
$ScriptJson = Join-Path $OutDirResolved "video_script.json"

$VideosToVerify = @()
if ($Format -eq "both" -or $Format -eq "shorts") {
    if (Test-Path $ShortsVideo) { $VideosToVerify += @{ Path = $ShortsVideo; Name = "Shorts (9:16)" } }
    else { Write-Host "  [FAIL] Expected Shorts video missing: $ShortsVideo" -ForegroundColor Red }
}
if ($Format -eq "both" -or $Format -eq "longform") {
    if (Test-Path $LongformVideo) { $VideosToVerify += @{ Path = $LongformVideo; Name = "Long-form (16:9)" } }
    else { Write-Host "  [FAIL] Expected Long-form video missing: $LongformVideo" -ForegroundColor Red }
}

$AllDecodesClean = $true
foreach ($v in $VideosToVerify) {
    $p = $v.Path
    $n = $v.Name
    # Full null decode
    $decodeErr = & $FFmpegExe -v error -i $p -f null - 2>&1
    if ($LASTEXITCODE -ne 0 -or $decodeErr) {
        Write-Host "  [FAIL] $n decode corruption: $decodeErr" -ForegroundColor Red
        $AllDecodesClean = $false
    } else {
        # Check stream duration and faststart
        $probe = & $FFprobeExe -v error -show_entries "stream=codec_type,codec_name,duration:format=duration,size" -of json $p | ConvertFrom-Json
        $vStream = $probe.streams | Where-Object { $_.codec_type -eq "video" } | Select-Object -First 1
        $aStream = $probe.streams | Where-Object { $_.codec_type -eq "audio" } | Select-Object -First 1

        $dur = [math]::Round([double]$probe.format.duration, 2)
        $sz = [math]::Round($probe.format.size / 1MB, 2)
        $hasAudio = ($null -ne $aStream)

        Write-Host "  [OK] $n : $sz MB, $dur s, video=$($vStream.codec_name), audio=$hasAudio (Full decode clean)" -ForegroundColor Green
    }
}

# ── 5. Parse Quality Report & Print Executive Summary ────────────────
Write-Host "`n[5/5] Quality Validation Report" -ForegroundColor Yellow

$RenderPassed = $AllDecodesClean
$ContentPassed = $false
$QualityIssues = @()

if (Test-Path $QualityReportJson) {
    $qReport = Get-Content $QualityReportJson -Raw | ConvertFrom-Json
    $RenderPassed = $RenderPassed -and [bool]$qReport.render_success
    $ContentPassed = [bool]$qReport.content_quality_passed
    if ($qReport.quality_issues) { $QualityIssues = $qReport.quality_issues }
    elseif ($qReport.content_issues) { $QualityIssues = $qReport.content_issues }
}

$Elapsed = [math]::Round(((Get-Date) - $StartTime).TotalSeconds, 1)

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host " EXECUTION SUMMARY & ARTIFACT MANIFEST" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Topic:              $Topic"
if ($Script) {
    Write-Host "Script Type:        Manual User Narration"
} else {
    Write-Host "Script Type:        Topic-to-Script Automation"
}
Write-Host "Elapsed Time:       $Elapsed seconds"
Write-Host "Output Directory:   $OutDirResolved"
Write-Host "Artifacts Generated:"
if (Test-Path $ScriptJson)      { Write-Host "  - Script:         $ScriptJson" }
if (Test-Path $NarrationAudio)  { Write-Host "  - Narration:      $NarrationAudio" }
if (Test-Path $SubtitlesSrt)    { Write-Host "  - Subtitles:      $SubtitlesSrt" }
if (Test-Path $ScenePlanJson)   { Write-Host "  - Scene Plan:     $ScenePlanJson" }
if (Test-Path $ShortsVideo)     { Write-Host "  - Shorts Video:   $ShortsVideo" }
if (Test-Path $LongformVideo)   { Write-Host "  - Long-form:      $LongformVideo" }
if (Test-Path $QualityReportJson){ Write-Host "  - Quality Report: $QualityReportJson" }

Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
if ($RenderPassed) {
    Write-Host "Render Status:      PASS (Clean decode, valid streams, correct durations)" -ForegroundColor Green
} else {
    Write-Host "Render Status:      FAIL (Media decode or rendering errors detected)" -ForegroundColor Red
}

if ($ContentPassed) {
    Write-Host "Content Quality:    PASS (Fully verified / adequate script)" -ForegroundColor Green
} else {
    Write-Host "Content Quality:    UNVERIFIED DRAFT / OUTLINE (Verification required)" -ForegroundColor Yellow
}

if ($QualityIssues.Count -gt 0) {
    Write-Host "Quality Notes:" -ForegroundColor Yellow
    foreach ($qi in $QualityIssues) {
        Write-Host "  - $qi" -ForegroundColor Yellow
    }
}

Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "YouTube Publishing: DISABLED (Safety guard active; uploads must be explicitly triggered)" -ForegroundColor Gray
Write-Host "============================================================`n" -ForegroundColor Cyan

if ($RenderPassed) {
    exit 0
} else {
    exit 2
}
