from __future__ import annotations

from langchain_core.messages import AIMessage
from typer.testing import CliRunner

from scripts.langgraph import vanilla

runner = CliRunner()


class _FakeAgent:
    def invoke(self, _payload, config=None):  # noqa: ANN001
        _ = config
        return {
            "messages": [
                AIMessage(
                    content="done",
                    tool_calls=[
                        {
                            "id": "call_1",
                            "name": "create_task",
                            "args": {"title": "milk"},
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(content="タスクを追加しました。"),
            ]
        }


def test_cli_help_commands() -> None:
    for args in (["--help"], ["run", "--help"], ["chat", "--help"]):
        result = runner.invoke(vanilla.app, args)
        assert result.exit_code == 0


def test_run_command_prints_final_response(monkeypatch) -> None:
    monkeypatch.setattr(vanilla, "_build_agent", lambda **kwargs: _FakeAgent())

    result = runner.invoke(vanilla.app, ["run", "--query", "牛乳タスクを追加して"])

    assert result.exit_code == 0
    assert "タスクを追加しました。" in result.stdout
