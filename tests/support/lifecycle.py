"""Test wrapper: scopes AGORA_HOME with monkeypatch so tests do not leak environment."""

from agora_ai_sdlc import scenario


class Lifecycle(scenario.Lifecycle):
    def __init__(self, root, home, monkeypatch) -> None:
        monkeypatch.setenv("AGORA_HOME", str(home))
        super().__init__(root, home)
