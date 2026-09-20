"""Credential-free Starter bootstrap sample."""

import json
import shutil
import tempfile
from pathlib import Path

from agora_ai_sdlc.starter import apply, preview

HERE = Path(__file__).parent


def main() -> dict:
    runtime = Path(tempfile.mkdtemp(prefix="agora-ai-sdlc-starter-"))
    target, home = runtime / "project", runtime / "home"
    config = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    plan = preview(config, target)
    result = apply(config, target, home)
    summary = {
        "final_state": "completed" if result["work_state"] == "readiness" else "failed",
        "validate": result["validate"],
        "profile": result["profile"],
        "depth": result["depth"],
        "method": result["method"],
        "preview_matches": plan == {key: result[key] for key in plan},
        "first_work_state": result["work_state"],
        "runtime_count": len(config["runtimes"]),
    }
    print(json.dumps(summary, sort_keys=True))
    if summary["validate"] == "ok":
        shutil.rmtree(runtime)
    else:
        summary["workspace"] = str(target)
    return summary


if __name__ == "__main__":
    main()
