"""Run Rulemancer with one command:

    uv run python run.py [port]

Serves the API and the frontend from ONE process (frontend/ is mounted as
static files on the FastAPI app) and opens your browser once it's up. Default
port 8000; pass another as the first argument. Set RULESMANCER_NO_BROWSER=1 to
skip the auto-open (useful for scripts/tests).

Startup loads the vector store, so the first page load waits a few seconds for
/health to flip ready -- that's normal.
"""

import os
import sys
import threading
import time
import webbrowser

import uvicorn

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
URL = f"http://127.0.0.1:{PORT}"


def _open_browser() -> None:
    time.sleep(1.5)  # requests during startup queue until the store is loaded
    webbrowser.open(URL)


if __name__ == "__main__":
    print(f"Rulesmancer -> {URL}   (API docs: {URL}/docs)")
    if not os.environ.get("RULESMANCER_NO_BROWSER"):
        threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run("rulesagent.api.main:app", host="127.0.0.1", port=PORT)
