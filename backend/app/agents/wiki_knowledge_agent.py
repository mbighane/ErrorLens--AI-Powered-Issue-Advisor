"""
📘 Wiki Knowledge Agent
Searches lessons learned from Azure DevOps wiki
"""

from typing import Dict, Any, List
from .base_agent import Agent
from ..services.ado_wiki_search_service import ADOWikiSearchService
from ..schemas.issue_schemas import WikiResult

class WikiKnowledgeAgent(Agent):
    """
    Searches wiki knowledge base for lessons learned and troubleshooting guides
    """
    
    def __init__(self):
        super().__init__("📘 Wiki Knowledge Agent")
        self.wiki_service = ADOWikiSearchService()
    
    async def execute(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Search wiki and extract relevant knowledge
        """
        try:
            # Search wiki pages
            wiki_pages = await self.wiki_service.search_wiki_pages(query, top_k)
            
            return {
                "agent": self.name,
                "status": "success",
                "wiki_pages": wiki_pages,
                "page_count": len(wiki_pages)
            }
        except Exception as e:
            return {
                "agent": self.name,
                "status": "error",
                "error": str(e),
                "wiki_pages": [],
                "page_count": 0
            }
    
