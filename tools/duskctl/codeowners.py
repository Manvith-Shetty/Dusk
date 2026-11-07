"""GitHub CODEOWNERS parsing and matching.

Rules implemented as GitHub documents them
(docs.github.com/articles/about-code-owners):

- The file is searched for at `.github/CODEOWNERS`, `CODEOWNERS`, then
  `docs/CODEOWNERS`; the first found is used.
- Each non-blank, non-comment line is `<pattern> [owner ...]`. A pattern with
  no owner un-sets ownership for matching paths.
- Patterns use gitignore-like syntax: `*` matches within a segment, `**`
  across segments, `?` one character, a leading `/` anchors to the repo root,
  a trailing `/` matches a directory and everything in it, and a pattern with
  no slash matches that name anywhere in the tree. A pattern like `/docs/*`
  matches direct children only. `!` negation and `[...]` character ranges are
  NOT supported by GitHub, and we treat them as literal.
- **The last matching pattern wins**, not the most specific one.

Owners are `@org/team`, `@user`, or an email address.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

CANDIDATE_PATHS = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")


@dataclass(frozen=True)
class Rule:
    pattern: str
    owners: tuple[str, ...]
    line_no: int
    regex: re.Pattern[str]

    def matches(self, path: str) -> bool:
        return self.regex.match(path) is not None


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate one CODEOWNERS pattern into a regex over repo-relative POSIX paths."""
    p = pattern.strip()
    anchored = p.startswith("/")
    if anchored:
        p = p[1:]
    dir_only = p.endswith("/")
    if dir_only:
        p = p[:-1]

    # A pattern with no slash matches the name anywhere in the tree.
    anywhere = "/" not in p and not anchored

    out = []
    i = 0
    while i < len(p):
        c = p[i]
        if c == "*":
            if p[i : i + 2] == "**":
                # `**/` matches zero or more directories; a trailing `**` matches everything.
                if p[i : i + 3] == "**/":
                    out.append("(?:.*/)?")
                    i += 3
                    continue
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    body = "".join(out)

    if anywhere:
        prefix = "(?:.*/)?"
    else:
        prefix = ""

    last_segment = p.rsplit("/", 1)[-1]
    if dir_only:
        tail = "/.*"
    elif "*" in last_segment or "?" in last_segment:
        # `/docs/*` matches direct children only; `*.js` names files.
        tail = ""
    else:
        # A directory pattern without a trailing slash still owns its contents on GitHub
        # (`/pkg/api` matches `/pkg/api/x.go`), and a file pattern matches the file.
        tail = "(?:/.*)?"
    return re.compile("^" + prefix + body + tail + "$")


def parse(text: str) -> list[Rule]:
    rules: list[Rule] = []
    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Owners never contain spaces; the pattern may, escaped as `\ `.
        parts = re.split(r"(?<!\\)\s+", line)
        pattern = parts[0].replace("\\ ", " ")
        owners = tuple(o for o in parts[1:] if not o.startswith("#"))
        rules.append(Rule(pattern=pattern, owners=owners, line_no=n, regex=_glob_to_regex(pattern)))
    return rules


class CodeOwners:
    def __init__(self, rules: list[Rule], source: str = "<memory>"):
        self.rules = rules
        self.source = source

    @classmethod
    def from_text(cls, text: str, source: str = "<memory>") -> "CodeOwners":
        return cls(parse(text), source)

    @classmethod
    def from_repo(cls, repo_root: str | Path) -> "CodeOwners | None":
        root = Path(repo_root)
        for rel in CANDIDATE_PATHS:
            f = root / rel
            if f.is_file():
                return cls.from_text(f.read_text(encoding="utf-8", errors="replace"), rel)
        return None

    def owners_of(self, path: str) -> tuple[str, ...]:
        """Owners of a repo-relative path; empty when unowned. Last match wins."""
        p = PurePosixPath(path.replace("\\", "/")).as_posix().lstrip("/")
        winner: Rule | None = None
        for rule in self.rules:
            if rule.matches(p):
                winner = rule
        return winner.owners if winner else ()

    def rule_for(self, path: str) -> Rule | None:
        p = path.replace("\\", "/").lstrip("/")
        winner = None
        for rule in self.rules:
            if rule.matches(p):
                winner = rule
        return winner

    def teams(self) -> list[str]:
        seen: dict[str, None] = {}
        for r in self.rules:
            for o in r.owners:
                seen.setdefault(o, None)
        return list(seen)
