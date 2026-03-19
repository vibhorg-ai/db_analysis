"""
Graph components: knowledge graph, entity graph, dependency engine.
"""

from backend.graph.dependency_engine import DependencyEngine, get_dependency_engine
from backend.graph.entity_graph import build_entity_graph
from backend.graph.knowledge_graph import KnowledgeGraph, get_knowledge_graph

__all__ = [
    "KnowledgeGraph",
    "get_knowledge_graph",
    "build_entity_graph",
    "DependencyEngine",
    "get_dependency_engine",
]
