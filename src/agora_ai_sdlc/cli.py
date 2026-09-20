"""Minimal CLI. The lifecycle CLI remains `agora` (Agora Core)."""

import argparse

from agora_ai_sdlc import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agora-ai-sdlc")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.parse_args(argv)
    parser.print_help()
    return 0
