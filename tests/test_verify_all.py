import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "verify_all.py"
spec = importlib.util.spec_from_file_location("verify_all", SCRIPT)
verify_all = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify_all)


def test_links_pass_and_fail(tmp_path):
    (tmp_path / "a.md").write_text("[ok](b.md) [web](https://x.io) [anchor](#h)")
    (tmp_path / "b.md").write_text("hi")
    verify_all.check_links(tmp_path)
    (tmp_path / "c.md").write_text("[bad](missing.md)")
    with pytest.raises(verify_all.PhaseError) as exc:
        verify_all.check_links(tmp_path)
    assert "c.md -> missing.md" in str(exc.value)


def test_malformed_manifest_fails_manifest_phase(tmp_path):
    manifest = tmp_path / "src" / "pkg" / "flavor.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("schema: agora/flavor/v9\n")
    with pytest.raises(verify_all.PhaseError) as exc:
        verify_all.check_manifest(tmp_path)
    assert "manifest.schema" in str(exc.value) and exc.value.recovery


def test_empty_packs_and_samples_are_explicit(tmp_path):
    assert "nothing" in verify_all.check_packs(tmp_path)
    (tmp_path / "samples").mkdir()
    assert "nothing" in verify_all.check_samples(tmp_path)
    (tmp_path / "samples" / "s1").mkdir()
    with pytest.raises(verify_all.PhaseError):
        verify_all.check_samples(tmp_path)


def test_failure_names_phase_and_recovery(monkeypatch, capsys):
    def boom():
        raise verify_all.PhaseError("bad", "do this")

    monkeypatch.setattr(verify_all, "PHASES", [("demo", boom)])
    assert verify_all.main() == 1
    err = capsys.readouterr().err
    assert "FAILED phase: demo" in err and "recovery: do this" in err
