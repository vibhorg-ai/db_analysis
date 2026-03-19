"""
Agent, router, circuit breaker, knowledge graph, and dependency engine tests.
"""

import pytest
from unittest.mock import AsyncMock

from backend.core.agent_router import AgentRouter, StubAgent
from backend.core.prompt_trim import estimate_tokens, trim_context_for_llm, CHARS_PER_TOKEN
from backend.core.circuit_breaker import CircuitBreaker, CircuitOpenError
from backend.agents import AgentOrchestrator, SchemaIntelligenceAgent
from backend.graph import KnowledgeGraph, DependencyEngine


def test_agent_router_instantiation() -> None:
    """Verify AgentRouter can be instantiated."""
    router = AgentRouter()
    assert router is not None


def test_agent_router_get_agent_returns_stub_for_unknown() -> None:
    """Verify get_agent('nonexistent', mock_llm) returns a StubAgent."""
    router = AgentRouter()
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value="mock response")
    agent = router.get_agent("nonexistent", mock_llm)
    assert isinstance(agent, StubAgent)


@pytest.mark.asyncio
async def test_schema_intelligence_agent_init() -> None:
    """Verify SchemaIntelligenceAgent can be instantiated with a mock LLM and a prompt string."""
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value="mock response")
    agent = SchemaIntelligenceAgent(llm=mock_llm, prompt="# Test prompt")
    assert agent is not None
    assert agent.llm == mock_llm
    assert agent.prompt == "# Test prompt"


def test_prompt_trim_estimate_tokens() -> None:
    """Verify estimate_tokens('hello world') returns approximately len('hello world') / 4."""
    text = "hello world"
    expected = len(text) // CHARS_PER_TOKEN
    assert estimate_tokens(text) == expected
    assert estimate_tokens(text) == 2  # 11 // 4 = 2


def test_prompt_trim_context() -> None:
    """Verify trim_context_for_llm with a simple dict returns a string."""
    ctx = {"key": "value", "num": 42}
    result = trim_context_for_llm(ctx, max_total_chars=10000)
    assert isinstance(result, str)
    assert "key" in result and "value" in result


def test_circuit_breaker_records() -> None:
    """Verify CircuitBreaker can record_success and record_failure."""
    cb = CircuitBreaker(failures_threshold=5, open_seconds=60)
    cb.record_success()
    cb.record_failure()
    cb.record_success()
    # Should not raise
    cb.check()


def test_circuit_breaker_opens() -> None:
    """Verify that after circuit_breaker_failures consecutive failures, check() raises CircuitOpenError."""
    cb = CircuitBreaker(failures_threshold=2, open_seconds=60)
    cb.record_failure()
    cb.record_failure()
    with pytest.raises(CircuitOpenError) as exc_info:
        cb.check()
    assert "Circuit open" in str(exc_info.value)


def test_orchestrator_instantiation() -> None:
    """Verify AgentOrchestrator can be instantiated."""
    orchestrator = AgentOrchestrator()
    assert orchestrator is not None


def test_knowledge_graph_add_node() -> None:
    """Verify adding a node and retrieving it."""
    kg = KnowledgeGraph()
    node = kg.add_node("table_1", "table", {"schema": "public"})
    assert node is not None
    retrieved = kg.get_node("table_1")
    assert retrieved is not None
    assert retrieved.id == "table_1"
    assert retrieved.node_type == "table"
    assert retrieved.properties.get("schema") == "public"


def test_dependency_engine_register() -> None:
    """Verify registering a service and query."""
    engine = DependencyEngine()
    engine.register_service("svc_1", "My Service")
    engine.register_query("q1", "SELECT * FROM users", ["users"], [])
    engine.link_service_query("svc_1", "q1")
    deps = engine.get_service_dependencies("svc_1")
    assert deps["service_id"] == "svc_1"
    assert deps["service_name"] == "My Service"
    assert "q1" in deps["queries"]
    assert "users" in deps["tables"]
