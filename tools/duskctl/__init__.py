"""duskctl: the deterministic half of Dusk Room.

The agents do the judgement (asking teams, negotiating dates, deciding when to
escalate). Everything that must be exact is done here and called from their
shell:

- `codeowners`  GitHub CODEOWNERS parsing with GitHub's own rules (last match wins).
- `discover`    clone a repo, find every caller of an endpoint, map files to teams.
- `state`       the retirement's single source of truth, `state.json`.
- `render`      the status table (Markdown) and the one-line-per-team form
                (Telegram, Slack) from that state.
- `cli`         `duskctl discover|status|ask|date|block|pr|verify|done|nudge|...`
"""

__version__ = "0.1.0"
