import os
from dotenv import load_dotenv

load_dotenv(override=True)


class Settings:
    # OpenAI compatibility settings
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_chat_model: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")

    # Azure OpenAI Service settings
    azure_openai_api_key: str = os.getenv("AZURE_OPENAI_API_KEY", openai_api_key)
    azure_openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    azure_openai_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
    azure_openai_chat_deployment: str = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", openai_chat_model)
    azure_openai_embedding_deployment: str = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
    use_azure_openai: bool = bool(azure_openai_api_key and azure_openai_endpoint)

    # Azure AI Search configuration
    azure_search_api_key: str = os.getenv("AZURE_SEARCH_API_KEY", "")
    azure_search_endpoint: str = os.getenv("AZURE_SEARCH_ENDPOINT", "")
    azure_search_index_name: str = os.getenv("AZURE_SEARCH_INDEX_NAME", "bug-search-index")
    azure_search_enabled: bool = bool(azure_search_api_key and azure_search_endpoint)

    # Azure Monitor / Application Insights configuration for live tracing
    azure_monitor_connection_string: str = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "") or os.getenv("AZURE_MONITOR_CONNECTION_STRING", "")
    azure_monitor_tracing_enabled: bool = os.getenv("AZURE_MONITOR_TRACING_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    azure_monitor_trace_name: str = os.getenv("AZURE_MONITOR_TRACE_NAME", "errorlens-ai-trace")

    azure_devops_org: str = os.getenv("AZURE_DEVOPS_ORG", "")
    azure_devops_project: str = os.getenv("AZURE_DEVOPS_PROJECT", "")
    azure_devops_token: str = os.getenv("AZURE_DEVOPS_TOKEN", "")
    # Directory where local vector embeddings are persisted
    vector_index_dir: str = os.getenv("VECTOR_INDEX_DIR", "data/vector_index")
    # Minimum similarity score required for a result to be considered a match.
    # Keep it strict enough to avoid bad matches, but low enough to show valid near-matches.
    search_similarity_threshold: float = float(os.getenv("SEARCH_SIMILARITY_THRESHOLD", 0.35))


settings = Settings()