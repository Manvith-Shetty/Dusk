"""`duskctl`: the commands the agents run from their shell.

Every command prints something the agent can paste into the room, and exits
non-zero with a one-line reason when a transition is not allowed. State lives
in `state.json` in the current directory unless `--state` says otherwise.

    duskctl discover --repo URL --endpoint X [--pattern RE] [--include G]... [--exclude G]... [--declaring G]...
    duskctl init     --from discovery.json [--replacement Y] [--target-date D] [--lead NAME]
    duskctl status   [--format table|lines|document|json|counts]
    duskctl teams    [--status S]
    duskctl brief    TEAM
    duskctl ask      TEAM [--room R] [--chat-app A] [--thread-id ID]
    duskctl date     TEAM YYYY-MM-DD [--contact WHO]
    duskctl block    TEAM "reason" [--proposed-date D] [--contact WHO]
    duskctl pr       TEAM URL
    duskctl verify   TEAM [--ref BRANCH]        (re-grep; 0 callers ⇒ done)
    duskctl nudge    [--older-than HOURS] [--mark]
    duskctl decide   WHO "decision" [--about TEAM]
    duskctl gate                                (all done AND fresh grep = 0 ⇒ removable)
    duskctl removal-pr URL
    duskctl steward                             (PR ledger from `pr:` notes; widen/narrow advice for Fixer)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import discover as disc
from . import render
from .state import State, StateError


def _load(args) -> State:
    p = Path(args.state)
    if not p.exists():
        sys.exit(f"no state at {p}; run `duskctl init --from discovery.json` first")
    return State.load(p)


def _save(st: State, args) -> None:
    st.save(args.state)


def cmd_discover(args) -> int:
    d = disc.discover(
        args.repo, args.endpoint, pattern=args.pattern, includes=args.include, excludes=args.exclude,
        declaring=args.declaring, cache_dir=args.cache_dir, ref=args.ref, update=not args.no_update,
    )
    Path(args.out).write_text(d.to_json(), encoding="utf-8")
    Path(args.out).with_suffix(".md").write_text(disc.to_markdown(d), encoding="utf-8")
    print(disc.to_lines(d) if args.format == "lines" else disc.to_markdown(d))
    print(f"\nwrote {args.out} and {Path(args.out).with_suffix('.md')}", file=sys.stderr)
    return 0


def cmd_init(args) -> int:
    raw = json.loads(Path(args.from_).read_text(encoding="utf-8"))
    teams = [disc.TeamReport(team=t["team"], files=t["files"], call_sites=t["call_sites"],
                             samples=[disc.CallSite(**s) for s in t.get("samples", [])]) for t in raw["teams"]]
    d = disc.Discovery(**{**raw, "teams": teams})
    if Path(args.state).exists() and not args.force:
        sys.exit(f"{args.state} exists; pass --force to overwrite")
    st = State.from_discovery(d, replacement=args.replacement, target_date=args.target_date, lead=args.lead)
    _save(st, args)
    print(render.table(st))
    return 0


def cmd_status(args) -> int:
    st = _load(args)
    fmt = args.format
    if fmt == "table":
        print(render.table(st))
    elif fmt == "lines":
        print(render.lines(st))
    elif fmt == "document":
        print(render.document(st))
    elif fmt == "counts":
        print(json.dumps(st.counts()))
    else:
        print(json.dumps(json.loads(Path(args.state).read_text()), indent=2))
    return 0


def cmd_teams(args) -> int:
    st = _load(args)
    for t in st.teams.values():
        if args.status and t.status != args.status:
            continue
        print(f"{t.name}\t{t.status}\t{len(t.files)} files\t{t.call_sites} calls\troom={t.room or '-'}\tthread={t.thread_id or '-'}")
    return 0


def cmd_brief(args) -> int:
    st = _load(args)
    print(render.team_brief(st, st.team(args.team)))
    return 0


def _transition(fn):
    def run(args) -> int:
        st = _load(args)
        try:
            t = fn(st, args)
        except StateError as exc:
            sys.exit(f"refused: {exc}")
        _save(st, args)
        print(f"{t.name}: {t.status}")
        return 0
    return run


cmd_ask = _transition(lambda st, a: st.ask(a.team, room=a.room, chat_app=a.chat_app, thread_id=a.thread_id))
cmd_date = _transition(lambda st, a: st.set_date(a.team, a.date, contact=a.contact))
cmd_block = _transition(lambda st, a: st.block(a.team, a.reason, proposed_date=a.proposed_date, contact=a.contact))
cmd_pr = _transition(lambda st, a: st.set_pr(a.team, a.url))
cmd_note = _transition(lambda st, a: st.note(a.team, a.text))


def cmd_verify(args) -> int:
    st = _load(args)
    try:
        t = st.team(args.team)
    except StateError as exc:
        sys.exit(f"refused: {exc}")
    remaining = disc.verify_gone(st.repo, st.pattern, t.files, cache_dir=args.cache_dir, ref=args.ref,
                                 includes=args.include or st.includes, excludes=args.exclude or st.excludes)
    st.verified(t.name, len(remaining))
    _save(st, args)
    if remaining:
        print(f"{t.name}: {len(remaining)} call sites still present" + (f" on {args.ref}" if args.ref else ""))
        for s in remaining[:20]:
            print(f"  {s.file}:{s.line}: {s.text}")
        return 1
    print(f"{t.name}: 0 call sites left → done")
    return 0


def cmd_nudge(args) -> int:
    st = _load(args)
    due = st.unanswered(args.older_than * 3600)
    for t in due:
        print(f"{t.name}\troom={t.room or '-'}\tthread={t.thread_id or '-'}\tasked {((__import__('time').time() - (t.asked_at or 0)) / 3600):.1f}h ago\tnudges={t.nudges}")
        if args.mark:
            st.nudged(t.name)
    if args.mark:
        _save(st, args)
    if not due:
        print("nobody to nudge")
    return 0


def cmd_decide(args) -> int:
    st = _load(args)
    st.decide(args.who, args.decision, about=args.about)
    _save(st, args)
    print("recorded")
    return 0


def cmd_gate(args) -> int:
    """Removable only when every team is done AND a fresh full grep finds zero callers."""
    st = _load(args)
    if not st.all_done():
        c = st.counts()
        st.removable = False
        _save(st, args)
        print("NOT removable: " + ", ".join(f"{v} {k}" for k, v in c.items() if v and k != "done"))
        return 1
    includes = args.include or st.includes
    excludes = args.exclude or st.excludes
    # Any caller anywhere counts, not only in the files we knew about: a full
    # fresh grep, minus the files that declare the endpoint itself.
    root = disc.ensure_clone(st.repo, args.cache_dir, update=True)
    target = None
    if args.ref:
        disc.subprocess.run(["git", "-C", str(root), "fetch", "--depth", "1", "--quiet", "origin", args.ref], check=False)
        target = "FETCH_HEAD"
    full = [s for s in disc.grep_callers(root, st.pattern, includes, excludes, ref=target)
            if s.file not in set(st.declaring_files)]
    st.removable = not full
    st._log("gate", removable=st.removable, remaining=len(full))
    _save(st, args)
    if st.removable:
        print("REMOVABLE: every team done and a fresh grep finds 0 callers")
        return 0
    print(f"NOT removable: {len(full)} call sites still exist")
    return 1


def cmd_removal_pr(args) -> int:
    st = _load(args)
    st.set_removal_pr(args.url)
    _save(st, args)
    print("recorded")
    return 0


def cmd_steward(args) -> int:
    """The Steward's ledger: how teams received Fixer's PRs, and what that implies.

    Dusk records a team's verdict on a PR with `duskctl note TEAM "pr:approved by X"`,
    `"pr:changes-requested by X: what"` or `"pr:rejected by X: why"`. Three approved
    PRs and no rejection ⇒ recommend widening Fixer to anyone; any rejection ⇒ recommend
    narrowing it back to owner-agents. The Steward proposes; the lead decides.
    """
    st = _load(args)
    approved, rejected = st.pr_ledger()
    clean = st.clean_confirmations()
    blocked = [t.name for t in st.blocked()]
    out = {
        "approved_prs": approved,
        "rejected_prs": rejected,
        "threshold": args.threshold,
        "recommend_widen": len(approved) >= args.threshold and not rejected,
        "recommend_narrow": bool(rejected),
        "clean_confirmations": clean,
        "blocked_teams": blocked,
        "decisions": [d for d in st.decisions if d.get("about") == "fixer"],
        "counts": st.counts(),
    }
    print(json.dumps(out, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="duskctl", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--state", default="state.json")
    p.add_argument("--cache-dir", default=".cache/repos")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("discover"); s.set_defaults(fn=cmd_discover)
    s.add_argument("--repo", required=True); s.add_argument("--endpoint", required=True)
    s.add_argument("--pattern"); s.add_argument("--include", action="append", default=[])
    s.add_argument("--exclude", action="append", default=[]); s.add_argument("--declaring", action="append", default=[])
    s.add_argument("--ref"); s.add_argument("--out", default="discovery.json"); s.add_argument("--format", default="table")
    s.add_argument("--no-update", action="store_true")

    s = sub.add_parser("init"); s.set_defaults(fn=cmd_init)
    s.add_argument("--from", dest="from_", default="discovery.json"); s.add_argument("--replacement")
    s.add_argument("--target-date"); s.add_argument("--lead"); s.add_argument("--force", action="store_true")

    s = sub.add_parser("status"); s.set_defaults(fn=cmd_status)
    s.add_argument("--format", choices=["table", "lines", "document", "json", "counts"], default="table")

    s = sub.add_parser("teams"); s.set_defaults(fn=cmd_teams); s.add_argument("--status")
    s = sub.add_parser("brief"); s.set_defaults(fn=cmd_brief); s.add_argument("team")

    s = sub.add_parser("ask"); s.set_defaults(fn=cmd_ask); s.add_argument("team")
    s.add_argument("--room"); s.add_argument("--chat-app"); s.add_argument("--thread-id")
    s = sub.add_parser("date"); s.set_defaults(fn=cmd_date); s.add_argument("team"); s.add_argument("date"); s.add_argument("--contact")
    s = sub.add_parser("block"); s.set_defaults(fn=cmd_block); s.add_argument("team"); s.add_argument("reason")
    s.add_argument("--proposed-date"); s.add_argument("--contact")
    s = sub.add_parser("pr"); s.set_defaults(fn=cmd_pr); s.add_argument("team"); s.add_argument("url")
    s = sub.add_parser("note"); s.set_defaults(fn=cmd_note); s.add_argument("team"); s.add_argument("text")

    s = sub.add_parser("verify"); s.set_defaults(fn=cmd_verify); s.add_argument("team"); s.add_argument("--ref")
    s.add_argument("--include", action="append"); s.add_argument("--exclude", action="append")

    s = sub.add_parser("nudge"); s.set_defaults(fn=cmd_nudge)
    s.add_argument("--older-than", type=float, default=24.0, help="hours"); s.add_argument("--mark", action="store_true")

    s = sub.add_parser("decide"); s.set_defaults(fn=cmd_decide); s.add_argument("who"); s.add_argument("decision"); s.add_argument("--about")

    s = sub.add_parser("gate"); s.set_defaults(fn=cmd_gate); s.add_argument("--ref")
    s.add_argument("--include", action="append"); s.add_argument("--exclude", action="append")
    s = sub.add_parser("removal-pr"); s.set_defaults(fn=cmd_removal_pr); s.add_argument("url")
    s = sub.add_parser("steward"); s.set_defaults(fn=cmd_steward); s.add_argument("--threshold", type=int, default=3)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
