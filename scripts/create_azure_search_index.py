"""Create the Azure AI Search index used by ErrorLens."""

import os

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
)


def main() -> None:
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
        SearchableField(name="path", type=SearchFieldDataType.String),
        SearchableField(name="url", type=SearchFieldDataType.String),
        SearchableField(name="category", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="source", type=SearchFieldDataType.String, filterable=True),
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
                    ],
                ),
            )
        ]
    )

    index = SearchIndex(
        name=index_name,
        fields=fields,
        semantic_search=semantic_search,
    )

    client = SearchIndexClient(endpoint=endpoint, credential=AzureKeyCredential(api_key))
    result = client.create_or_update_index(index)
    print(f"Created or updated Azure AI Search index '{result.name}'")
    print(f"Semantic profile configured: '{semantic_profile}'")
    print("Fields:", ", ".join(field.name for field in result.fields))


if __name__ == "__main__":
    main()
