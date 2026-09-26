from agora_ai_sdlc import local_operations


def test_security_scan_ignores_lockfiles_but_flags_source(monkeypatch, tmp_path):
    (tmp_path / "package-lock.json").write_text('{"resolved": "https://registry.npmjs.org/x"}', encoding="utf-8")
    (tmp_path / "app.ts").write_text("fetch('https://evil.example')", encoding="utf-8")
    monkeypatch.setattr(
        local_operations,
        "changed_product_files",
        lambda root, work: ("package-lock.json", "app.ts"),
    )

    _, findings = local_operations._scan_local_product(tmp_path, "w")

    assert findings == ("network-access:app.ts",)
