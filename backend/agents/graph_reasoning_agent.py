"""
Graph reasoning agent — uses knowledge graph and dependency engine
to identify dependency chains, bottlenecks, and schema relationships.
"""

from __future__ import annotations


class GraphReasoningAgent:
    """Analyzes database graph for dependency chains, bottlenecks, and schema patterns."""

    def __init__(self, llm, prompt: str) -> None:
        self.llm = llm
        self.prompt = prompt

    async def run(self, context: dict) -> dict:
        """Run graph analysis. Returns raw_response and graph_summary."""
        from backend.core.config import get_settings
        from backend.core.prompt_trim import CHARS_PER_TOKEN, trim_context_for_llm
        from backend.graph import (
            build_entity_graph,
            get_dependency_engine,
            get_knowledge_graph,
        )

        kg = get_knowledge_graph()
        de = get_dependency_engine()
        schema_metadata = context.get("schema_metadata") or context.get("schema") or []

        if schema_metadata:
            kg.populate_from_schema(
                schema_metadata if isinstance(schema_metadata, list) else schema_metadata.get("tables", [])
            )

        graph_summary: dict = {
            "kg_summary": kg.summary(),
            "entity_graph": build_entity_graph(schema_metadata),
            "dependency_engine": de.to_dict(),
        }

        settings = get_settings()
        max_chars = settings.llm_max_context_tokens * CHARS_PER_TOKEN
        input_data = {
            "graph_summary": graph_summary,
            "schema_metadata": schema_metadata,
        }
        input_str = trim_context_for_llm(
            input_data,
            max_chars,
            reserved_chars=len(self.prompt) + 500,
        )

        prompt_text = f"{self.prompt}\n\n# INPUT DATA\n\n{input_str}"
        raw_response = await self.llm.generate(prompt_text)

        return {
            "raw_response": raw_response,
            "graph_summary": graph_summary,
        }
