"""
Script to ingest historical bugs from Azure DevOps
"""

import asyncio
from backend.app.services.azure_devops_connector import AzureDevOpsConnector
from backend.app.services.local_vector_search_service import LocalVectorSearchService
from backend.app.services.redis_vector_search_service import RedisVectorSearchService

async def ingest_bugs():
    """
    Fetch bugs from Azure DevOps and embed them into the local vector index.
    Also indexes into Redis if Redis Stack is available.
    """
    print("🔍 Starting bug ingestion from Azure DevOps...")
    
    try:
        connector = AzureDevOpsConnector()
        local_service = LocalVectorSearchService()
        redis_service = RedisVectorSearchService()

        if local_service.enabled:
            print("✅ Local vector search enabled — embeddings will be persisted locally.")
        else:
            print(f"⚠️  Local vector search disabled: {local_service.init_error}")

        # Keep the old variable name so the rest of the script is unchanged.
        vector_service = local_service
        
        # Common bug search queries to gather historical data
        search_queries = [
            "error",
            "crash",
            "failure",
            "bug",
            "issue",
            "broken",
            "not working",
            "exception",
            "timeout",
            "memory leak"
        ]
        
        all_bugs = []
        
        for query in search_queries:
            print(f"  🔎 Searching for bugs with keyword: '{query}'")
            bugs = await connector.search_bugs(query, top_k=5)
            all_bugs.extend(bugs)
            print(f"     ✓ Found {len(bugs)} bugs")
        
        print(f"\n✅ Total bugs ingested: {len(all_bugs)}")
        
        indexed_count = vector_service.index_bugs(all_bugs)
        print(f"📦 Indexed {indexed_count} new bug(s) in local vector store")

        # Also index into Redis if available.
        try:
            redis_count = redis_service.index_bugs(all_bugs)
            if redis_count:
                print(f"📦 Also indexed {redis_count} bug(s) into Redis vector store")
        except Exception:
            pass
        if all_bugs:
            print(f"\n📌 Sample bug:")
            bug = all_bugs[0]
            print(f"   ID: {bug['id']}")
            print(f"   Title: {bug['title']}")
            print(f"   State: {bug['state']}")
        
    except Exception as e:
        print(f"❌ Error during bug ingestion: {str(e)}")
        print("Make sure your Azure DevOps credentials are set in .env")

if __name__ == "__main__":
    asyncio.run(ingest_bugs())