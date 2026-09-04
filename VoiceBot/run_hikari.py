"""Start and supervise the Hikari backend and frontend with one command."""
from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


def command_path(name: str) -> str | None:
    return shutil.which(name) or shutil.which(f"{name}.cmd") or shutil.which(f"{name}.exe")


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def preflight(require_frontend_tools: bool = False) -> tuple[Path, str | None]:
    python = VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)
    probe = "import importlib.util,sys; names=('fastapi','uvicorn','psutil','ChatTTS','faster_whisper'); sys.exit(0 if all(importlib.util.find_spec(n) for n in names) else 1)"
    check = subprocess.run([str(python), "-c", probe], cwd=ROOT)
    if check.returncode:
        raise RuntimeError("Python packages are incomplete. Run: .venv\\Scripts\\python.exe -m pip install -r requirements.txt")
    npm = command_path("npm")
    if require_frontend_tools and not npm:
        raise RuntimeError("Development mode needs Node.js/npm. Install Node.js 20 or newer.")
    if require_frontend_tools and not (FRONTEND / "node_modules" / "vite").exists():
        raise RuntimeError("Frontend packages are missing. Run: cd frontend; npm install")
    if not (FRONTEND / "dist" / "index.html").exists():
        raise RuntimeError("Compiled frontend is missing. Run npm run build once in the frontend folder.")
    return python, npm


def wait_for_backend(process: subprocess.Popen, timeout: int) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Backend exited during startup with code {process.returncode}.")
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(1)
    raise RuntimeError(f"Backend did not become ready within {timeout} seconds.")


def stop_tree(process: subprocess.Popen | None) -> None:
    if not process or process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=5)
    except (subprocess.TimeoutExpired, OSError):
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
        else:
            process.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Hikari backend and frontend together.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the dashboard automatically.")
    parser.add_argument("--skip-models", action="store_true", help="Start in text-only test mode without loading AI models.")
    parser.add_argument("--dev", action="store_true", help="Run the Vite development server as a second process.")
    parser.add_argument("--check", action="store_true", help="Validate prerequisites without starting servers.")
    parser.add_argument("--backend-timeout", type=int, default=420, help="Seconds allowed for first model startup.")
    args = parser.parse_args()
    backend = frontend = None
    try:
        python, npm = preflight(args.dev)
        if args.check:
            print("Hikari preflight passed: Python, voice packages and the compiled dashboard are ready.")
            return 0
        if Path(sys.executable).resolve() != python.resolve():
            os.execv(str(python), [str(python), str(Path(__file__).resolve()), *sys.argv[1:]])
        ports = (8000, 5173) if args.dev else (8000,)
        busy = [str(port) for port in ports if not port_is_free(port)]
        if busy:
            raise RuntimeError(f"Port(s) {', '.join(busy)} are already in use. Stop the existing Hikari run first.")
        environment = os.environ.copy()
        if args.skip_models:
            environment["HIKARI_SKIP_MODELS"] = "true"
        if not args.dev:
            os.environ.update(environment)
            def announce_ready():
                deadline = time.monotonic() + args.backend_timeout
                while time.monotonic() < deadline:
                    try:
                        with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2) as response:
                            if response.status == 200:
                                print("\nHikari is ready: http://localhost:8000")
                                print("Monitor: open Hikari and select Monitor in the sidebar.")
                                print("Press Ctrl+C once to stop Hikari.\n")
                                if not args.no_browser:
                                    webbrowser.open("http://localhost:8000")
                                return
                    except (urllib.error.URLError, TimeoutError):
                        time.sleep(1)
            threading.Thread(target=announce_ready, daemon=True).start()
            print("Starting Hikari. First model load can take several minutes...")
            import uvicorn
            uvicorn.run("api.server:app", host="127.0.0.1", port=8000, reload=False)
            return 0
        # Share the console group so one Ctrl+C reaches the supervisor and both children.
        creationflags = 0
        print("Starting Hikari backend. First model load can take several minutes...")
        backend = subprocess.Popen(
            [str(python), "-m", "uvicorn", "api.server:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=ROOT, env=environment, creationflags=creationflags,
        )
        wait_for_backend(backend, args.backend_timeout)
        app_url = "http://localhost:8000"
        if args.dev:
            print("Starting Hikari development dashboard...")
            frontend = subprocess.Popen(
                [npm, "run", "dev", "--", "--host", "127.0.0.1"],
                cwd=FRONTEND, env=environment, creationflags=creationflags,
            )
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and frontend.poll() is None:
                try:
                    with urllib.request.urlopen("http://127.0.0.1:5173", timeout=2) as response:
                        if response.status == 200:
                            app_url = "http://localhost:5173"
                            break
                except (urllib.error.URLError, TimeoutError):
                    time.sleep(.5)
            else:
                raise RuntimeError("Frontend did not become ready.")
        print(f"\nHikari is ready: {app_url}")
        print("Monitor: open Hikari and select Monitor in the sidebar.")
        print("Press Ctrl+C once to stop both services.\n")
        if not args.no_browser:
            webbrowser.open(app_url)
        while backend.poll() is None and (frontend is None or frontend.poll() is None):
            time.sleep(.5)
        failed = "backend" if backend.poll() is not None else "frontend"
        process = backend if failed == "backend" else frontend
        raise RuntimeError(f"The {failed} stopped unexpectedly with code {process.returncode}.")
    except KeyboardInterrupt:
        print("\nStopping Hikari...")
        return 0
    except RuntimeError as exc:
        print(f"\nCannot start Hikari: {exc}", file=sys.stderr)
        return 1
    finally:
        stop_tree(frontend)
        stop_tree(backend)


if __name__ == "__main__":
    raise SystemExit(main())
