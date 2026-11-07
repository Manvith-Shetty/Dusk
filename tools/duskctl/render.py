"""Render the retirement status from `state.json`.

Two shapes, because the chat apps differ:
- `table()`  Markdown table. Mattermost renders it.
- `lines()`  One short line per team. Telegram and Slack show tables as raw
             pipes, so they get this.
Both are also what goes into the hub room document.
"""

from __future__ import annotations

import time

from .state import State, Team

ICON = {
    "pending": "⬜",
    "asked": "✉️",
    "scheduled": "📅",
    "blocked": "⛔",
    "pr_open": "🔧",
    "done": "✅",
}
LABEL = {
    "pending": "not asked yet",
    "asked": "asked, waiting",
    "scheduled": "date agreed",
    "blocked": "blocked",
    "pr_open": "PR open",
    "done": "migrated",
}


def _short(team: str) -> str:
    return team.split("/", 1)[1] if "/" in team else team.lstrip("@")


def _detail(t: Team) -> str:
    bits = []
    if t.status == "scheduled" and t.date:
        bits.append(f"by {t.date}")
    if t.status == "blocked":
        bits.append(t.blocker or "no reason given")
        if t.proposed_date:
            bits.append(f"proposed {t.proposed_date}")
    if t.pr_url:
        bits.append(f"[PR]({t.pr_url})")
    if t.status == "done" and t.verified_at:
        bits.append("0 callers left")
    elif t.remaining_call_sites is not None and t.remaining_call_sites > 0:
        bits.append(f"{t.remaining_call_sites} callers left")
    if t.status == "asked" and t.nudges:
        bits.append(f"nudged ×{t.nudges}")
    if t.contact:
        bits.append(f"via {t.contact}")
    return " · ".join(bits) or "—"


def headline(st: State) -> str:
    c = st.counts()
    total = len(st.teams)
    done = c["done"]
    blocked = c["blocked"]
    head = f"**Retiring `{st.endpoint}`** — {done}/{total} teams migrated"
    if blocked:
        head += f", {blocked} blocked"
    if st.target_date:
        head += f" · target {st.target_date}"
    if st.removable:
        head += " · **ready to remove**"
    return head


def table(st: State) -> str:
    rows = [headline(st), "", "| Team | Status | Files | Calls | Detail |", "|---|---|---:|---:|---|"]
    for t in sorted(st.teams.values(), key=_sort_key):
        rows.append(
            f"| {_short(t.name)} | {ICON[t.status]} {LABEL[t.status]} | {len(t.files)} | {t.call_sites} | {_detail(t)} |"
        )
    rows.append("")
    rows.append(_footer(st))
    return "\n".join(rows)


def lines(st: State) -> str:
    out = [headline(st).replace("**", ""), ""]
    for t in sorted(st.teams.values(), key=_sort_key):
        out.append(f"{ICON[t.status]} **{_short(t.name)}** — {LABEL[t.status]} · {t.call_sites} calls in {len(t.files)} files · {_detail(t)}")
    out.append("")
    out.append(_footer(st))
    return "\n".join(out)


def team_brief(st: State, t: Team, *, max_files: int = 8) -> str:
    """The root message Dusk posts in a team's room."""
    files = "\n".join(f"- `{f}`" for f in t.files[:max_files])
    if len(t.files) > max_files:
        files += f"\n- …and {len(t.files) - max_files} more"
    repl = f"\n\n**Replacement:** `{st.replacement}`" if st.replacement else ""
    target = f" The platform team would like everything migrated by **{st.target_date}**." if st.target_date else ""
    return (
        f"Hi {_short(t.name)} — we're retiring `{st.endpoint}` in `{st.repo}`.{target}\n\n"
        f"Your team owns **{t.call_sites} call sites** in **{len(t.files)} files** (per CODEOWNERS):\n{files}{repl}\n\n"
        "Two questions:\n"
        "1. **By what date** can you migrate these? Reply with a date (YYYY-MM-DD), or say what blocks you.\n"
        "2. Would you like **a draft PR**? Say *yes* and our fixer agent will open one for you to review.\n\n"
        "Reply in this thread; I keep the status for every team in the hub room."
    )


def document(st: State) -> str:
    """Full status document content for the hub room (Markdown)."""
    parts = [f"# Retirement of `{st.endpoint}`", "", table(st), "", "## History"]
    for h in st.history[-50:]:
        when = time.strftime("%Y-%m-%d %H:%M", time.gmtime(h["at"]))
        rest = ", ".join(f"{k}={v}" for k, v in h.items() if k not in ("at", "action"))
        parts.append(f"- {when} — **{h['action']}** {rest}")
    if st.decisions:
        parts += ["", "## Lead decisions"]
        for d in st.decisions:
            when = time.strftime("%Y-%m-%d %H:%M", time.gmtime(d["at"]))
            parts.append(f"- {when} — {d['by']}: {d['decision']}" + (f" (about {d['about']})" if d.get("about") else ""))
    return "\n".join(parts)


def _footer(st: State) -> str:
    bits = [f"commit `{st.commit[:10]}`", f"{len(st.history)} events"]
    if st.removal_pr_url:
        bits.append(f"removal PR {st.removal_pr_url}")
    return "_" + " · ".join(bits) + "_"


def _sort_key(t: Team):
    order = {"blocked": 0, "asked": 1, "pending": 2, "scheduled": 3, "pr_open": 4, "done": 5}
    return (order[t.status], -t.call_sites, t.name)
