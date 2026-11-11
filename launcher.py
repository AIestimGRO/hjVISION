"""HI, JACK LIVE desktop launcher for Windows 11.

The local HTTP server powers OBS Browser Sources and is *not* an internet VPS.
The operator gets an isolated Microsoft Edge --app window by default.
The legacy WebView2 bridge is opt-in with --webview2 for diagnostics.
All data and logs stay outside the updateable modules folder.
"""
from __future__ import annotations

import argparse
import logging
import faulthandler
import os
import socket
import shutil
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import webbrowser
import urllib.request
from pathlib import Path
from fastapi import Request

LOG = logging.getLogger("hijack.desktop")


def app_directory() -> Path:
    """External modules sit NEXT TO the EXE, not in PyInstaller's temp folder."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def user_data_directory(staging: bool) -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "HiJackLive"
    return base / ("staging" if staging else "production")


def prepare_logging(data_dir: Path) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "launcher.log"
    # A --windowed PyInstaller EXE has sys.stdout/sys.stderr == None.  Libraries
    # must never try to call .isatty() on None (the reported Uvicorn failure).
    if sys.stdout is None or sys.stderr is None:
        logfile = open(path, "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = logfile
        if sys.stderr is None:
            sys.stderr = logfile
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(path, encoding="utf-8")],
        force=True,
    )
    return path


def show_error(title: str, message: str) -> None:
    """A useful Windows error dialog instead of an unhandled PyInstaller crash."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
            return
        except Exception:
            pass
    print(f"{title}: {message}", file=sys.stderr)


def port_is_busy(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def wait_for_server(url: str, thread: threading.Thread, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not thread.is_alive():
            raise RuntimeError("Local server stopped during startup. Read launcher.log")
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    return
        except (OSError, TimeoutError):
            time.sleep(0.12)
    raise RuntimeError("Local server did not become ready. Read launcher.log")


def self_test(module_root: Path) -> None:
    """Headless smoke check; MUST NOT alter the operator's production data."""
    if not (module_root / "hj_players" / "module.json").is_file():
        raise RuntimeError("Missing modules/hj_players/module.json next to HiJackLive.exe")
    if not (module_root / "hj_effects" / "module.json").is_file():
        raise RuntimeError("Missing modules/hj_effects/module.json next to HiJackLive.exe")
    if sys.platform == "win32":
        # Verify that the packaged Windows runtime contains the native window
        # bridge and pythonnet before declaring the EXE build successful.
        import webview  # noqa: F401
        import clr      # noqa: F401
        import psutil   # noqa: F401
    with tempfile.TemporaryDirectory(prefix="hijack-preflight-") as tmp:
        # app.main has a legacy module-level ASGI app for CLI compatibility.
        # Isolate even THAT import so the build's preflight never migrates or
        # writes the real production SQLite DB or themes directory.
        old_data = os.environ.get("HJ_DATA_DIR")
        old_theme = os.environ.get("HJ_THEME_DIR")
        os.environ["HJ_DATA_DIR"] = tmp
        os.environ["HJ_THEME_DIR"] = str(Path(tmp) / "themes")
        try:
            from app.main import create_app
            app = create_app(Path(tmp) / "preflight.sqlite3", modules_dir=module_root)
            records = app.state.module_loader.records
            for ident in ("hj.players", "hj.effects"):
                if ident not in records or records[ident].status != "loaded":
                    raise RuntimeError(f"Module failed to load: {ident}: " +
                                       (records[ident].error if ident in records else "not found"))
            paths = {route.path for route in app.routes if hasattr(route, "path")}
            for route in ("/admin", "/modules", "/overlay/players", "/overlay/effects", "/health"):
                if route not in paths:
                    raise RuntimeError("Missing HTTP route: " + route)
        finally:
            if old_data is None: os.environ.pop("HJ_DATA_DIR", None)
            else: os.environ["HJ_DATA_DIR"] = old_data
            if old_theme is None: os.environ.pop("HJ_THEME_DIR", None)
            else: os.environ["HJ_THEME_DIR"] = old_theme
    LOG.info("SELF TEST OK: modules and OBS routes are available")


def run_browser_diagnostic(staging: bool) -> None:
    """Troubleshoot WebView2 by running identical frontend in a normal browser.

    A native Windows status dialog keeps the local OBS server alive and gives
    the operator an explicit, reliable Stop action (without a console window).
    """
    import uvicorn
    host, port = "127.0.0.1", 8766 if staging else 8765
    if port_is_busy(host, port):
        raise RuntimeError(f"Port {port} is busy. Close HI, JACK LIVE first.")
    from app.main import create_app
    data_dir = user_data_directory(staging)
    app = create_app(data_dir / "hi-jack.sqlite3", modules_dir=app_directory() / "modules")
    config = uvicorn.Config(app, host=host, port=port, log_config=None,
                            access_log=False, log_level="warning", loop="asyncio",
                            http="h11", ws="websockets")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="HJ diagnostic server", daemon=True)
    thread.start()
    try:
        wait_for_server(f"http://{host}:{port}/health", thread)
        LOG.info("BROWSER_DIAGNOSTIC_BEGIN port=%d", port)
        webbrowser.open(f"http://{host}:{port}/admin")
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(0,
                "Browser diagnostic is running.\n\n"
                "Test adding a player in the browser.\n"
                "Press OK here to STOP the local HI, JACK LIVE server.",
                "HI, JACK LIVE - Browser diagnostic", 0x40)
        else:
            input("Press Enter to stop diagnostic server...")
    finally:
        LOG.info("BROWSER_DIAGNOSTIC_END")
        server.should_exit = True
        thread.join(timeout=12)


def run_desktop(staging: bool, safe_mode: bool = False) -> None:
    import uvicorn

    home = user_data_directory(staging)
    host, port = "127.0.0.1", (8766 if staging else 8765)
    if port_is_busy(host, port):
        raise RuntimeError(
            f"Port {port} is already in use. HI, JACK LIVE may already be running.\n"
            "Close its window (or stop the other application) before starting again."
        )

    from app.main import create_app
    application = create_app(home / "hi-jack.sqlite3", modules_dir=app_directory() / "modules")
    records = application.state.module_loader.records
    if records.get("hj.players") is None or records["hj.players"].status != "loaded":
        raise RuntimeError("Players module is missing or broken. Check modules/hj_players and launcher.log")

    # Critical Windows --windowed fix: never use Uvicorn's default console
    # formatter. It assumes a non-None stdout/stderr and can crash at launch.
    config = uvicorn.Config(
        application,
        host=host,
        port=port,
        log_level="warning",
        log_config=None,
        access_log=False,
        loop="asyncio",
        http="h11",
        ws="websockets",
    )
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, name="HJ local server", daemon=True)
    server_thread.start()
    try:
        wait_for_server(f"http://{host}:{port}/health", server_thread)
        LOG.info("Local OBS server ready at http://%s:%d", host, port)
        watchdog_stop = threading.Event()
        def watch_ui():
            announced=False
            while not watchdog_stop.wait(4):
                last=application.state.ui_heartbeat_time
                if last and time.monotonic()-last > 15:
                    if not announced:
                        LOG.warning('UI_HEARTBEAT_MISSED 15s: native window may be frozen or page hidden')
                        with open(home/'hang-thread-dump.log','a',encoding='utf-8') as dump:
                            dump.write('\n--- UI heartbeat timeout ---\n')
                            faulthandler.dump_traceback(file=dump,all_threads=True)
                        announced=True
                else: announced=False
        watchdog_thread=threading.Thread(target=watch_ui, name='HJ UI watchdog', daemon=True)
        watchdog_thread.start()

        # WebView2 provides a real Windows window, not an external browser tab.
        # WebView2 is normally present on Windows 11; if missing, show a clear error.
        try:
            import webview
        except Exception as exc:
            raise RuntimeError("Desktop window components are missing (pywebview). "
                               "Rebuild with the updated Windows 11 builder.") from exc

        class DesktopControl:
            def __init__(self):
                self.window = None

            def quit(self):
                """Only the embedded desktop window can call this JS bridge."""
                if self.window:
                    threading.Thread(target=self.window.destroy, daemon=True).start()
                return {"ok": True}

        # Safe mode disables GPU composition only for the desktop control panel;
        # OBS Browser Sources remain independent. No user data is modified.
        if safe_mode:
            existing=os.environ.get('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS','')
            os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS']=(existing+' --disable-gpu --disable-gpu-compositing').strip()
            LOG.warning('SAFE MODE enabled: WebView2 GPU acceleration disabled')
        # Set explicit taskbar identity so Explorer picks up the branded EXE icon.
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("HiJack.Live.Windows11")
            except Exception:
                LOG.warning("Unable to set Windows taskbar identity", exc_info=True)
        control = DesktopControl()
        window = webview.create_window(
            "HI, JACK LIVE  |  OBS Studio Control",
            f"http://{host}:{port}/admin",
            width=1480,
            height=930,
            min_size=(980, 640),
            resizable=True,
            confirm_close=True,
            js_api=control,
            text_select=True,
        )
        control.window = window
        LOG.info("Opening native WebView2 desktop window")
        webview.start(gui="edgechromium", debug=False)
        LOG.info("Desktop window closed by operator")
    finally:
        if 'watchdog_stop' in locals():watchdog_stop.set()
        server.should_exit = True
        server_thread.join(timeout=12)
        LOG.info("HI, JACK LIVE exited (server stopped=%s)", not server_thread.is_alive())



def find_edge_executable() -> Path | None:
    """Find the installed full Microsoft Edge browser, not WebView2 Runtime.

    Edge ships with Windows 11.  Do not execute an arbitrary browser from the
    user's project directory or use ShellExecute on an unvalidated URL.
    """
    candidates = []
    for variable in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
        root = os.environ.get(variable)
        if root:
            candidates.append(Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
    path_candidate = shutil.which("msedge.exe") or shutil.which("msedge")
    if path_candidate:
        candidates.append(Path(path_candidate))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None



def edge_profile_process_active(browser_profile: Path) -> bool:
    """Check Edge's *actual* browser process, not only Popen's starter PID.

    On Windows Edge may hand an --app window to another process and the PID
    returned by Popen may exit even while the real browser window is open.
    Only processes advertising this exact isolated profile count.
    """
    import psutil

    def normalized(value: str) -> str:
        return os.path.normpath(value.strip('"')).replace('\\', '/').casefold()

    profile = normalized(str(browser_profile))
    for process in psutil.process_iter(['name', 'cmdline']):
        try:
            info = process.info
            if str(info.get('name') or '').lower() != 'msedge.exe':
                continue
            for arg in info.get('cmdline') or ():
                if arg.lower().startswith('--user-data-dir=') and normalized(arg.split('=', 1)[1]) == profile:
                    return True
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
    return False


def edge_session_should_exit(now: float, launched_at: float,
                             last_panel_heartbeat: float, edge_process_alive: bool) -> bool:
    """Do not kill the backend when the Edge launcher merely hands off its PID.

    A panel which was open may be temporarily busy, throttled or frozen, so
    allow a generous grace period before orphan cleanup. A launch that never
    established any panel connection is an error after 30 seconds.
    """
    if edge_process_alive:
        return False
    if last_panel_heartbeat:
        return now - last_panel_heartbeat > 180
    return now - launched_at > 30


def configure_edge_control_routes(application, shutdown_event: threading.Event) -> None:
    """Expose an explicit, nonce-verified Exit button for isolated Edge mode.

    This is absent in normal browser diagnostics and OBS overlays. The nonce
    is generated anew for each local process; foreign webpages cannot read
    it via fetch because FastAPI does not grant cross-origin access.
    """
    from fastapi import HTTPException

    nonce = secrets.token_urlsafe(32)

    @application.get('/api/desktop/edge-session')
    async def edge_session(request: Request):
        if request.client and request.client.host not in ('127.0.0.1', '::1'):
            raise HTTPException(403, 'Local access only')
        return {'edge_app': True, 'quit_token': nonce}

    @application.post('/api/desktop/edge-quit')
    async def edge_quit(request: Request):
        if request.client and request.client.host not in ('127.0.0.1', '::1'):
            raise HTTPException(403, 'Local access only')
        if request.headers.get('x-hj-desktop-token') != nonce:
            raise HTTPException(403, 'Invalid desktop session')
        origin = request.headers.get('origin')
        if origin and origin != str(request.base_url).rstrip('/'):
            raise HTTPException(403, 'Invalid origin')
        LOG.info('EDGE_APP_MODE operator requested graceful shutdown')
        shutdown_event.set()
        return {'ok': True}


def run_edge_desktop(staging: bool) -> None:
    """Reliable app-style Windows control window without pywebview/pythonnet.

    Edge runs in its own isolated browser profile and ``--app`` window (no tabs).
    The local HTTP/OBS backend still belongs to HiJackLive.exe.  It must NOT
    stop merely because Edge hands the UI window to a different PID. Users may
    shut down explicitly; orphan cleanup is deferred. No user-data changes.
    """
    import uvicorn

    edge = find_edge_executable()
    if not edge:
        raise RuntimeError(
            "Microsoft Edge browser was not found. Install/repair Microsoft Edge "
            "or start --browser-diagnostic for the ordinary-browser test."
        )
    home = user_data_directory(staging)
    host, port = "127.0.0.1", (8766 if staging else 8765)
    if port_is_busy(host, port):
        raise RuntimeError(f"Port {port} is busy. Close the previous HiJackLive instance first.")

    from app.main import create_app
    application = create_app(home / "hi-jack.sqlite3", modules_dir=app_directory() / "modules")
    records = application.state.module_loader.records
    if records.get("hj.players") is None or records["hj.players"].status != "loaded":
        raise RuntimeError("Players module is missing. Check modules/hj_players and launcher.log")

    config = uvicorn.Config(
        application, host=host, port=port, log_level="warning", log_config=None,
        access_log=False, loop="asyncio", http="h11", ws="websockets",
    )
    server = uvicorn.Server(config)
    shutdown_event = threading.Event()
    configure_edge_control_routes(application, shutdown_event)
    thread = threading.Thread(target=server.run, name="HJ local OBS server", daemon=True)
    thread.start()
    browser_process = None
    watchdog_stop = threading.Event()
    try:
        wait_for_server(f"http://{host}:{port}/health", thread)
        LOG.info("EDGE_APP_MODE server ready port=%s browser=%s", port, edge)

        # Never pass --disable-gpu in normal operation. The old release forced
        # software composition, which is only a diagnostic WebView2 workaround.
        browser_profile = home / "edge-control-profile"
        browser_profile.mkdir(parents=True, exist_ok=True)
        command = [
            str(edge), f"--user-data-dir={browser_profile}",
            "--no-first-run", "--no-default-browser-check",
            "--disable-extensions", "--disable-background-mode",
            f"--app=http://{host}:{port}/admin",
        ]
        # Only local, fixed-origin UI URL; browser profile and user SQLite are
        # stored outside the updateable executable/modules directory.
        browser_process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        LOG.info("EDGE_APP_MODE opened pid=%s", browser_process.pid)
        launched_at = time.monotonic()
        warned = False
        handed_off = False
        while not shutdown_event.is_set():
            if not thread.is_alive():
                raise RuntimeError("Local OBS server stopped unexpectedly. Check launcher.log")
            starter_alive = browser_process.poll() is None
            # Edge can fork/hand off to an already running process and exit the
            # starter PID. An app window can still be on screen at that point.
            profile_alive = edge_profile_process_active(browser_profile) if not starter_alive else True
            browser_alive = starter_alive or profile_alive
            if not starter_alive and not handed_off:
                LOG.warning('EDGE_STARTER_EXIT pid=%s exit_code=%s; preserving backend while checking active Edge/profile/heartbeat',
                            browser_process.pid, browser_process.returncode)
                handed_off = True
            now = time.monotonic()
            last = application.state.ui_heartbeat_time
            if edge_session_should_exit(now, launched_at, last, browser_alive):
                if not last:
                    raise RuntimeError(
                        'Edge window did not connect to the local panel within 30 seconds. '
                        'Check antivirus/Edge policies and launcher.log.'
                    )
                LOG.info('EDGE_APP_MODE panel has been absent for 180s and no Edge process remains; stopping backend')
                break
            if last and now - last > 15:
                if not warned:
                    LOG.warning('EDGE_APP_MODE UI_HEARTBEAT_MISSED >15s; server stays running to protect OBS sources')
                    warned = True
            else:
                warned = False
            watchdog_stop.wait(1)
        LOG.info('EDGE_APP_MODE shutdown requested=%s starter_exit_code=%s',
                 shutdown_event.is_set(), browser_process.poll())
    finally:
        watchdog_stop.set()
        if browser_process is not None and browser_process.poll() is None and shutdown_event.is_set():
            browser_process.terminate()
            try:
                browser_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                browser_process.kill()
        server.should_exit = True
        thread.join(timeout=12)
        LOG.info("EDGE_APP_MODE stopped (server_stopped=%s)", not thread.is_alive())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staging", action="store_true")
    parser.add_argument("--self-test", action="store_true", help="Headless packaged app smoke test")
    parser.add_argument("--browser-diagnostic", action="store_true", help="Open control panel in normal browser for WebView2 isolation")
    parser.add_argument("--gpu-mode", action="store_true", help="Enable GPU in desktop control window after testing")
    parser.add_argument("--safe-mode", action="store_true", help="Compatibility mode: open the Edge app window")
    parser.add_argument("--webview2", action="store_true", help="Legacy pywebview/WebView2 window (diagnostic only)")
    args = parser.parse_args()

    home = user_data_directory(args.staging)
    log_file = prepare_logging(home)
    # Module code is replaceable; user data, themes, keys and DB are not.
    os.environ["HJ_DATA_DIR"] = str(home)
    os.environ["HJ_MODULES_DIR"] = str(app_directory() / "modules")
    os.environ["HJ_THEME_DIR"] = str(home.parent / "themes")
    try:
        if args.self_test:
            self_test(app_directory() / "modules")
        elif args.browser_diagnostic:
            run_browser_diagnostic(args.staging)
        elif args.webview2 or args.gpu_mode:
            # Legacy control is opt-in only: this embedded window freezes on
            # some Windows 11 systems despite a healthy local HTTP server.
            run_desktop(args.staging, safe_mode=(args.safe_mode or not args.gpu_mode))
        else:
            # Default: isolated Edge --app window.  It is still a separate
            # Windows application window, without the unstable .NET GUI bridge.
            run_edge_desktop(args.staging)
        return 0
    except Exception as exc:
        LOG.error("Startup failed: %s\n%s", exc, traceback.format_exc())
        show_error(
            "HI, JACK LIVE - launch error",
            f"{exc}\n\nDiagnostic log:\n{log_file}\n\n"
            "The local OBS server was stopped. No files were deleted.",
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
