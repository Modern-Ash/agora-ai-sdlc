"""Credential-free cross-repository impact-analysis sample."""

import json
from pathlib import Path

from agora_ai_sdlc.impact_analysis import (
    affected_repositories,
    enterprise_review_evidence,
    parse_impact_analysis,
    summary,
)

HERE = Path(__file__).parent


def main() -> dict:
    analysis = parse_impact_analysis((HERE / "impact-analysis.md").read_text(encoding="utf-8"))
    result = {
        "final_state": "completed",
        "validate": "ok",
        "repositories": list(affected_repositories(analysis)),
        "summary": summary(analysis),
        "enterprise_review_evidence": list(enterprise_review_evidence(analysis)),
    }
    print(json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
