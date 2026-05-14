from __future__ import annotations

from scripts.langgraph import vanilla


def test_exit_command_dispatch() -> None:
    should_continue, thread_id = vanilla._dispatch_slash_command(
        "/exit",
        thread_id="thread-1",
        tools=[],
        thread_id_factory=lambda: "new-thread",
    )

    assert not should_continue
    assert thread_id == "thread-1"


def test_reset_command_dispatch(capsys) -> None:
    should_continue, thread_id = vanilla._dispatch_slash_command(
        "/reset",
        thread_id="thread-1",
        tools=[],
        thread_id_factory=lambda: "thread-2",
    )

    captured = capsys.readouterr()
    assert should_continue
    assert thread_id == "thread-2"
    assert "Thread reset: thread-1 -> thread-2" in captured.out


def test_help_command_dispatch(capsys) -> None:
    should_continue, thread_id = vanilla._dispatch_slash_command(
        "/help",
        thread_id="thread-1",
        tools=[],
        thread_id_factory=lambda: "thread-2",
    )

    captured = capsys.readouterr()
    assert should_continue
    assert thread_id == "thread-1"
    assert "/exit" in captured.out
    assert "Available tools" in captured.out
