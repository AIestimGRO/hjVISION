@echo off
setlocal EnableExtensions
echo.
echo HI, JACK LIVE - LOCAL SERVER CHECK
echo Checking http://127.0.0.1:8765/health ...
echo.
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; try { $r=Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 4; if(-not $r.ok) { throw 'Health returned ok=false' }; Write-Host 'SERVER HEALTHY: localhost:8765' -ForegroundColor Green; Write-Host ('Loaded modules: ' + $r.modules_loaded); exit 0 } catch { Write-Host ('SERVER UNAVAILABLE: ' + $_.Exception.Message) -ForegroundColor Red; exit 1 }"
if errorlevel 1 (
  echo.
  echo Log: %%LOCALAPPDATA%%\HiJackLive\production\launcher.log
  echo Run OPEN_DIAGNOSTICS.cmd to inspect the log.
)
echo.
pause
