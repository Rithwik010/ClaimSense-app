"""`make offline-check`: no stack process talks to anything but the laptop (D-PROC-5). Run it right
after `make demo-reset` with the stack up (`make demo-up`); it runs `make e2e-api` and, while that
runs, records the connections of every stack process:

- on the laptop, with `lsof` about every 0.25 s: the API (port 8000, and the second API the e2e
  check starts on 8001; it also serves the web app), Ollama (port 11434 and its model runner),
  the dev server of `make demo` (port 5173) when it runs, and
  the e2e client, each with its child processes;
- in Docker, about every second: the Postgres and Qdrant containers' socket tables
  (/proc/net/tcp, tcp6, udp, udp6), which also keep connections closed in the last minute.

A remote address that is not the loopback (or, inside a container, its own Docker network) fails
the check. It also checks, inside the running Qdrant container, that its telemetry is off: the
container's environment holds QDRANT__TELEMETRY_DISABLED=true (from docker-compose.yml) and its
latest start-up logged "Telemetry reporting disabled". Sampling can miss a connection opened and
closed between two `lsof` samples on the
laptop; the containers' tables cannot miss one.

    uv run python -m scripts.verify.offline_check
"""

import ipaddress
import json
import subprocess
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORTS = {"API": (8000, 8001), "Ollama": (11434,), "Web server": (5173,)}
HOST_INTERVAL, CONTAINER_INTERVAL = 0.25, 1.0
TCP_STATES = {"01": "ESTABLISHED", "02": "SYN_SENT", "06": "TIME_WAIT", "08": "CLOSE_WAIT"}


def run(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True).stdout


def descendants(pids: set[int]) -> set[int]:
    children: dict[int, set[int]] = defaultdict(set)
    for line in run("ps", "-A", "-o", "pid=,ppid=").splitlines():
        pid, ppid = (int(x) for x in line.split())
        children[ppid].add(pid)
    found, todo = set(pids), list(pids)
    while todo:
        for child in children[todo.pop()] - found:
            found.add(child)
            todo.append(child)
    return found


def host_processes(client: int) -> dict[int, str]:
    """pid -> stack role, now (the second API comes and goes)."""
    roles: dict[int, str] = {}
    for role, ports in PORTS.items():
        for port in ports:
            listeners = {int(p) for p in run("lsof", "-t", f"-i:{port}", "-sTCP:LISTEN").split()}
            roles.update({pid: role for pid in descendants(listeners)})
    for pid in descendants({client}):
        roles.setdefault(pid, "e2e client")
    return roles


def local_host(address: str) -> bool:
    host = address.rsplit(":", 1)[0].strip("[]")
    if host in ("*", "localhost"):
        return True
    try:
        return ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        return False


def containers() -> dict[str, tuple[str, list[ipaddress.IPv4Network]]]:
    """Container ID -> (compose service, its Docker networks)."""
    found = {}
    for cid in run("docker", "compose", "ps", "-q").split():
        info = json.loads(run("docker", "inspect", cid))[0]
        service = info["Config"]["Labels"].get("com.docker.compose.service", cid[:12])
        networks = [
            ipaddress.ip_network(f"{n['IPAddress']}/{n['IPPrefixLen']}", strict=False)
            for n in info["NetworkSettings"]["Networks"].values()
            if n.get("IPAddress")
        ]
        found[cid] = (service, networks)
    return found


def proc_address(hex_address: str) -> ipaddress._BaseAddress:
    host, _ = hex_address.split(":")
    raw = bytes.fromhex(host)
    if len(raw) == 4:
        return ipaddress.IPv4Address(raw[::-1])
    words = b"".join(raw[i : i + 4][::-1] for i in range(0, 16, 4))
    address = ipaddress.IPv6Address(words)
    return address.ipv4_mapped or address


def container_remotes(cid: str) -> list[tuple[str, str]]:
    """(remote address, state) of every connected socket in the container's tables; a table that
    cannot be read is an error, never "no connections"."""
    tables = [f"/proc/net/{t}" for t in ("tcp", "tcp6", "udp", "udp6")]
    read = subprocess.run(["docker", "exec", cid, "cat", *tables], capture_output=True, text=True)
    if read.returncode != 0 or "local_address" not in read.stdout:
        raise RuntimeError(read.stderr.strip()[-120:] or "no socket table")
    out = read.stdout
    remotes = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 4 or parts[0] == "sl":
            continue
        remote, state = parts[2], parts[3]
        address = proc_address(remote)
        if address.is_unspecified:
            continue  # listening, or an unconnected UDP socket
        port = int(remote.split(":")[1], 16)
        remotes.append((f"{address}:{port}", TCP_STATES.get(state, state)))
    return remotes


class Recorder:
    def __init__(self) -> None:
        self.seen: dict[str, set[str]] = defaultdict(set)
        self.outside: list[str] = []
        self.samples: dict[str, int] = defaultdict(int)
        self.stop = threading.Event()

    def note(self, role: str, remote: str, ok: bool, detail: str) -> None:
        self.seen[role].add(remote.rsplit(":", 1)[0])
        if not ok and detail not in self.outside:
            self.outside.append(detail)

    def host(self, client: int) -> None:
        while not self.stop.is_set():
            roles = host_processes(client)
            listing = run("lsof", "-nP", "-a", "-i", "-p", ",".join(map(str, roles)))
            for line in listing.splitlines()[1:]:
                parts = line.split()
                name = parts[8] if len(parts) > 8 else ""
                if "->" not in name:
                    continue
                remote = name.split("->", 1)[1]
                role = roles.get(int(parts[1]), "?")
                self.note(role, remote, local_host(remote), f"{role} ({parts[0]}) -> {remote}")
            self.samples["laptop"] += 1
            self.stop.wait(HOST_INTERVAL)

    def docker(self, found: dict[str, tuple[str, list]]) -> None:
        while not self.stop.is_set():
            for cid, (service, networks) in found.items():
                try:
                    remotes = container_remotes(cid)
                except RuntimeError as exc:
                    detail = f"{service}: socket table unreadable ({exc})"
                    self.note(f"{service} container", "?:0", False, detail)
                    continue
                for remote, state in remotes:
                    address = ipaddress.ip_address(remote.rsplit(":", 1)[0])
                    ok = address.is_loopback or any(address in n for n in networks)
                    self.note(f"{service} container", remote, ok, f"{service} -> {remote} {state}")
            self.samples["containers"] += 1
            self.stop.wait(CONTAINER_INTERVAL)


def qdrant_telemetry_off(found: dict[str, tuple[str, list]]) -> tuple[bool, str]:
    """Qdrant's telemetry setting as the running container has it, and what its start-up said."""
    cid = next((c for c, (service, _) in found.items() if service == "qdrant"), None)
    if cid is None:
        return False, "no qdrant container"
    setting = (
        "QDRANT__TELEMETRY_DISABLED=true"
        in json.loads(run("docker", "inspect", cid))[0]["Config"]["Env"]
    )
    logs = subprocess.run(["docker", "logs", cid], capture_output=True, text=True)
    said = [
        line.rstrip()
        for line in (logs.stdout + logs.stderr).splitlines()
        if "Telemetry reporting" in line
    ]
    logged = bool(said) and said[-1].endswith("Telemetry reporting disabled")
    return setting and logged, (
        ("QDRANT__TELEMETRY_DISABLED=true" if setting else "no QDRANT__TELEMETRY_DISABLED=true")
        + f"; start-up log: {said[-1].split('qdrant: ')[-1] if said else 'no telemetry line'}"
    )


def main() -> None:
    found = containers()
    if not found:
        raise SystemExit("no compose containers running: start the stack (make demo-up)")
    qdrant_ok, qdrant_detail = qdrant_telemetry_off(found)
    e2e = subprocess.Popen(["make", "e2e-api"], cwd=ROOT)
    recorder = Recorder()
    threads = [
        threading.Thread(target=recorder.host, args=(e2e.pid,), daemon=True),
        threading.Thread(target=recorder.docker, args=(found,), daemon=True),
    ]
    for thread in threads:
        thread.start()
    started = time.monotonic()
    code = e2e.wait()
    recorder.stop.set()
    for thread in threads:
        thread.join()
    minutes = (time.monotonic() - started) / 60
    print(
        f"\nOffline check during make e2e-api ({minutes:.1f} min; {recorder.samples['laptop']}"
        f" laptop samples, {recorder.samples['containers']} container samples)"
    )
    for role in (
        "API",
        "Ollama",
        "Web server",
        "e2e client",
        *(f"{s} container" for s, _ in found.values()),
    ):
        addresses = sorted(recorder.seen.get(role, set()))
        print(f"  {role:<20} remote addresses: {', '.join(addresses) or 'none'}")
    for detail in recorder.outside:
        print(f"FAIL outside the laptop: {detail}")
    print(
        f"{'OK  ' if qdrant_ok else 'FAIL'} Qdrant telemetry off in its container: {qdrant_detail}"
    )
    ok = code == 0 and not recorder.outside and qdrant_ok
    print(
        ("OK   no connection outside the laptop" if not recorder.outside else "FAIL")
        + ("" if code == 0 else f"; make e2e-api failed ({code})")
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
