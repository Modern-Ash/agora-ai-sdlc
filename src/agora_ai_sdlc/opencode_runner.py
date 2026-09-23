"""Fail-fast supervisor for non-interactive OpenCode execution."""

from __future__ import annotations

import argparse
import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import TextIO

TERMINAL_PROVIDER_ERRORS = (
    "usage limit has been reached",
    "usage limit reached",
    "monthly usage limit",
    "free usage exceeded",
    "quota exceeded",
    "quota has been reached",
    "invalid api key",
    "authentication failed",
    "unauthorized",
)


def terminal_provider_error(line: str) -> bool:
    normalized = line.casefold()
    return any(marker in normalized for marker in TERMINAL_PROVIDER_ERRORS)


def _pump(stream: TextIO, name: str, events: queue.Queue[tuple[str, str | None]]) -> None:
    try:
        for line in iter(stream.readline, ""):
            events.put((name, line))
    finally:
        events.put((name, None))


def run_opencode(
    *,
    executable: str,
    root: Path,
    model: str,
    prompt: str,
) -> int:
    command = [
        executable,
        "--print-logs",
        "--log-level",
        "ERROR",
        "run",
        "--auto",
        "--model",
        model,
        "--dir",
        str(root.resolve()),
        prompt,
    ]
    process = subprocess.Popen(
        command,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    assert process.stderr is not None

    events: queue.Queue[tuple[str, str | None]] = queue.Queue()
    threads = [
        threading.Thread(target=_pump, args=(process.stdout, "stdout", events), daemon=True),
        threading.Thread(target=_pump, args=(process.stderr, "stderr", events), daemon=True),
    ]
    for thread in threads:
        thread.start()

    closed: set[str] = set()
    fatal: str | None = None
    try:
        while len(closed) < 2:
            name, line = events.get()
            if line is None:
                closed.add(name)
                continue
            target = sys.stdout if name == "stdout" else sys.stderr
            target.write(line)
            target.flush()
            if name == "stderr" and terminal_provider_error(line):
                fatal = " ".join(line.split())
                if process.poll() is None:
                    process.kill()
                break
    finally:
        if fatal is not None:
            process.wait()
        elif process.poll() is None and len(closed) == 2:
            process.wait()

    if fatal is not None:
        print(f"OpenCode terminal provider error: {fatal}", file=sys.stderr)
        return 70
    return process.wait()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt", required=True)
    args = parser.parse_args(argv)
    return run_opencode(
        executable=args.executable,
        root=Path(args.root),
        model=args.model,
        prompt=args.prompt,
    )


if __name__ == "__main__":
    raise SystemExit(main())
