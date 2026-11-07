import pytest

from duskctl import render
from duskctl.discover import CallSite, Discovery, TeamReport
from duskctl.state import State, StateError


def make_discovery():
    return Discovery(
        repo="https://github.com/org/repo", endpoint="pkg/old.Thing", pattern="pkg/old\\.Thing",
        commit="abc123def456", scanned_at="2026-11-06T00:00:00Z", elapsed_s=3.2,
        includes=["*.go"], excludes=["vendor/**"], codeowners_source=".github/CODEOWNERS",
        call_sites=7, files=4,
        teams=[
            TeamReport("@org/alerting", ["pkg/a/x.go", "pkg/a/y.go"], 4, [CallSite("pkg/a/x.go", 10, "old.Thing()")]),
            TeamReport("@org/search", ["pkg/s/z.go"], 2),
            TeamReport("@org/mobile", ["pkg/m/m.go"], 1),
        ],
        declaring_files=["pkg/old/thing.go"],
    )


def test_lifecycle_happy_path(tmp_path):
    st = State.from_discovery(make_discovery(), replacement="pkg/new.Thing", target_date="2027-03-01", lead="ravi")
    st.ask("alerting", room="Alerting — pkg/old.Thing", chat_app="Mattermost", thread_id="m1")
    assert st.team("@org/alerting").status == "asked"
    st.set_date("alerting", "2027-01-15", contact="priya")
    assert st.team("alerting").status == "scheduled"
    st.set_pr("alerting", "https://github.com/org/repo/pull/1")
    assert st.team("alerting").status == "pr_open"
    st.verified("alerting", 0)
    assert st.team("alerting").status == "done"
    assert st.clean_confirmations() == 1
    p = tmp_path / "state.json"
    st.save(p)
    again = State.load(p)
    assert again.team("alerting").pr_url.endswith("/pull/1")
    assert again.includes == ["*.go"] and again.declaring_files == ["pkg/old/thing.go"]


def test_done_only_via_verify_and_reopens():
    st = State.from_discovery(make_discovery())
    st.ask("search")
    st.set_date("search", "2027-02-01")
    st.verified("search", 2)
    assert st.team("search").status == "scheduled"
    st.verified("search", 0)
    assert st.team("search").status == "done"
    st.verified("search", 1)  # a caller came back
    assert st.team("search").status == "pr_open"
    assert not st.all_done()


def test_block_then_date_and_not_clean():
    st = State.from_discovery(make_discovery())
    st.ask("search")
    st.block("search", "release freeze until March", proposed_date="2027-04-01", contact="dev")
    assert st.team("search").status == "blocked" and st.blocked()
    st.decide("ravi", "accept April for search", about="@org/search")
    st.set_date("search", "2027-04-01")
    assert st.team("search").status == "scheduled"
    assert st.clean_confirmations() == 0  # it was blocked once
    assert st.decisions[0]["by"] == "ravi"


def test_bad_transitions_and_dates():
    st = State.from_discovery(make_discovery())
    with pytest.raises(StateError):
        st.set_date("alerting", "15/01/2027")
    with pytest.raises(StateError):
        st.team("nobody")
    st.verified("mobile", 0)
    with pytest.raises(StateError):
        st.ask("mobile")  # done teams are not asked again


def test_unanswered_and_nudges(monkeypatch):
    st = State.from_discovery(make_discovery())
    st.ask("alerting")
    st.team("alerting").asked_at -= 48 * 3600
    assert [t.name for t in st.unanswered(24 * 3600)] == ["@org/alerting"]
    st.nudged("alerting")
    assert st.unanswered(24 * 3600) == []


def test_render_shapes():
    st = State.from_discovery(make_discovery(), target_date="2027-03-01")
    st.ask("alerting")
    st.block("search", "freeze", proposed_date="2027-04-01")
    t = render.table(st)
    assert "| Team | Status |" in t and "⛔ blocked" in t and "proposed 2027-04-01" in t
    l = render.lines(st)
    assert "|" not in l.splitlines()[2]  # no table pipes in the per-team lines
    brief = render.team_brief(st, st.team("alerting"))
    assert "2 files" in brief and "`pkg/a/x.go`" in brief and "2027-03-01" in brief
    doc = render.document(st)
    assert doc.startswith("# Retirement of") and "## History" in doc
