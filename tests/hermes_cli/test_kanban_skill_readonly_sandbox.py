from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb


pytestmark = pytest.mark.skipif(
    not shutil.which("bwrap"), reason="bubblewrap is required for the Kanban skill boundary"
)


def _env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, str], Path, Path, Path]:
    root = tmp_path / "hermes"
    profile = root / "profiles" / "worker"
    local_skills = profile / "skills"
    external = tmp_path / "external-skills"
    outside = tmp_path / "outside-skill"
    for path in (root / "skills", local_skills, external, outside):
        path.mkdir(parents=True)
    (local_skills / "local").mkdir()
    (local_skills / "local" / "SKILL.md").write_text("local", encoding="utf-8")
    (outside / "SKILL.md").write_text("linked", encoding="utf-8")
    (local_skills / "linked").symlink_to(outside, target_is_directory=True)
    profile.joinpath("config.yaml").write_text(
        f"skills:\n  external_dirs:\n    - {external}\n", encoding="utf-8"
    )
    monkeypatch.setattr("hermes_constants.get_default_hermes_root", lambda: root)
    return {"HERMES_HOME": str(profile)}, local_skills, external, outside


def test_skill_roots_include_profile_external_and_symlink_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env, local_skills, external, outside = _env(tmp_path, monkeypatch)
    roots = kb._kanban_worker_skill_roots(env)
    assert local_skills.resolve() in roots
    assert external.resolve() in roots
    assert outside.resolve() in roots


def test_sandbox_preserves_python_runtime_mounts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    default_root = tmp_path / "default"
    profile_root = default_root / "profiles" / "worker"
    skill_root = profile_root / "skills"
    (skill_root / "local").mkdir(parents=True)
    (skill_root / "local" / "SKILL.md").write_text("readable", encoding="utf-8")
    monkeypatch.setattr("hermes_constants.get_default_hermes_root", lambda: default_root)

    cmd = kb._sandbox_kanban_worker_skills_read_only(
        [
            shutil.which("python3") or "python3",
            "-c",
            "import secrets, socket; assert len(secrets.token_bytes(16)) == 16; socket.getaddrinfo('localhost', 80)",
        ],
        {"HERMES_HOME": str(profile_root)},
    )
    completed = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr


def test_worker_can_read_skills_and_write_workspace_but_cannot_mutate_any_skill_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env, local_skills, external, outside = _env(tmp_path, monkeypatch)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (external / "external.md").write_text("external", encoding="utf-8")

    read_and_work = kb._sandbox_kanban_worker_skills_read_only(
        [
            "/bin/sh",
            "-c",
            'cat "$1/local/SKILL.md" "$2/SKILL.md" >/dev/null; printf ok > "$3/output"',
            "sh",
            str(local_skills),
            str(outside),
            str(workspace),
        ],
        env,
    )
    subprocess.run(read_and_work, check=True)
    assert (workspace / "output").read_text(encoding="utf-8") == "ok"

    attempts = [
        ["/bin/sh", "-c", 'printf changed > "$1/local/SKILL.md"', "sh", str(local_skills)],
        ["/bin/sh", "-c", 'chmod -R u+w "$1"; printf changed > "$1/local/SKILL.md"', "sh", str(local_skills)],
        ["/bin/sh", "-c", 'rm "$1/local/SKILL.md"', "sh", str(local_skills)],
        ["/bin/sh", "-c", 'mv "$1/local" "$1/replaced"', "sh", str(local_skills)],
        ["/bin/sh", "-c", 'mv "$1" "$1.replaced"', "sh", str(local_skills)],
        ["/bin/sh", "-c", 'printf changed > "$1/SKILL.md"', "sh", str(outside)],
        ["/bin/sh", "-c", 'printf changed > "$1/external.md"', "sh", str(external)],
    ]
    for attempt in attempts:
        wrapped = kb._sandbox_kanban_worker_skills_read_only(attempt, env)
        assert subprocess.run(wrapped, check=False).returncode != 0

    assert (local_skills / "local" / "SKILL.md").read_text(encoding="utf-8") == "local"
    assert (outside / "SKILL.md").read_text(encoding="utf-8") == "linked"
    assert (external / "external.md").read_text(encoding="utf-8") == "external"


def test_worker_spawn_fails_closed_without_bubblewrap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(kb.sys, "platform", "linux")
    monkeypatch.setattr(kb.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="bwrap not found"):
        kb._sandbox_kanban_worker_skills_read_only(["/bin/true"], {"HERMES_HOME": "/tmp"})
