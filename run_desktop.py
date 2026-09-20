"""Desktop launcher: opens a native window (pywebview, Chromium/WebView2 on
Windows, WebKitGTK on Linux) pointed at the Flask backend running in Docker.

This process does NOT run inside the Docker container - GUI windows don't
work reliably inside containers (no display server on Windows, X11 socket
forwarding needed on Linux). Instead, the installer starts the backend via
`docker compose up -d` and this launcher just waits for it to come up and
then shows it in a window, like a dedicated browser.
"""

import argparse
import sys
import time

import requests
import webview


def wait_for_backend(url: str, timeout: int) -> bool:
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
    parser.add_argument("--url", default="http://localhost:5000")
    parser.add_argument("--timeout", type=int, default=60, help="segundos esperando o backend subir")
    args = parser.parse_args()

    if not wait_for_backend(args.url, args.timeout):
        print(
            f"Não foi possível conectar em {args.url} após {args.timeout}s. "
            "Verifique se o backend (Docker) está rodando.",
            file=sys.stderr,
        )
        sys.exit(1)

    webview.create_window("OpsVenda", args.url, width=1280, height=800, min_size=(960, 600))
    webview.start()


if __name__ == "__main__":
    main()
