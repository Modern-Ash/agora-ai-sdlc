import sys
import types

from agora_ai_sdlc.laya_provider import LayaDecisionProvider


def test_router_initialization_does_not_leak_third_party_stderr(monkeypatch, capsys):
    class NoisyRouter:
        def __init__(self):
            print("Fetching model files", file=sys.stderr)

    monkeypatch.setitem(sys.modules, "laya", types.SimpleNamespace(Router=NoisyRouter))
    provider = LayaDecisionProvider()

    assert isinstance(provider._get_router(), NoisyRouter)
    assert capsys.readouterr().err == ""
