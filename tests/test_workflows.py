"""The CI release-invocation job runs release.yml's exact wheel-test command.

Skipped (per test, so the collected IDs match in the sdist) where .github/ is
absent, e.g. an unpacked sdist.
"""
import re
from pathlib import Path

import pytest

WF = Path(__file__).resolve().parent.parent / ".github" / "workflows"
needs_workflows = pytest.mark.skipif(not WF.is_dir(), reason=".github/workflows not present (not a checkout)")


def _pytest_invocation(text: str) -> str:
    """The wheel-venv pytest command, with its backslash continuations joined."""
    m = re.search(r"(/tmp/wheel_test_venv/bin/pytest tests/(?:[^\n\\]|\\\n)*)", text)
    assert m, "no /tmp/wheel_test_venv/bin/pytest invocation found"
    return " ".join(part.strip() for part in m.group(1).replace("\\\n", "\n").split("\n"))


@needs_workflows
def test_release_invocation_matches_release_yml():
    ci = _pytest_invocation((WF / "ci.yml").read_text())
    rel = _pytest_invocation((WF / "release.yml").read_text())
    assert ci == rel
    assert rel == "/tmp/wheel_test_venv/bin/pytest tests/ -v --tb=short --no-header --import-mode=importlib"


@needs_workflows
def test_wheel_runs_never_use_python_dash_m_pytest():
    for name in ("ci.yml", "release.yml"):
        assert "wheel_test_venv/bin/python -m pytest" not in (WF / name).read_text(), name


@needs_workflows
def test_release_version_check_runs_outside_checkout():
    rel = (WF / "release.yml").read_text()
    step = rel.split("Confirm the installed version matches the tag", 1)[1].split("- name:", 1)[0]
    assert 'cd "$(mktemp -d)"' in step
    assert "/site-packages/" in step


@needs_workflows
def test_publish_waits_for_sdist_and_wheel():
    rel = (WF / "release.yml").read_text()
    assert "needs: [verify-version, build, test-wheel, test-sdist]" in rel
    assert "tools/check_sdist.py --sdist dist/*.tar.gz" in rel


@needs_workflows
def test_ci_runs_every_gate():
    ci = (WF / "ci.yml").read_text()
    for needle in ("tools/mutation_gate.py", "tools/check_sdist.py", "tools/docs_check.py --root .",
                   "release-invocation:"):
        assert needle in ci, needle


@needs_workflows
def test_ci_runs_mutation_ratchet_with_full_history():
    ci = (WF / "ci.yml").read_text()
    job = ci.split("  mutation:", 1)[1].split("\n  release-invocation:", 1)[0]
    assert "python tools/mutation_gate.py --ratchet-only" in job
    assert "fetch-depth: 0" in job
