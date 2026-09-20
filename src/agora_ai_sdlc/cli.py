"""Minimal CLI. The lifecycle CLI remains `agora` (Agora Core)."""

import argparse
import json
import runpy
import sys

from agora_ai_sdlc import __version__
from agora_ai_sdlc.depth_profiles import DEFAULT, ProfileError, asset_root, resolve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agora-ai-sdlc")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")
    show = sub.add_parser("profile", help="Print the resolved obligations of a depth profile as JSON")
    show.add_argument("depth", nargs="?", default=DEFAULT)
    sample = sub.add_parser("run-sample", help="Run a bundled credential-free sample and print a JSON summary")
    sample.add_argument("name")
    args = parser.parse_args(argv)
    if args.command == "run-sample":
        script = asset_root("samples") / args.name / "run.py"
        if not script.is_file() or "/" in args.name or args.name.startswith("."):
            print(f"unknown sample {args.name!r}", file=sys.stderr)
            return 2
        summary = runpy.run_path(str(script), run_name="sample")["main"]()
        return 0 if summary["final_state"] == "completed" and summary["validate"] == "ok" else 1
    if args.command == "profile":
        try:
            print(json.dumps(resolve(args.depth).snapshot(), indent=2))
        except ProfileError as error:
            print(error, file=sys.stderr)
            return 2
        return 0
    parser.print_help()
    return 0
