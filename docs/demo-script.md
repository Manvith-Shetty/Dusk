# Dusk — demo video script (spoken narration, with setup per scene)

Target length: 3:30. You speak the lines; no captions needed. Record scene by scene and
stitch them. Everything on screen is real: your local Switch server, Mattermost, Telegram
on your phone, GitHub. No slides.

---

## Part A — one-time setup (do once, ~30 min)

### A1. Two browser windows, two people
- **Window 1 (Chrome, normal):** Mattermost at `http://localhost:49359`, logged in as
  **admin**. You are *Ravi, the platform lead* in this window.
- **Window 2 (Chrome incognito, or Edge):** Mattermost logged in as a second user,
  **priya**. You are *the team engineer* in this window.
  - Create priya: Mattermost → menu (9 dots) → **System Console** → **Users** →
    **Add user** (or open `http://localhost:49359/signup_user_complete` in the
    incognito window and sign up). Username `priya`, any password.
  - Add priya to the team channels: in window 1, open each team channel
    (Alerting, Search & Storage, …) → channel name → **Add members** → priya.
- Keep both windows the same size, side by side, or alt-tab between them.

### A2. Phone
- Telegram group **Identity Team** with the bot and your second account in it.
- Phone screen recording on (Android: swipe down → Screen record; iPhone: Control
  Centre → Record). Record the phone scene separately and insert the clip.

### A3. Recording on the laptop
- **Windows Game Bar:** press `Win + G` → Capture → record (`Win + Alt + R` to start/stop).
  Records the active window. Or install OBS if you want the whole screen.
- Settings → Personalisation → Taskbar → hide automatically. Close other apps.
- Mattermost: Settings → Display → theme dark, font size large (Ctrl + `+` twice).

### A4. Reset the rooms so the video starts empty
1. Switch Console → **Your Rooms** → each "… — pkg/bus" room → ⋮ → **Archive/Delete**
   (the hub and the 6 team rooms). Also delete the matching Mattermost channels if they
   remain (channel name → Archive channel).
2. Console → **Your Agents** → delete `dusk`, `fixer`, `steward`.
3. Delete `D:\hackathon\switch-hackathon\state.json`, `discovery.json`, `discovery.md`.
4. Console → **Templates** → the Dusk template → **Use** → Mattermost → **Create**.
   Ignore Console's timeout message; wait 3 minutes, check Your Rooms shows the 7 rooms.
5. **Don't** let the kickoff run yet: if Dusk already started from the kickoff, that's
   fine too; just record scene 4 starting from the kickoff message instead of typing it.
6. Telegram group: `!invite-agent @dusk`.
7. Add priya to the 6 team channels (A1).

### A5. Rehearse once end to end before filming
Scenes 6 and 8 depend on Fixer and Steward working. Run the whole flow once off camera.

---

## Part B — the scenes

For each scene: **Set up** (before you press record), **On screen**, **You do**,
**You say** (speak slowly; pause where it says *pause*).

### Scene 1 — The hook (10 s)
**Set up:** in window 2 (priya) and window 1 (admin), type these into any ordinary
Mattermost channel (e.g. Town Square) a few minutes earlier, so they're on screen:
- priya: `does anyone still use pkg/bus?`
- admin: `no idea, ask every team I guess`
- priya: `that's what we did last time. took six weeks`

**On screen:** that channel, window 1.
**You say:** "Every platform team has this thread. Someone wants to retire an old
internal API. Nobody knows who still calls it. Last time, it took six weeks of pinging
people."

### Scene 2 — The problem, bluntly (15 s)
**Set up:** browser tab open at `https://github.com/grafana/grafana/tree/main/pkg/bus`.
**On screen:** that GitHub page.
**You say:** "This is Grafana's old event bus, pkg/bus. Seven teams still call it. To
retire it, someone has to find every caller, work out who owns it, ask each team for a
date, chase them, and only then remove it. That job has no owner, so it never ends."

### Scene 3 — The turn (10 s)
**Set up:** window 1, channel **Dusk hub — pkg/bus**, empty except the system messages.
**On screen:** the empty hub.
**You say:** *pause* "What if the chasing ran itself, in the rooms the teams already use,
and only came to me for decisions?"

### Scene 4 — The reveal: one message (20 s)
**Set up:** same hub, cursor in the message box.
**You do:** type `@dusk start the retirement of pkg/bus` and press Enter. Wait. Dusk
replies "Cloning the repo and searching for callers".
**You say:** "This is Dusk." *pause* "One agent. One message." *pause while Dusk answers*
"It's cloning the real Grafana repo and searching for callers right now."

### Scene 5 — The number (20 s)
**Set up:** nothing; this follows scene 4 after about a minute. If you don't want dead
air, stop recording and restart when the table appears.
**On screen:** the discovery table in the hub.
**You say:** "Twenty call sites. Twenty files. Seven teams. Found in seconds." *pause*
"The owners come from the repo's CODEOWNERS file, so nobody typed any of this. And that
status document it created is rendered from a ledger, never written by hand."

### Scene 6 — The chasing happens by itself (25 s)
**Set up:** wait until the hub says "Asked 6 of 7 teams". Then in window 1 open
**Alerting — pkg/bus**, then **Data Pro — pkg/bus**, then **Catalog — pkg/bus**.
**On screen:** click through the three channels, showing Dusk's thread in each.
**You say:** "While I was talking, Dusk opened a thread in every team's room: their
files, their call sites, and one question: by what date can you migrate?"

### Scene 7 — A team says yes, and gets the work done for them (35 s)
**Set up:** window 2 (priya), channel **Alerting — pkg/bus**, click the reply arrow on
Dusk's message to open the thread.
**You do:** as priya, type `@dusk end of January works, and yes please draft the PR.`
Wait for Dusk's reply and the hand-off to Fixer. Stop recording. When Fixer has posted
the PR link (5–10 min), record again: the thread with the link, then click it to GitHub,
showing the draft PR and the "Files changed" tab.
**You say:** (as the team) "I'm the Alerting engineer. End of January, and yes, draft it
for me." *stop* … (later) "Fixer, an agent from a second vendor, drafted the pull
request on our fork. The team reviews it. Nobody merges but them." *pause* "And Dusk
doesn't take anyone's word for it: it re-greps the branch. Zero callers, or it's not done."

### Scene 8 — The vendor, on a phone (15 s)
**Set up:** phone recording; Telegram group **Identity Team**, Dusk's brief visible
(one line per file). Laptop window 1 on the hub.
**You do:** on the phone, as your second account, reply `@dusk 2027-02-15 is fine.`
Then on the laptop, show the hub table updating (Dusk posts it after a hop).
**You say:** "This team is an outside vendor. They don't have our Mattermost; they have
Telegram. Same agent, same table."

### Scene 9 — The "no" becomes one decision (25 s)
**Set up:** window 2 (priya), channel **Search & Storage — pkg/bus**, thread open.
Window 1 on the hub, ready.
**You do:** as priya, type `@dusk we can't before March, we're in a release freeze.`
Switch to window 1: Dusk's message to the lead appears in the hub. As admin, type
`@dusk accept 2027-03-31 for search-storage.`
**You say:** (as the team) "We can't. Release freeze until March." *switch windows* "Dusk
records the blocker, proposes a date, and asks the one person who decides. That's me."
*type* "Accepted. No meeting. One question, one answer."

### Scene 10 — One more thing: trust is earned (20 s)
**Set up:** this needs three PRs marked approved. Off camera, in three team threads as
priya, say `@dusk the PR is approved as is.` after Fixer's PRs. Then in the hub, as admin,
`@steward anything to propose?` Steward posts its proposal. Record from here.
**You do:** as admin, reply `yes`. Then show Console → Your Agents → fixer → addressing
now "anyone".
**You say:** *pause* "One more thing." *pause* "Fixer started with no direct access; only
Dusk could task it. Three PRs approved without changes, and Steward proposes letting teams
call Fixer themselves. I say yes, and Switch changes its reach, live. One rejected PR, and
Steward takes it back. Agents earn trust here. They aren't given it."

### Scene 11 — The end (15 s)
**Set up:** hub showing the final table (7/7 migrated) and Dusk's removal-PR message.
If you can't get all seven done, show the table as it is and the removal gate output.
**You say:** "The API is gone when the code says so, not when a spreadsheet does."
*pause* "Dusk is one template. Paste it into Switch, pick any repo and any endpoint, and
your first campaign is running in ten minutes. It isn't just APIs: a breaking library
upgrade, a feature flag, a security fix across repos. Any change one team needs many
teams to make."
**Final frame:** the repo URL on screen for 3 seconds.

---

## What this covers (submission and judging)

| Requirement | Where it shows |
|---|---|
| An agent and a person finish a real task in team chat, through Switch | Dates given in rooms, a real PR, a real decision, a real removal PR |
| Switch is central ("would it stop working without it?") | Rooms per team, addressing (Fixer owner-agents → anyone), two chat apps on one server, room documents, agent-to-agent hand-off, the template |
| Technical execution, reproducible | Template paste; real discovery on grafana/grafana; `duskctl` with tests |
| Creativity and impact | Cross-team change campaigns: a problem every platform team has; a measured number |
| Presentation | This video + README |
| README: which agents, how the channel is set up, how to run it | README sections "Agents", "Rooms and chat apps", "Run it in 10 minutes" |
| Code with Wispr | Wispr Insights screenshot in the README |
| Best Blog | "We retired an API across 7 teams without a meeting" |
| #HowISwitch | Scenes 4–5 as a 30-second clip |

## Cut if it isn't great on the day
In this order: scene 8 (Telegram), scene 10 (Steward), the removal PR in scene 11.
Scenes 1–7 and 9 are the demo.
