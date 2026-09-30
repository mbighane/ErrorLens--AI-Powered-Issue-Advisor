from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class QueryInput(BaseModel):
    user_id: str = Field(..., min_length=1, description="Unique user/session id")
    message: str = Field(..., min_length=2, description="Issue description from user")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)


class IssueSolveRequest(QueryInput):
    pass


class BugTicket(BaseModel):
    id: str
    title: str
    description: str = ""
    state: Optional[str] = None
    assigned_to: Optional[str] = None
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    source: Optional[str] = None
    url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BugResult(BugTicket):
    pass


class WikiResult(BaseModel):
    title: str
    content: str = ""
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    source: Optional[str] = None
    path: Optional[str] = None
    url: Optional[str] = None


class RootCause(BaseModel):
    description: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class SuggestedFix(BaseModel):
    description: str
    steps: List[str] = Field(default_factory=list)
    priority: Literal["high", "medium", "low"] = "medium"


class ModelInfo(BaseModel):
    """Reports which actual model/backend served this response, so the UI can
    show users whether they got a cloud or local (Ollama) result, and which
    retrieval backend was used — rather than users having to guess."""

    deployment_mode: Literal["azure", "on_prem"] = "azure"
    chat_provider: Optional[Literal["azure_openai", "ollama", "template"]] = None
    chat_model: Optional[str] = None
    retrieval_backend: Optional[Literal["azure_ai_search", "local_vector_index"]] = None


class IssueSolveResponse(BaseModel):
    analysis: str
    similar_bugs: List[BugResult] = Field(default_factory=list)
    relevant_wiki: List[WikiResult] = Field(default_factory=list)
    root_causes: List[RootCause] = Field(default_factory=list)
    suggested_fixes: List[SuggestedFix] = Field(default_factory=list)
    model_info: Optional[ModelInfo] = None
