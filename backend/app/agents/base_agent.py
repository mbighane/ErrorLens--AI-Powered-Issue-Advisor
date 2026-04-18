"""
Base Agent class - foundation for all specialized agents
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

class Agent(ABC):
    """
    Abstract base class for all agents in the multi-agent system
    """
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the agent's task
        Returns a dictionary with results
        """
        pass
    
    def __repr__(self):
        return f"<{self.name}>"