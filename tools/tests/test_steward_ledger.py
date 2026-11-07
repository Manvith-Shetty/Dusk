"""The Steward's ledger: PR verdicts recorded as `pr:` notes drive widen/narrow advice."""

import json
import time

from duskctl import cli
from duskctl.discover import Discovery, TeamReport
from duskctl.state import State


def _state(tmp_path, n_teams=4):
    teams = [TeamReport(team=f"@org/team-{i}", files=[f"pkg/t{i}/a.go"], call_sites=1) for i in range(n_teams)]
    d = Discovery(repo="https://example.com/r", endpoint="pkg/bus", pattern="bus", commit="abc", scanned_at="",
                  elapsed_s=0.1, includes=[], excludes=[], codeowners_source=None, call_sites=n_teams,
                  files=n_teams, teams=teams)
    st = State.from_discovery(d)
    p = tmp_path / "state.json"
    st.save(p)
    return st, p


def _steward(p, capsys, threshold=3):
    cli.main(["--state", str(p), "steward", "--threshold", str(threshold)])
    return json.loads(capsys.readouterr().out)


def test_empty_ledger_recommends_nothing(tmp_path, capsys):
    _, p = _state(tmp_path)
    out = _steward(p, capsys)
    assert out["approved_prs"] == [] and out["rejected_prs"] == []
    assert out["recommend_widen"] is False and out["recommend_narrow"] is False


def test_three_approvals_recommend_widening(tmp_path, capsys):
    st, p = _state(tmp_path)
    for i in range(3):
        st.note(f"team-{i}", f"pr:approved by dev{i}")
    st.save(p)
    out = _steward(p, capsys)
    assert len(out["approved_prs"]) == 3
    assert out["recommend_widen"] is True and out["recommend_narrow"] is False


def test_two_approvals_are_not_enough(tmp_path, capsys):
    st, p = _state(tmp_path)
    st.note("team-0", "pr:approved by a")
    st.note("team-1", "pr:approved by b")
    st.save(p)
    assert _steward(p, capsys)["recommend_widen"] is False


def test_rejection_recommends_narrowing_and_blocks_widening(tmp_path, capsys):
    st, p = _state(tmp_path)
    for i in range(3):
        st.note(f"team-{i}", f"pr:approved by dev{i}")
    st.note("team-3", "pr:changes-requested by dev3: wrong replacement")
    st.save(p)
    out = _steward(p, capsys)
    assert out["recommend_narrow"] is True and out["recommend_widen"] is False
    assert out["rejected_prs"][0]["team"] == "@org/team-3"


def test_latest_verdict_per_team_wins(tmp_path, capsys):
    st, p = _state(tmp_path)
    st.note("team-0", "pr:changes-requested by a: nit")
    st.note("team-0", "pr:approved by a")
    st.save(p)
    out = _steward(p, capsys)
    assert len(out["approved_prs"]) == 1 and out["rejected_prs"] == []


def test_fixer_decisions_are_surfaced(tmp_path, capsys):
    st, p = _state(tmp_path)
    st.decide("lead", "widen fixer to anyone", about="fixer")
    st.decide("lead", "accept 2027-04-30", about="@org/team-1")
    st.save(p)
    out = _steward(p, capsys)
    assert [d["decision"] for d in out["decisions"]] == ["widen fixer to anyone"]
