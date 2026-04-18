from functools import lru_cache

from fastapi import APIRouter, HTTPException
from ..schemas.issue_schemas import IssueSolveRequest, IssueSolveResponse
from ..agents.orchestrator_agent import OrchestratorAgent

router = APIRouter()


@lru_cache(maxsize=1)
def get_orchestrator() -> OrchestratorAgent:
    return OrchestratorAgent()

@router.post("/solve", response_model=IssueSolveResponse)
async def solve_issue(request: IssueSolveRequest):
    """
    Multi-agent issue solver endpoint
    
    Uses coordinated agents:
    - 🔍 Bug Analysis Agent
    - 📘 Wiki Knowledge Agent
    - 🔗 Integration Context Agent
    - 🧪 Recommendation Agent
    - 🧠 Orchestrator Agent (Brain)
    
    Request:
    {
        "user_id": "string",
        "message": "string - describe your issue"
    }
    
    Returns comprehensive analysis with root causes and solutions
    """
    try:
        orchestrator = get_orchestrator()
        response = await orchestrator.execute(request.message, request.user_id)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error solving issue: {str(e)}")