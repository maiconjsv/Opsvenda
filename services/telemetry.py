"""Non-invasive, best-effort usage telemetry.

Reports only an anonymous per-install id, the app version, and counters of
which features/screens were used (one counter per Flask endpoint hit) -
never product names, prices, sale amounts, customer data or anything else
from the business database. OpsVenda is normally used offline, so every
operation here is wrapped to fail silently: a network error never surfaces
to the caller, never blocks startup, and never blocks a request. Counters
that couldn't be sent just stay on disk and go out with the next attempt.

Can be turned off entirely with OPSVENDA_TELEMETRY=0.
"""

import json
import os
import threading
import uuid
from pathlib import Path

TELEMETRY_URL = os.environ.get(
    "OPSVENDA_TELEMETRY_URL", "https://bookcase.montiqtech.com.br/api/opsvenda/ping"
)
TELEMETRY_KEY = os.environ.get("OPSVENDA_TELEMETRY_KEY", "opsvenda-telemetry-2026")
TELEMETRY_TIMEOUT = 3
INSTALL_ID_FILENAME = "telemetry_id.txt"
COUNTERS_FILENAME = "telemetry_counters.json"

_lock = threading.Lock()


def is_enabled() -> bool:
    return os.environ.get("OPSVENDA_TELEMETRY", "1") != "0"


def get_or_create_install_id(instance_dir: str) -> str:
    path = Path(instance_dir) / INSTALL_ID_FILENAME
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    Path(instance_dir).mkdir(parents=True, exist_ok=True)
    install_id = uuid.uuid4().hex
    path.write_text(install_id, encoding="utf-8")
    return install_id


def _counters_path(instance_dir: str) -> Path:
    return Path(instance_dir) / COUNTERS_FILENAME


def _read_counters(instance_dir: str) -> dict:
    path = _counters_path(instance_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def _write_counters(instance_dir: str, counters: dict) -> None:
    _counters_path(instance_dir).write_text(json.dumps(counters), encoding="utf-8")


def bump(instance_dir: str, feature: str) -> None:
    """Increment the local usage counter for `feature`. Never raises."""
    if not is_enabled():
        return
    try:
        with _lock:
            counters = _read_counters(instance_dir)
            counters[feature] = counters.get(feature, 0) + 1
            _write_counters(instance_dir, counters)
    except Exception:
        pass


def send_ping_async(instance_dir: str, version: str) -> None:
    """Fire-and-forget: reports the install id, version, and the counters
    accumulated since the last successful send, in a background thread.
    """
    if not is_enabled():
        return

    def _worker():
        try:
            import requests

            install_id = get_or_create_install_id(instance_dir)
            with _lock:
                counters = _read_counters(instance_dir)

            resp = requests.post(
                TELEMETRY_URL,
                json={"install_id": install_id, "version": version, "counters": counters},
                timeout=TELEMETRY_TIMEOUT,
                headers={"X-OpsVenda-Key": TELEMETRY_KEY},
            )
            if resp.ok:
                # Only subtract what was actually sent, in case new hits came
                # in concurrently while the request was in flight.
                with _lock:
                    current = _read_counters(instance_dir)
                    for key, value in counters.items():
                        if key in current:
                            current[key] = max(0, current[key] - value)
                    _write_counters(instance_dir, current)
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()
