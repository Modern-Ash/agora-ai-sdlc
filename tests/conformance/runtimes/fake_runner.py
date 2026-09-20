"""Credential-free adapter-shaped runner used only by the conformance matrix."""

import argparse
import json
from pathlib import Path


def payload(adapter: str, phase: str) -> str:
    artifact = "implementation" if phase == "production" else "review-report"
    if adapter == "codex":
        records = [
            {"type": "item.completed", "item": {"type": "agent_message", "text": artifact}},
            {
                "type": "turn.completed",
                "result": {"outcome": "success", "phase": phase, "artifact": artifact},
                "usage": {"input_tokens": 7, "output_tokens": 5},
            },
        ]
        return "\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n"
    if adapter == "claude":
        return (
            json.dumps(
                {
                    "type": "result",
                    "subtype": "success",
                    "is_error": False,
                    "result": {"phase": phase, "artifact": artifact},
                    "usage": {"input_tokens": 7, "output_tokens": 5},
                },
                sort_keys=True,
            )
            + "\n"
        )
    if adapter == "generic":
        return (
            json.dumps(
                {
                    "status": "ok",
                    "payload": {"phase": phase, "artifact": artifact},
                    "metrics": {"prompt_tokens": 7, "completion_tokens": 5},
                },
                sort_keys=True,
            )
            + "\n"
        )
    raise ValueError(f"unsupported fake adapter: {adapter}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", choices=("codex", "claude", "generic"), required=True)
    parser.add_argument("--phase", choices=("production", "review"), required=True)
    parser.add_argument("--capture", type=Path, required=True)
    args = parser.parse_args()
    output = payload(args.adapter, args.phase)
    args.capture.parent.mkdir(parents=True, exist_ok=True)
    args.capture.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
