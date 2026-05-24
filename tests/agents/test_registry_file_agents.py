from __future__ import annotations

from collections.abc import Generator

import pytest

from concierge.agents.infrastructure.github_copilot_sdk_agent import GitHubCopilotSdkAgent
from concierge.agents.infrastructure.langgraph_agent import LangGraphAgent
from concierge.agents.infrastructure.microsoft_agent_framework_agent import MicrosoftAgentFrameworkAgent
from concierge.agents.infrastructure.registry_factory import get_agent_registry
from concierge.settings.agents import get_agents_settings
from concierge.settings.agents_knowledge import get_agents_knowledge_settings


@pytest.fixture(autouse=True)
def _clear_agent_caches() -> Generator[None, None, None]:
    get_agents_settings.cache_clear()
    get_agents_knowledge_settings.cache_clear()
    get_agent_registry.cache_clear()
    yield
    get_agents_settings.cache_clear()
    get_agents_knowledge_settings.cache_clear()
    get_agent_registry.cache_clear()


def test_registry_defaults_include_read_only_file_tools(monkeypatch) -> None:
    # Pin to the package default so a developer's .env (which may enable
    # additional file tools) cannot influence this assertion.
    monkeypatch.setenv("AGENTS_FILE_TOOLS_ENABLED", "read_file,list_directory,file_search")
    monkeypatch.setenv("AGENTS_SHELL_TOOLS_ENABLED", "")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", "")
    registry = get_agent_registry()

    langgraph = registry.resolve("langgraph")
    copilot = registry.resolve("github-copilot-sdk")
    maf = registry.resolve("microsoft-agent-framework")

    assert isinstance(langgraph, LangGraphAgent)
    assert isinstance(copilot, GitHubCopilotSdkAgent)
    assert isinstance(maf, MicrosoftAgentFrameworkAgent)
    assert len(langgraph._tool_builders) == 5
    assert len(copilot._tool_builders) == 5
    assert len(maf._tool_builders) == 5


def test_registry_single_file_tool_enabled(monkeypatch) -> None:
    monkeypatch.setenv("AGENTS_FILE_TOOLS_ENABLED", "read_file")
    monkeypatch.setenv("AGENTS_SHELL_TOOLS_ENABLED", "")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", "")
    registry = get_agent_registry()
    langgraph = registry.resolve("langgraph")
    assert isinstance(langgraph, LangGraphAgent)
    assert len(langgraph._tool_builders) == 3


def test_registry_file_tools_disabled(monkeypatch) -> None:
    monkeypatch.setenv("AGENTS_FILE_TOOLS_ENABLED", "")
    monkeypatch.setenv("AGENTS_SHELL_TOOLS_ENABLED", "")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", "")
    registry = get_agent_registry()
    langgraph = registry.resolve("langgraph")
    assert isinstance(langgraph, LangGraphAgent)
    assert len(langgraph._tool_builders) == 2


def test_registry_unknown_file_tool_raises(monkeypatch) -> None:
    monkeypatch.setenv("AGENTS_FILE_TOOLS_ENABLED", "read_file,unknown_tool")
    monkeypatch.setenv("AGENTS_SHELL_TOOLS_ENABLED", "")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", "")
    with pytest.raises(ValueError, match="Unknown file tool"):
        get_agent_registry()


def test_registry_shell_tools_disabled_by_default(monkeypatch) -> None:
    # Pin to the package default so a developer's .env (which may enable
    # shell tools) cannot influence this assertion.
    monkeypatch.setenv("AGENTS_FILE_TOOLS_ENABLED", "")
    monkeypatch.setenv("AGENTS_SHELL_TOOLS_ENABLED", "")
    monkeypatch.setenv("AGENTS_SHELL_ALLOWED_COMMANDS", "")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", "")

    registry = get_agent_registry()
    langgraph = registry.resolve("langgraph")
    assert isinstance(langgraph, LangGraphAgent)
    assert len(langgraph._tool_builders) == 2


def test_registry_shell_tools_enabled_require_allowed_commands(monkeypatch) -> None:
    monkeypatch.setenv("AGENTS_SHELL_TOOLS_ENABLED", "shell_exec")
    monkeypatch.setenv("AGENTS_SHELL_ALLOWED_COMMANDS", "")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", "")
    with pytest.raises(ValueError, match="AGENTS_SHELL_ALLOWED_COMMANDS"):
        get_agent_registry()


def test_registry_shell_tool_wired_for_all_framework_agents(monkeypatch) -> None:
    monkeypatch.setenv("AGENTS_FILE_TOOLS_ENABLED", "")
    monkeypatch.setenv("AGENTS_SHELL_TOOLS_ENABLED", "shell_exec")
    monkeypatch.setenv("AGENTS_SHELL_ALLOWED_COMMANDS", "echo")
    monkeypatch.setenv("AGENTS_KNOWLEDGE__TOOLS", "")
    registry = get_agent_registry()

    langgraph = registry.resolve("langgraph")
    copilot = registry.resolve("github-copilot-sdk")
    maf = registry.resolve("microsoft-agent-framework")

    assert isinstance(langgraph, LangGraphAgent)
    assert isinstance(copilot, GitHubCopilotSdkAgent)
    assert isinstance(maf, MicrosoftAgentFrameworkAgent)
    assert len(langgraph._tool_builders) == 3
    assert len(copilot._tool_builders) == 3
    assert len(maf._tool_builders) == 3
