"""
Script to ingest wiki pages from Azure DevOps knowledge base
"""

import asyncio
from backend.app.services.azure_devops_connector import AzureDevOpsConnector
from backend.app.services.local_vector_search_service import LocalVectorSearchService
from backend.app.services.redis_vector_search_service import RedisVectorSearchService

async def ingest_wiki():
    """
    Fetch wiki pages from Azure DevOps and embed them into the local vector index.
    Also indexes into Redis if Redis Stack is available.
    """
    print("📘 Starting wiki ingestion from Azure DevOps...")
    
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
        
        # Common wiki search queries
        search_queries = [
            "deployment",
            "build",
            "configuration",
            "troubleshooting",
            "setup",
            "installation",
            "integration",
            "testing",
            "best practices",
            "lessons learned"
        ]
        
        all_wiki_pages = []
        
        for query in search_queries:
            print(f"  🔎 Searching wiki for: '{query}'")
            wiki_pages = await connector.search_wiki_pages(query, top_k=5)
            all_wiki_pages.extend(wiki_pages)
            print(f"     ✓ Found {len(wiki_pages)} wiki pages")
        
        print(f"\n✅ Total wiki pages ingested: {len(all_wiki_pages)}")
        
        indexed_count = vector_service.index_wiki_pages(all_wiki_pages)
        print(f"📦 Indexed {indexed_count} new wiki page(s) in local vector store")

        # Also index into Redis if available.
        try:
            redis_count = redis_service.index_wiki_pages(all_wiki_pages)
            if redis_count:
                print(f"📦 Also indexed {redis_count} wiki page(s) into Redis vector store")
        except Exception:
            pass
        if all_wiki_pages:
            print(f"\n📌 Sample wiki page:")
            page = all_wiki_pages[0]
            print(f"   Title: {page['title']}")
            print(f"   Path: {page['path']}")
        
    except Exception as e:
        print(f"❌ Error during wiki ingestion: {str(e)}")
        print("Make sure your Azure DevOps credentials are set in .env")

if __name__ == "__main__":
    asyncio.run(ingest_wiki())