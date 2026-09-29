"""Measured token amplification against an explicit direct-execution baseline.

This module never estimates provider usage. Ratios are produced only when both
baseline and Agora observations use the same token basis.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

SCHEMA = "agora-ai-sdlc/amplification/v1"
TOKEN_BASIS = "provider_reported_tokens"


@dataclass(frozen=True)
class TokenMeasurement:
    input_tokens: int
    output_tokens: int
    basis: str = TOKEN_BASIS

    def __post_init__(self) -> None:
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("token measurements must be non-negative")
        if self.basis != TOKEN_BASIS:
            raise ValueError("amplification requires provider-reported tokens")

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class AmplificationReport:
    work: str
    baseline: TokenMeasurement | None
    agora: TokenMeasurement | None
    factor: float | None
    comparable: bool
    reason: str

    def to_dict(self) -> dict:
        return {
            "schema": SCHEMA,
            "work": self.work,
            "baseline": None if self.baseline is None else asdict(self.baseline),
            "agora": None if self.agora is None else asdict(self.agora),
            "factor": self.factor,
            "comparable": self.comparable,
            "reason": self.reason,
        }


def baseline_path(root: Path, work: str) -> Path:
    return root / ".agora" / "ai-sdlc" / "economics" / work / "BASELINE.json"


def save_baseline(root: Path, work: str, measurement: TokenMeasurement) -> str:
    path = baseline_path(root, work)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"schema": SCHEMA, "work": work, "measurement": asdict(measurement)},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return str(path)


def load_baseline(root: Path, work: str) -> TokenMeasurement | None:
    path = baseline_path(root, work)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        measurement = payload.get("measurement") if payload.get("schema") == SCHEMA else None
        if not isinstance(measurement, dict):
            return None
        return TokenMeasurement(
            input_tokens=int(measurement["input_tokens"]),
            output_tokens=int(measurement["output_tokens"]),
            basis=str(measurement["basis"]),
        )
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
        return None


def amplification_report(
    root: Path,
    work: str,
    agora: TokenMeasurement | None,
) -> AmplificationReport:
    baseline = load_baseline(root, work)
    if baseline is None:
        return AmplificationReport(work, None, agora, None, False, "baseline-missing")
    if agora is None:
        return AmplificationReport(work, baseline, None, None, False, "agora-usage-missing")
    if baseline.basis != agora.basis:
        return AmplificationReport(work, baseline, agora, None, False, "measurement-basis-mismatch")
    if baseline.total_tokens == 0:
        return AmplificationReport(work, baseline, agora, None, False, "baseline-zero")
    return AmplificationReport(
        work,
        baseline,
        agora,
        round(agora.total_tokens / baseline.total_tokens, 4),
        True,
        "measured",
    )
