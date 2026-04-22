"""LangGraph-backed orchestrator for multi-agent workflows."""

from __future__ import annotations

from typing import Any, Dict, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .base_agent import Agent
from .bug_analysis_agent import BugAnalysisAgent
from .integration_context_agent import IntegrationContextAgent
from .recommendation_agent import RecommendationAgent
from .wiki_knowledge_agent import WikiKnowledgeAgent
from ..schemas.issue_schemas import IssueSolveResponse


class WorkflowState(TypedDict, total=False):
    user_query: str
    user_id: str
    bug_analysis: Dict[str, Any]
    wiki_knowledge: Dict[str, Any]
    context_analysis: Dict[str, Any]
    recommendations: Dict[str, Any]
    response: IssueSolveResponse
    errors: list[str]

class OrchestratorAgent(Agent):
    """Brain agent using LangGraph for durable, resilient orchestration."""

    def __init__(self):
        super().__init__("🧠 Orchestrator Agent")
        self.bug_agent = BugAnalysisAgent()
        self.wiki_agent = WikiKnowledgeAgent()
        self.context_agent = IntegrationContextAgent()
        self.recommendation_agent = RecommendationAgent()
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(WorkflowState)

        workflow.add_node("run_bug_analysis", self._node_bug_analysis)
        workflow.add_node("run_wiki_knowledge", self._node_wiki_knowledge)
        workflow.add_node("run_context_analysis", self._node_context_analysis)
        workflow.add_node("run_recommendations", self._node_recommendations)
        workflow.add_node("assemble_response", self._node_assemble_response)

        # Fan-out: all three retrievers run in parallel from START
        workflow.add_edge(START, "run_bug_analysis")
        workflow.add_edge(START, "run_wiki_knowledge")
        workflow.add_edge(START, "run_context_analysis")

        # Fan-in: recommendations waits for all three to complete
        workflow.add_edge("run_bug_analysis", "run_recommendations")
        workflow.add_edge("run_wiki_knowledge", "run_recommendations")
        workflow.add_edge("run_context_analysis", "run_recommendations")

        workflow.add_edge("run_recommendations", "assemble_response")
        workflow.add_edge("assemble_response", END)

        return workflow.compile(checkpointer=MemorySaver())
    
    async def execute(self, user_query: str, user_id: str = "default") -> IssueSolveResponse:
        state: WorkflowState = {
            "user_query": user_query,
            "user_id": user_id,
            "errors": [],
        }
        config = {"configurable": {"thread_id": f"issue-{user_id}"}}
        result = await self.graph.ainvoke(state, config=config)
        if result.get("response"):
            return result["response"]

        error_text = "; ".join(result.get("errors", [])) or "Unknown orchestration error"
        return IssueSolveResponse(
            analysis=f"Error occurred during analysis: {error_text}",
            similar_bugs=[],
            relevant_wiki=[],
            root_causes=[],
            suggested_fixes=[],
        )

    async def _node_bug_analysis(self, state: WorkflowState) -> WorkflowState:
        try:
            return {"bug_analysis": await self.bug_agent.execute(state["user_query"]) }
        except Exception as exc:
            return {"bug_analysis": {}, "errors": [*state.get("errors", []), f"bug_analysis: {exc}"]}

    async def _node_wiki_knowledge(self, state: WorkflowState) -> WorkflowState:
        try:
            return {"wiki_knowledge": await self.wiki_agent.execute(state["user_query"]) }
        except Exception as exc:
            return {"wiki_knowledge": {}, "errors": [*state.get("errors", []), f"wiki_knowledge: {exc}"]}

    async def _node_context_analysis(self, state: WorkflowState) -> WorkflowState:
        try:
            return {"context_analysis": await self.context_agent.execute(state["user_query"]) }
        except Exception as exc:
            return {"context_analysis": {}, "errors": [*state.get("errors", []), f"context_analysis: {exc}"]}

    async def _node_recommendations(self, state: WorkflowState) -> WorkflowState:
        try:
            recommendations = await self.recommendation_agent.execute(
                bug_analysis=state.get("bug_analysis", {}),
                wiki_knowledge=state.get("wiki_knowledge", {}),
                integration_context=state.get("context_analysis", {}),
                original_query=state["user_query"],
            )
            return {"recommendations": recommendations}
        except Exception as exc:
            return {"recommendations": {}, "errors": [*state.get("errors", []), f"recommendations: {exc}"]}

    async def _node_assemble_response(self, state: WorkflowState) -> WorkflowState:
        response = self._assemble_response(
            query=state["user_query"],
            bug_analysis=state.get("bug_analysis", {}),
            wiki_knowledge=state.get("wiki_knowledge", {}),
            context_analysis=state.get("context_analysis", {}),
            recommendations=state.get("recommendations", {}),
        )
        return {"response": response}
    
    def _assemble_response(self,
                          query: str,
                          bug_analysis: Dict[str, Any],
                          wiki_knowledge: Dict[str, Any],
                          context_analysis: Dict[str, Any],
                          recommendations: Dict[str, Any]) -> IssueSolveResponse:
        """
        Assemble all insights into final response
        """
        # Build comprehensive analysis
        analysis = self._build_analysis_text(
            bug_analysis,
            wiki_knowledge,
            context_analysis,
            recommendations
        )
        
        # Keep only the single highest-scoring bug (Pass-2 score, already sorted descending)
        all_similar_bugs = bug_analysis.get("similar_bugs", [])
        filtered_similar_bugs = all_similar_bugs[:1] if all_similar_bugs else []

        return IssueSolveResponse(
            analysis=analysis,
            similar_bugs=filtered_similar_bugs,
            relevant_wiki=wiki_knowledge.get("wiki_pages", []),
            root_causes=recommendations.get("root_causes", []),
            suggested_fixes=recommendations.get("suggested_fixes", []),
        )
    
    def _build_analysis_text(self,
                            bug_analysis: Dict,
                            wiki_knowledge: Dict,
                            context_analysis: Dict,
                            recommendations: Dict) -> str:
        """
        Build comprehensive analysis text
        """
        analysis = "## AI-Powered Issue Analysis\n\n"
        
        # Context
        if context_analysis.get("context"):
            analysis += f"### 🔗 Context\n{context_analysis['context']}\n\n"
        
        # Confidence
        confidence = recommendations.get("confidence_level", 0)
        analysis += f"##### 📊 Recommendation Confidence: {confidence:.0%}\n"
        
        return analysis