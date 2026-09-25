"""Deterministic verification planning and bounded execution with no LLM calls."""

from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from agora_ai_sdlc.execution_bundle import ExecutionBundle, build_execution_bundle, resolve_work_workspace

SCHEMA = "agora-ai-sdlc/verification-report/v1"
MAX_OUTPUT_CHARS = 16000
ALLOWED_COMMANDS = {
    ("mvn", "test"),
    ("./mvnw", "test"),
    ("mvn", "-q", "-DskipTests", "package"),
    ("./mvnw", "-q", "-DskipTests", "package"),
    ("gradle", "build"),
    ("./gradlew", "build"),
    ("./gradlew", "test"),
    ("pnpm", "build"),
    ("pnpm", "test"),
    ("yarn", "build"),
    ("yarn", "test"),
    ("npm", "run", "build"),
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


def _package_script(root: Path, name: str) -> bool:
    package = root / "package.json"
    if not package.is_file():
        return False
    try:
        payload = json.loads(package.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    scripts = payload.get("scripts") if isinstance(payload, dict) else None
    return isinstance(scripts, dict) and isinstance(scripts.get(name), str)


def _build_commands(root: Path, bundle: ExecutionBundle) -> tuple[str, ...]:
    systems = {str(item).casefold() for item in bundle.build_systems}
    commands: list[str] = []

    if any("maven" in item or item == "mvn" for item in systems):
        executable = "./mvnw" if (root / "mvnw").is_file() else "mvn"
        commands.append(f"{executable} -q -DskipTests package")

    if any("gradle" in item for item in systems):
        executable = "./gradlew" if (root / "gradlew").is_file() else "gradle"
        commands.append(f"{executable} build")

    if "pnpm" in systems and _package_script(root, "build"):
        commands.append("pnpm build")
    elif "yarn" in systems and _package_script(root, "build"):
        commands.append("yarn build")
    elif ("npm" in systems or "node" in systems) and _package_script(root, "build"):
        commands.append("npm run build")

    return tuple(commands)


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

    root = resolve_work_workspace(root, work)
    bundle = build_execution_bundle(root, swarm=swarm, work=work, persist=False)
    planned_commands = tuple(dict.fromkeys((*_build_commands(root, bundle), *bundle.verification_commands)))
    commands = tuple(_run(root, command, timeout_seconds) if run else _planned(command) for command in planned_commands)
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
    persisted = replace(report, report_path=str(target))
    target.write_text(json.dumps(persisted.snapshot(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return persisted


def _compact_human_diagnostic(command: VerificationCommand, max_chars: int = 1200) -> str:
    source = command.stderr or command.stdout
    value = " ".join(source.split())
    if len(value) <= max_chars:
        return value
    return "… " + value[-(max_chars - 2) :]


def persisted_verification_diagnostic(root: Path, work: str | None) -> str | None:
    """Return a compact host-readable diagnosis from the latest executed verification."""

    if not work:
        return None
    path = root.resolve() / ".agora" / "ai-sdlc" / "verification" / work / "VERIFICATION.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("executed") is not True:
        return None

    commands = payload.get("commands")
    if not isinstance(commands, list) or not commands:
        return "No deterministic build/test command was detected. Add executable tests and the minimal build/test configuration."

    lines: list[str] = []
    for command in commands:
        if not isinstance(command, dict):
            continue
        status = str(command.get("status") or "").casefold()
        if status == "passed":
            continue
        name = str(command.get("command") or "<unknown command>")
        exit_code = command.get("exit_code")
        stderr = str(command.get("stderr") or "").strip()
        stdout = str(command.get("stdout") or "").strip()
        diagnostic = " ".join((stderr or stdout).split())
        if len(diagnostic) > 1200:
            diagnostic = "… " + diagnostic[-1198:]
        suffix = f" exit={exit_code}" if exit_code is not None else ""
        detail = f" diagnostic={diagnostic}" if diagnostic else ""
        lines.append(f"{name}: {status}{suffix}{detail}")

    if not lines:
        return None
    return " | ".join(lines[:4])


def persisted_verification_failed(root: Path, work: str | None) -> bool:
    """Return whether the latest executed deterministic verification failed or was not runnable."""

    if not work:
        return False
    path = root.resolve() / ".agora" / "ai-sdlc" / "verification" / work / "VERIFICATION.json"
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict) or payload.get("executed") is not True:
        return False
    commands = payload.get("commands")
    if not isinstance(commands, list) or not commands:
        return True
    return any(
        not isinstance(command, dict) or str(command.get("status") or "").casefold() != "passed" for command in commands
    )


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
        if command.status in {"failed", "timeout", "unavailable", "blocked"}:
            diagnostic = _compact_human_diagnostic(command)
            if diagnostic:
                lines.append(f"    diagnostic: {diagnostic}")

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
