"""`make ollama-up` (run by `make demo`, `make demo-up` and `make demo-reset`): start `ollama serve`
when nothing answers at OLLAMA_URL, so a rebooted laptop gets the same setup.

Started in its own session (it outlives `make demo-up` and its Ctrl-C), with the models kept loaded
(OLLAMA_KEEP_ALIVE=-1; the client asks for that on every request too) and Ollama's cloud features
off (OLLAMA_NO_CLOUD=1, no remote inference or web search). Log: data/generated/logs/ollama.log.
An Ollama that is already running is left as it is.

    uv run python -m scripts.demo.ollama_up
"""

import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from app.core.settings import get_settings

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "data" / "generated" / "logs" / "ollama.log"
SERVER_ENV = {"OLLAMA_KEEP_ALIVE": "-1", "OLLAMA_NO_CLOUD": "1"}


def version(url: str) -> str | None:
    try:
        return httpx.get(f"{url}/api/version", timeout=2).json()["version"]
    except httpx.HTTPError:
        return None


def main() -> None:
    url = get_settings().ollama_url
    running = version(url)
    if running:
        print(f"ollama: {running} already running at {url}")
        return
    binary = shutil.which("ollama")
    if binary is None:
        raise SystemExit("ollama: not installed (SETUP.md Part G)")
    address = urlsplit(url)
    env = dict(os.environ, **SERVER_ENV, OLLAMA_HOST=f"{address.hostname}:{address.port or 11434}")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as log:
        subprocess.Popen(
            [binary, "serve"],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    for _ in range(60):
        if started := version(url):
            settings = " ".join(f"{k}={v}" for k, v in SERVER_ENV.items())
            print(f"ollama: started {started} at {url} ({settings}); log {LOG.relative_to(ROOT)}")
            return
        time.sleep(0.5)
    raise SystemExit(f"ollama: did not answer at {url} within 30 s; see {LOG.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
