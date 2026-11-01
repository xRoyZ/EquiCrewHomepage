#!/usr/bin/env python3
"""Development start: the api (backend/) and the static website (frontend/) together.

    python3 dev.py [--api-port 8000] [--web-port 8080]

Starts `uvicorn app.main:app` in backend/ and `dev_server.py` in frontend/, with
API_BASE_URL (for the website) and FRONTEND_ORIGIN (for the api's CORS) pointing at
each other. Ctrl+C stops both; if one of them exits, the other is stopped too.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
HOST = "127.0.0.1"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start api and website for development.")
    parser.add_argument("--api-port", type=int, default=8000, help="port of the api")
    parser.add_argument("--web-port", type=int, default=8080, help="port of the website")
    return parser.parse_args()


def _spawn(name: str, argv: list[str], cwd: Path, env: dict[str, str]) -> subprocess.Popen:
    print(f"[dev] starting {name}: {' '.join(argv)}  (in {cwd.relative_to(ROOT)}/)")
    kwargs: dict[str, object] = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(argv, cwd=cwd, env=env, **kwargs)


def _stop(processes: dict[str, subprocess.Popen]) -> None:
    for proc in processes.values():
        if proc.poll() is None:
            proc.terminate()
    deadline = time.monotonic() + 5
    for name, proc in processes.items():
        remaining = max(0.1, deadline - time.monotonic())
        try:
            proc.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            print(f"[dev] {name} did not stop in time - killing it")
            proc.kill()
            proc.wait()


def main() -> int:
    args = _parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    api_origin = f"http://{HOST}:{args.api_port}"
    web_origin = f"http://{HOST}:{args.web_port}"

    api_env = dict(os.environ)
    api_env["FRONTEND_ORIGIN"] = web_origin
    api_env["PORT"] = str(args.api_port)

    web_env = dict(os.environ)
    web_env["API_BASE_URL"] = api_origin
    web_env["PORT"] = str(args.web_port)

    processes: dict[str, subprocess.Popen] = {}
    try:
        processes["api"] = _spawn(
            "api",
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                HOST,
                "--port",
                str(args.api_port),
            ],
            BACKEND,
            api_env,
        )
        if (FRONTEND / "dev_server.py").is_file():
            processes["web"] = _spawn("web", [sys.executable, "dev_server.py"], FRONTEND, web_env)
        else:
            print("[dev] frontend/dev_server.py not found - starting the api only")

        print(f"[dev] api:     {api_origin}/api/health")
        if "web" in processes:
            print(f"[dev] website: {web_origin}/")
        print("[dev] press Ctrl+C to stop")

        while True:
            for name, proc in processes.items():
                code = proc.poll()
                if code is not None:
                    print(f"[dev] {name} exited with code {code} - stopping the rest")
                    return code or 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[dev] stopping ...")
        return 0
    except OSError as exc:
        print(f"[dev] could not start a process: {exc}")
        return 1
    finally:
        _stop(processes)


def _on_sigterm(signum: int, frame: object) -> None:
    """Treat SIGTERM like Ctrl+C so both children are stopped too."""
    raise KeyboardInterrupt


if __name__ == "__main__":
    if os.name != "nt":
        signal.signal(signal.SIGTERM, _on_sigterm)
    sys.exit(main())
