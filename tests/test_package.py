import subprocess
import sys

import pytest

from agora_ai_sdlc import __version__
from agora_ai_sdlc.cli import main


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_unknown_flag_fails():
    with pytest.raises(SystemExit) as exc:
        main(["--nope"])
    assert exc.value.code != 0


def test_module_importable_without_provider_sdk():
    out = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, agora_ai_sdlc; print([m for m in sys.modules if m.split('.')[0] in ('openai','anthropic')])",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert out.strip() == "[]"
