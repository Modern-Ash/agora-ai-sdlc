import sys
import types

from agora_ai_sdlc.laya_provider import LayaDecisionProvider
from agora_ai_sdlc.decision_plane import DecisionQuestion


QUESTION = DecisionQuestion(
    id="route",
    type="choice",
    instructions="choose",
    criteria={"local": "local"},
)


def test_router_initialization_does_not_leak_third_party_stderr(monkeypatch, capsys):
    class NoisyRouter:
        def __init__(self):
            print("Fetching model files", file=sys.stderr)

    monkeypatch.setitem(sys.modules, "laya", types.SimpleNamespace(Router=NoisyRouter))
    provider = LayaDecisionProvider()

    assert isinstance(provider._get_router(), NoisyRouter)
    assert capsys.readouterr().err == ""


def test_deferred_predict_progress_does_not_leak_to_stderr(monkeypatch, capsys):
    class NoisyRouter:
        def predict(self, state, questions, model=None):
            print("Fetching 5 files", file=sys.stderr)
            return {
                "answers": {
                    "route": {
                        "choice": "local",
                        "confidence": 1.0,
                        "probabilities": {"local": 1.0},
                    }
                }
            }

    monkeypatch.setitem(sys.modules, "laya", types.SimpleNamespace(Router=NoisyRouter))
    result = LayaDecisionProvider().decide({"work": "x"}, (QUESTION,))

    assert result.answers["route"].value == "local"
    assert capsys.readouterr().err == ""
