"""`state.json`: the retirement's single source of truth.

Dusk's sessions share no memory (one session per room, nothing in common),
so every fact lives here and in the hub room document rendered from here.
Transitions are explicit and validated; every change is appended to `history`
so the hub can show who did what and when.

Team status lifecycle:

    pending ─ask─▶ asked ─date─▶ scheduled ─pr─▶ pr_open ─verify ok─▶ done
                    │                                 │
                    └──block──▶ blocked ──date──▶ scheduled   (lead decides)

`done` is only ever set by `verify`: a fresh grep showing zero callers in that
team's files. Nothing marks a team done by hand.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .discover import Discovery

STATUSES = ("pending", "asked", "scheduled", "blocked", "pr_open", "done")
TRANSITIONS = {
    "ask": ({"pending", "asked", "blocked"}, "asked"),
    "date": ({"asked", "blocked", "scheduled", "pending"}, "scheduled"),
    "block": ({"pending", "asked", "scheduled", "pr_open"}, "blocked"),
    "pr": ({"scheduled", "asked", "pr_open", "pending"}, "pr_open"),
    "done": ({"pr_open", "scheduled", "asked", "blocked", "pending"}, "done"),
    "reopen": ({"done"}, "pr_open"),
}


class StateError(ValueError):
    pass


@dataclass
class Team:
    name: str                      # CODEOWNERS handle, e.g. @grafana/alerting-squad
    files: list[str]
    call_sites: int
    status: str = "pending"
    room: str | None = None        # Switch room name (filled by the template/agent)
    chat_app: str | None = None    # Mattermost | Telegram | Slack ...
    thread_id: str | None = None   # root message id of this team's thread
    contact: str | None = None     # who answered for the team
    date: str | None = None        # agreed migration date, YYYY-MM-DD
    pr_url: str | None = None
    blocker: str | None = None
    proposed_date: str | None = None
    asked_at: float | None = None
    last_nudge_at: float | None = None
    nudges: int = 0
    remaining_call_sites: int | None = None
    verified_at: float | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class State:
    endpoint: str
    repo: str
    pattern: str
    commit: str
    replacement: str | None
    target_date: str | None
    created_at: float
    includes: list[str] = field(default_factory=list)
    excludes: list[str] = field(default_factory=list)
    declaring_files: list[str] = field(default_factory=list)
    lead: str | None = None
    hub_room: str | None = None
    status_document_id: str | None = None
    removal_pr_url: str | None = None
    removable: bool = False
    teams: dict[str, Team] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)

    # ── persistence ──────────────────────────────────────────────────────────

    @classmethod
    def from_discovery(cls, d: Discovery, *, replacement: str | None = None, target_date: str | None = None,
                       lead: str | None = None) -> "State":
        st = cls(endpoint=d.endpoint, repo=d.repo, pattern=d.pattern, commit=d.commit, replacement=replacement,
                 target_date=target_date, created_at=time.time(), lead=lead,
                 includes=list(d.includes), excludes=list(d.excludes), declaring_files=list(d.declaring_files))
        for t in d.teams:
            st.teams[t.team] = Team(name=t.team, files=list(t.files), call_sites=t.call_sites)
        st._log("discovered", teams=len(st.teams), call_sites=d.call_sites, files=d.files, elapsed_s=d.elapsed_s)
        return st

    @classmethod
    def load(cls, path: str | Path) -> "State":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        teams = {k: Team(**v) for k, v in raw.pop("teams", {}).items()}
        return cls(**raw, teams=teams)

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        tmp.replace(p)

    # ── transitions ─────────────────────────────────────────────────────────

    def team(self, name: str) -> Team:
        if name not in self.teams:
            # Allow the short form: "alerting-squad" for "@grafana/alerting-squad".
            matches = [t for t in self.teams if t.endswith("/" + name) or t == "@" + name]
            if len(matches) == 1:
                return self.teams[matches[0]]
            raise StateError(f"unknown team {name!r}; known: {', '.join(self.teams)}")
        return self.teams[name]

    def _move(self, team: Team, action: str) -> None:
        allowed, target = TRANSITIONS[action]
        if team.status not in allowed:
            raise StateError(f"{team.name}: cannot {action} from status {team.status!r}")
        team.status = target

    def _log(self, action: str, **data: Any) -> None:
        self.history.append({"at": time.time(), "action": action, **data})

    def ask(self, name: str, *, room: str | None = None, chat_app: str | None = None, thread_id: str | None = None,
            by: str = "dusk") -> Team:
        t = self.team(name)
        self._move(t, "ask")
        t.asked_at = t.asked_at or time.time()
        t.room = room or t.room
        t.chat_app = chat_app or t.chat_app
        t.thread_id = thread_id or t.thread_id
        self._log("asked", team=t.name, room=t.room, by=by)
        return t

    def set_date(self, name: str, date: str, *, contact: str | None = None, by: str = "dusk") -> Team:
        t = self.team(name)
        _check_date(date)
        self._move(t, "date")
        t.date = date
        t.blocker = None
        t.proposed_date = None
        t.contact = contact or t.contact
        self._log("date", team=t.name, date=date, contact=t.contact, by=by)
        return t

    def block(self, name: str, reason: str, *, proposed_date: str | None = None, contact: str | None = None,
              by: str = "dusk") -> Team:
        t = self.team(name)
        if proposed_date:
            _check_date(proposed_date)
        self._move(t, "block")
        t.blocker = reason
        t.proposed_date = proposed_date
        t.contact = contact or t.contact
        self.removable = False
        self._log("blocked", team=t.name, reason=reason, proposed_date=proposed_date, by=by)
        return t

    def set_pr(self, name: str, url: str, *, by: str = "fixer") -> Team:
        t = self.team(name)
        self._move(t, "pr")
        t.pr_url = url
        self._log("pr_open", team=t.name, url=url, by=by)
        return t

    def verified(self, name: str, remaining: int, *, by: str = "dusk") -> Team:
        """Record a fresh grep result. Zero remaining callers ⇒ done; otherwise not."""
        t = self.team(name)
        t.remaining_call_sites = remaining
        t.verified_at = time.time()
        if remaining == 0:
            self._move(t, "done")
        elif t.status == "done":
            self._move(t, "reopen")
        self._log("verified", team=t.name, remaining=remaining, by=by)
        return t

    def nudged(self, name: str) -> Team:
        t = self.team(name)
        t.last_nudge_at = time.time()
        t.nudges += 1
        self._log("nudged", team=t.name, count=t.nudges)
        return t

    def decide(self, who: str, decision: str, *, about: str | None = None) -> None:
        self.decisions.append({"at": time.time(), "by": who, "decision": decision, "about": about})
        self._log("decision", by=who, decision=decision, about=about)

    def note(self, name: str, text: str) -> Team:
        t = self.team(name)
        t.notes.append(text)
        self._log("note", team=t.name, text=text)
        return t

    def set_removal_pr(self, url: str) -> None:
        self.removal_pr_url = url
        self._log("removal_pr", url=url)

    # ── queries ─────────────────────────────────────────────────────────────

    def all_done(self) -> bool:
        return bool(self.teams) and all(t.status == "done" for t in self.teams.values())

    def blocked(self) -> list[Team]:
        return [t for t in self.teams.values() if t.status == "blocked"]

    def unanswered(self, older_than_s: float) -> list[Team]:
        now = time.time()
        out = []
        for t in self.teams.values():
            if t.status != "asked" or t.asked_at is None:
                continue
            last = t.last_nudge_at or t.asked_at
            if now - last >= older_than_s:
                out.append(t)
        return out

    def clean_confirmations(self) -> int:
        """Teams that gave a date (or finished) without ever being blocked. The
        Steward promotes Dusk after N of these."""
        n = 0
        for t in self.teams.values():
            ever_blocked = any(h.get("action") == "blocked" and h.get("team") == t.name for h in self.history)
            if t.status in ("scheduled", "pr_open", "done") and not ever_blocked:
                n += 1
        return n

    def pr_ledger(self) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        """PR verdicts recorded by Dusk as notes starting with `pr:`.

        Returns (approved, rejected); each entry is {"team", "note"}. A later verdict on
        the same team replaces an earlier one, so a PR that was first sent back and then
        approved counts once, as approved. `changes-requested` counts as rejected: the
        Steward's rule is "approved without changes".
        """
        latest: dict[str, str] = {}
        for t in self.teams.values():
            for n in t.notes:
                if n.startswith("pr:"):
                    latest[t.name] = n
        approved = [{"team": k, "note": v} for k, v in latest.items() if v.startswith("pr:approved")]
        rejected = [{"team": k, "note": v} for k, v in latest.items()
                    if v.startswith("pr:rejected") or v.startswith("pr:changes-requested")]
        return approved, rejected

    def counts(self) -> dict[str, int]:
        c = {s: 0 for s in STATUSES}
        for t in self.teams.values():
            c[t.status] += 1
        return c


def _check_date(date: str) -> None:
    try:
        time.strptime(date, "%Y-%m-%d")
    except ValueError as exc:
        raise StateError(f"dates are YYYY-MM-DD, got {date!r}") from exc
