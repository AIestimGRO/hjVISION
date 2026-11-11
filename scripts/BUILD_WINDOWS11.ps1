﻿# HI, JACK LIVE Windows 11 builder - PowerShell 5.1 compatible.
# The app works offline after a successful build; this builder needs internet for packages.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $project
$log = Join-Path $project 'BUILD_WINDOWS11_LOG.txt'
$transcriptStarted = $false
$success = $false

function Run-Step([string] $exe, [string[]] $commandArguments, [string] $description) {
    Write-Host ('[RUN] ' + $description) -ForegroundColor Cyan
    & $exe @commandArguments
    if ($LASTEXITCODE -ne 0) {
        throw ('Command failed, exit code ' + $LASTEXITCODE + ': ' + $description)
    }
}

function Candidate([string] $exe, [string[]] $prefix) {
    if (-not $exe) { return $null }
    $test = "import sys; ok=(sys.version_info[:2] in ((3,11),(3,12)) and sys.maxsize > 2**32); sys.exit(0 if ok else 2)"
    try {
        & $exe @prefix -c $test 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            return @{ Exe = $exe; Args = $prefix }
        }
    } catch { }
    return $null
}

function Find-Python {
    $local311 = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'
    $local312 = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
    foreach ($candidate in @($local311, $local312)) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $p = Candidate $candidate @()
            if ($p) { return $p }
        }
    }
    foreach ($version in @('3.11','3.12')) {
        if (Get-Command 'py.exe' -ErrorAction SilentlyContinue) {
            $p = Candidate 'py.exe' @('-' + $version)
            if ($p) { return $p }
        }
    }
    foreach ($pythonName in @('python.exe','python3.exe')) {
        if (Get-Command $pythonName -ErrorAction SilentlyContinue) {
            $p = Candidate $pythonName @()
            if ($p) { return $p }
        }
    }
    return $null
}

try {
    Start-Transcript -Path $log -Force | Out-Null
    $transcriptStarted = $true
    Write-Host 'HI, JACK LIVE - WINDOWS 11 v0.3.5 EDGE LIFECYCLE FIX (branded + diagnostics)' -ForegroundColor Cyan
    Write-Host ('Project: ' + $project)
    if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem) {
        throw 'This script requires 64-bit Windows 11 or Windows 10.'
    }
    foreach ($file in @('launcher.py','requirements-build.txt','modules\hj_players\module.json','modules\hj_effects\module.json')) {
        if (-not (Test-Path (Join-Path $project $file))) {
            throw ('Missing project file: ' + $file + '. Extract the entire archive before building.')
        }
    }
    $python = Find-Python
    if (-not $python) {
        Write-Host 'Python 3.11/3.12 (64-bit) not found. Installing Python 3.11 using winget...' -ForegroundColor Yellow
        if (-not (Get-Command 'winget.exe' -ErrorAction SilentlyContinue)) {
            throw 'winget is unavailable. Install Python 3.11 x64 from python.org and rerun.'
        }
        Run-Step 'winget.exe' @('install','--id','Python.Python.3.11','--exact','--source','winget','--scope','user','--accept-package-agreements','--accept-source-agreements') 'Install Python 3.11'
        $python = Find-Python
        if (-not $python) {
            throw 'Python installation finished, but python.exe was not found. Reopen Windows Terminal and rerun the builder.'
        }
    }
    Write-Host ('Python selected: ' + $python.Exe) -ForegroundColor Green
    $venv = Join-Path $project '.venv-build-win11'
    $venvExe = Join-Path $venv 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $venvExe -PathType Leaf)) {
        Run-Step $python.Exe ($python.Args + @('-m','venv',$venv)) 'Create isolated build environment'
    }
    Run-Step $venvExe @('-m','pip','install','--disable-pip-version-check','--retries','3','-r','requirements-build.txt') 'Install Windows dependencies and PyInstaller'

    $buildRoot = Join-Path $project '.build-win11'
    $binBuild = Join-Path $buildRoot 'bundle'
    $buildCache = Join-Path $buildRoot 'cache'
    $specDir = Join-Path $buildRoot 'spec'
    foreach ($d in @($buildRoot, $binBuild, $buildCache, $specDir)) {
        New-Item -ItemType Directory -Force -Path $d | Out-Null
    }
    # Validate and use ABSOLUTE source paths. Since the .spec is written to
    # .build-win11\spec, relative --add-data sources resolve from that folder
    # and cause PyInstaller's "Unable to find ...\spec\core\ui" error.
    $uiSource = Join-Path $project 'core\ui'
    $brandingSource = Join-Path $project 'branding'
    $launcherSource = Join-Path $project 'launcher.py'
    foreach ($sourcePath in @($uiSource, $brandingSource, $launcherSource)) {
        if (-not (Test-Path -LiteralPath $sourcePath)) {
            throw ('Missing required build source: ' + $sourcePath)
        }
    }
    $uiDataArg = $uiSource + ';core/ui'
    $brandingDataArg = $brandingSource + ';branding'
    $icon = Join-Path $project 'branding\HiJackLive.ico'
    if (-not (Test-Path -LiteralPath $icon -PathType Leaf)) { throw 'Missing branding\HiJackLive.ico' }
    # python -m PyInstaller MUST precede ALL PyInstaller-specific switches.
    # Otherwise --distpath is interpreted by python.exe and build fails.
    $buildArgs = @(
        '-m','PyInstaller',
        '--distpath', $binBuild,
        '--workpath', $buildCache,
        '--specpath', $specDir,
        '--icon', $icon,
        '--noconfirm','--clean','--onedir','--windowed',
        '--name','HiJackLive',
        '--paths', $project,
        '--add-data', $uiDataArg,
        '--add-data', $brandingDataArg,
        '--collect-submodules','uvicorn',
        '--collect-submodules','fastapi',
        '--collect-submodules','webview',
        '--collect-submodules','psutil',
        '--collect-data','webview',
        '--hidden-import','clr',
        '--hidden-import','uvicorn.logging',
        '--hidden-import','uvicorn.loops.auto',
        '--hidden-import','uvicorn.protocols.http.auto',
        '--hidden-import','uvicorn.protocols.websockets.auto',
        '--hidden-import','uvicorn.lifespan.on',
        $launcherSource
    )
    if ($buildArgs.Count -lt 3 -or $buildArgs[0] -ne '-m' -or $buildArgs[1] -ne 'PyInstaller') {
        throw 'Invalid PyInstaller arguments: expected python -m PyInstaller BEFORE build switches.'
    }
    Write-Host ('[INFO] UI data source: ' + $uiSource)
    Write-Host ('[INFO] Branding data source: ' + $brandingSource)
    Write-Host ('[INFO] Launcher script: ' + $launcherSource)
    Run-Step $venvExe $buildArgs 'Build HiJackLive.exe'

    $dist = Join-Path $project 'dist'
    $binaryDir = Join-Path $binBuild 'HiJackLive'
    $binary = Join-Path $binaryDir 'HiJackLive.exe'
    if (-not (Test-Path -LiteralPath $binary -PathType Leaf)) {
        throw ('PyInstaller did not produce ' + $binary)
    }
    $sizeBytes = (Get-Item -LiteralPath $binary).Length
    if ($sizeBytes -lt 1000000) { throw 'Output EXE is unexpectedly small.' }
    if (-not (Test-Path -LiteralPath (Join-Path $binaryDir '_internal') -PathType Container)) { throw 'Missing PyInstaller _internal runtime directory.' }

    if (-not (Test-Path -LiteralPath $dist)) { New-Item -ItemType Directory -Path $dist | Out-Null }
    $ready = Join-Path $dist 'HI_JACK_LIVE'
    $stage = Join-Path $dist 'HI_JACK_LIVE_READY_TEMP'
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    # Copy the COMPLETE onedir bundle: its _internal folder is required.
    Copy-Item -Path (Join-Path $binaryDir '*') -Destination $stage -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $project 'modules') -Destination $stage -Recurse -Force
    $safeMode = '@echo off' + "`r`n" + 'cd /d "%~dp0"' + "`r`n" + 'start "" "%~dp0HiJackLive.exe" --safe-mode' + "`r`n"
    [System.IO.File]::WriteAllText((Join-Path $stage 'START_SAFE_MODE.cmd'),$safeMode,[System.Text.Encoding]::ASCII)
    $legacyMode = '@echo off' + "`r`n" + 'cd /d "%~dp0"' + "`r`n" + 'start "" "%~dp0HiJackLive.exe" --webview2' + "`r`n"
    [System.IO.File]::WriteAllText((Join-Path $stage 'START_WEBVIEW2_TEST.cmd'),$legacyMode,[System.Text.Encoding]::ASCII)
    Copy-Item -LiteralPath (Join-Path $project 'OPEN_DIAGNOSTICS.cmd') -Destination (Join-Path $stage 'OPEN_DIAGNOSTICS.cmd') -Force
    Copy-Item -LiteralPath (Join-Path $project 'CHECK_LOCAL_SERVER.cmd') -Destination (Join-Path $stage 'CHECK_LOCAL_SERVER.cmd') -Force
    Copy-Item -LiteralPath (Join-Path $project 'START_BROWSER_DIAGNOSTIC.cmd') -Destination (Join-Path $stage 'START_BROWSER_DIAGNOSTIC.cmd') -Force
    Copy-Item -LiteralPath (Join-Path $project 'branding\HiJackLive.ico') -Destination (Join-Path $stage 'HiJackLive.ico') -Force
    if (-not (Test-Path -LiteralPath (Join-Path $stage 'modules\hj_players\module.json'))) {
        throw 'Players module was not packaged.'
    }
    # Run the actual packaged EXE in headless test mode before switching the
    # published folder. This catches missing bundled modules and assets.
    # GUI executables launched with PowerShell's call operator can return before
    # the process exits; deleting the staging directory then corrupts the build.
    # Start-Process -Wait must be used to verify the ACTUAL exit code.
    Write-Host '[RUN] Verify complete onedir package' -ForegroundColor Cyan
    $testRun = Start-Process -FilePath (Join-Path $stage 'HiJackLive.exe') -ArgumentList @('--self-test') -WorkingDirectory $stage -PassThru -ErrorAction Stop
    if (-not $testRun.WaitForExit(45000)) {
        try { $testRun.Kill() } catch { }
        throw 'Packaged EXE self-test timed out after 45 seconds. Inspect launcher.log before running the build.'
    }
    if ($testRun.ExitCode -ne 0) { throw ('Packaged self-test failed with exit code ' + $testRun.ExitCode) }

    if (Test-Path -LiteralPath $ready) {
        $previous = Join-Path $dist ('HI_JACK_LIVE_PREVIOUS_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
        Move-Item -LiteralPath $ready -Destination $previous
        Write-Host ('Previous build saved at: ' + $previous)
    }
    Move-Item -LiteralPath $stage -Destination $ready

    $zip = Join-Path $dist 'HI_JACK_LIVE_WINDOWS11_READY.zip'
    Compress-Archive -Path (Join-Path $ready '*') -DestinationPath $zip -Force
    if (-not (Test-Path -LiteralPath $zip)) { throw 'Ready ZIP was not created.' }

    Write-Host ''
    Write-Host 'BUILD SUCCESS!' -ForegroundColor Green
    Write-Host ('EXE: ' + (Join-Path $ready 'HiJackLive.exe')) -ForegroundColor Green
    Write-Host ('Portable ZIP: ' + $zip) -ForegroundColor Green
    Write-Host 'IMPORTANT: Keep modules and _internal folders next to HiJackLive.exe.'
    Write-Host 'Only dist\HI_JACK_LIVE is a published build. .build-win11 is temporary.'
    Write-Host 'The app data is stored separately under LOCALAPPDATA\HiJackLive.'
    $success = $true
} catch {
    Write-Host ''
    Write-Host ('BUILD FAILED: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('The log is here: ' + $log) -ForegroundColor Yellow
} finally {
    if ($transcriptStarted) { Stop-Transcript | Out-Null }
}
if ($success) {
    Start-Process explorer.exe -ArgumentList ('"' + (Join-Path $project 'dist\HI_JACK_LIVE') + '"')
    exit 0
} else { exit 1 }
