"""Minimal CLI. The lifecycle CLI remains `agora` (Agora Core)."""

import argparse
import json
import runpy
import sys
from pathlib import Path

from agora_ai_sdlc import __version__
from agora_ai_sdlc.depth_profiles import DEFAULT, ProfileError, asset_root, resolve
from agora_ai_sdlc.starter import apply as apply_starter
from agora_ai_sdlc.starter import interactive as interactive_starter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agora-ai-sdlc")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")
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
    starter = sub.add_parser("starter-bootstrap", help="Preview and apply the Starter profile")
    starter.add_argument("--config", required=True)
    starter.add_argument("--target", required=True)
    starter.add_argument("--home", required=True)
    starter.add_argument("--yes", action="store_true", help="Apply the preview non-interactively")
    args = parser.parse_args(argv)
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
            AwsOriginalRuleError,
            ConformanceError,
            derive_aws_original_facts,
            evaluate,
            evaluate_project,
            render_human,
        )

        try:
            if args.derive:
                if args.facts:
                    print("conformance.input: --derive and --facts are mutually exclusive", file=sys.stderr)
                    return 2
                if args.profile != "aws-original":
                    print(
                        f"conformance.provider: no derived fact provider is available for {args.profile!r}",
                        file=sys.stderr,
                    )
                    return 2
                profile = load_profile(args.profile)
                facts = derive_aws_original_facts(Path(args.root))
                report = evaluate(profile, facts, facts_source="derived:aws-original-rules/v1")
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
        from agora_ai_sdlc.adaptive_planning import AdaptivePlanningError, validate_adaptive_plan
        from agora_ai_sdlc.plans import PlanError, parse_plan

        try:
            plan = parse_plan(Path(args.path).read_text(encoding="utf-8"))
            decision = validate_adaptive_plan(
                plan,
                args.pathway,
                depth=args.depth,
                adoption_profile=args.profile,
            )
        except (OSError, PlanError, AdaptivePlanningError) as error:
            print(error, file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(decision.snapshot(), sort_keys=True))
        else:
            print(
                f"authorized pathway={decision.pathway} depth={decision.effective_depth} "
                f"executed={len(decision.executed_steps)} skipped={len(decision.skipped_steps)}"
            )
        return 0
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
