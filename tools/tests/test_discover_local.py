"""End-to-end discovery against a tiny git repo built in a temp dir."""

import subprocess
from pathlib import Path

from duskctl.discover import discover, to_lines, to_markdown, verify_gone


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def make_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / ".github").mkdir(parents=True)
    (root / ".github" / "CODEOWNERS").write_text(
        "*            @org/platform\n/pkg/alerting/ @org/alerting\n/pkg/search/   @org/search\n/pkg/old/  @org/platform\n"
    )
    files = {
        "pkg/old/thing.go": "package old\n// Thing is the legacy entry point, referenced as old.Thing by callers.\nfunc Thing() {}\n",
        "pkg/alerting/a.go": "package alerting\nimport \"x/pkg/old\"\nfunc f() { old.Thing(); old.Thing() }\n",
        "pkg/alerting/a_test.go": "package alerting\nfunc TestF() { old.Thing() }\n",
        "pkg/search/s.go": "package search\nfunc g() { old.Thing() }\n",
        "vendor/dep/d.go": "package dep\nfunc h() { old.Thing() }\n",
        "README.md": "old.Thing is deprecated\n",
    }
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git(root, "init", "-q")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t", "add", ".")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init")
    return root


def test_discover_maps_callers_to_teams(tmp_path):
    root = make_repo(tmp_path)
    d = discover(str(root), "old.Thing", includes=["*.go"], excludes=["vendor/**", "**/*_test.go"],
                 declaring=["pkg/old/**"], cache_dir=tmp_path / "cache")
    assert d.call_sites == 2  # alerting line (one grep line, two calls) + search line
    assert d.files == 2
    assert [t.team for t in d.teams] == ["@org/alerting", "@org/search"]
    assert d.declaring_files == ["pkg/old/thing.go"]
    assert d.codeowners_source == ".github/CODEOWNERS"
    md = to_markdown(d)
    assert "| @org/alerting | 1 | 1 |" in md
    assert "2 teams" in to_lines(d)


def test_verify_gone_after_migration(tmp_path):
    root = make_repo(tmp_path)
    d = discover(str(root), "old.Thing", includes=["*.go"], excludes=["vendor/**"], cache_dir=tmp_path / "cache")
    search = [t for t in d.teams if t.team == "@org/search"][0]
    assert verify_gone(str(root), d.pattern, search.files, cache_dir=tmp_path / "cache")
    (root / "pkg/search/s.go").write_text("package search\nfunc g() { new.Thing() }\n")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-am", "migrate")
    assert verify_gone(str(root), d.pattern, search.files, cache_dir=tmp_path / "cache") == []
