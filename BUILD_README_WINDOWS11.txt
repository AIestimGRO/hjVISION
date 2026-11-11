HI, JACK LIVE - WINDOWS 11 BUILD v0.3.4

1. Extract the whole ZIP into a NEW folder; do not run .cmd inside ZIP.
2. Run BUILD_EXE_WINDOWS11.cmd. First build needs internet.
3. Upon BUILD SUCCESS, open dist\HI_JACK_LIVE\HiJackLive.exe.
4. Default interface: isolated Microsoft Edge --app window without tabs.
5. For comparison with the old frozen WebView2: START_WEBVIEW2_TEST.cmd.
6. Open source version in a normal browser: START_BROWSER_DIAGNOSTIC.cmd.
7. Launch diagnostics folder: OPEN_DIAGNOSTICS.cmd.

If the build fails: BUILD_WINDOWS11_LOG.txt in project root.
If the app freezes: %LOCALAPPDATA%\HiJackLive\production\launcher.log.
KEEP modules and _internal next to the EXE. DO NOT remove LOCALAPPDATA data.

The PyInstaller absolute --add-data path hotfix from v0.3.3 is preserved.
This archive is a build kit, not a precompiled EXE.
Windows 11 GUI stability still needs validation on the target PC.
