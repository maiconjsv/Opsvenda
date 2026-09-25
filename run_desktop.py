"""Desktop launcher: opens a native window (pywebview, WebView2/Chromium on
Windows, Qt WebEngine on Linux) around the Flask app.

By default (no --url) the backend is started in-process in a background
thread via `waitress`, and the app's per-user data directory is set to an
OS-appropriate writable location (no admin rights, no Docker required) --
this is how the packaged standalone distribution runs.

Passing --url points the window at an already-running backend instead
(e.g. `flask run`, or a Docker container's published port) without
starting an embedded server -- used for local development and by the
Docker-based install.ps1/install.sh.
"""

import argparse
import os
import sys
import threading
import time
from pathlib import Path

# The Windows embeddable Python distribution uses a `._pth` file that fully
# replaces sys.path -- unlike a normal install, it does NOT automatically add
# the launched script's own directory. Without this, `from app import
# create_app` below fails to find the sibling `app.py` module when run from
# the packaged bundle (python.exe/pythonw.exe run_desktop.py).
sys.path.insert(0, str(Path(__file__).resolve().parent))


def default_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "OpsVenda"


def configure_webview2_runtime() -> None:
    """Point pywebview at a bundled WebView2 Fixed Version Runtime, if present
    alongside this script (see packaging/build_windows.ps1). Falls back to
    the system-installed runtime when the bundled folder doesn't exist.
    """
    if sys.platform != "win32":
        return
    # sys.executable is <install_dir>/python/pythonw.exe; webview2/ is bundled
    # as a sibling of python/, directly under <install_dir> (see build_windows.ps1).
    bundled_runtime = Path(sys.executable).resolve().parent.parent / "webview2"
    if bundled_runtime.is_dir():
        os.environ["WEBVIEW2_BROWSER_EXECUTABLE_FOLDER"] = str(bundled_runtime)


def start_embedded_backend() -> str:
    """Start the Flask app in-process via waitress and return its base URL."""
    os.environ.setdefault("OPSVENDA_DATA_DIR", str(default_data_dir()))

    from waitress import create_server

    from app import create_app

    application = create_app()
    server = create_server(application, host="127.0.0.1", port=0)
    threading.Thread(target=server.run, daemon=True).start()
    return f"http://127.0.0.1:{server.effective_port}"


def wait_for_backend(url: str, timeout: int) -> bool:
    import requests

    deadline = time.time() + timeout
    health_url = url.rstrip("/") + "/health"
    while time.time() < deadline:
        try:
            resp = requests.get(health_url, timeout=2)
            if resp.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    return False


def main():
    parser = argparse.ArgumentParser(description="OpsVenda - launcher desktop")
    parser.add_argument("--url", default=None, help="aponta para um backend já rodando (modo dev/Docker)")
    parser.add_argument("--timeout", type=int, default=60, help="segundos esperando o backend subir")
    args = parser.parse_args()

    configure_webview2_runtime()
    import webview

    if args.url:
        url = args.url
    else:
        url = start_embedded_backend()

    if not wait_for_backend(url, args.timeout):
        print(
            f"Não foi possível conectar em {url} após {args.timeout}s.",
            file=sys.stderr,
        )
        sys.exit(1)

    webview.create_window("OpsVenda", url, width=1280, height=800, min_size=(960, 600))
    webview.start()


if __name__ == "__main__":
    main()
