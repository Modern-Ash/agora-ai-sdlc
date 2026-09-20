import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
SECTION = "## Prerequisites, permissions and failure modes"


def _supported_core() -> str:
    text = (ROOT / "src/agora_ai_sdlc/flavor/flavor.yaml").read_text(encoding="utf-8")
    return re.search(r'^supported_core:\s*"([^"]+)"', text, re.MULTILINE).group(1)


def test_declared_core_range_is_identical_in_manifest_package_and_policy():
    supported = _supported_core()
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f"agora-framework{supported}" in pyproject
    policy = (ROOT / "docs/development/versioning-and-releases.md").read_text(encoding="utf-8")
    assert f"Current range: `{supported}`" in policy


def test_release_policy_is_linked_and_states_the_compatibility_rules():
    policy = (ROOT / "docs/development/versioning-and-releases.md").read_text(encoding="utf-8")
    for required in ("Semantic Versioning", "verify_all.py", "CHANGELOG.md", "not assumed compatible"):
        assert required in policy
    assert "versioning-and-releases.md" in (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")


def test_every_integration_profile_documents_prerequisites_permissions_and_failure_modes():
    documents = [
        "github.md", "gitlab-jira.md", "ci.md", "security.md", "observability.md",
    ]  # fmt: skip
    for name in documents:
        text = (ROOT / "docs/integrations" / name).read_text(encoding="utf-8")
        lowered = text.lower()
        assert "prerequisite" in lowered, name
        assert "permission" in lowered, name
        assert re.search(r"failure|fail closed|fails closed", lowered), name


def test_new_profile_sections_cover_all_three_topics():
    for name in ("ci.md", "security.md", "observability.md"):
        text = (ROOT / "docs/integrations" / name).read_text(encoding="utf-8")
        section = text.split(SECTION, 1)[1].split("\n## ", 1)[0]
        for label in ("**Prerequisites.**", "**Permissions.**", "**Failure modes.**"):
            assert label in section, (name, label)
