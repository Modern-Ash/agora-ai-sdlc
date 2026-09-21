"""Offline governed change-management sample."""

import json
from pathlib import Path

from agora_ai_sdlc.change_management import (
    parse_change_plan,
    parse_change_request,
    parse_configuration_delta,
    summary,
    validate_chain,
)

HERE = Path(__file__).parent


def main() -> dict:
    chain = validate_chain(
        parse_change_request((HERE / "change-request.md").read_text(encoding="utf-8")),
        parse_change_plan((HERE / "change-plan.md").read_text(encoding="utf-8")),
        parse_configuration_delta((HERE / "configuration-delta.md").read_text(encoding="utf-8")),
    )
    result = {"final_state": "completed", "validate": "ok", **summary(chain)}
    print(json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
