import os
from pathlib import Path

import pytest

from conformance.runtimes.harness import normalize_output

LIVE_DIR = os.environ.get("AGORA_AI_SDLC_LIVE_SMOKE_DIR")


@pytest.mark.skipif(not LIVE_DIR, reason="set AGORA_AI_SDLC_LIVE_SMOKE_DIR for opt-in captured live outputs")
def test_opt_in_live_outputs_satisfy_normalized_contract():
    root = Path(LIVE_DIR)
    paths = {"codex": root / "codex.jsonl", "claude": root / "claude.json"}
    assert all(path.is_file() for path in paths.values())
    for adapter, path in paths.items():
        normalized = normalize_output(adapter, path.read_text(encoding="utf-8"))
        assert normalized["outcome"] == "success"
        assert normalized["phase"] in {"production", "review"}
        assert normalized["artifact"]
        assert normalized["tokens"]["input"] >= 0 and normalized["tokens"]["output"] >= 0
