class AgentNotFoundError(Exception):
    def __init__(self, agent_type: str):
        self.agent_type = agent_type
        super().__init__(f"Agent not found: {agent_type!r}")


class AgentExecutionError(Exception):
    """Generic execution-time failure (reserved for future use)."""
