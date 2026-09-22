"""CLI handlers for read-only visibility and progressive skill discovery."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from agora_ai_sdlc.i18n import SUPPORTED_LANGUAGES, resolve_language
from agora_ai_sdlc.observation import MAX_ITEMS, agent_summary, collect
from agora_ai_sdlc.observation_ui import DETAILS, HumanChannel, render, watch
from agora_ai_sdlc.skill_resources import PHASES, bundle, install_resources, resource_paths, resource_root


def add_commands(sub) -> None:
    observe = sub.add_parser(
        "observe", help="Observe an exact Core Work without running an agent or changing authority"
    )
    observe.add_argument("--root", default=".")
    observe.add_argument("--swarm", required=True)
    observe.add_argument("--work", required=True)
    observe.add_argument(
        "--detail", choices=DETAILS, default="normal", help="Human view only; never changes agent context"
    )
    observe.add_argument("--lang", choices=SUPPORTED_LANGUAGES)
    observe.add_argument("--limit", type=int, default=20, help=f"Maximum records per section (1-{MAX_ITEMS})")
    observe.add_argument(
        "--json", action="store_true", help="One compact machine snapshot; excludes the human activity stream"
    )
    observe.add_argument("--watch", action="store_true", help="Local polling; no LLM calls")
    observe.add_argument("--interval", type=float, default=2.0, help="Watch interval in seconds (1-60)")
    observe.add_argument("--duration", type=float, help="Stop watching after this many seconds (maximum 86400)")
    observe.add_argument("--ui-file", help="New private human-only output file, separate from captured stdout/stderr")
    skill = sub.add_parser("skill", help="Load only the root skill and requested phase, identically for any executor")
    skill.add_argument("--phase", choices=PHASES)
    skill.add_argument(
        "--install",
        action="store_true",
        help="Explicitly sync only packaged guided skill resources into an existing project",
    )
    skill.add_argument("--root", default=".", help="Existing project for --install")
    skill.add_argument(
        "--json", action="store_true", help="Resource references, hashes and byte sizes; no content by default"
    )
    skill.add_argument("--content", action="store_true", help="Explicitly include instructions in JSON")
    skill.add_argument("--paths", action="store_true", help="Print packaged resource paths only")


def dispatch(args) -> int:
    try:
        if args.command == "skill":
            if args.install:
                if args.phase or args.content or args.paths:
                    raise ValueError("skill.incompatible-output-options")
                from agora.workspace import AgoraWorkspace

                project = AgoraWorkspace(cwd=Path(args.root).expanduser()).project_root()
                destination = project / ".agora" / "skills" / "agora-ai-sdlc-guided"
                installed = install_resources(resource_root(), destination)
                result = {
                    "schema": "agora-ai-sdlc/skill-install/v1",
                    "status": "installed",
                    "path": str(installed.relative_to(project)),
                    "resources": 1 + len(PHASES),
                }
                print(
                    json.dumps(result, sort_keys=True)
                    if args.json
                    else f"Guided skill synchronized: {result['path']} ({result['resources']} resources)"
                )
                return 0
            if args.paths and (args.json or args.content):
                raise ValueError("skill.incompatible-output-options")
            if args.content and not args.json:
                raise ValueError("skill.content-requires-json")
            if args.paths:
                print("\n".join(str(p) for p in resource_paths(args.phase)))
            else:
                result = bundle(args.phase, include_content=args.content or not args.json)
                if args.json:
                    print(json.dumps(result, sort_keys=True))
                else:
                    print("\n\n".join(r["content"] for r in result["resources"]))
            return 0
        if args.json and args.watch:
            raise ValueError("observation.watch-is-human-only")
        if args.duration is not None and not args.watch:
            raise ValueError("observation.duration-requires-watch")
        if not 1 <= args.limit <= MAX_ITEMS:
            raise ValueError("observation.invalid-limit")
        language = resolve_language(args.lang)

        def read() -> dict:
            return collect(Path(args.root).expanduser(), swarm=args.swarm, work=args.work, limit=args.limit)

        with HumanChannel(
            path=Path(args.ui_file) if args.ui_file else None,
            stream=None if args.json or args.ui_file else sys.stdout,
            lang=language,
        ) as channel:
            if args.watch:
                return watch(
                    read, channel, detail=args.detail, lang=language, interval=args.interval, duration=args.duration
                )
            snapshot = read()
            if channel.active:
                channel.write(render(snapshot, detail=args.detail, lang=language))
            if args.json:
                print(json.dumps(agent_summary(snapshot), sort_keys=True))
            return 2 if snapshot["status"] != "observed" or channel.failed or channel.limited else 0
    except (OSError, ValueError) as error:
        # Only our own stable codes are public. No raw exception or filesystem detail.
        public_errors = {
            "observation.invalid-scope",
            "observation.invalid-limit",
            "observation.invalid-interval",
            "observation.invalid-duration",
            "observation.watch-is-human-only",
            "observation.duration-requires-watch",
            "observation.ui-path-protected",
            "observation.ui-path-symlink",
            "observation.ui-path-not-file",
            "skill.unknown-phase",
            "skill.resource-unavailable",
            "skill.resource-too-large",
            "skill.incompatible-output-options",
            "skill.content-requires-json",
            "skill.install-symlink",
            "skill.install-not-file",
        }
        code = (
            str(error)
            if isinstance(error, ValueError) and str(error) in public_errors
            else "observation.output-unavailable"
        )
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {"schema": "agora-ai-sdlc/observation-error/v1", "status": "unavailable", "code": code},
                    sort_keys=True,
                )
            )
        else:
            print(code, file=sys.stderr)
        return 2
