"""Deterministic verification planning and bounded execution with no LLM calls."""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from agora_ai_sdlc.execution_bundle import ExecutionBundle, build_execution_bundle

SCHEMA = "agora-ai-sdlc/verification-report/v1"
MAX_OUTPUT_CHARS = 16000
ALLOWED_COMMANDS = {
    ("mvn", "test"),
    ("./gradlew", "test"),
    ("pnpm", "test"),
    ("yarn", "test"),
    ("npm", "test"),
    ("pytest",),
}


class VerificationError(ValueError):
    """Stable deterministic verification error."""


@dataclass(frozen=True)
class VerificationCommand:
    command: str
    argv: tuple[str, ...]
    allowed: bool
    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    elapsed_seconds: float | None

    def snapshot(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AcceptanceCoverage:
    criterion: str
    candidate_test_paths: tuple[str, ...]
    mechanically_satisfied: bool = False

    def snapshot(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class VerificationReport:
    schema: str
    work: str | None
    head: str | None
    executed: bool
    commands: tuple[VerificationCommand, ...]
    acceptance_coverage: tuple[AcceptanceCoverage, ...]
    all_executed_commands_passed: bool | None
    report_path: str | None

    def snapshot(self) -> dict:
        return asdict(self)


def _bounded(text: str) -> str:
    value = text.strip()
    if len(value) <= MAX_OUTPUT_CHARS:
        return value
    head = value[:4000].rstrip()
    tail = value[-(MAX_OUTPUT_CHARS - 4100) :].lstrip()
    return f"{head}\n\n… verification output abbreviated …\n\n{tail}"


def _argv(command: str) -> tuple[str, ...]:
    try:
        parsed = tuple(shlex.split(command))
    except ValueError as error:
        raise VerificationError(f"verification.command.invalid: {command!r}") from error
    if not parsed:
        raise VerificationError("verification.command.empty")
    return parsed


def _is_allowed(argv: tuple[str, ...]) -> bool:
    return argv in ALLOWED_COMMANDS


def _test_paths(bundle: ExecutionBundle) -> tuple[str, ...]:
    values = []
    for path in (*bundle.changed_paths, *bundle.dirty_paths, *bundle.related_paths):
        lowered = path.casefold()
        name = Path(path).name.casefold()
        stem = Path(path).stem.casefold()
        if (
            "/test/" in lowered
            or "/tests/" in lowered
            or "/__tests__/" in lowered
            or name.startswith("test_")
            or stem.endswith((".test", ".spec", "_test", "test"))
            or name.endswith(("test.java", "tests.java", "test.kt", "tests.kt"))
        ):
            values.append(path)
    return tuple(dict.fromkeys(values))


def _criterion_terms(criterion: str) -> tuple[str, ...]:
    stop = {
        "each",
        "explicit",
        "same",
        "tests",
        "test",
        "with",
        "from",
        "that",
        "this",
        "path",
        "drives",
        "both",
        "runtime",
    }
    terms = []
    for token in re.findall(r"[a-z][a-z0-9_-]{3,}", criterion.casefold()):
        if token in stop or token in terms:
            continue
        terms.append(token)
    return tuple(terms[:8])


def _coverage(bundle: ExecutionBundle) -> tuple[AcceptanceCoverage, ...]:
    test_paths = _test_paths(bundle)
    coverage = []
    for criterion in bundle.acceptance_criteria:
        terms = _criterion_terms(criterion)
        candidates = tuple(path for path in test_paths if any(term in path.casefold() for term in terms))
        coverage.append(
            AcceptanceCoverage(
                criterion=criterion,
                candidate_test_paths=candidates,
                mechanically_satisfied=False,
            )
        )
    return tuple(coverage)


def _planned(command: str) -> VerificationCommand:
    argv = _argv(command)
    return VerificationCommand(
        command=command,
        argv=argv,
        allowed=_is_allowed(argv),
        status="planned" if _is_allowed(argv) else "blocked",
        exit_code=None,
        stdout="",
        stderr="",
        elapsed_seconds=None,
    )


def _run(root: Path, command: str, timeout_seconds: int) -> VerificationCommand:
    import time

    argv = _argv(command)
    if not _is_allowed(argv):
        return VerificationCommand(
            command=command,
            argv=argv,
            allowed=False,
            status="blocked",
            exit_code=None,
            stdout="",
            stderr="command is outside the deterministic verification allowlist",
            elapsed_seconds=None,
        )

    started = time.monotonic()
    try:
        result = subprocess.run(
            list(argv),
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as error:
        return VerificationCommand(
            command=command,
            argv=argv,
            allowed=True,
            status="unavailable",
            exit_code=None,
            stdout="",
            stderr=str(error),
            elapsed_seconds=round(time.monotonic() - started, 3),
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode() if isinstance(error.stdout, bytes) else (error.stdout or "")
        stderr = error.stderr.decode() if isinstance(error.stderr, bytes) else (error.stderr or "")
        return VerificationCommand(
            command=command,
            argv=argv,
            allowed=True,
            status="timeout",
            exit_code=None,
            stdout=_bounded(stdout),
            stderr=_bounded(stderr),
            elapsed_seconds=round(time.monotonic() - started, 3),
        )

    return VerificationCommand(
        command=command,
        argv=argv,
        allowed=True,
        status="passed" if result.returncode == 0 else "failed",
        exit_code=result.returncode,
        stdout=_bounded(result.stdout),
        stderr=_bounded(result.stderr),
        elapsed_seconds=round(time.monotonic() - started, 3),
    )


def build_verification_report(
    root: Path,
    *,
    swarm: str | None = None,
    work: str | None = None,
    run: bool = False,
    timeout_seconds: int = 300,
    persist: bool = True,
) -> VerificationReport:
    if timeout_seconds < 1:
        raise VerificationError("verification.timeout: timeout must be positive")

    root = root.expanduser().resolve()
    bundle = build_execution_bundle(root, swarm=swarm, work=work, persist=False)
    commands = tuple(
        _run(root, command, timeout_seconds) if run else _planned(command) for command in bundle.verification_commands
    )
    executed_commands = tuple(command for command in commands if command.status != "planned")
    passed = all(command.status == "passed" for command in executed_commands) if run and executed_commands else None

    report = VerificationReport(
        schema=SCHEMA,
        work=bundle.work,
        head=bundle.head,
        executed=run,
        commands=commands,
        acceptance_coverage=_coverage(bundle),
        all_executed_commands_passed=passed,
        report_path=None,
    )
    if not persist:
        return report

    target = root / ".agora" / "ai-sdlc" / "verification" / (bundle.work or "unscoped") / "VERIFICATION.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    persisted = VerificationReport(**{**report.snapshot(), "report_path": str(target)})
    target.write_text(json.dumps(persisted.snapshot(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return persisted


def render_verification(report: VerificationReport) -> str:
    lines = [
        "Agora AI-SDLC | Deterministic Verification",
        "",
        f"Work: {report.work or '-'}",
        f"HEAD: {report.head or 'unknown'}",
        f"Mode: {'executed' if report.executed else 'plan-only'}",
        "",
        "Commands",
    ]
    if not report.commands:
        lines.append("  - no deterministic verification command detected")
    for command in report.commands:
        lines.append(f"  - [{command.status}] {command.command}")
        if command.exit_code is not None:
            lines.append(f"    exit={command.exit_code} elapsed={command.elapsed_seconds}s")

    lines.extend(["", "Acceptance criteria"])
    if not report.acceptance_coverage:
        lines.append("  - none")
    for item in report.acceptance_coverage:
        candidates = ", ".join(item.candidate_test_paths) or "no deterministic test-path match"
        lines.append(f"  - {item.criterion}")
        lines.append(f"    candidates: {candidates}")
        lines.append("    mechanically satisfied: false")

    lines.extend(
        [
            "",
            (
                "Boundary: command success is verification evidence only; "
                "it does not automatically satisfy an acceptance criterion."
            ),
        ]
    )
    return "\n".join(lines)
