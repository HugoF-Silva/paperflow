import prompts

def test_promise_tag_exact():
    assert prompts.PROMISE_TAG == "<promise>VENUE-MATCH-COMPLETE</promise>"

def test_system_prompt_includes_guidance():
    sp = prompts.build_system_prompt()
    assert "neurotic" in sp.lower()
    assert "country" in sp.lower()
    assert "brazil" in sp.lower()
    assert prompts.PROMISE_TAG in sp           # promise rules embedded
    assert "ranking.json" in sp

def test_user_order_has_paper_and_soon_days():
    order = prompts.build_user_order("PAPER BODY HERE", 31)
    assert "PAPER BODY HERE" in order
    assert "31" in order
    assert "language" not in order.lower()     # no language placeholder
