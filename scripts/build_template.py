#!/usr/bin/env python3
"""Generate the Dusk Room v2 Switch template from a real discovery.

    python scripts/build_template.py examples/grafana-pkg-bus --out dist/dusk.template.yaml

Inputs (in the example directory):
  discovery.json   written by `duskctl discover`
  teams.yaml       team → room mapping and the retirement's bindings
Plus the agents' instruction files: agents/<name>/AGENT.md (body after the
front matter). The template inlines them, the way Switch's own switch-expert
template does.

Output: one `version: 2` template with three agents (dusk, fixer, steward),
one room group, a hub room, one room per team, links hub ↔ team, and a kickoff
in the hub. Room instructions carry the bindings (repo, endpoint, pattern,
replacement, target date, the team's handle and files), so the agents'
instructions stay portable.

Template language reference: docs/TEMPLATES.md in sandbox-quantum/switch
("Version 2"). Keys used here were checked against core/switch_core/template_v2.py.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class Str(str):
    """A string that dumps as a YAML block scalar (|) when multi-line."""


def _repr_str(dumper, data):
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


yaml.add_representer(Str, _repr_str)
yaml.add_representer(str, _repr_str)


def instructions_of(agent: str) -> str:
    """Body of agents/<agent>/AGENT.md with the YAML front matter removed."""
    f = ROOT / "agents" / agent / "AGENT.md"
    if not f.exists():
        sys.exit(f"missing {f}: write the agent's instructions first (see agents/README.md)")
    text = f.read_text(encoding="utf-8")
    m = re.match(r"^---\n.*?\n---\n", text, flags=re.S)
    return text[m.end():].strip() + "\n" if m else text.strip() + "\n"


def room_key(short: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", short.lower()).strip("_")


def bindings(cfg: dict, team: dict | None = None, hub_name: str = "") -> str:
    """Room instructions: the facts an agent needs on arrival, nothing else."""
    lines = [
        f"Retirement bindings (read these on every arrival; they override defaults):",
        f"- repo: {cfg['repo']}",
        f"- endpoint: {cfg['endpoint']}",
        f"- grep_pattern: {cfg['pattern']}",
        f"- include: {', '.join(cfg.get('include', []))}",
        f"- exclude: {', '.join(cfg.get('exclude', []))}",
        f"- declaring: {', '.join(cfg.get('declaring', []))}",
        f"- replacement: {cfg.get('replacement') or 'see the hub'}",
        f"- target_date: {cfg.get('target_date') or 'none set'}",
        f"- fork: {cfg.get('fork') or cfg['repo']} (every PR is opened here, never on repo)",
        "- lead: {lead}",
        f"- hub_room: {hub_name}",
        f"- state_file: state.json in the Dusk Room checkout (write it only through duskctl)",
    ]
    if team:
        files = "\n".join(f"  - {f}" for f in team["files"])
        lines += [
            f"- team: {team['team']}",
            f"- team_short: {team['short']}",
            f"- chat_app: {team.get('chat_app', 'Mattermost')} ({'tables render' if team.get('chat_app', 'Mattermost') == 'Mattermost' else 'no tables: one line per item'})",
            f"- call_sites: {team['call_sites']} in {len(team['files'])} files:",
            files,
        ]
    return "\n".join(lines) + "\n"


def build(example_dir: Path, local_checkout: str | None = None, skip_join: bool = False) -> dict:
    """`local_checkout`: run Dusk and Steward straight from this checkout of the
    Dusk Room repo (no clone), for rehearsals before the code is pushed."""
    disc = json.loads((example_dir / "discovery.json").read_text(encoding="utf-8"))
    cfg = yaml.safe_load((example_dir / "teams.yaml").read_text(encoding="utf-8"))
    team_cfg = cfg.get("teams", {})

    teams = []
    for t in disc["teams"]:
        handle = t["team"]
        extra = team_cfg.get(handle, {})
        short = extra.get("short") or handle.split("/")[-1].lstrip("@")
        teams.append({
            **t,
            "short": short,
            "display": extra.get("display", short),
            "chat_app": extra.get("chat_app", "Mattermost"),
            "room_name": extra.get("room_name") or f"{extra.get('display', short)} — {cfg['endpoint']}",
            "key": "team_" + room_key(short),
        })

    endpoint = cfg["endpoint"]
    hub_name = f"Dusk hub — {endpoint}"
    hub_key = "hub"

    params = {
        "bridge": {"type": "bridge", "label": "Messaging app for the rooms", "default": ["Mattermost", "$first"]},
        "machine": {"type": "machine", "default": ["$first"], "input": "advanced"},
        "lead": {"type": "string", "label": "Platform lead (name as teams know them)", "default": "{$creator}"},
    }

    resources: dict = {}

    resources["dusk"] = {
        "type": "agent",
        "display_name": "Dusk",
        "description": f"Retires {endpoint} across every team that still calls it: finds callers, asks each team for a date in its room, keeps the status in the hub, opens the removal PR when a fresh grep proves zero callers.",
        "provider": "claude",
        "machine": "{machine}",
        "directory": "{$agents_dir}/{dusk.name}",
        "repo": cfg.get("dusk_room_repo", "https://github.com/Manvith-Shetty/Dusk"),
        "auto_mode": True,
        "addressing": "anyone",
        "join": [t["room_name"] for t in teams if t["chat_app"] == "Telegram"],
        "instructions": Str(instructions_of("dusk")),
    }
    resources["fixer"] = {
        "type": "agent",
        "display_name": "Fixer",
        "description": "Drafts a team's migration PR when Dusk asks, posts the PR URL in the team's room, never merges.",
        # Literal, not a `{param}`: on Windows the Console's template form cannot
        # resolve a provider param (switch issue #1511), while a literal works.
        "provider": cfg.get("fixer_provider", "opencode"),
        "machine": "{machine}",
        "directory": "{$agents_dir}/{fixer.name}",
        # Fixer works on the fork so its PRs never land on the upstream repo.
        "repo": cfg.get("fork") or cfg["repo"],
        "auto_mode": True,
        # Starts narrow: only Dusk (same owner) can task it. Steward widens it
        # to `anyone` after three PRs that teams approved without changes.
        "addressing": "owner-agents",
        "instructions": Str(instructions_of("fixer")),
    }
    resources["steward"] = {
        "type": "agent",
        "display_name": "Steward",
        "description": "Watches the hub. Proposes widening or narrowing Fixer's reach from the ledger of approved and rejected PRs; acts only on the lead's word.",
        "provider": "claude",
        "machine": "{machine}",
        "directory": "{$agents_dir}/{steward.name}",
        "repo": cfg.get("dusk_room_repo", "https://github.com/Manvith-Shetty/Dusk"),
        "auto_mode": True,
        "addressing": "owner",
        "instructions": Str(instructions_of("steward")),
    }

    links = []
    for t in teams:
        if t["chat_app"] == "Telegram":
            continue  # adopted room, not created here; link it by hand after adoption
        links.append({"from": hub_key, "to": t["key"], "label": "owning team"})
        links.append({"from": t["key"], "to": hub_key, "label": "status hub"})

    resources["program"] = {
        "type": "group",
        "name": f"Dusk: {endpoint}",
        "description": f"Retirement of {endpoint} in {cfg['repo']}: one room per owning team, one hub.",
        "links": links,
    }

    resources[hub_key] = {
        "type": "room",
        "group": "program",
        "name": hub_name,
        "description": f"Status of the {endpoint} retirement. Decisions are made here; the per-team work happens in the team rooms.",
        "bridge": "{bridge}",
        "channel_type": "channel_private",
        "agents": ["dusk", "steward"],
        "users": ["{$creator}"],
        "instructions": Str(
            "This is the hub. The platform lead is {lead}. Dusk rests here between trips to team rooms and keeps the "
            "status document here. Steward watches here and speaks only to propose or report a change to Fixer's reach.\n\n"
            + bindings(cfg, None, hub_name)
        ),
        "kickoff": Str(
            f"@{{dusk.name}} start the retirement of {endpoint}. Discover the callers, post the table here, "
            f"create the status document, then open a thread per team in its room and ask for a date.\n\n"
            f"@{{steward.name}} you are watching. Say nothing until the ledger gives you something to propose."
        ),
    }

    for t in teams:
        if t["chat_app"] == "Telegram":
            continue
        resources[t["key"]] = {
            "type": "room",
            "group": "program",
            "name": t["room_name"],
            "description": f"{t['display']} and the {endpoint} retirement: {t['call_sites']} call sites in {len(t['files'])} files.",
            "bridge": "{bridge}",
            "channel_type": "channel_private",
            "agents": ["dusk", "fixer"],
            "users": ["{$creator}"],
            "instructions": Str(
                f"This is {t['display']}'s room for the {endpoint} retirement. Dusk asks here and leaves; "
                f"Fixer drafts this team's PR when asked; the team's people answer here.\n\n" + bindings(cfg, t, hub_name)
            ),
        }

    if skip_join:
        # Adopted Telegram rooms are joined by hand instead: `!invite-agent @dusk`
        # typed in the group. Needed when the room's name on the server differs
        # from teams.yaml.
        resources["dusk"].pop("join", None)
    if local_checkout:
        local = str(Path(local_checkout).resolve()).replace("\\", "/")
        for key in ("dusk", "steward"):
            resources[key]["directory"] = local
            resources[key].pop("repo", None)

    doc = {
        "version": 2,
        "params": params,
        "form": {"advanced": {"label": "Advanced", "open": False}},
        "resources": resources,
    }
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("example_dir", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "dist" / "dusk.template.yaml")
    ap.add_argument("--local-checkout", metavar="DIR",
                    help="run Dusk and Steward from this local checkout instead of cloning the repo")
    ap.add_argument("--skip-join", action="store_true",
                    help="do not auto-join adopted Telegram rooms; invite Dusk there by hand")
    args = ap.parse_args()
    doc = build(args.example_dir, local_checkout=args.local_checkout, skip_join=args.skip_join)
    header = (
        "# Dusk Room — generated by scripts/build_template.py from a real discovery.\n"
        "# Paste into Switch Console → Templates → Use, or save it there. Needs a server\n"
        "# with agent management (version 2) and a workspace admin (room groups).\n"
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(header + yaml.dump(doc, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    rooms = sum(1 for r in doc["resources"].values() if r["type"] == "room")
    print(f"wrote {args.out}: 3 agents, 1 group, {rooms} rooms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
