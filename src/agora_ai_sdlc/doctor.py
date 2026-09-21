"""Environment diagnostics for Agora AI-SDLC."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from agora.workspace import AgoraWorkspace

from agora_ai_sdlc import __version__
from agora_ai_sdlc.flavor_manifest import installed_core_version
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery, discover_runtimes


@dataclass(frozen=True)
class DoctorCheck:
    id: str
    ok: bool
    detail: str

    def snapshot(self) -> dict:
        return {"id": self.id, "ok": self.ok, "detail": self.detail}


def _tool_check(command: str, args: list[str] | None = None, timeout: float = 2.0) -> DoctorCheck:
    executable = shutil.which(command)
    if executable is None:
        return DoctorCheck(command, False, "not installed")
    try:
        result = subprocess.run(
            [executable, *(args or ["--version"])],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return DoctorCheck(command, False, f"probe failed: {error.__class__.__name__}")
    output = (result.stdout or result.stderr or "").strip().splitlines()
    detail = output[0].strip() if output else executable
    return DoctorCheck(command, result.returncode == 0, detail)


def run_doctor(root: Path) -> tuple[tuple[DoctorCheck, ...], tuple[RuntimeDiscovery, ...]]:
    checks: list[DoctorCheck] = []

    try:
        core_version = installed_core_version()
        checks.append(DoctorCheck("agora-core", True, core_version))
    except Exception as error:
        checks.append(DoctorCheck("agora-core", False, error.__class__.__name__))

    checks.append(DoctorCheck("agora-ai-sdlc", True, __version__))
    checks.append(_tool_check("git"))
    checks.append(_tool_check("gh"))

    project_state = root / ".agora"
    if not project_state.is_dir():
        checks.append(DoctorCheck("project", False, "no .agora project state"))
    else:
        try:
            workspace = AgoraWorkspace(cwd=root)
            validation = workspace.validate()
            checks.append(
                DoctorCheck(
                    "project",
                    bool(validation.ok),
                    "valid Agora project" if validation.ok else "Agora validation failed",
                )
            )
        except (OSError, ValueError) as error:
            checks.append(DoctorCheck("project", False, error.__class__.__name__))

    skill = root / ".agora" / "skills" / "agora-ai-sdlc-guided" / "SKILL.md"
    checks.append(
        DoctorCheck(
            "guided-skill",
            skill.is_file(),
            str(skill.relative_to(root)) if skill.is_file() else "not installed",
        )
    )

    runtimes = discover_runtimes(root)
    return tuple(checks), runtimes


def render_doctor(checks: tuple[DoctorCheck, ...], runtimes: tuple[RuntimeDiscovery, ...]) -> str:
    lines = ["Agora AI-SDLC environment", ""]
    for check in checks:
        marker = "✓" if check.ok else "!"
        lines.append(f"{marker} {check.id:<15} {check.detail}")

    lines.extend(["", "AI runtimes"])
    for runtime in runtimes:
        if runtime.installed and runtime.responsive:
            marker = "✓"
            state = "responsive"
        elif runtime.installed:
            marker = "!"
            state = f"installed, probe failed ({runtime.error or 'unknown'})"
        else:
            marker = "-"
            state = "not installed"
        if runtime.configured:
            state += " · configured"
        if runtime.service is not None:
            state += f" · service {runtime.service}"
        lines.append(f"{marker} {runtime.name:<15} {state}")

    overall = all(check.ok for check in checks if check.id != "gh")
    lines.extend(["", "Ready for guided delivery." if overall else "Environment needs attention."])
    return "\n".join(lines)
