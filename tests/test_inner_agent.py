import inner_agent

def test_messages_user_only_when_no_seed():
    msgs = inner_agent.build_input_messages(None, "ORDER")
    assert len(msgs) == 1
    assert msgs[0]["type"] == "user"
    assert msgs[0]["message"]["role"] == "user"
    assert msgs[0]["message"]["content"] == "ORDER"

def test_messages_seed_assistant_first():
    msgs = inner_agent.build_input_messages("RECAP BULLETS", "ORDER")
    assert [m["type"] for m in msgs] == ["assistant", "user"]
    assert msgs[0]["message"]["role"] == "assistant"
    assert msgs[0]["message"]["content"] == "RECAP BULLETS"
    assert msgs[1]["message"]["content"] == "ORDER"
