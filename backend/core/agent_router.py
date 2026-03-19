"""
Resolves agents by name and supplies prompts from prompts_dir.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from backend.core.config import get_settings

logger = logging.getLogger(__name__)


class AgentProtocol(Protocol):
    """Protocol for agents that run with context."""

    async def run(self, context: dict) -> dict:
        """Run the agent with the given context. Return result dict."""
        ...


class StubAgent:
    """Placeholder agent returning not_implemented."""

    async def run(self, context: dict) -> dict:
        return {"status": "not_implemented"}


class AgentRouter:
    """Resolves agents by name, loads prompts from prompts_dir."""

    def __init__(self) -> None:
        self._settings = get_settings()
        base = Path(__file__).resolve().parent.parent.parent
        self._prompts_dir = base / self._settings.prompts_dir
        self._agents: dict[str, type] = {}
        self._register_agents()

    def _register_agents(self) -> None:
        """Map names to agent classes. Import from backend.agents."""
        try:
            from backend.agents import (
                BlastRadiusAgent,
                GraphReasoningAgent,
                IndexAdvisorAgent,
                LearningAgent,
                MonitoringAgent,
                OptimizerAgent,
                QueryAnalysisAgent,
                ReportAnalysisAgent,
                SchemaIntelligenceAgent,
                SelfCriticAgent,
                TimeTravelAgent,
                WorkloadIntelligenceAgent,
            )

            if SchemaIntelligenceAgent is not None:
                self._agents["schema_intelligence"] = SchemaIntelligenceAgent
            if QueryAnalysisAgent is not None:
                self._agents["query_analysis"] = QueryAnalysisAgent
            if OptimizerAgent is not None:
                self._agents["optimizer"] = OptimizerAgent
            if IndexAdvisorAgent is not None:
                self._agents["index_advisor"] = IndexAdvisorAgent
            if WorkloadIntelligenceAgent is not None:
                self._agents["workload_intelligence"] = WorkloadIntelligenceAgent
            if MonitoringAgent is not None:
                self._agents["monitoring"] = MonitoringAgent
            if BlastRadiusAgent is not None:
                self._agents["blast_radius"] = BlastRadiusAgent
            if ReportAnalysisAgent is not None:
                self._agents["report_analysis"] = ReportAnalysisAgent
            if GraphReasoningAgent is not None:
                self._agents["graph_reasoning"] = GraphReasoningAgent
            if TimeTravelAgent is not None:
                self._agents["time_travel"] = TimeTravelAgent
            if SelfCriticAgent is not None:
                self._agents["self_critic"] = SelfCriticAgent
            if LearningAgent is not None:
                self._agents["learning_agent"] = LearningAgent
        except ImportError as e:
            logger.warning("Some agents failed to import: %s", e)
            # Register whatever succeeded; StubAgent covers the rest

    def _load_prompt(self, agent_name: str) -> str:
        """Read prompts_dir/{agent_name}_prompt.md."""
        path = self._prompts_dir / f"{agent_name}_prompt.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return f"# {agent_name}\nNo prompt file found at {path}."

    def get_agent(self, agent_name: str, llm) -> AgentProtocol:
        """Instantiate agent with prompt and LLM. Returns StubAgent if not registered."""
        cls = self._agents.get(agent_name)
        if cls is None:
            return StubAgent()
        prompt = self._load_prompt(agent_name)
        return cls(llm=llm, prompt=prompt)
