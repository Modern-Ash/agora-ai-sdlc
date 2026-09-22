"""Minimal CLI. The lifecycle CLI remains `agora` (Agora Core)."""

import argparse
import json
import runpy
import subprocess
import sys
from pathlib import Path

from agora_ai_sdlc import __version__
from agora_ai_sdlc.depth_profiles import DEFAULT, ProfileError, asset_root, resolve
from agora_ai_sdlc.i18n import SUPPORTED_LANGUAGES, resolve_language
from agora_ai_sdlc.starter import apply as apply_starter
from agora_ai_sdlc.starter import interactive as interactive_starter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agora-ai-sdlc")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")
    from agora_ai_sdlc.observation_cli import add_commands

    add_commands(sub)
    show = sub.add_parser("profile", help="Print the resolved obligations of a depth profile as JSON")
    show.add_argument("depth", nargs="?", default=DEFAULT)
    sample = sub.add_parser("run-sample", help="Run a bundled credential-free sample and print a JSON summary")
    sample.add_argument("name")
    self_test = sub.add_parser("self-test", help="Verify all bundled AI-SDLC assets in temporary repositories")
    self_test.add_argument("--json", action="store_true", help="Print the schema-versioned result as JSON")
    conformance = sub.add_parser("conformance", help="Evaluate a compatibility profile against local project facts")
    conformance.add_argument("profile")
    conformance.add_argument("--facts", help="Explicit conformance facts YAML file")
    conformance.add_argument("--root", default=".", help="Project root used for default local facts discovery")
    conformance.add_argument("--json", action="store_true", help="Print the schema-versioned report as JSON")
    conformance.add_argument("--strict", action="store_true", help="Return non-zero when the report contains FAIL")
    conformance.add_argument(
        "--derive",
        action="store_true",
        help="Derive supported compatibility facts from the local repository instead of reading a facts file",
    )
    plan_validate = sub.add_parser("plan-validate", help="Validate an approved plan against an adaptive pathway")
    plan_validate.add_argument("path")
    plan_validate.add_argument("--pathway", required=True)
    plan_validate.add_argument("--depth")
    plan_validate.add_argument("--profile")
    plan_validate.add_argument("--json", action="store_true")
    plan_validate.add_argument("--artifacts", help="artifact directory; enforces brown-field semantic elevation")
    context = sub.add_parser("context", help="Assemble deterministic context for an Intent, Unit, artifact or Bolt")
    context.add_argument("artifacts", help="directory of artifact documents")
    context.add_argument("id", help="artifact id or Bolt (BLP-001/bolt-id)")
    context.add_argument("--direction", choices=["backward", "forward", "both"], default="both")
    context.add_argument("--depth", type=int)
    context.add_argument("--max-tokens", type=int)
    context.add_argument("--strict", action="store_true")
    context.add_argument("--content", action="store_true", help="include document text")
    context.add_argument("--json", action="store_true")
    bolt_validate = sub.add_parser(
        "bolt-validate", help="Validate a Bolt plan and print Unit -> Bolt -> evidence trace"
    )
    bolt_validate.add_argument("path")
    bolt_validate.add_argument("--json", action="store_true")
    runtimes = sub.add_parser("runtimes", help="Detect local AI CLI runtimes without reading credentials")
    runtimes.add_argument("--root", default=".", help="Project root used to correlate configured runtimes")
    runtimes.add_argument("--json", action="store_true", help="Print deterministic machine-readable output")
    runtimes.add_argument("--timeout", type=float, default=2.0, help="Probe timeout in seconds")
    runtimes.add_argument("--lang", choices=SUPPORTED_LANGUAGES, help="Presentation language")
    doctor = sub.add_parser("doctor", help="Diagnose the local AI-SDLC environment")
    doctor.add_argument("--root", default=".", help="Project root")
    doctor.add_argument("--json", action="store_true", help="Print machine-readable diagnostics")
    doctor.add_argument("--lang", choices=SUPPORTED_LANGUAGES, help="Presentation language")
    install = sub.add_parser("install", help="Configure and bootstrap an Agora AI-SDLC project")
    install.add_argument("target", nargs="?", default=".")
    install.add_argument("--home", default="~/.agora")
    install.add_argument("--config", help="Read a reproducible YAML/JSON install config")
    install.add_argument("--write-config", help="Write the resolved install config without applying")
    install.add_argument("--yes", action="store_true", help="Apply without interactive confirmation")
    start = sub.add_parser("start", help="Start AI-SDLC work from a real issue and stop at human plan review")
    start.add_argument("--issue", type=int, required=True, help="Issue number to use as the candidate Intent source")
    start.add_argument("--project", help="GitHub owner/repository; inferred from origin when omitted")
    start.add_argument(
        "--agent", choices=["codex", "claude", "opencode", "ollama"], help="AI runtime for Level 1 Plan preparation"
    )
    start.add_argument("--swarm", default="delivery", help="Agora delivery swarm used for the governed issue read")
    start.add_argument("--actor", default="product-owner", help="Agora actor used for the governed issue read")
    start.add_argument("--root", default=".", help="Project root")
    start.add_argument("--json", action="store_true", help="Print machine-readable start handoff")
    start.add_argument("--lang", choices=SUPPORTED_LANGUAGES, help="Presentation language")
    start.add_argument("--ui-file", help="Write human progress to a new file, separate from agent output")
    guided = sub.add_parser("continue", help="Show the next governed decision in human-friendly AI-SDLC language")
    guided.add_argument("--root", default=".", help="Project root")
    guided.add_argument("--swarm", help="Limit to one delivery swarm")
    guided.add_argument("--work", help="Limit to one work item")
    guided.add_argument("--expert", action="store_true", help="Include raw Agora Core governance blockers")
    guided.add_argument("--commands", action="store_true", help="Show the underlying grouped Agora Core command bundle")
    guided.add_argument("--json", action="store_true", help="Print the structured guided decision as JSON")
    guided.add_argument("--skill", action="store_true", help="Print the packaged guided-agent skill path")
    guided.add_argument("--non-interactive", action="store_true", help="Force one-shot output even on a terminal")
    guided.add_argument("--lang", choices=SUPPORTED_LANGUAGES, help="Presentation language")
    status = sub.add_parser("status", help="Show rich local/Core iteration status without invoking an LLM")
    status.add_argument("--root", default=".", help="Project root")
    status.add_argument("--swarm", help="Limit to one delivery swarm")
    status.add_argument("--work", help="Limit to one work item")
    status.add_argument("--detail", action="store_true", help="Include observed artifacts, evidence and activity")
    status.add_argument("--diagnostic", action="store_true", help="Include governance diagnostics")
    status.add_argument("--json", action="store_true", help="Print full structured iteration status")
    status.add_argument(
        "--agent-context",
        action="store_true",
        help="Print compact bounded context for an executor instead of the human status view",
    )
    starter = sub.add_parser("starter-bootstrap", help="Preview and apply the Starter profile")
    starter.add_argument("--config", required=True)
    starter.add_argument("--target", required=True)
    starter.add_argument("--home", required=True)
    starter.add_argument("--yes", action="store_true", help="Apply the preview non-interactively")
    args = parser.parse_args(argv)
    if args.command in {"observe", "skill"}:
        from agora_ai_sdlc.observation_cli import dispatch

        return dispatch(args)
    if args.command == "self-test":
        from agora_ai_sdlc.conformance import run_self_test

        summary = run_self_test(progress=lambda message: print(f"[self-test] {message}", file=sys.stderr))
        if args.json:
            print(json.dumps(summary, sort_keys=True))
        else:
            outcome = "passed" if summary["ok"] else "failed"
            print(f"AI-SDLC self-test {outcome}: {len(summary['checks'])} checks")
            if summary["workspace"]:
                print(f"Diagnostic workspace: {summary['workspace']}")
        return 0 if summary["ok"] else 1
    if args.command == "conformance":
        from agora_ai_sdlc.compatibility_profiles import load_profile
        from agora_ai_sdlc.conformance import (
            LG_ENTERPRISE_FACTS_SOURCE,
            AwsOriginalRuleError,
            ConformanceError,
            derive_aws_original_facts,
            derive_lg_enterprise_facts,
            evaluate,
            evaluate_project,
            render_human,
        )

        try:
            if args.derive:
                if args.facts:
                    print("conformance.input: --derive and --facts are mutually exclusive", file=sys.stderr)
                    return 2
                profile = load_profile(args.profile)
                if args.profile == "aws-original":
                    facts = derive_aws_original_facts(Path(args.root))
                    source = "derived:aws-original-rules/v1"
                elif args.profile == "lg-enterprise":
                    facts = derive_lg_enterprise_facts(Path(args.root))
                    source = LG_ENTERPRISE_FACTS_SOURCE
                else:
                    print(
                        f"conformance.provider: no derived fact provider is available for {args.profile!r}",
                        file=sys.stderr,
                    )
                    return 2
                report = evaluate(profile, facts, facts_source=source)
            else:
                report = evaluate_project(
                    args.profile,
                    project_root=Path(args.root),
                    facts_path=Path(args.facts) if args.facts else None,
                )
        except (ConformanceError, AwsOriginalRuleError) as error:
            print(error, file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(report.snapshot(), sort_keys=True))
        else:
            print(render_human(report))
        return 1 if args.strict and report.has_failures else 0
    if args.command == "plan-validate":
        from agora_ai_sdlc.adaptive_planning import AdaptivePlanningError, load_pathway, validate_adaptive_plan
        from agora_ai_sdlc.context_graph import ContextError, load_artifacts
        from agora_ai_sdlc.plans import PlanError, parse_plan
        from agora_ai_sdlc.semantic_elevation import (
            SemanticElevationError,
            requires_elevation,
            validate_semantic_elevation,
        )

        try:
            plan = parse_plan(Path(args.path).read_text(encoding="utf-8"))
            decision = validate_adaptive_plan(
                plan,
                args.pathway,
                depth=args.depth,
                adoption_profile=args.profile,
            )
            elevation = None
            if args.artifacts and requires_elevation(load_pathway(args.pathway)):
                documents = load_artifacts(Path(args.artifacts))
                elevation = validate_semantic_elevation(
                    [artifact for _, _, artifact in documents], str(plan.artifact.front.get("work"))
                )
        except (OSError, PlanError, AdaptivePlanningError, ContextError, SemanticElevationError) as error:
            print(error, file=sys.stderr)
            return 2
        if args.json:
            snapshot = decision.snapshot()
            if elevation is not None:
                snapshot["semantic_elevation"] = {"static": elevation[0], "dynamic": elevation[1]}
            print(json.dumps(snapshot, sort_keys=True))
        else:
            print(
                f"authorized pathway={decision.pathway} depth={decision.effective_depth} "
                f"executed={len(decision.executed_steps)} skipped={len(decision.skipped_steps)}"
            )
        return 0
    if args.command == "context":
        from agora_ai_sdlc.context_graph import ContextError, context_bundle, graph_from_directory

        try:
            bundle = context_bundle(
                graph_from_directory(Path(args.artifacts)),
                args.id,
                direction=args.direction,
                max_depth=args.depth,
                max_tokens=args.max_tokens,
                strict=args.strict,
            )
        except (OSError, ContextError) as error:
            print(error, file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(bundle.snapshot(include_text=args.content), sort_keys=True))
        else:
            for item in bundle.items:
                print(f"{item.distance} {item.relation} {item.id} ({item.kind}) {item.path} ~{item.tokens}t")
                if args.content:
                    print(bundle.text[item.id])
            if bundle.omitted:
                print(f"omitted (budget): {', '.join(bundle.omitted)}")
        return 0
    if args.command == "bolt-validate":
        from agora_ai_sdlc.bolts import BoltError, parse_bolt_plan, trace

        try:
            summary = trace(parse_bolt_plan(Path(args.path).read_text(encoding="utf-8")))
        except (OSError, BoltError) as error:
            print(error, file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(summary, sort_keys=True))
        else:
            print(
                f"valid unit={summary['unit']} bolts={len(summary['bolts'])} ready={','.join(summary['ready']) or '-'} "
                f"construction_evidence_complete={summary['construction_evidence_complete']}"
            )
        return 0
    if args.command == "runtimes":
        from agora_ai_sdlc.runtime_discovery import discover_runtimes, render_runtimes

        discoveries = discover_runtimes(
            Path(args.root).expanduser(),
            timeout_seconds=args.timeout,
        )
        if args.json:
            print(json.dumps([item.snapshot() for item in discoveries], sort_keys=True))
        else:
            language = resolve_language(args.lang)
            print(render_runtimes(discoveries) if language == "en" else render_runtimes(discoveries, lang=language))
        return 0
    if args.command == "doctor":
        from agora_ai_sdlc.doctor import render_doctor, run_doctor

        checks, runtimes_found = run_doctor(Path(args.root).expanduser())
        if args.json:
            print(
                json.dumps(
                    {
                        "checks": [item.snapshot() for item in checks],
                        "runtimes": [item.snapshot() for item in runtimes_found],
                    },
                    sort_keys=True,
                )
            )
        else:
            language = resolve_language(args.lang)
            print(
                render_doctor(checks, runtimes_found)
                if language == "en"
                else render_doctor(checks, runtimes_found, lang=language)
            )
        return 0
    if args.command == "start":
        from agora_ai_sdlc.observation_ui import HumanChannel, safe_text
        from agora_ai_sdlc.start_flow import StartFlowError, prepare_start, render_start

        try:
            with HumanChannel(
                path=Path(args.ui_file) if args.ui_file else None,
                stream=sys.stderr if not args.json and not args.ui_file and sys.stderr.isatty() else None,
                lang=resolve_language(args.lang),
            ) as channel:
                options = {"progress": channel.event} if channel.active else {}
                result = prepare_start(
                    Path(args.root),
                    issue=args.issue,
                    project=args.project,
                    agent=args.agent,
                    swarm=args.swarm,
                    actor=args.actor,
                    **options,
                )
                if args.json:
                    print(json.dumps(result.snapshot(), sort_keys=True))
                elif args.ui_file:
                    channel.write(render_start(result, lang=resolve_language(args.lang)))
                else:
                    print(render_start(result, lang=resolve_language(args.lang)))
        except (OSError, StartFlowError, ValueError, PermissionError) as error:
            print(safe_text(str(error), max_chars=1024), file=sys.stderr)
            return 2
        return 0
    if args.command == "continue":
        from agora_ai_sdlc.guided import inspect_next, render, skill_path

        if args.skill:
            print(skill_path())
            return 0
        root = Path(args.root).expanduser()
        interactive = (
            not args.non_interactive
            and not args.json
            and not args.commands
            and not args.expert
            and sys.stdin.isatty()
            and sys.stdout.isatty()
        )
        if interactive:
            from agora_ai_sdlc.guided_session import run_interactive

            try:
                language = resolve_language(args.lang)
                if language == "en":
                    run_interactive(root, swarm=args.swarm, work=args.work)
                else:
                    run_interactive(root, swarm=args.swarm, work=args.work, lang=language)
            except (OSError, ValueError) as error:
                print(error, file=sys.stderr)
                return 2
            return 0
        try:
            language = resolve_language(args.lang)
            decision = (
                inspect_next(root, swarm=args.swarm, work=args.work)
                if language == "en"
                else inspect_next(root, swarm=args.swarm, work=args.work, lang=language)
            )
        except (OSError, ValueError) as error:
            print(error, file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(decision.snapshot() if decision is not None else {"status": "clear"}, sort_keys=True))
        else:
            print(
                render(decision, expert=args.expert, show_commands=args.commands)
                if language == "en"
                else render(decision, expert=args.expert, show_commands=args.commands, lang=language)
            )
        return 0
    if args.command == "status":
        from agora_ai_sdlc.iteration_status import inspect_iteration, render_status

        try:
            status_result = inspect_iteration(
                Path(args.root),
                swarm=args.swarm,
                work=args.work,
            )
        except (OSError, ValueError) as error:
            print(error, file=sys.stderr)
            return 2
        if args.agent_context:
            print(json.dumps(status_result.agent_context(), sort_keys=True))
        elif args.json:
            print(json.dumps(status_result.snapshot(), sort_keys=True))
        else:
            level = "diagnostic" if args.diagnostic else ("detail" if args.detail else "normal")
            print(render_status(status_result, detail=level))
        return 0
    if args.command == "install":
        from agora_ai_sdlc import installer as project_installer

        target = Path(args.target).expanduser()
        home = Path(args.home).expanduser()
        try:
            config = (
                project_installer.load_config(Path(args.config)) if args.config else project_installer.wizard(target)
            )
            if args.write_config:
                output = Path(args.write_config)
                output.write_text(project_installer.render_config(config), encoding="utf-8")
                print(json.dumps({"status": "configured", "config": str(output)}, sort_keys=True))
                return 0
            plan = project_installer.preview(config, target)
            if not args.yes:
                print(json.dumps(plan, sort_keys=True))
                if input("Apply Agora AI-SDLC installation? [y/N] ").strip().casefold() not in {
                    "y",
                    "yes",
                }:
                    print(json.dumps({"status": "cancelled"}, sort_keys=True))
                    return 0
            print(json.dumps(project_installer.apply(config, target, home), sort_keys=True))
            return 0
        except (project_installer.InstallerError, OSError, subprocess.CalledProcessError) as error:
            print(error, file=sys.stderr)
            return 2
    if args.command == "starter-bootstrap":
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
        target, home = Path(args.target), Path(args.home)
        if args.yes:
            print(json.dumps(apply_starter(config, target, home), sort_keys=True))
        else:
            result = interactive_starter(config, target, home)
            if result is None:
                print(json.dumps({"status": "cancelled"}, sort_keys=True))
            else:
                print(json.dumps(result, sort_keys=True))
        return 0
    if args.command == "run-sample":
        script = asset_root("samples") / args.name / "run.py"
        if not script.is_file() or "/" in args.name or args.name.startswith("."):
            print(f"unknown sample {args.name!r}", file=sys.stderr)
            return 2
        summary = runpy.run_path(str(script), run_name="sample")["main"]()
        return 0 if summary["final_state"] == "completed" and summary["validate"] == "ok" else 1
    if args.command == "profile":
        try:
            print(json.dumps(resolve(args.depth).snapshot(), indent=2))
        except ProfileError as error:
            print(error, file=sys.stderr)
            return 2
        return 0
    parser.print_help()
    return 0
