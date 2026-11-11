from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]


def test_packaged_icon_is_valid_multisize_ico():
    ico = ROOT / "branding" / "HiJackLive.ico"
    assert ico.exists() and ico.stat().st_size > 1000
    with ico.open("rb") as fh:
        reserved, image_type, count = struct.unpack("<HHH", fh.read(6))
        assert reserved == 0 and image_type == 1 and count >= 6


def test_fallback_browser_and_software_desktop_options():
    source = (ROOT / "launcher.py").read_text(encoding="utf-8")
    assert '"--browser-diagnostic"' in source
    assert '"--gpu-mode"' in source
    assert 'run_browser_diagnostic(args.staging)' in source
    assert "args.safe_mode or not args.gpu_mode" in source
    assert "run_edge_desktop(args.staging)" in source
    assert '"--webview2"' in source
    assert (ROOT / "START_BROWSER_DIAGNOSTIC.cmd").exists()


def test_modal_does_not_autofocus_in_native_webview():
    html=(ROOT / "modules/hj_players/frontend/admin.html").read_text(encoding="utf-8")
    js=(ROOT / "modules/hj_players/frontend/admin.js").read_text(encoding="utf-8")
    assert 'autofocus' not in html
    assert "$('formName').focus()" not in js


def test_builder_invokes_pyinstaller_module_before_options():
    source = (ROOT / "scripts" / "BUILD_WINDOWS11.ps1").read_text(encoding="utf-8-sig")
    block = source.split("$buildArgs = @(", 1)[1].split("    )", 1)[0]
    assert block.index("'-m','PyInstaller'") < block.index("'--distpath'")
    assert block.count("'-m','PyInstaller'") == 1
    assert 'WaitForExit(45000)' in source
