"""Local human-only rendering; no model client and no prompt construction.

Raw transcripts, tool stdout/stderr, commands, signatures, and exception messages
are deliberately not consumed. Redaction is defense in depth for metadata, not a
general-purpose PII classifier.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import stat
import threading
import time
import unicodedata
from contextlib import AbstractContextManager
from pathlib import Path
from typing import TextIO
from urllib.parse import urlsplit, urlunsplit

from agora_ai_sdlc.progress import start_progress

DETAILS = ("normal", "detailed", "diagnostic")
MAX_UI_BYTES = 1024 * 1024
_ANSI = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]")
_SECRET = re.compile(
    r"-----BEGIN [^-]*PRIVATE KEY-----.*?(?:-----END [^-]*PRIVATE KEY-----|$)"
    r"|\b(?:github_pat_|gh[pousr]_|sk-)[A-Za-z0-9_-]{8,}"
    r"|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"
    r"|\bBearer\s+[^\s,;]+"
    r"|\b(?:api[_-]?key|password|secret|token|authorization)\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)",
    re.IGNORECASE | re.DOTALL,
)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_URL = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)


def safe_text(value: object, max_chars: int = 240) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return "[unavailable]"
    # Bound processing of unexpectedly large free text, then redact before truncation.
    value = value[:16384]
    value = _ANSI.sub("", value)
    value = _SECRET.sub("[redacted]", value)
    value = _EMAIL.sub("[redacted-email]", value)

    def clean_url(match: re.Match) -> str:
        try:
            url = urlsplit(match.group())
            return urlunsplit((url.scheme, url.hostname or "", url.path, "", ""))
        except ValueError:
            return "[redacted-url]"

    value = _URL.sub(clean_url, value)
    value = "".join(c if not unicodedata.category(c).startswith("C") else " " for c in value)
    value = " ".join(value.split())
    return value if len(value) <= max_chars else value[:max_chars] + "…"


_TEXT = {
    "en": {
        "title": "Agora AI-SDLC | Observation",
        "scope": "Work",
        "state": "State",
        "branch": "Work branch",
        "base": "Base",
        "unknown": "not reported",
        "unavailable": "Core state unavailable; no other Work was substituted.",
        "boundary": "Read-only observation. Recheck Core before acting; this view grants no authorization.",
        "gate": "Gate",
        "blockers": "Blockers",
        "roles": "Approval roles",
        "next": "Next step",
        "activity": "Recent activity",
        "sessions": "Recorded sessions",
        "artifacts": "Artifact evidence",
        "usage": "Recorded usage",
        "cost": "Cost (USD)",
        "warnings": "Attention",
        "truncated": "Bounded sections",
        "sessions_unavailable": "Session information unavailable; activity cannot be inferred.",
        "no_sessions": "No governed session recorded for this Work; external agents are not inferred.",
        "heartbeat": "Observer active; durable state unchanged. This is not an executor heartbeat.",
        "inspect-core-state": "Inspect/refresh the exact Core Work before proceeding.",
        "review-core-transition": "Core reports an eligible transition; the responsible actor must recheck authority.",
        "resolve-core-obligations": "Resolve the listed Core obligations; do not bypass the gate.",
        "review-delivery": "Review delivery and branch/PR handoff; no merge or PR creation is authorized by this view.",
        "start.inspect": "Inspecting repository, issue source and runtime availability",
        "start.workspace-ready": "Issue workspace resolved without disturbing unrelated local changes",
        "start.runtime-ready": "Runtime selected; selection does not grant authority",
        "start.project-ready": "Project prerequisites checked and safely reconciled",
        "start.work-ready": "Governed issue Work and branch resolved",
        "start.issue-read": "Reading issue through the governed Tool Run",
        "start.issue-reused": "Reusing the previously recorded issue snapshot",
        "start.intent-ready": "Durable Intent resolved",
        "start.pathway": "Adaptive delivery pathway selected",
        "start.handoff": "Preparing portable Inception handoff",
        "start.executor-launch": "Launching the selected executor in the governed Work workspace",
        "start.deterministic-inception": "Building Inception deterministically from issue and repository facts",
        "start.deterministic-complete": "Deterministic Inception ready; no LLM call was required",
        "start.executor-waiting": "waiting for result",
        "start.executor-auto": "automatic model",
        "start.executor-configured": "configured model",
        "start.executor-attempt": "attempt",
        "start.executor-skipped-launch": "Executor launch skipped by explicit prepare-only mode",
        "start.executor-complete": "Executor completed Inception and returned a reviewable proposal",
        "start.executor-skipped-complete": "Executor completion skipped by explicit prepare-only mode",
        "start.prepared": "Start completed the requested mode",
        "start.failed": "Start stopped; inspect the command result",
        "limit": "Human output limit reached; machine result and Core state are unchanged.",
    },
    "es": {
        "title": "Agora AI-SDLC | Observación",
        "scope": "Trabajo",
        "state": "Estado",
        "branch": "Rama del Work",
        "base": "Base",
        "unknown": "no informado",
        "unavailable": "Estado de Core no disponible; no se sustituyó por otro Work.",
        "boundary": "Observación de sólo lectura. Consultá Core antes de actuar; esta vista no otorga autorización.",
        "gate": "Gate",
        "blockers": "Bloqueos",
        "roles": "Roles de aprobación",
        "next": "Próximo paso",
        "activity": "Actividad reciente",
        "sessions": "Sesiones registradas",
        "artifacts": "Evidencia de artefactos",
        "usage": "Consumo registrado",
        "cost": "Costo (USD)",
        "warnings": "Atención",
        "truncated": "Secciones acotadas",
        "sessions_unavailable": "Información de sesiones no disponible; no se puede inferir actividad.",
        "no_sessions": "No hay sesión gobernada registrada para este Work; no se infieren agentes externos.",
        "heartbeat": "Observador activo; estado durable sin cambios. No es una señal de actividad del executor.",
        "inspect-core-state": "Inspeccionar/actualizar el Work exacto en Core antes de continuar.",
        "review-core-transition": "Core informa una transición elegible; el actor responsable debe verificar su autoridad.",
        "resolve-core-obligations": "Resolver las obligaciones de Core indicadas; no saltear el gate.",
        "review-delivery": "Revisar la entrega y su rama/PR; esta vista no autoriza crear el PR ni hacer merge.",
        "start.inspect": "Inspeccionando repositorio, issue y runtimes disponibles",
        "start.workspace-ready": "Workspace del issue resuelto sin tocar cambios locales ajenos",
        "start.runtime-ready": "Runtime seleccionado; la selección no otorga autoridad",
        "start.project-ready": "Prerequisitos del proyecto verificados y reconciliados de forma segura",
        "start.work-ready": "Work gobernado y rama del issue resueltos",
        "start.issue-read": "Leyendo el issue mediante un Tool Run gobernado",
        "start.issue-reused": "Reutilizando el snapshot del issue registrado anteriormente",
        "start.intent-ready": "Intent durable resuelto",
        "start.pathway": "Pathway adaptativo de entrega seleccionado",
        "start.handoff": "Preparando el handoff portable de Inception",
        "start.executor-launch": "Iniciando el executor seleccionado en el workspace gobernado del Work",
        "start.deterministic-inception": "Construyendo Inception de forma determinística desde el issue y hechos del repositorio",
        "start.deterministic-complete": "Inception determinística lista; no fue necesaria una llamada a LLM",
        "start.executor-waiting": "esperando resultado",
        "start.executor-auto": "modelo automático",
        "start.executor-configured": "modelo configurado",
        "start.executor-attempt": "intento",
        "start.executor-skipped-launch": "Inicio del executor omitido por modo prepare-only explícito",
        "start.executor-complete": "El executor completó Inception y devolvió una propuesta revisable",
        "start.executor-skipped-complete": "Finalización del executor omitida por modo prepare-only explícito",
        "start.prepared": "Start completó el modo solicitado",
        "start.failed": "Start detenido; revisá el resultado del comando",
        "limit": "Límite de salida humana alcanzado; el resultado de máquina y Core no cambiaron.",
    },
}


def text(key: str, lang: str = "en") -> str:
    return _TEXT.get(lang, _TEXT["en"]).get(key, _TEXT["en"].get(key, key))


def render(snapshot: dict, *, detail: str = "normal", lang: str = "en") -> str:
    if detail not in DETAILS:
        raise ValueError("observation.invalid-detail")
    unknown = text("unknown", lang)
    lines = [
        text("title", lang),
        text("boundary", lang),
        "",
        f"{text('scope', lang)}: {snapshot['scope']['swarm']}/{snapshot['scope']['work']}",
        f"{text('state', lang)}: {snapshot['status']}",
    ]
    work = snapshot["work"]
    if work:
        lines.extend(
            [
                f"{work['title']} · {work['method']} · {work['state']} · revision={work['revision']}",
                f"operational_status={work['operational_status']}",
                f"{text('branch', lang)}: {work['branch'] or unknown} · {text('base', lang)}: {work['base_branch'] or unknown}",
                f"criteria: {work['satisfied_criteria_count']}/{work['criteria_count']} · {text('roles', lang)}: "
                + (", ".join(work["approval_roles"]) or "—"),
            ]
        )
    else:
        lines.append(text("unavailable", lang))
    for gate in snapshot["gates"]:
        lines.append(f"{text('gate', lang)}: {gate['id']} · satisfied={gate['satisfied']}")
        lines.append(f"  {text('roles', lang)}: {', '.join(gate['approval_roles']) or '—'}")
        for blocker in gate["blockers"]:
            lines.append(f"  ! {blocker['code']} ({blocker['category']}): {', '.join(blocker['references'])}")
        if gate["truncated"]:
            lines.append(f"  ! {text('truncated', lang)}: governance")
    lines.extend(["", text("sessions", lang)])
    sessions = snapshot["sessions"][:1] if detail == "normal" else snapshot["sessions"]
    if not sessions:
        lines.append(
            text(
                "sessions_unavailable" if "observation.sessions-unavailable" in snapshot["warnings"] else "no_sessions",
                lang,
            )
        )
    for session in sessions:
        lines.append(f"  {session['id']} · {session['status']} · executor={session['executor']}")
        lines.append(
            f"  {session['integration']} / {session['provider']} / {session['model']} · basis={session['basis']}"
        )
        if detail != "normal":
            lines.append(
                f"  created_at={session['created_at']} · exit_code={session['exit_code']} · "
                f"timeout_seconds={session['timeout_seconds']} · output_bytes={session['output_bytes']}"
            )
    lines.extend(["", text("usage", lang)])
    dimensions = snapshot["usage"]["dimensions"]
    if not dimensions:
        lines.append(f"  {unknown}")
    for name, values in dimensions.items():
        amount = values["recorded"] if values["recorded"] is not None else unknown
        remaining = values["remaining"] if values["remaining"] is not None else unknown
        lines.append(f"  {name}: {amount} ({values['measurement']}) · limit={values['limit']} · remaining={remaining}")
    lines.append(f"  {text('cost', lang)}: {unknown}")
    lines.extend(["", text("activity", lang)])
    entries = snapshot["activity"][:1] if detail == "normal" else snapshot["activity"]
    for entry in entries:
        lines.append(f"  {entry['timestamp']} · {entry['type']} · actor={entry['actor']}")
    if detail != "normal":
        lines.extend(["", text("artifacts", lang)])
        for artifact in snapshot["artifacts"]:
            lines.append(f"  {artifact['kind']} · {artifact['uri']} · sha256={artifact['sha256'] or unknown}")
    # Warnings, truncation and boundaries are never hidden by verbosity.
    for warning in snapshot["warnings"]:
        lines.append(f"! {text('warnings', lang)}: {warning}")
    if snapshot["truncated"]:
        lines.append(f"! {text('truncated', lang)}: {', '.join(snapshot['truncated'])}")
    lines.extend(["", text("next", lang), text(snapshot["next_action"], lang)])
    if detail == "diagnostic":
        # This is the allowlisted observation, not raw Core records or process output.
        lines.extend(["", json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2)])
    return "\n".join(lines)


class HumanChannel(AbstractContextManager):
    """Explicit UI file is separate from stdout AND stderr captured by an agent host.

    Files are new/exclusive, regular, private, bounded and never inside `.agora`
    or `.git`. No existing file is overwritten or silently appended to.
    """

    def __init__(self, *, path: Path | None = None, stream: TextIO | None = None, lang: str = "en"):
        self.lang = lang
        self.started = time.monotonic()
        self.used = 0
        self.limited = False
        self.failed = False
        self.owns_stream = path is not None
        self.stream = stream
        self._io_lock = threading.RLock()
        self._spinner_stop = threading.Event()
        self._spinner_thread: threading.Thread | None = None
        self._spinner_visible = False
        self._spinner_issue: int | None = None
        self._spinner_agent: str | None = None
        self._spinner_model: str | None = None
        self._spinner_attempt: int | None = None
        self._spinner_phase = "Inception"
        self._spinner_enabled = bool(
            path is None and stream is not None and callable(getattr(stream, "isatty", None)) and stream.isatty()
        )
        if path is not None:
            target = path.expanduser().absolute()
            if any(part in {".agora", ".git"} for part in target.parts):
                raise ValueError("observation.ui-path-protected")
            if target.is_symlink() or any(parent.is_symlink() for parent in target.parents):
                raise ValueError("observation.ui-path-symlink")
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(target, flags, 0o600)
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                os.close(descriptor)
                raise ValueError("observation.ui-path-not-file")
            self.stream = os.fdopen(descriptor, "w", encoding="utf-8")

    @property
    def active(self) -> bool:
        return self.stream is not None and not self.limited and not self.failed

    def write(self, message: str) -> None:
        self.stop_spinner()
        if not self.active:
            return
        # Keep layout while sanitizing each line; do not accidentally log raw host output.
        message = _SECRET.sub("[redacted]", _ANSI.sub("", message))
        safe = "\n".join(safe_text(line, max_chars=2048) or "" for line in message.splitlines()) + "\n"
        size = len(safe.encode("utf-8"))
        with self._io_lock:
            if self.used + size > MAX_UI_BYTES - 256:
                safe = text("limit", self.lang) + "\n"
                self.limited = True
            try:
                assert self.stream is not None
                self.stream.write(safe)
                self.stream.flush()
                self.used += len(safe.encode("utf-8"))
            except OSError:
                # An unavailable display must not change an already performed Core operation.
                self.failed = True

    def set_executor_context(
        self,
        *,
        issue: int | None,
        agent: str | None,
        model: str | None,
        attempt: int | None,
        phase: str = "Inception",
    ) -> None:
        self._spinner_issue = issue
        self._spinner_agent = agent
        self._spinner_model = model
        self._spinner_attempt = attempt
        self._spinner_phase = phase

    def _executor_label(self) -> str:
        labels = {
            "opencode": "OpenCode",
            "codex": "Codex",
            "claude": "Claude Code",
            "ollama": "Ollama",
        }
        return labels.get(self._spinner_agent or "", self._spinner_agent or "AI")

    def _model_label(self) -> str:
        if self._spinner_model:
            return self._spinner_model
        if self._spinner_agent == "opencode":
            return text("start.executor-auto", self.lang)
        return text("start.executor-configured", self.lang)

    def _spinner_detail(self) -> str:
        parts = [self._spinner_phase]
        if self._spinner_issue is not None:
            parts.append(f"issue #{self._spinner_issue}")
        if self._spinner_attempt is not None:
            parts.append(f"{text('start.executor-attempt', self.lang)} {self._spinner_attempt}")
        parts.extend([self._executor_label(), self._model_label(), text("start.executor-waiting", self.lang)])
        return " · ".join(parts)

    def _terminal_columns(self) -> int:
        if self.stream is not None:
            try:
                return os.get_terminal_size(self.stream.fileno()).columns
            except (AttributeError, OSError, ValueError):
                pass
        return shutil.get_terminal_size(fallback=(120, 24)).columns

    def _fit_spinner_line(self, line: str) -> str:
        width = max(20, self._terminal_columns() - 1)
        if len(line) <= width:
            return line
        return line[: max(1, width - 1)].rstrip() + "…"

    def _spinner_loop(self) -> None:
        frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        index = 0
        try:
            while not self._spinner_stop.is_set() and self.active:
                elapsed = time.monotonic() - self.started
                line = self._fit_spinner_line(
                    f"[{elapsed:.1f}s] {frames[index % len(frames)]} {self._spinner_detail()}"
                )
                with self._io_lock:
                    if not self.active or self.stream is None:
                        break
                    self.stream.write("\r\x1b[2K" + line)
                    self.stream.flush()
                    self._spinner_visible = True
                index += 1
                self._spinner_stop.wait(0.12)
        except OSError:
            self.failed = True
        finally:
            with self._io_lock:
                if self._spinner_visible and self.stream is not None:
                    try:
                        self.stream.write("\r\x1b[2K")
                        self.stream.flush()
                    except OSError:
                        self.failed = True
                self._spinner_visible = False

    def start_spinner(self) -> None:
        if not self._spinner_enabled or not self.active:
            return
        self.stop_spinner()
        self._spinner_stop.clear()
        self._spinner_thread = threading.Thread(
            target=self._spinner_loop,
            name="agora-ai-sdlc-executor-spinner",
            daemon=True,
        )
        self._spinner_thread.start()

    def stop_spinner(self) -> None:
        thread = self._spinner_thread
        if thread is None:
            return
        self._spinner_stop.set()
        if thread is not threading.current_thread():
            thread.join(timeout=1.0)
        self._spinner_thread = None

    def event(self, code: str) -> None:
        if code not in _TEXT["en"] or not code.startswith("start."):
            return
        elapsed = time.monotonic() - self.started
        label = text(code, self.lang)
        progress = start_progress(code, label)
        self.write(f"[{elapsed:.1f}s] {progress or label}")
        if code == "start.executor-launch":
            self.start_spinner()

    def __exit__(self, *args) -> None:
        self.stop_spinner()
        if self.owns_stream and self.stream is not None:
            self.stream.close()


def watch(
    collect_snapshot,
    channel: HumanChannel,
    *,
    detail="normal",
    lang="en",
    interval=2.0,
    duration: float | None = None,
    clock=time.monotonic,
    sleep=time.sleep,
) -> int:
    """Local polling only; unchanged state emits a clearly labelled observer heartbeat."""
    if not math.isfinite(interval) or not 1 <= interval <= 60:
        raise ValueError("observation.invalid-interval")
    if duration is not None and (not math.isfinite(duration) or not 0 < duration <= 86400):
        raise ValueError("observation.invalid-duration")
    previous = None
    began = clock()
    try:
        while channel.active:
            snapshot = collect_snapshot()
            # Wall-clock sampling is not a meaningful state change.
            signature = json.dumps({k: v for k, v in snapshot.items() if k != "observed_at"}, sort_keys=True)
            if previous != signature:
                channel.write(render(snapshot, detail=detail, lang=lang))
            else:
                channel.write(f"[{clock() - began:.1f}s] {text('heartbeat', lang)}")
            previous = signature
            elapsed = clock() - began
            if duration is not None and elapsed >= duration:
                return 0
            sleep(min(interval, duration - elapsed) if duration is not None else interval)
    except KeyboardInterrupt:
        return 130
    return 2 if channel.failed or channel.limited else 0
