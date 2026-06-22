import pathlib
import json
import ralph
import prompts

def test_has_promise():
    assert ralph.has_promise(f"done\n{prompts.PROMISE_TAG}")
    assert not ralph.has_promise("not yet")

def _fake_pass_factory(promise_on_pass):
    calls = {"n": 0, "seeds": []}
    async def fake_pass(system_prompt, user_order, seed_assistant, cwd, max_turns, model, **kwargs):
        calls["n"] += 1
        calls["seeds"].append(seed_assistant)
        from inner_agent import PassResult
        text = prompts.PROMISE_TAG if calls["n"] >= promise_on_pass else "still working"
        return PassResult(session_id=f"sid-{calls['n']}", last_text=text)
    return fake_pass, calls

async def _fake_compact(session_id, model):
    return f"recap-of-{session_id}"

def test_stops_on_promise_first_pass(tmp_path):
    fake_pass, calls = _fake_pass_factory(promise_on_pass=1)
    res = ralph.run_for_paper("paper", 31, tmp_path, max_ralph=8, inner_max_turns=60,
                              run_pass=fake_pass, compact_recap=_fake_compact)
    assert res.success and res.passes == 1
    assert calls["seeds"] == [None]               # no seed on pass 1

def test_threads_recap_until_promise(tmp_path):
    fake_pass, calls = _fake_pass_factory(promise_on_pass=3)
    res = ralph.run_for_paper("paper", 31, tmp_path, max_ralph=8, inner_max_turns=60,
                              run_pass=fake_pass, compact_recap=_fake_compact)
    assert res.success and res.passes == 3
    # pass 2 seeded with recap of pass 1's session, pass 3 with recap of pass 2
    assert calls["seeds"] == [None, "recap-of-sid-1", "recap-of-sid-2"]

def test_logs_recap_bullets(tmp_path, capsys):
    fake_pass, calls = _fake_pass_factory(promise_on_pass=2)

    async def fake_compact(session_id, model):
        return "- found weak ENIAC fit\n- check SI venues next"

    res = ralph.run_for_paper("paper", 31, tmp_path, max_ralph=3, inner_max_turns=60,
                              run_pass=fake_pass, compact_recap=fake_compact)

    out = capsys.readouterr().out
    assert res.success
    assert "ralph_recap_bullet" in out
    assert 'text="- found weak ENIAC fit"' in out
    assert 'text="- check SI venues next"' in out

def test_exhausts_without_promise(tmp_path):
    fake_pass, calls = _fake_pass_factory(promise_on_pass=99)
    res = ralph.run_for_paper("paper", 31, tmp_path, max_ralph=2, inner_max_turns=60,
                              run_pass=fake_pass, compact_recap=_fake_compact)
    assert not res.success and res.passes == 2
    assert res.last_reason == "max_ralph_exhausted"

def test_authentication_error_aborts_without_retry(tmp_path, capsys):
    calls = {"n": 0}

    class AuthenticationError(Exception):
        pass

    async def fake_pass(system_prompt, user_order, seed_assistant, cwd, max_turns, model, **kwargs):
        calls["n"] += 1
        raise AuthenticationError("bad key")

    res = ralph.run_for_paper("paper", 31, tmp_path, max_ralph=8, inner_max_turns=60,
                              run_pass=fake_pass, compact_recap=_fake_compact)

    out = capsys.readouterr().out
    assert not res.success
    assert res.passes == 1
    assert calls["n"] == 1
    assert res.last_reason == "pass_exception:AuthenticationError"
    assert "ralph_abort" in out

def test_logs_pass_artifact_snapshot(tmp_path, capsys):
    async def fake_pass(system_prompt, user_order, seed_assistant, cwd, max_turns, model, **kwargs):
        from inner_agent import PassResult

        (cwd / "ranking.json").write_text(json.dumps({
            "paper": {"is_statement": "Applied decision-support workflow."},
            "open_now": [{"name": "ENIAC 2026"}],
            "agent_notes": "Checked the fit.",
        }), encoding="utf-8")
        return PassResult(session_id="sid-1", last_text=prompts.PROMISE_TAG)

    res = ralph.run_for_paper("paper", 31, tmp_path, max_ralph=2, inner_max_turns=60,
                              run_pass=fake_pass, compact_recap=_fake_compact)

    out = capsys.readouterr().out
    assert res.success
    assert "ralph_pass_start" in out
    assert "ralph_pass_finish" in out
    assert 'paper_is="Applied decision-support workflow."' in out
    assert 'top_venue="ENIAC 2026"' in out
    assert "agent_notes_chars=16" in out
