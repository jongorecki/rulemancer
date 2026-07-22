"""Run Rulemancer with one command:

    python run.py [port]        (or: uv run python run.py [port])

Serves the API and the frontend from ONE process (frontend/ is mounted as
static files on the FastAPI app) and opens your browser once it's up. Default
port 8000. Set RULESMANCER_NO_BROWSER=1 to skip the auto-open.

Robustness built in:
- Ran with the wrong Python (system install, no uvicorn)? The script re-launches
  itself under the project environment via `uv run`, so `python run.py` just
  works.
- A stale copy of the server already on the port (e.g. started before a code
  update)? It's stopped first and a fresh one starts -- but ONLY if it's a
  python/uvicorn process; anything else holding the port is reported, not
  killed.

Startup loads the vector store, so the first page load waits a few seconds for
/health to flip ready -- that's normal.
"""

import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parent

try:
    import uvicorn
except ModuleNotFoundError:
    # Wrong interpreter (e.g. `python run.py` with the system Python). Re-exec
    # under the project environment. The env flag guards against looping if
    # even the project env lacks uvicorn (deps not installed).
    if os.environ.get("RULESMANCER_REEXEC"):
        sys.exit("uvicorn is still missing inside the project environment -- "
                 "run `uv sync` in the repo, then try again.")
    env = {**os.environ, "RULESMANCER_REEXEC": "1"}
    venv_py = REPO / ".venv" / "Scripts" / "python.exe"  # Windows venv layout
    if shutil.which("uv"):
        cmd = ["uv", "run", "--project", str(REPO), "python", str(REPO / "run.py"), *sys.argv[1:]]
    elif venv_py.exists():
        cmd = [str(venv_py), str(REPO / "run.py"), *sys.argv[1:]]
    else:
        sys.exit("Can't find the project environment. Install uv "
                 "(https://docs.astral.sh/uv/) or create it with `uv sync`.")
    print("(switching to the project environment...)")
    sys.exit(subprocess.call(cmd, env=env))

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
URL = f"http://127.0.0.1:{PORT}"


def _listening_pids(port: int) -> list[int]:
    """PIDs listening on `port` (TCP)."""
    pids: set[int] = set()
    if os.name == "nt":
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
        for line in out.stdout.splitlines():
            parts = line.split()
            # TCP  <local addr>  <foreign addr>  LISTENING  <pid>
            if (len(parts) >= 5 and parts[0] == "TCP" and parts[3] == "LISTENING"
                    and parts[1].endswith(f":{port}")):
                pids.add(int(parts[4]))
    else:
        out = subprocess.run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
                             capture_output=True, text=True)
        if out.returncode == 0:
            pids.update(int(p) for p in out.stdout.split())
    pids.discard(os.getpid())
    return sorted(pids)


def _image_name(pid: int) -> str:
    """Process image name for a PID (Windows), lowercased. '' if unknown."""
    if os.name != "nt":
        try:
            return Path(os.readlink(f"/proc/{pid}/exe")).name.lower()
        except OSError:
            return ""
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True)
    first = (out.stdout.strip().splitlines() or [""])[0]
    return first.split(",")[0].strip('"').lower() if "," in first else ""


def _stop_stale_instances(port: int) -> None:
    """Kill stale copies of OUR server on `port`; refuse to touch anything else.

    A stale instance is the common failure mode after a code update (the old
    process keeps serving old Python). Only python/uvicorn processes qualify --
    if some unrelated app owns the port, say so and exit instead of killing it.
    """
    for pid in _listening_pids(port):
        name = _image_name(pid)
        if "python" in name or "uvicorn" in name or name == "":
            print(f"Stopping stale server on port {port} (PID {pid}"
                  + (f", {name}" if name else "") + ") ...")
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
            else:
                subprocess.run(["kill", "-9", str(pid)], capture_output=True)
        else:
            sys.exit(f"Port {port} is used by '{name}' (PID {pid}) -- that isn't "
                     f"one of ours, so I won't kill it. Pick another port: "
                     f"python run.py {port + 1}")
    if _listening_pids(port):
        time.sleep(0.8)  # give the OS a beat to release the socket


def _open_browser() -> None:
    time.sleep(1.5)  # requests during startup queue until the store is loaded
    webbrowser.open(URL)


if __name__ == "__main__":
    _stop_stale_instances(PORT)
    print(f"Rulemancer -> {URL}   (API docs: {URL}/docs)")
    if not os.environ.get("RULESMANCER_NO_BROWSER"):
        threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run("rulesagent.api.main:app", host="127.0.0.1", port=PORT)
