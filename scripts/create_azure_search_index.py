"""Create the Azure AI Search index used by ErrorLens."""

import os

from dotenv import load_dotenv

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SearchableField,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
)


def main() -> None:
    load_dotenv(override=True)
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "").strip()
    api_key = os.getenv("AZURE_SEARCH_API_KEY", "").strip()
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "bug-search-index").strip()
    semantic_profile = os.getenv("AZURE_SEARCH_SEMANTIC_CONFIGURATION", "default").strip() or "default"

    if not endpoint or not api_key:
        raise RuntimeError("AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY must be set in the environment.")

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, sortable=True, filterable=True, facetable=True),
        SearchableField(name="title", type=SearchFieldDataType.String, sortable=True),
        SearchableField(name="description", type=SearchFieldDataType.String),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SearchableField(name="root_cause_analysis", type=SearchFieldDataType.String),
        SearchableField(name="path", type=SearchFieldDataType.String),
        SearchableField(name="url", type=SearchFieldDataType.String),
        SearchableField(name="category", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="source", type=SearchFieldDataType.String, filterable=True),
        SearchField(
            name="contentVector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=int(os.getenv("AZURE_OPENAI_EMBEDDING_DIMS", "1536")),
            vector_search_profile_name="content-vector-profile",
        ),
    ]

    semantic_search = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name=semantic_profile,
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="title"),
                    content_fields=[
                        SemanticField(field_name="description"),
                        SemanticField(field_name="content"),
                        SemanticField(field_name="root_cause_analysis"),
                    ],
                ),
            )
        ]
    )

    index = SearchIndex(
        name=index_name,
        fields=fields,
        semantic_search=semantic_search,
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="content-vector-algorithm")],
            profiles=[
                VectorSearchProfile(
                    name="content-vector-profile",
                    algorithm_configuration_name="content-vector-algorithm",
                )
            ],
        ),
    )

    client = SearchIndexClient(endpoint=endpoint, credential=AzureKeyCredential(api_key))
    try:
        client.delete_index(index_name)
        print(f"Deleted existing Azure AI Search index '{index_name}'")
    except Exception as exc:
        if "not found" not in str(exc).lower() and "resource_not_found" not in str(exc).lower():
            raise
    result = client.create_index(index)
    print(f"Created or updated Azure AI Search index '{result.name}'")
    print(f"Semantic profile configured: '{semantic_profile}'")
    print("Fields:", ", ".join(field.name for field in result.fields))


if __name__ == "__main__":
    main()
