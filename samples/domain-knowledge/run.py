"""Offline domain-knowledge descriptor sample."""

import json
from pathlib import Path

from agora_ai_sdlc.domain_knowledge import load_descriptor, snapshot

HERE = Path(__file__).parent


def main() -> dict:
    local = load_descriptor(HERE / "local.yaml")
    external = load_descriptor(HERE / "external.yaml")
    result = {
        "final_state": "completed",
        "validate": "ok",
        "sources": [snapshot(local), snapshot(external)],
    }
    print(json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
