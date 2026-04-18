"""
🧪 Recommendation Agent
Combines insights from all agents and generates final recommendations
"""

import json
from typing import Dict, Any, List, Optional
from .base_agent import Agent
from ..schemas.issue_schemas import RootCause, SuggestedFix
from ..config import settings


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
    
    def __init__(self):
        super().__init__("🧪 Recommendation Agent")
    
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
            if not fixes:
                fixes = self._generate_fix_suggestions(
                    bug_analysis.get("fixes", []),
                    integration_context,
                )
            
            return {
                "agent": self.name,
                "status": "success",
                "root_causes": root_causes,
                "suggested_fixes": fixes,
                "confidence_level": self._calculate_confidence(bug_analysis, wiki_knowledge)
            }
        except Exception as e:
            return {
                "agent": self.name,
                "status": "error",
                "error": str(e),
                "root_causes": [],
                "suggested_fixes": []
            }

    def _generate_ai_fixes(
        self,
        original_query: str,
        similar_bugs: list,
        root_causes: List[RootCause],
    ) -> Optional[List[SuggestedFix]]:
        """
        Use OpenAI GPT to generate programmer-friendly, query-specific fix suggestions
        based on the actual similar bugs found and identified root causes.
        Falls back to None if OpenAI is unavailable.
        """
        if not settings.openai_api_key:
            return None

        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)

            # Build context from similar bugs
            bugs_context_lines = []
            for bug in similar_bugs[:5]:
                score = getattr(bug, "similarity_score", 0.0)
                title = getattr(bug, "title", "")
                desc = getattr(bug, "description", "") or ""
                # Pull out Root Cause Analysis from description if embedded
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

            response = client.chat.completions.create(
                model="gpt-4o-mini",
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
                temperature=0.3,
                max_tokens=1200,
            )

            raw = response.choices[0].message.content.strip()
            # Strip markdown code fences if model adds them anyway
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
            print(f"[RecommendationAgent] AI generated {len(fixes)} fix suggestion(s).")
            return fixes if fixes else None

        except Exception as exc:
            print(f"[RecommendationAgent] AI fix generation failed: {exc}")
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