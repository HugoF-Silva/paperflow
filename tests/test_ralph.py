import pathlib
import ralph
import prompts

def test_has_promise():
    assert ralph.has_promise(f"done\n{prompts.PROMISE_TAG}")
    assert not ralph.has_promise("not yet")

def _fake_pass_factory(promise_on_pass):
    calls = {"n": 0, "seeds": []}
    async def fake_pass(system_prompt, user_order, seed_assistant, cwd, max_turns, model):
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

def test_exhausts_without_promise(tmp_path):
    fake_pass, calls = _fake_pass_factory(promise_on_pass=99)
    res = ralph.run_for_paper("paper", 31, tmp_path, max_ralph=2, inner_max_turns=60,
                              run_pass=fake_pass, compact_recap=_fake_compact)
    assert not res.success and res.passes == 2
    assert res.last_reason == "max_ralph_exhausted"
