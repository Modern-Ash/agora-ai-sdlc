"""Credential-free provider-shaped worker for the existing-codebase pilot."""

import argparse
import json
import os
from pathlib import Path

IMPLEMENTATION = '''"""Catalog pricing with volume discounts."""

from decimal import Decimal

PRICES = {"adapter": Decimal("12.50"), "cable": Decimal("4.00")}


def quote(sku: str, quantity: int) -> Decimal:
    subtotal = PRICES[sku] * quantity
    return subtotal * Decimal("0.90") if quantity >= 10 else subtotal
'''

CORRECTION = '''"""Catalog pricing with validated volume discounts."""

from decimal import Decimal

PRICES = {"adapter": Decimal("12.50"), "cable": Decimal("4.00")}


def quote(sku: str, quantity: int) -> Decimal:
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
        raise ValueError("quantity must be a positive integer")
    subtotal = PRICES[sku] * quantity
    return subtotal * Decimal("0.90") if quantity >= 10 else subtotal
'''

FIRST_TEST = """
    def test_volume_discount(self):
        self.assertEqual(quote("adapter", 10), Decimal("112.5000"))
"""

CORRECTION_TEST = """
    def test_invalid_quantities(self):
        for quantity in (0, -1, True):
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                quote("adapter", quantity)
"""


def _append_test(path: Path, test: str) -> None:
    source = path.read_text(encoding="utf-8")
    marker = '\n\nif __name__ == "__main__":'
    if test.strip() not in source:
        source = source.replace(marker, test + marker)
        path.write_text(source, encoding="utf-8")


def _review(project: Path) -> dict:
    source = (project / "catalog.py").read_text(encoding="utf-8")
    corrected = "quantity < 1" in source and "isinstance(quantity, bool)" in source
    return {
        "outcome": "success",
        "phase": "review",
        "artifact": "review-report",
        "verdict": "approved" if corrected else "changes-requested",
        "finding": None if corrected else "invalid quantities are not rejected",
    }


def _adapter_output(adapter: str, payload: dict) -> str:
    usage = {"input_tokens": 11, "output_tokens": 7}
    if adapter == "codex":
        return "\n".join(
            json.dumps(item, sort_keys=True)
            for item in (
                {"type": "item.completed", "item": {"type": "agent_message", "text": payload["artifact"]}},
                {"type": "turn.completed", "result": payload, "usage": usage},
            )
        )
    if adapter == "claude":
        return json.dumps(
            {"type": "result", "subtype": "success", "is_error": False, "result": payload, "usage": usage},
            sort_keys=True,
        )
    return json.dumps(
        {
            "status": "ok",
            "payload": payload,
            "metrics": {"prompt_tokens": usage["input_tokens"], "completion_tokens": usage["output_tokens"]},
        },
        sort_keys=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", choices=("codex", "claude", "generic"), required=True)
    parser.add_argument("--operation", choices=("implement", "review", "correct"), required=True)
    parser.add_argument("--capture", type=Path, required=True)
    args = parser.parse_args()
    project = Path(os.environ["AGORA_PROJECT"])
    if args.operation == "implement":
        (project / "catalog.py").write_text(IMPLEMENTATION, encoding="utf-8")
        _append_test(project / "test_catalog.py", FIRST_TEST)
        payload = {"outcome": "success", "phase": "implementation", "artifact": "catalog.py"}
    elif args.operation == "correct":
        (project / "catalog.py").write_text(CORRECTION, encoding="utf-8")
        _append_test(project / "test_catalog.py", CORRECTION_TEST)
        payload = {"outcome": "success", "phase": "correction", "artifact": "catalog.py"}
    else:
        payload = _review(project)
    args.capture.parent.mkdir(parents=True, exist_ok=True)
    args.capture.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    print(_adapter_output(args.adapter, payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
