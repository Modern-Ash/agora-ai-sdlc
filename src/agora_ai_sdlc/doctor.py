"""Environment diagnostics for Agora AI-SDLC."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from agora.workspace import AgoraWorkspace

from agora_ai_sdlc import __version__
from agora_ai_sdlc.flavor_manifest import installed_core_version
from agora_ai_sdlc.i18n import t
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


def _validation_detail(validation) -> str:
    if validation.ok:
        return "valid Agora project"
    items = []
    for issue in validation.issues[:3]:
        message = " ".join(str(issue.message).split())
        items.append(f"{issue.code}: {message[:160]}")
    suffix = "" if len(validation.issues) <= 3 else f"; +{len(validation.issues) - 3} more"
    return "Agora validation failed — " + "; ".join(items) + suffix


def run_doctor(root: Path) -> tuple[tuple[DoctorCheck, ...], tuple[RuntimeDiscovery, ...]]:
    checks: list[DoctorCheck] = []

    try:
        core_version = installed_core_version()
        checks.append(DoctorCheck("agora-core", True, core_version))
    except metadata.PackageNotFoundError:
        checks.append(DoctorCheck("agora-core", False, "not installed"))

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
                    _validation_detail(validation),
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


def render_doctor(
    checks: tuple[DoctorCheck, ...],
    runtimes: tuple[RuntimeDiscovery, ...],
    *,
    lang: str = "en",
) -> str:
    lines = [t("doctor.title", lang=lang), ""]
    for check in checks:
        marker = "✓" if check.ok else "!"
        lines.append(f"{marker} {check.id:<15} {check.detail}")

    lines.extend(["", t("doctor.runtime_title", lang=lang)])
    for runtime in runtimes:
        if runtime.installed and runtime.responsive:
            marker = "✓"
            state = t("doctor.responsive", lang=lang)
        elif runtime.installed:
            marker = "!"
            state = t("doctor.installed_failed", lang=lang, error=runtime.error or "unknown")
        else:
            marker = "-"
            state = t("doctor.not_installed", lang=lang)
        if runtime.configured:
            state += " · " + t("doctor.configured", lang=lang)
        if runtime.service is not None:
            state += f" · {t('doctor.service', lang=lang)} {runtime.service}"
        lines.append(f"{marker} {runtime.name:<15} {state}")

    overall = all(check.ok for check in checks if check.id != "gh")
    lines.extend(["", t("doctor.ready" if overall else "doctor.attention", lang=lang)])
    return "\n".join(lines)
