import os
from dotenv import load_dotenv

load_dotenv(override=False)


class Settings:
    # Deployment mode: "azure" (default) uses Azure AI Search + Azure OpenAI as the
    # managed cloud path. "on_prem" disables Azure entirely — even if Azure credentials
    # are present in the environment — and restricts the app to Ollama and local vector search.
    # This is a deliberate customer-facing choice, not
    # something inferred from which env vars happen to be configured.
    deployment_mode: str = os.getenv("DEPLOYMENT_MODE", "azure").strip().lower()
    if deployment_mode not in {"azure", "on_prem"}:
        raise ValueError("DEPLOYMENT_MODE must be either 'azure' or 'on_prem'")

    @property
    def is_on_prem_deployment(self) -> bool:
        return self.deployment_mode == "on_prem"

    # Ollama settings — used exclusively when deployment_mode=on_prem. Ollama
    # exposes an OpenAI-compatible API, so the same `openai` SDK is reused
    # here, just pointed at a local endpoint instead of Azure/OpenAI's cloud.
    # Requires an Ollama server running locally with these models pulled:
    #   ollama pull llama3.1          (or whichever chat model you choose)
    #   ollama pull nomic-embed-text  (or whichever embedding model you choose)
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    ollama_api_key: str = os.getenv("OLLAMA_API_KEY", "ollama")
    ollama_enabled: bool = os.getenv("OLLAMA_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    ollama_chat_model: str = os.getenv("OLLAMA_CHAT_MODEL", "llama3.1")
    ollama_embedding_model: str = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
    # nomic-embed-text produces 768-dim vectors, vs. 1536 for OpenAI/Azure
    # embeddings — these are NOT interchangeable. Switching a deployment
    # between on_prem and azure mode requires re-indexing from scratch, since
    # existing embeddings won't match the new model's dimensionality.
    ollama_embedding_dims: int = int(os.getenv("OLLAMA_EMBEDDING_DIMS", "768"))

    # Ollama local LLM settings for on-prem deployments
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    ollama_enabled: bool = os.getenv("OLLAMA_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    ollama_embedding_model: str = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
    ollama_chat_model: str = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2")

    # Azure OpenAI Service settings.
    # Deployment names are resource-specific and must match the Azure OpenAI resource exactly.
    # If the Azure resource does not expose these deployments, Azure AI generation is
    # unavailable and the recommendation agent uses its template-based fallback.
    azure_openai_api_key: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    azure_openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    azure_openai_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
    azure_openai_chat_deployment: str = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "").strip()
    azure_openai_embedding_deployment: str = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "").strip()
    azure_openai_embedding_dims: int = int(os.getenv("AZURE_OPENAI_EMBEDDING_DIMS", "1536"))
    use_azure_openai: bool = bool(
        deployment_mode != "on_prem"
        and azure_openai_api_key
        and azure_openai_endpoint
        and azure_openai_chat_deployment
        and azure_openai_embedding_deployment
    )

    # Azure AI Search configuration
    # Keep this aligned with the exact index/profile deployed for the app.
    azure_search_api_key: str = os.getenv("AZURE_SEARCH_API_KEY", "")
    azure_search_endpoint: str = os.getenv("AZURE_SEARCH_ENDPOINT", "")
    azure_search_index_name: str = os.getenv("AZURE_SEARCH_INDEX_NAME", "bug-search-index")
    azure_search_semantic_configuration: str = os.getenv("AZURE_SEARCH_SEMANTIC_CONFIGURATION", "default")
    azure_search_semantic_fields: str = os.getenv(
        "AZURE_SEARCH_SEMANTIC_FIELDS",
        "id,title,description,content,root_cause_analysis,path,url,category,source",
    )
    azure_search_use_semantic_search: bool = (
        deployment_mode != "on_prem"
        and os.getenv("AZURE_SEARCH_USE_SEMANTIC_SEARCH", "true").lower() in {"1", "true", "yes", "on"}
        and bool(os.getenv("AZURE_SEARCH_SEMANTIC_CONFIGURATION", "default").strip())
    )
    azure_semantic_reranker_max_score: float = float(
        os.getenv("AZURE_SEMANTIC_RERANKER_MAX_SCORE", "4.0")
    )
    azure_semantic_min_reranker_score: float = float(
        os.getenv("AZURE_SEMANTIC_MIN_RERANKER_SCORE", "1.0")
    )
    azure_query_expansion_enabled: bool = os.getenv(
        "AZURE_QUERY_EXPANSION_ENABLED", "true"
    ).lower() in {"1", "true", "yes", "on"}
    azure_search_enabled: bool = bool(
        deployment_mode != "on_prem"
        and azure_search_api_key
        and azure_search_endpoint
        and azure_search_index_name
    )

    # Azure Monitor / Application Insights configuration for live tracing
    azure_monitor_connection_string: str = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "") or os.getenv("AZURE_MONITOR_CONNECTION_STRING", "")
    azure_monitor_tracing_enabled: bool = (
        deployment_mode != "on_prem"
        and os.getenv("AZURE_MONITOR_TRACING_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    )
    azure_monitor_trace_name: str = os.getenv("AZURE_MONITOR_TRACE_NAME", "errorlens-ai-trace")

    azure_devops_org: str = os.getenv("AZURE_DEVOPS_ORG", "")
    azure_devops_project: str = os.getenv("AZURE_DEVOPS_PROJECT", "")
    azure_devops_token: str = os.getenv("AZURE_DEVOPS_TOKEN", "")

    # Directory where local vector embeddings are persisted
    vector_index_dir: str = os.getenv("VECTOR_INDEX_DIR", "data/vector_index")
    index_refresh_hours: int = int(os.getenv("INDEX_REFRESH_HOURS", "48"))

    # Search tuning and match gating
    search_similarity_threshold: float = float(os.getenv("SEARCH_SIMILARITY_THRESHOLD", 0.06))
    exact_match_min_score: float = float(os.getenv("EXACT_MATCH_MIN_SCORE", "0.08"))
    title_overlap_min_score: float = float(os.getenv("TITLE_OVERLAP_MIN_SCORE", "0.18"))
    semantic_title_overlap_min_score: float = float(os.getenv("SEMANTIC_TITLE_OVERLAP_MIN_SCORE", "0.03"))

    # Hybrid retrieval weights
    hybrid_semantic_weight: float = float(os.getenv("HYBRID_SEMANTIC_WEIGHT", "0.6"))
    hybrid_exact_match_weight: float = float(os.getenv("HYBRID_EXACT_MATCH_WEIGHT", "0.4"))
    hybrid_rrf_k: int = int(os.getenv("HYBRID_RRF_K", "60"))

    # Local vector tuning
    max_embedding_text_chars: int = int(os.getenv("MAX_EMBEDDING_TEXT_CHARS", "4000"))
    query_expansion_temperature: float = float(os.getenv("QUERY_EXPANSION_TEMPERATURE", "0.2"))
    query_expansion_max_tokens: int = int(os.getenv("QUERY_EXPANSION_MAX_TOKENS", "80"))
    query_context_snippet_chars: int = int(os.getenv("QUERY_CONTEXT_SNIPPET_CHARS", "300"))
    wiki_keyword_bonus_per_match: float = float(os.getenv("WIKI_KEYWORD_BONUS_PER_MATCH", "0.04"))
    wiki_keyword_bonus_cap: float = float(os.getenv("WIKI_KEYWORD_BONUS_CAP", "0.15"))
    wiki_content_preview_chars: int = int(os.getenv("WIKI_CONTENT_PREVIEW_CHARS", "2000"))

    # Recommendation generation tuning
    recommendation_temperature: float = float(os.getenv("RECOMMENDATION_TEMPERATURE", "0.3"))
    recommendation_max_tokens: int = int(os.getenv("RECOMMENDATION_MAX_TOKENS", "1200"))

    # ADO bug-match scoring tuning
    ado_theme_weight: float = float(os.getenv("ADO_THEME_WEIGHT", "0.6"))
    ado_title_weight: float = float(os.getenv("ADO_TITLE_WEIGHT", "0.4"))
    ado_exact_title_bonus: float = float(os.getenv("ADO_EXACT_TITLE_BONUS", "0.35"))
    ado_near_title_bonus: float = float(os.getenv("ADO_NEAR_TITLE_BONUS", "0.20"))


settings = Settings()