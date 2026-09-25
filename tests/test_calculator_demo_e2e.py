from pathlib import Path

from agora_ai_sdlc.brief_flow import prepare_brief_start
from agora_ai_sdlc.construction_reconciliation import (
    CONSTRUCTION_ARTIFACTS,
    prepare_construction_scaffold,
    reconcile_construction_execution,
)
from agora_ai_sdlc.guided import inspect_next
from agora_ai_sdlc.iteration_status import inspect_iteration
from agora_ai_sdlc.runtime_discovery import RuntimeDiscovery
from agora_ai_sdlc.wizard_actions import execute_in_session_action, next_in_session_action


def _runtime() -> RuntimeDiscovery:
    return RuntimeDiscovery(
        id="opencode",
        name="OpenCode",
        command="opencode",
        installed=True,
        executable="/usr/bin/opencode",
        responsive=True,
        version="test",
        configured=True,
    )


def _write_brief(root: Path) -> None:
    (root / "intent_brief.md").write_text(
        """# Percentage Discount Calculator

## Objective

Calculate the final price after applying a percentage discount.

## Requirements

- Price must be zero or greater.
- Percentage must be between 0 and 100.
- The result must be deterministic.

## Acceptance criteria

- 100 with 10 percent returns 90.
- 50 with 0 percent returns 50.
- 80 with 100 percent returns 0.
- Negative price is rejected.
- Percentage below 0 is rejected.
- Percentage above 100 is rejected.

## Constraints

- TypeScript.
- Unit tests required.
- No external services.
""",
        encoding="utf-8",
    )


def _write_product_outputs(root: Path) -> None:
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "src" / "discount.ts").write_text(
        """export function calculateDiscount(price: number, percentage: number): number {
  if (price < 0) throw new RangeError("price must be >= 0");
  if (percentage < 0 || percentage > 100) throw new RangeError("percentage must be between 0 and 100");
  return price * (1 - percentage / 100);
}
""",
        encoding="utf-8",
    )
    (root / "tests" / "discount.test.ts").write_text(
        """import test from "node:test";
import assert from "node:assert/strict";
import { calculateDiscount } from "../src/discount.ts";

test("discount examples", () => {
  assert.equal(calculateDiscount(100, 10), 90);
  assert.equal(calculateDiscount(50, 0), 50);
  assert.equal(calculateDiscount(80, 100), 0);
});

test("invalid values", () => {
  assert.throws(() => calculateDiscount(-1, 10), RangeError);
  assert.throws(() => calculateDiscount(100, -1), RangeError);
  assert.throws(() => calculateDiscount(100, 101), RangeError);
});
""",
        encoding="utf-8",
    )
    (root / "package.json").write_text(
        """{
  "name": "percentage-discount-calculator",
  "private": true,
  "type": "module",
  "scripts": {
    "build": "node --experimental-strip-types -e \\"import('./src/discount.ts')\\"",
    "test": "node --experimental-strip-types --test tests/discount.test.ts"
  }
}
""",
        encoding="utf-8",
    )


def _confirm_until_state(root: Path, swarm: str, work: str, target_state: str) -> None:
    for _ in range(8):
        decision = inspect_next(root, swarm=swarm, work=work)
        assert decision is not None
        if decision.state == target_state:
            return
        action = next_in_session_action(decision, root=root)
        assert action in {"approve", "transition"}
        execute_in_session_action(root, decision)
    raise AssertionError(f"did not reach {target_state}")


def test_calculator_brief_happy_path_reaches_completed(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AGORA_HOME", str(tmp_path / "home"))
    root = tmp_path / "calculator-demo"
    root.mkdir()
    _write_brief(root)

    result = prepare_brief_start(
        root,
        brief=Path("intent_brief.md"),
        agent="opencode",
        runtime_discovery=lambda _: (_runtime(),),
    )

    inception = inspect_next(root, swarm=result.swarm_id, work=result.work_id)
    assert inception is not None
    assert inception.state == "inception"
    assert inception.missing_artifacts == ()
    assert set(inception.missing_approvals) == {"product-owner", "developer"}

    _confirm_until_state(root, result.swarm_id, result.work_id, "construction")

    construction = inspect_next(root, swarm=result.swarm_id, work=result.work_id)
    assert construction is not None
    assert construction.state == "construction"
    assert set(construction.missing_artifacts) == {
        "domain-model",
        "logical-design",
        "implementation-plan",
        "test-strategy",
        "deployment-unit",
    }

    scaffold = prepare_construction_scaffold(root, construction)
    assert set(scaffold.generated_artifacts) == {kind for kind, _ in CONSTRUCTION_ARTIFACTS}
    assert set(scaffold.registered_artifacts) == {kind for kind, _ in CONSTRUCTION_ARTIFACTS}
    assert scaffold.criterion_stages == ("designed",)
    assert Path(scaffold.task_path).is_file()

    prepared_construction = inspect_next(root, swarm=result.swarm_id, work=result.work_id)
    assert prepared_construction is not None
    assert prepared_construction.missing_artifacts == ()

    _write_product_outputs(root)
    reconciled = reconcile_construction_execution(root, prepared_construction)

    assert reconciled.registered_artifacts == ()
    assert set(reconciled.criterion_stages) == {"built", "verified"}
    assert reconciled.verification_passed is True
    assert reconciled.verification_report is not None

    after_reconcile = inspect_next(root, swarm=result.swarm_id, work=result.work_id)
    assert after_reconcile is not None
    assert after_reconcile.state == "construction"
    assert after_reconcile.missing_artifacts == ()
    assert after_reconcile.missing_evidence == ()
    assert after_reconcile.unsatisfied_criteria == ()

    construction_action = next_in_session_action(after_reconcile, root=root)
    assert construction_action in {"approve", "transition"}
    execute_in_session_action(root, after_reconcile)
    if construction_action == "approve":
        ready_transition = inspect_next(root, swarm=result.swarm_id, work=result.work_id)
        assert ready_transition is not None
        assert next_in_session_action(ready_transition, root=root) == "transition"
        execute_in_session_action(root, ready_transition)

    operations = inspect_next(root, swarm=result.swarm_id, work=result.work_id)
    assert operations is not None
    assert operations.state == "operations"
    assert next_in_session_action(operations, root=root) == "prepare-local-operations"
    execute_in_session_action(root, operations)

    publish = inspect_next(root, swarm=result.swarm_id, work=result.work_id)
    assert publish is not None
    assert next_in_session_action(publish, root=root) == "publish-local-artifacts"
    publish_result = execute_in_session_action(root, publish)
    assert publish_result.kind == "local_artifacts_published"

    accept = inspect_next(root, swarm=result.swarm_id, work=result.work_id)
    assert accept is not None
    assert next_in_session_action(accept, root=root) == "accept-criteria"
    execute_in_session_action(root, accept)

    completion_gate = inspect_next(root, swarm=result.swarm_id, work=result.work_id)
    assert completion_gate is not None
    final_action = next_in_session_action(completion_gate, root=root)
    assert final_action in {"approve", "transition"}
    execute_in_session_action(root, completion_gate)

    if final_action == "approve":
        complete = inspect_next(root, swarm=result.swarm_id, work=result.work_id)
        assert complete is not None
        assert next_in_session_action(complete, root=root) == "transition"
        execute_in_session_action(root, complete)

    assert inspect_next(root, swarm=result.swarm_id, work=result.work_id) is None
    status = inspect_iteration(root, swarm=result.swarm_id, work=result.work_id)
    assert status.state == "completed"

    output = root / "output" / result.work_id
    assert (output / "MANIFEST.md").is_file()
    assert (output / "product" / "src" / "discount.ts").is_file()
    assert (output / "product" / "tests" / "discount.test.ts").is_file()
    assert (output / "product" / "package.json").is_file()
