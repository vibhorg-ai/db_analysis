"""
12 database intelligence agents + agent orchestrator.
"""

from __future__ import annotations

try:
    from backend.agents.schema_intelligence_agent import SchemaIntelligenceAgent
except ImportError:
    SchemaIntelligenceAgent = None

try:
    from backend.agents.query_analysis_agent import QueryAnalysisAgent
except ImportError:
    QueryAnalysisAgent = None

try:
    from backend.agents.optimizer_agent import OptimizerAgent
except ImportError:
    OptimizerAgent = None

try:
    from backend.agents.index_advisor_agent import IndexAdvisorAgent
except ImportError:
    IndexAdvisorAgent = None

try:
    from backend.agents.workload_intelligence_agent import WorkloadIntelligenceAgent
except ImportError:
    WorkloadIntelligenceAgent = None

try:
    from backend.agents.monitoring_agent import MonitoringAgent
except ImportError:
    MonitoringAgent = None

try:
    from backend.agents.blast_radius_agent import BlastRadiusAgent
except ImportError:
    BlastRadiusAgent = None

try:
    from backend.agents.report_analysis_agent import ReportAnalysisAgent
except ImportError:
    ReportAnalysisAgent = None

try:
    from backend.agents.graph_reasoning_agent import GraphReasoningAgent
except ImportError:
    GraphReasoningAgent = None

try:
    from backend.agents.time_travel_agent import TimeTravelAgent
except ImportError:
    TimeTravelAgent = None

try:
    from backend.agents.self_critic_agent import SelfCriticAgent
except ImportError:
    SelfCriticAgent = None

try:
    from backend.agents.learning_agent import LearningAgent
except ImportError:
    LearningAgent = None

from backend.agents.agent_orchestrator import (
    AgentOrchestrator,
    FULL_PIPELINE_BATCHES,
    INDEX_ONLY_STAGES,
    MONITORING_STAGES,
    QUERY_ONLY_STAGES,
    REPORT_ONLY_STAGES,
)

__all__ = [
    "AgentOrchestrator",
    "BlastRadiusAgent",
    "GraphReasoningAgent",
    "IndexAdvisorAgent",
    "LearningAgent",
    "MonitoringAgent",
    "OptimizerAgent",
    "QueryAnalysisAgent",
    "ReportAnalysisAgent",
    "SchemaIntelligenceAgent",
    "SelfCriticAgent",
    "TimeTravelAgent",
    "WorkloadIntelligenceAgent",
    "FULL_PIPELINE_BATCHES",
    "INDEX_ONLY_STAGES",
    "MONITORING_STAGES",
    "QUERY_ONLY_STAGES",
    "REPORT_ONLY_STAGES",
]
