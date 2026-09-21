"""Offline provider-neutral risk/issue management sample."""

import json
from pathlib import Path

from agora_ai_sdlc.risk_issue_management import load_record, portfolio

HERE = Path(__file__).parent


def main() -> dict:
    records = (
        load_record(HERE / "risk.yaml"),
        load_record(HERE / "issue.yaml"),
    )
    summary = portfolio(records)
    result = {
        "final_state": "completed",
        "validate": "ok",
        "portfolio": summary,
    }
    print(json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
