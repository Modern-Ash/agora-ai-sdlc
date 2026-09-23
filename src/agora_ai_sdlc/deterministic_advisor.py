"""Small deterministic runners consumed through Agora Core's advisory runner contract."""

from __future__ import annotations

import json
import sys


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["zero-clarification"]:
        print(json.dumps({"questions": []}, separators=(",", ":")))
        return 0
    print("unsupported deterministic advisor operation", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
