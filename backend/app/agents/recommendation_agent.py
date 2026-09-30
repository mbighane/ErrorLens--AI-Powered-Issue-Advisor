"""
🧪 Recommendation Agent
Combines insights from all agents and generates final recommendations
"""

import json
from typing import Dict, Any, List, Optional
from .base_agent import Agent
from ..schemas.issue_schemas import RootCause, SuggestedFix
from ..config import settings
from ..services.azure_ai_monitoring import AzureAIMonitoring
from ..providers.factory import create_chat_provider
from ..providers.interfaces import IChatProvider


class RecommendationAgent(Agent):
    """
    Combines insights from all other agents:
    - Bug Analysis
    - Wiki Knowledge
    - Integration Context
    
    Generates:
    - Root cause analysis
    - Fix suggestions
    """
    
    def __init__(self, chat_provider: Optional[IChatProvider] = None):
        super().__init__("🧪 Recommendation Agent")
        self.chat_provider = chat_provider or create_chat_provider()
        # Set during _generate_ai_fixes so execute() can report which actual
        # provider/model served this request, for the response's model_info.
        self.last_chat_provider: Optional[str] = None
        self.last_chat_model: Optional[str] = None
    
    async def execute(self, 
                     bug_analysis: Dict[str, Any],
                     wiki_knowledge: Dict[str, Any],
                     integration_context: Dict[str, Any],
                     original_query: str) -> Dict[str, Any]:
        """
        Combine all agent insights and generate recommendations
        """
        try:
            # Synthesize root causes
            root_causes = self._synthesize_root_causes(bug_analysis, integration_context)

            # Try AI-powered fix generation first
            fixes = self._generate_ai_fixes(
                original_query=original_query,
                similar_bugs=bug_analysis.get("similar_bugs", []),
                root_causes=root_causes,
            )

            # Fall back to template-based if AI unavailable or failed
            used_template_fallback = False
            if not fixes:
                fixes = self._generate_fix_suggestions(
                    bug_analysis.get("fixes", []),
                    integration_context,
                )
                used_template_fallback = True

            model_info = {
                "deployment_mode": "on_prem" if settings.is_on_prem_deployment else "azure",
                "chat_provider": "template" if used_template_fallback else self.last_chat_provider,
                "chat_model": None if used_template_fallback else self.last_chat_model,
                "retrieval_backend": "azure_ai_search" if settings.azure_search_enabled else "local_vector_index",
            }

            return {
                "agent": self.name,
                "status": "success",
                "root_causes": root_causes,
                "suggested_fixes": fixes,
                "confidence_level": self._calculate_confidence(bug_analysis, wiki_knowledge),
                "model_info": model_info,
            }
        except Exception as e:
            return {
                "agent": self.name,
                "status": "error",
                "error": str(e),
                "root_causes": [],
                "suggested_fixes": []
            }

    def _build_fix_prompt(self, original_query: str, similar_bugs, root_causes: List[RootCause]):
        """Shared prompt construction used by both the cloud (Azure/OpenAI) and
        Ollama fix-generation paths, so prompt wording stays identical regardless
        of which provider actually answers it."""
        bugs_context_lines = []
        if isinstance(similar_bugs, str):
            similar_bugs_iter = []
        else:
            similar_bugs_iter = similar_bugs[:5]
        for bug in similar_bugs_iter:
            score = float(bug.get("similarity_score", 0.0)) if isinstance(bug, dict) else getattr(bug, "similarity_score", 0.0)
            title = getattr(bug, "title", "")
            desc = getattr(bug, "description", "") or ""
            rca_marker = "Root Cause Analysis:"
            rca_part = ""
            if rca_marker in desc:
                rca_part = desc.split(rca_marker, 1)[1].strip()[:200]
                desc = desc.split(rca_marker, 1)[0].strip()
            line = f"- [score={score:.2f}] {title}"
            if desc.strip():
                import re
                clean_desc = re.sub(r"<[^>]+>", " ", desc)
                clean_desc = re.sub(r"\s+", " ", clean_desc).strip()[:200]
                line += f"\n  Description: {clean_desc}"
            if rca_part:
                line += f"\n  RCA: {rca_part}"
            bugs_context_lines.append(line)

        bugs_context = "\n".join(bugs_context_lines) if bugs_context_lines else "No similar bugs found."
        causes_text = "\n".join(f"- {c.description}" for c in root_causes[:4]) if root_causes else "Unknown"
        prompt = (
            f'A developer reported this issue:\n"{original_query}"\n\n'
            f"Similar historical bugs retrieved from Azure DevOps:\n{bugs_context}\n\n"
            f"Identified root causes:\n{causes_text}\n"
        )
        prompt += (
            "\nGenerate 3-5 specific, actionable, programmer-friendly fix suggestions "
            "tailored to this exact issue. Mention concrete code patterns, APIs, or "
            "configuration keys where applicable.\n\n"
            "Return ONLY a JSON array with this shape — no extra text:\n"
            "[\n"
            '  {"description": "Short fix title", "priority": "high|medium|low", '
            '"steps": ["step 1", "step 2", "step 3"]}\n'
            "]"
        )
        return prompt, similar_bugs_iter

    def _parse_fixes_json(self, raw: str) -> List[SuggestedFix]:
        """Shared JSON-response parsing, tolerant of markdown code fences that
        some local models add even when told not to."""
        raw = raw.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.lower().startswith("json"):
                raw = raw[4:]

        fixes_data: list = json.loads(raw)
        fixes: List[SuggestedFix] = []
        for item in fixes_data[:5]:
            priority = item.get("priority", "medium")
            if priority not in ("high", "medium", "low"):
                priority = "medium"
            fixes.append(SuggestedFix(
                description=item.get("description", ""),
                steps=item.get("steps", []),
                priority=priority,
            ))
        return fixes

    def _generate_ai_fixes(
        self,
        original_query: str,
        similar_bugs: list,
        root_causes: List[RootCause],
    ) -> Optional[List[SuggestedFix]]:
        return self._generate_with_chat_provider(original_query, similar_bugs, root_causes)

    def _generate_with_chat_provider(
        self,
        original_query: str,
        similar_bugs,
        root_causes: List[RootCause],
    ) -> Optional[List[SuggestedFix]]:
        if isinstance(similar_bugs, str) and similar_bugs == "no match" and not root_causes:
            return "no match"
        if self.chat_provider is None:
            self.last_chat_provider = None
            self.last_chat_model = None
            return None

        monitoring = AzureAIMonitoring()
        prompt, similar_bugs_iter = self._build_fix_prompt(
            original_query, similar_bugs, root_causes
        )
        try:
            self.last_chat_provider = self.chat_provider.provider_name
            self.last_chat_model = self.chat_provider.model_name
            monitoring.trace_event(
                "recommendation_ai_fix_generation",
                {
                    "status": "started",
                    "model": self.last_chat_model,
                    "provider": self.last_chat_provider,
                    "original_query": original_query,
                    "similar_bug_count": len(similar_bugs_iter) if isinstance(similar_bugs, list) else 0,
                },
            )
            raw = self.chat_provider.complete(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a senior software engineer. "
                            "Provide precise, code-level debugging guidance. "
                            "Always respond with valid JSON only — no markdown fences."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=settings.recommendation_temperature,
                max_tokens=settings.recommendation_max_tokens,
            )
            fixes = self._parse_fixes_json(raw)
            monitoring.trace_event(
                "recommendation_ai_fix_generation",
                {
                    "status": "success",
                    "model": self.last_chat_model,
                    "provider": self.last_chat_provider,
                    "fix_count": len(fixes),
                    "original_query": original_query,
                },
            )
            return fixes if fixes else None
        except Exception as exc:
            monitoring.trace_event(
                "recommendation_ai_fix_generation",
                {
                    "status": "error",
                    "model": self.last_chat_model,
                    "provider": self.last_chat_provider,
                    "original_query": original_query,
                    "error": str(exc),
                },
            )
            self.last_chat_provider = None
            self.last_chat_model = None
            return None

    
    def _synthesize_root_causes(self, 
                               bug_analysis: Dict, 
                               context: Dict) -> List[RootCause]:
        """
        Combine insights to identify root causes
        """
        root_causes = []
        seen = set()
        
        # From bug analysis
        for cause in bug_analysis.get("root_causes", []):
            if cause not in seen:
                root_causes.append(RootCause(
                    description=cause,
                    confidence=0.7 if bug_analysis.get("bug_count", 0) > 2 else 0.5
                ))
                seen.add(cause)
        
        # From context analysis
        context_modules = context.get("modules", [])
        if context_modules:
            for module in context_modules:
                cause_desc = f"Issue in {module}"
                if cause_desc not in seen:
                    root_causes.append(RootCause(
                        description=cause_desc,
                        confidence=0.6
                    ))
                    seen.add(cause_desc)
        
        # Sort by confidence
        root_causes.sort(key=lambda x: x.confidence, reverse=True)
        
        return root_causes[:5]  # Top 5 root causes
    
    def _generate_fix_suggestions(self, 
                                 bug_fixes: List[str],
                                 context: Dict) -> List[SuggestedFix]:
        """
        Generate comprehensive fix suggestions
        """
        fixes = []
        
        # Immediate fixes (high priority)
        if bug_fixes:
            for i, fix in enumerate(bug_fixes[:2], 1):
                fixes.append(SuggestedFix(
                    description=f"Applied Fix {i}: {fix}",
                    steps=[
                        f"Review the fix: {fix}",
                        "Implement the solution in your code",
                        "Test the changes thoroughly"
                    ],
                    priority="high"
                ))
        
        # Preventive measures (medium priority)
        preventive_steps = [
            SuggestedFix(
                description="Add comprehensive logging",
                steps=[
                    "Enable debug logging for affected modules",
                    "Log request/response details",
                    "Monitor performance metrics"
                ],
                priority="medium"
            ),
            SuggestedFix(
                description="Implement proper error handling",
                steps=[
                    "Add try-catch blocks",
                    "Log exceptions with full stack trace",
                    "Provide meaningful error messages"
                ],
                priority="medium"
            )
        ]
        
        fixes.extend(preventive_steps)
        
        return fixes
    def _calculate_confidence(self, bug_analysis: Dict, wiki_knowledge: Dict) -> float:
        """
        Calculate overall confidence in the recommendations
        """
        confidence = 0.0
        
        # Higher confidence if we found similar bugs
        bug_count = bug_analysis.get("bug_count", 0)
        if bug_count >= 3:
            confidence += 0.4
        elif bug_count >= 1:
            confidence += 0.2
        
        # Higher confidence if we found wiki knowledge
        page_count = wiki_knowledge.get("page_count", 0)
        if page_count >= 3:
            confidence += 0.3
        elif page_count >= 1:
            confidence += 0.15
        
        # Base confidence
        confidence += 0.25
        
        # Cap at 1.0
        return min(confidence, 1.0)