HI, JACK LIVE v0.3.5 — WINDOWS 11 COMPATIBILITY BUILD

This ZIP contains source and a Windows 11 builder; it is NOT a prebuilt EXE.
OBS local API / overlays: http://127.0.0.1:8765, unchanged.

1. Back up %LOCALAPPDATA%\HiJackLive and your old EXE folder.
2. Unpack this archive into a NEW clean folder.
3. Run BUILD_EXE_WINDOWS11.cmd.
4. After BUILD SUCCESS, run dist\HI_JACK_LIVE\HiJackLive.exe.
5. The controls will open as a dedicated Microsoft Edge --app window without tabs.
   Edge is included with Windows 11. Its full browser is used, not embedded WebView2.
6. For immediate, clean shutdown, click "Завершить программу" in the top-right of the admin panel.
   Closing Edge with X also triggers automatic cleanup, which can be delayed after Edge process hand-off.
7. To compare with the old embedded WebView2, run START_WEBVIEW2_TEST.cmd.
8. To test in your normal browser, run START_BROWSER_DIAGNOSTIC.cmd.
9. CHECK_LOCAL_SERVER.cmd checks whether the local server is running.
10. OPEN_DIAGNOSTICS.cmd opens production logs. Inspect launcher.log if a freeze returns.

No SQLite database, user settings, modules, themes or backups are deleted.
The browser user profile is in LOCALAPPDATA\HiJackLive\production\edge-control-profile.

The Windows window has NOT been tested on the target Windows 11 machine.
Do not use the unverified build for a live OBS broadcast until testing it.

Note (v0.3.5): Edge starter PID may exit while the actual app window stays open; backend is no longer tied to its Popen.poll(). Use the Exit control in the main panel for immediate safe shutdown. Closing the Edge window also triggers idle cleanup if its process has terminated.

IF EDGE SHOWS ERR_CONNECTION_REFUSED:
  - While the app is still open, run CHECK_LOCAL_SERVER.cmd.
  - Then open OPEN_DIAGNOSTICS.cmd and inspect launcher.log.
  - If the server is stopped, check for EDGE_STARTER_EXIT and any startup error.
  - If the server is healthy but the page still fails, close the stale Edge window
    and reopen HiJackLive.exe after ensuring no older version is running.
  - Do not delete LOCALAPPDATA\HiJackLive or your SQLite data folder.
