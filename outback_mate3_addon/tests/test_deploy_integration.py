"""Regression tests for the startup integration-deploy step.

Root cause of the crash-loop these guard against: run.sh runs with `set -e`,
and the old inline `rm -rf "$TARGET"` aborted the *entire* run script when the
target dir was not removable (permission denied), so `exec python3 -m src.main`
never ran and s6 restarted the service forever. The relay is the add-on's core
job and does not depend on the integration sync, so a sync failure must be
non-fatal.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "deploy_integration.sh"


def _run(bundled: Path | str, target: Path | str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), str(bundled), str(target)],
        capture_output=True,
        text=True,
    )


def _make_bundled(tmp_path: Path, content: str = "new") -> Path:
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    (bundled / "__init__.py").write_text(content)
    return bundled


def test_script_is_executable() -> None:
    assert SCRIPT.exists()
    assert SCRIPT.stat().st_mode & stat.S_IXUSR, "deploy_integration.sh must be executable"


def test_fresh_deploy_when_target_absent(tmp_path: Path) -> None:
    bundled = _make_bundled(tmp_path)
    target = tmp_path / "cc" / "outback_mate3"  # parent does not exist yet

    result = _run(bundled, target)

    assert result.returncode == 0, result.stderr
    assert (target / "__init__.py").read_text() == "new"


def test_already_current_returns_10(tmp_path: Path) -> None:
    bundled = _make_bundled(tmp_path)
    target = tmp_path / "cc" / "outback_mate3"
    _run(bundled, target)  # first deploy

    result = _run(bundled, target)  # identical content -> no-op

    assert result.returncode == 10


def test_updates_when_content_differs(tmp_path: Path) -> None:
    bundled = _make_bundled(tmp_path, content="v2")
    target = tmp_path / "cc" / "outback_mate3"
    target.mkdir(parents=True)
    (target / "__init__.py").write_text("v1")

    result = _run(bundled, target)

    assert result.returncode == 0, result.stderr
    assert (target / "__init__.py").read_text() == "v2"


def test_missing_bundled_returns_2(tmp_path: Path) -> None:
    result = _run(tmp_path / "does-not-exist", tmp_path / "target")
    assert result.returncode == 2


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses directory permissions")
def test_unremovable_target_is_reported_not_fatal(tmp_path: Path) -> None:
    """rm of the target fails -> exit 5, and the existing copy is left intact."""
    bundled = _make_bundled(tmp_path, content="new")
    target = tmp_path / "cc" / "outback_mate3"
    target.mkdir(parents=True)
    (target / "__init__.py").write_text("old")
    os.chmod(target, 0o555)  # read/exec only: entries can't be unlinked
    try:
        result = _run(bundled, target)
        assert result.returncode == 5, result.stderr
        # Existing integration untouched, not half-deleted.
        assert (target / "__init__.py").read_text() == "old"
    finally:
        os.chmod(target, 0o755)


def test_deploy_failure_does_not_abort_under_errexit(tmp_path: Path) -> None:
    """The actual crash-loop regression.

    Reproduce run.sh's guard: `set -e` + `deploy_integration.sh ... || rc=$?`
    followed by the code that would start the relay. A non-zero deploy must NOT
    abort the script — the "relay start" marker must still be reached.
    """
    bundled = _make_bundled(tmp_path)
    # Force a deterministic, non-root-dependent failure: the target's parent is
    # a regular file, so `mkdir -p` can't create it -> exit 3.
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file, not a dir")
    target = blocker / "sub" / "outback_mate3"

    wrapper = (
        "set -e\n"
        "rc=0\n"
        f'bash {SCRIPT} "{bundled}" "{target}" || rc=$?\n'
        'echo "AFTER_DEPLOY rc=$rc"\n'
        'echo "RELAY_WOULD_START"\n'
    )
    result = subprocess.run(["bash", "-c", wrapper], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert "AFTER_DEPLOY rc=3" in result.stdout
    assert "RELAY_WOULD_START" in result.stdout, "set -e aborted before relay start"
