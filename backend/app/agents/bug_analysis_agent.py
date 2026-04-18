"""
🔍 Bug Analysis Agent
Queries Azure DevOps for similar bugs, extracts root causes and fixes
"""

from typing import Dict, Any, List
from .base_agent import Agent
from ..services.ado_bug_search_service import ADOBugSearchService
from ..schemas.issue_schemas import BugResult

class BugAnalysisAgent(Agent):
    """
    Analyzes similar bugs from Azure DevOps
    Extracts:
    - Similar issues
    - Root causes
    - Applied fixes
    """
    
    def __init__(self):
        super().__init__("🔍 Bug Analysis Agent")
        self.bug_service = ADOBugSearchService()
    
    async def execute(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Search for similar bugs and extract patterns
        """
        try:
            # Search for similar bugs
            similar_bugs = await self.bug_service.search_similar_bugs(query, top_k)
            
            # Extract root causes from bug titles and descriptions
            root_causes = self._extract_root_causes_from_bugs(similar_bugs)
            
            # Extract fixes from bug discussions
            fixes = self._extract_fixes_from_bugs(similar_bugs)
            
            return {
                "agent": self.name,
                "status": "success",
                "similar_bugs": similar_bugs,
                "root_causes": root_causes,
                "fixes": fixes,
                "bug_count": len(similar_bugs)
            }
        except Exception as e:
            return {
                "agent": self.name,
                "status": "error",
                "error": str(e),
                "similar_bugs": [],
                "root_causes": [],
                "fixes": []
            }
    
    def _extract_root_causes_from_bugs(self, bugs: List[BugResult]) -> List[str]:
        """
        Extract common root causes from bug data
        """
        root_causes = set()
        
        for bug in bugs:
            # Look for common patterns in bug titles
            title_lower = bug.title.lower()
            
            if any(word in title_lower for word in ["null", "undefined", "none"]):
                root_causes.add("Null/Undefined reference")
            if any(word in title_lower for word in ["memory", "leak", "out of memory"]):
                root_causes.add("Memory management issue")
            if any(word in title_lower for word in ["timeout", "hang", "freeze"]):
                root_causes.add("Performance/Timeout issue")
            if any(word in title_lower for word in ["permission", "access", "denied"]):
                root_causes.add("Access/Permission issue")
            if any(word in title_lower for word in ["connection", "network", "endpoint"]):
                root_causes.add("Network/Connection issue")
            if any(word in title_lower for word in ["format", "parse", "invalid"]):
                root_causes.add("Data format/Parsing issue")
        
        return list(root_causes)
    
    def _extract_fixes_from_bugs(self, bugs: List[BugResult]) -> List[str]:
        """
        Extract common fixes/solutions from resolved bugs
        """
        fixes = set()
        
        for bug in bugs:
            description_lower = bug.description.lower()
            
            # Look for common fix patterns
            if any(word in description_lower for word in ["update", "upgrade", "patch"]):
                fixes.add("Apply latest patches/updates")
            if any(word in description_lower for word in ["cache", "clear", "reset"]):
                fixes.add("Clear cache or reset state")
            if any(word in description_lower for word in ["restart", "reboot", "refresh"]):
                fixes.add("Restart service/application")
            if any(word in description_lower for word in ["config", "setting", "parameter"]):
                fixes.add("Review configuration settings")
            if any(word in description_lower for word in ["log", "debug", "trace"]):
                fixes.add("Enable detailed logging for diagnosis")
        
        return list(fixes)