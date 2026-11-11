v0.3.4 Windows 11 Edge app compatibility patch

Underlying server and OBS Browser Source URLs are unchanged: http://127.0.0.1:8765
New default frontend: Microsoft Edge --app (separate Windows control window).
Legacy pywebview/WebView2 can be run with: HiJackLive.exe --webview2
This avoids forcing GPU off in normal operation.
Server WebSocket broadcasts now happen in parallel with 1.5 s total timeout,
instead of 1.5 s multiplied by each blocked OBS consumer.
Diagnostics still write to LOCALAPPDATA\HiJackLive\production\launcher.log.
Package contains source and builder, NOT a Windows executable.
