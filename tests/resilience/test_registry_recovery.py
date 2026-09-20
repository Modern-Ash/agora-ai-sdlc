import pytest
from agora.workspace import AgoraWorkspace
from test_enterprise import _config, _distribution, _files, _index, _project, _release

from agora_ai_sdlc import enterprise
from agora_ai_sdlc.enterprise import apply_upgrade, install, preview_install, preview_upgrade


def _assert_original_files_unchanged(project, before):
    after = _files(project)
    assert all(after.get(path) == contents for path, contents in before.items())


@pytest.mark.parametrize(
    "boundary",
    ("install-preview", "install-apply", "upgrade-preview", "upgrade-apply"),
)
def test_registry_failure_injection_preserves_valid_prior_snapshot(boundary, tmp_path, monkeypatch):
    project = _project(tmp_path, monkeypatch)
    root, private_key, public_key, index = _distribution(tmp_path)

    if boundary.startswith("install"):
        config = _config(index, public_key)
        before = _files(project)
        if boundary == "install-preview":
            monkeypatch.setattr(
                enterprise,
                "inspect_registry_release",
                lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("injected preview failure")),
            )
            operation = lambda: preview_install(config, project)
        else:
            monkeypatch.setattr(
                AgoraWorkspace,
                "install_registry",
                lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("injected install failure")),
            )
            operation = lambda: install(config, project)

        with pytest.raises(OSError, match="injected"):
            operation()
        _assert_original_files_unchanged(project, before)
        assert not (project / ".agora" / "registries" / "organization-registry").exists()
        assert AgoraWorkspace(cwd=project).validate().ok
        return

    installed = install(_config(index, public_key), project)
    _index(root, [_release(root, private_key, "2.0.0"), _release(root, private_key, "1.0.0")])
    config = _config(index, public_key, "2.0.0")
    before = _files(project)
    original_update = AgoraWorkspace.update_registry

    if boundary == "upgrade-preview":
        monkeypatch.setattr(
            AgoraWorkspace,
            "update_registry",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("injected upgrade preview failure")),
        )
        operation = lambda: preview_upgrade(config, project)
    else:

        def fail_apply(self, data):
            if data.apply:
                raise OSError("injected upgrade apply failure")
            return original_update(self, data)

        monkeypatch.setattr(AgoraWorkspace, "update_registry", fail_apply)
        plan = preview_upgrade(config, project)
        operation = lambda: apply_upgrade(config, project, reviewed_checksum=plan["checksum"])

    with pytest.raises(OSError, match="injected"):
        operation()
    _assert_original_files_unchanged(project, before)
    snapshot = next(
        item for item in AgoraWorkspace(cwd=project).list_registries() if item.id == "organization-registry"
    )
    assert snapshot.version == "1.0.0" and snapshot.checksum == installed["checksum"]
    assert AgoraWorkspace(cwd=project).validate().ok
