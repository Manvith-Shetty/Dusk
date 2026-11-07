"""Find every caller of an endpoint and map each to its owning team.

    duskctl discover --repo https://github.com/org/repo --endpoint "pkg/foo.Bar" \
        --include "*.go" --exclude "vendor/**" --exclude "**/*_test.go"

Pipeline: clone (shallow, cached) → `git grep -n -E` → CODEOWNERS mapping →
`discovery.json` + `discovery.md`. The headline number comes from here:
"N call sites in F files across T teams, found in S seconds".

Everything is measured; nothing is estimated. The JSON carries the commit
that was scanned so the result can be reproduced.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .codeowners import CodeOwners

UNOWNED = "(unowned)"


@dataclass
class CallSite:
    file: str
    line: int
    text: str


@dataclass
class TeamReport:
    team: str
    files: list[str]
    call_sites: int
    samples: list[CallSite] = field(default_factory=list)


@dataclass
class Discovery:
    repo: str
    endpoint: str
    pattern: str
    commit: str
    scanned_at: str
    elapsed_s: float
    includes: list[str]
    excludes: list[str]
    codeowners_source: str | None
    call_sites: int
    files: int
    teams: list[TeamReport]
    declaring_files: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def _run(cmd: list[str], cwd: str | Path | None = None, check: bool = True) -> str:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode not in (0, 1):  # git grep exits 1 on "no matches"
        raise RuntimeError(f"{' '.join(cmd)} failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout


def ensure_clone(repo: str, cache_dir: str | Path, *, ref: str | None = None, update: bool = True) -> Path:
    """Return a local checkout of `repo`. A local path is used as is."""
    if os.path.isdir(repo):
        return Path(repo)
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9_.-]+", "-", repo.rstrip("/").split("/")[-1].removesuffix(".git"))
    dest = cache / name
    if not (dest / ".git").exists():
        cmd = ["git", "clone", "--depth", "1", "--quiet"]
        if ref:
            cmd += ["--branch", ref]
        cmd += [repo, str(dest)]
        subprocess.run(cmd, check=True)
    elif update:
        subprocess.run(["git", "-C", str(dest), "fetch", "--depth", "1", "--quiet", "origin"], check=False)
        subprocess.run(["git", "-C", str(dest), "reset", "--hard", "--quiet", "FETCH_HEAD"], check=False)
    _ensure_index(dest)
    return dest


def _ensure_index(root: Path) -> None:
    """`git grep` searches the index; a clone whose index never got written
    (seen on Windows) silently matches nothing. Rebuild it from HEAD then."""
    probe = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", "."], capture_output=True)
    if probe.returncode == 0 and not probe.stdout:
        subprocess.run(["git", "-C", str(root), "read-tree", "HEAD"], check=False)


def grep_callers(root: Path, pattern: str, includes: list[str], excludes: list[str], *, ref: str | None = None) -> list[CallSite]:
    """`git grep -n -E <pattern>` limited to `includes` and minus `excludes`."""
    cmd = ["git", "grep", "-n", "-I", "-E", pattern]
    if ref:
        cmd.append(ref)
    # `:(glob)` gives `**` its usual meaning; without it git's `*` already
    # crosses slashes but `**` is not special.
    # A glob with no slash (`*.go`) means "anywhere in the tree", as in CODEOWNERS.
    norm = lambda g: g if "/" in g else f"**/{g}"
    pathspecs = [f":(glob){norm(i)}" for i in includes] + [f":(exclude,glob){norm(e)}" for e in excludes]
    if pathspecs:
        cmd += ["--"] + pathspecs
    out = _run(cmd, cwd=root)
    sites: list[CallSite] = []
    for line in out.splitlines():
        # With a ref, lines read "<ref>:<file>:<line>:<text>".
        if ref and line.startswith(ref + ":"):
            line = line[len(ref) + 1 :]
        try:
            file, lineno, text = line.split(":", 2)
        except ValueError:
            continue
        sites.append(CallSite(file=file, line=int(lineno), text=text.strip()[:200]))
    return sites


def discover(
    repo: str,
    endpoint: str,
    *,
    pattern: str | None = None,
    includes: list[str] | None = None,
    excludes: list[str] | None = None,
    declaring: list[str] | None = None,
    cache_dir: str | Path = ".cache/repos",
    ref: str | None = None,
    samples_per_team: int = 3,
    update: bool = True,
) -> Discovery:
    """Run the whole pipeline. `pattern` defaults to the endpoint, regex-escaped.

    `declaring` lists path globs that *define* the endpoint rather than call
    it (its own package); matches there are reported separately and not
    counted as callers.
    """
    t0 = time.perf_counter()
    includes = includes or []
    excludes = excludes or []
    declaring = declaring or []
    root = ensure_clone(repo, cache_dir, ref=ref, update=update)
    commit = _run(["git", "rev-parse", "HEAD"], cwd=root).strip()
    pat = pattern or re.escape(endpoint)

    sites = grep_callers(root, pat, includes, excludes)

    decl_regexes = [re.compile(_pathglob_to_regex(g)) for g in declaring]
    declaring_files = sorted({s.file for s in sites if any(r.match(s.file) for r in decl_regexes)})
    callers = [s for s in sites if s.file not in set(declaring_files)]

    owners = CodeOwners.from_repo(root)
    by_team: dict[str, list[CallSite]] = defaultdict(list)
    for s in callers:
        team_owners = owners.owners_of(s.file) if owners else ()
        # A file with several owners is attributed to each; the first listed is
        # the one Dusk asks. Keep it simple and deterministic: first owner.
        team = team_owners[0] if team_owners else UNOWNED
        by_team[team].append(s)

    teams = []
    for team, team_sites in sorted(by_team.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        files = sorted({s.file for s in team_sites})
        teams.append(TeamReport(team=team, files=files, call_sites=len(team_sites), samples=team_sites[:samples_per_team]))

    return Discovery(
        repo=repo,
        endpoint=endpoint,
        pattern=pat,
        commit=commit,
        scanned_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        elapsed_s=round(time.perf_counter() - t0, 2),
        includes=includes,
        excludes=excludes,
        codeowners_source=owners.source if owners else None,
        call_sites=len(callers),
        files=len({s.file for s in callers}),
        teams=teams,
        declaring_files=declaring_files,
    )


def verify_gone(repo: str, pattern: str, files: list[str], *, cache_dir: str | Path = ".cache/repos", ref: str | None = None,
                includes: list[str] | None = None, excludes: list[str] | None = None) -> list[CallSite]:
    """Re-grep; return the call sites that still exist in `files` (empty = migrated)."""
    root = ensure_clone(repo, cache_dir, ref=None, update=True)
    if ref:
        subprocess.run(["git", "-C", str(root), "fetch", "--depth", "1", "--quiet", "origin", ref], check=False)
        target = "FETCH_HEAD"
    else:
        target = None
    sites = grep_callers(root, pattern, includes or [], excludes or [], ref=target)
    wanted = set(files)
    return [s for s in sites if s.file in wanted]


def _pathglob_to_regex(glob: str) -> str:
    out = ""
    i = 0
    while i < len(glob):
        c = glob[i]
        if glob[i : i + 3] == "**/":
            out += "(?:.*/)?"
            i += 3
            continue
        if glob[i : i + 2] == "**":
            out += ".*"
            i += 2
            continue
        if c == "*":
            out += "[^/]*"
        elif c == "?":
            out += "[^/]"
        else:
            out += re.escape(c)
        i += 1
    return "^" + out + "$"


def to_markdown(d: Discovery, *, max_files: int = 4) -> str:
    """The discovery table Dusk posts in the hub (Mattermost renders tables)."""
    lines = [
        f"**{d.call_sites} call sites** of `{d.endpoint}` in **{d.files} files** across "
        f"**{len(d.teams)} teams**, found in {d.elapsed_s:.1f} s "
        f"(commit `{d.commit[:10]}`, owners from `{d.codeowners_source or 'none'}`).",
        "",
        "| Team | Files | Call sites | Where |",
        "|---|---:|---:|---|",
    ]
    for t in d.teams:
        where = ", ".join(f"`{f}`" for f in t.files[:max_files])
        if len(t.files) > max_files:
            where += f" +{len(t.files) - max_files} more"
        lines.append(f"| {t.team} | {len(t.files)} | {t.call_sites} | {where} |")
    if d.declaring_files:
        lines += ["", f"Declaring files (not counted): {', '.join(f'`{f}`' for f in d.declaring_files)}"]
    return "\n".join(lines)


def to_lines(d: Discovery) -> str:
    """The same, one line per team, for chat apps without tables (Telegram, Slack)."""
    head = f"{d.call_sites} call sites of {d.endpoint} in {d.files} files across {len(d.teams)} teams ({d.elapsed_s:.1f} s)."
    rows = [f"- **{t.team}** · {len(t.files)} files · {t.call_sites} call sites" for t in d.teams]
    return "\n".join([head, *rows])
