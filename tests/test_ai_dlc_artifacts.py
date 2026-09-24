import json
from pathlib import Path

from agora_ai_sdlc.artifacts import PREFIX, check_traceability, parse_artifact, parse_template

ROOT = Path(__file__).parent.parent


NEW_AI_DLC_KINDS = {
    "user-stories": "UST",
    "nfr": "NFR",
    "risk-register": "RSK",
    "measurement-criteria": "MCR",
    "prfaq": "PRF",
    "logical-design": "LOG",
    "deployment-unit": "DPU",
}


def artifact(kind, artifact_id, traces=(), *, criteria=(), covers=()):
    text = (
        "---\n"
        'schema: "agora-ai-sdlc/artifact/v1"\n'
        f'kind: "{kind}"\n'
        "version: 1\n"
        f'id: "{artifact_id}"\n'
        'work: "w"\n'
        "revision: 1\n"
        f"traces-to: {json.dumps(list(traces))}\n"
        f"criteria: {json.dumps(list(criteria))}\n"
        f"covers-criteria: {json.dumps(list(covers))}\n"
        'required-sections: ["S"]\n'
        "---\n\n# Artifact\n\n## S\n\ncontent\n"
    )
    return parse_artifact(text)


def test_ai_dlc_artifact_templates_are_first_class_and_parseable():
    for kind, prefix in NEW_AI_DLC_KINDS.items():
        assert PREFIX[kind] == prefix
        path = ROOT / "templates" / f"{kind}.md"
        assert path.is_file()
        parsed = parse_template(path.read_text(encoding="utf-8"))
        assert parsed.kind == kind


def test_ai_dlc_trace_chain_supports_inception_through_deployment_unit():
    artifacts = [
        artifact("intent", "INT-001"),
        artifact("unit-of-work", "UOW-001", ("INT-001",)),
        artifact("requirements", "REQ-001", ("UOW-001",), criteria=("ac-1",)),
        artifact("user-stories", "UST-001", ("REQ-001",)),
        artifact("nfr", "NFR-001", ("REQ-001",)),
        artifact("risk-register", "RSK-001", ("NFR-001",)),
        artifact("measurement-criteria", "MCR-001", ("UST-001",)),
        artifact("domain-model", "DOM-001", ("UST-001",)),
        artifact("logical-design", "LOG-001", ("DOM-001", "NFR-001", "RSK-001")),
        artifact("test-strategy", "TST-001", ("UST-001", "NFR-001"), covers=("ac-1",)),
        artifact("implementation-plan", "IMP-001", ("LOG-001", "TST-001")),
        artifact("deployment-unit", "DPU-001", ("IMP-001", "TST-001", "LOG-001")),
    ]

    check_traceability(artifacts)
