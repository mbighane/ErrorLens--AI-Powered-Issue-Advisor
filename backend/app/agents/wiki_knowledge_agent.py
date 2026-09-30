"""
📘 Wiki Knowledge Agent
Searches lessons learned from Azure DevOps wiki
"""

from typing import Dict, Any, List
from .base_agent import Agent
from ..schemas.issue_schemas import WikiResult
from ..providers.factory import create_search_provider
from ..providers.interfaces import ISearchProvider

class WikiKnowledgeAgent(Agent):
    """
    Searches wiki knowledge base for lessons learned and troubleshooting guides
    """
    
    def __init__(self, search_provider: ISearchProvider | None = None):
        super().__init__("📘 Wiki Knowledge Agent")
        self.search_provider = search_provider or create_search_provider()
    
    async def execute(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Search wiki and extract relevant knowledge
        """
        try:
            # Search wiki pages
            wiki_pages_raw = await self.search_provider.search_wiki(query, top_k)

            # Normalize sentinel: services may return the string "no match"
            no_match = False
            if isinstance(wiki_pages_raw, str) and wiki_pages_raw == "no match":
                wiki_pages = []
                no_match = True
            else:
                wiki_pages = wiki_pages_raw or []

            return {
                "agent": self.name,
                "status": "success",
                "wiki_pages": wiki_pages,
                "page_count": len(wiki_pages),
                "no_match": no_match,
            }
        except Exception as e:
            return {
                "agent": self.name,
                "status": "error",
                "error": str(e),
                "wiki_pages": [],
                "page_count": 0
            }
    
