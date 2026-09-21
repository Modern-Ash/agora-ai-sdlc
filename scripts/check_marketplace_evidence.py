"""Check or regenerate the Marketplace compatibility evidence matrix."""

import argparse
import sys
from pathlib import Path

from agora_ai_sdlc.marketplace_evidence import check, write

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Regenerate the checked-in matrix")
    args = parser.parse_args(argv)
    if args.write:
        path = write(ROOT)
        print(path.relative_to(ROOT))
        return 0
    ok, message = check(ROOT)
    if not ok:
        print(message, file=sys.stderr)
        print("recovery: uv run python scripts/check_marketplace_evidence.py --write", file=sys.stderr)
        return 1
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
