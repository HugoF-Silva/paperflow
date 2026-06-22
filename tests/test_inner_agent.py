import asyncio
import sys
import types

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

def test_claude_run_pass_logs_i_j_t_messages(monkeypatch, tmp_path, capsys):
    class SystemMessage:
        subtype = "init"
        data = {"session_id": "sid-1"}

    class AssistantMessage:
        content = [types.SimpleNamespace(text="working text")]

    class ResultMessage:
        subtype = "success"
        result = "final text"

    class ClaudeAgentOptions:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class ClaudeSDKClient:
        def __init__(self, options):
            self.options = options

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def query(self, messages):
            async for _ in messages:
                pass

        async def receive_response(self):
            yield SystemMessage()
            yield AssistantMessage()
            yield ResultMessage()

    monkeypatch.setitem(
        sys.modules,
        "claude_agent_sdk",
        types.SimpleNamespace(
            ClaudeSDKClient=ClaudeSDKClient,
            ClaudeAgentOptions=ClaudeAgentOptions,
            AssistantMessage=AssistantMessage,
            ResultMessage=ResultMessage,
            SystemMessage=SystemMessage,
        ),
    )

    result = asyncio.run(inner_agent.run_pass(
        "SYSTEM",
        "USER ORDER",
        None,
        tmp_path,
        50,
        ralph_pass_no=3,
        ralph_max_passes=8,
    ))

    out = capsys.readouterr().out
    assert result.session_id == "sid-1"
    assert result.last_text == "final text"
    assert "inner_agent_pass_start pass_no=3 max_ralph=8" in out
    assert "inner_agent_turn pass_no=3 max_ralph=8 agent_iteration=0 turn=1 event=input_message" in out
    assert "inner_agent_turn pass_no=3 max_ralph=8 agent_iteration=1" in out
    assert "event=AssistantMessage" in out
    assert "inner_agent_iteration_finish pass_no=3 max_ralph=8 agent_iteration=1" in out
    assert "stop_event=ResultMessage status=success" in out
