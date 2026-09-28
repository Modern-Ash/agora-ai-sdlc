from agora_ai_sdlc.decision_plane import DecisionAnswer, DecisionResult
from agora_ai_sdlc.verification import AcceptanceCoverage, VerificationCommand, VerificationReport
from agora_ai_sdlc.verification_triage import triage_verification_failure


def report(status="failed", stderr="cannot find symbol Foo") -> VerificationReport:
    return VerificationReport(
        schema="agora-ai-sdlc/verification-report/v1",
        work="issue-304",
        head="abc",
        executed=True,
        commands=(
            VerificationCommand(
                command="mvn test",
                argv=("mvn", "test"),
                allowed=True,
                status=status,
                exit_code=1 if status != "passed" else 0,
                stdout="",
                stderr=stderr,
                elapsed_seconds=1.0,
            ),
        ),
        acceptance_coverage=(AcceptanceCoverage("works", ()),),
        all_executed_commands_passed=status == "passed",
        report_path=None,
    )


class Provider:
    name = "laya"
    model = "test"

    def __init__(self, value, confidence=0.99):
        self.value = value
        self.confidence = confidence

    def decide(self, state, questions):
        return DecisionResult(
            provider=self.name,
            model=self.model,
            answers={
                "failure_class": DecisionAnswer(
                    "failure_class",
                    "choice",
                    self.value,
                    self.confidence,
                )
            },
            latency_ms=2.0,
        )


def test_compile_failure_routes_to_local_repair():
    result = triage_verification_failure(report(), provider=Provider("compile"))

    assert result is not None
    assert result.failure_class == "compile"
    assert result.route == "local-repair"
    assert result.escalated is False


def test_unknown_failure_routes_to_paid_advisory():
    result = triage_verification_failure(report(stderr="opaque failure"), provider=Provider("unknown"))

    assert result is not None
    assert result.route == "paid-advisory"


def test_security_failure_routes_to_paid_advisory():
    result = triage_verification_failure(report(stderr="credential policy failed"), provider=Provider("security"))

    assert result is not None
    assert result.route == "paid-advisory"


def test_low_confidence_known_class_fails_open_to_paid_advisory():
    result = triage_verification_failure(report(), provider=Provider("compile", confidence=0.4))

    assert result is not None
    assert result.escalated is True
    assert result.route == "paid-advisory"


def test_successful_verification_needs_no_laya_triage():
    result = triage_verification_failure(report(status="passed"), provider=Provider("compile"))

    assert result is None


def test_diagnostic_digest_is_stable_for_same_failure():
    first = triage_verification_failure(report(), provider=Provider("compile"))
    second = triage_verification_failure(report(), provider=Provider("compile"))

    assert first is not None and second is not None
    assert first.diagnostic_digest == second.diagnostic_digest
