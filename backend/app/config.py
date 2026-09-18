import os
from dotenv import load_dotenv

load_dotenv(override=True)

class Settings:
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", 6379))
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    azure_devops_org: str = os.getenv("AZURE_DEVOPS_ORG", "")
    azure_devops_project: str = os.getenv("AZURE_DEVOPS_PROJECT", "")
    azure_devops_token: str = os.getenv("AZURE_DEVOPS_TOKEN", "")
    # Directory where local vector embeddings are persisted
    vector_index_dir: str = os.getenv("VECTOR_INDEX_DIR", "data/vector_index")
    # Minimum similarity score required for a result to be considered a match.
    # Keep it strict enough to avoid bad matches, but low enough to show valid near-matches.
    search_similarity_threshold: float = float(os.getenv("SEARCH_SIMILARITY_THRESHOLD", 0.35))

settings = Settings()