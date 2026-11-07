# Agent instructions

Each agent's instructions live in `agents/<name>/AGENT.md`: YAML front matter
(`name`, `description`) followed by the instructions as Markdown.
`scripts/build_template.py` inlines the body into the template, the same way
Switch's own `switch-expert/template.yaml` does with its `AGENT.md`.

Three agents:

| Agent | Provider | Addressing at start | Job |
|---|---|---|---|
| `dusk` | Claude Code | anyone | discovery, outreach per team, status document, escalation, removal gate |
| `fixer` | Codex or OpenCode (a second vendor) | owner-agents (only Dusk can task it) | draft one team's migration PR when asked; never merge |
| `steward` | Claude Code | owner | from the ledger of approved/rejected PRs, propose widening or narrowing Fixer's reach; act only on the lead's word |

Rules that apply to all three (from the Switch skill and the Switch expert's
knowledge files, `switch-expert/knowledge/` in sandbox-quantum/switch):

- Procedure goes in `AGENT.md`; instance facts (repo, endpoint, team, files,
  hub name) come from the **room instructions**, which the template writes.
- Say one line before any slow step, then come back with the result.
- Never write a literal `@name` in message text; use `send_targeted_message`.
- Only address another agent in a room you know it is present in.
- Thread ids: read them back from `read_context`, not from the post result.
- Mattermost renders tables; Telegram and Slack do not (one line per item).
- A room document can only be edited by the agent that created it.
- Dusk rests in the hub and makes strict round trips to team rooms.
- State changes go through `duskctl`; nothing is marked done by hand.
- A team's verdict on a PR is recorded by Dusk as a note starting with `pr:`
  (`pr:approved by X`, `pr:changes-requested by X: what`, `pr:rejected by X: why`);
  `duskctl steward` turns those into the Steward's widen/narrow advice.
- Every PR goes to the `fork` binding, never to `repo`. Fixer only ever runs `gh` and
  `git`; only Dusk and Steward run `duskctl` (Steward only `steward` and `decide`).
