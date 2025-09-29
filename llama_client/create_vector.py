import uuid
import argparse

from llama_stack_client import LlamaStackClient, Document


def main(base_url):
    tavily_api_key = None
    provider_data = {"tavily_search_api_key": tavily_api_key} if tavily_api_key else None
    client = LlamaStackClient(base_url=base_url, provider_data=provider_data)
    print(f"✅ Connected to Llama Stack at {base_url}")

    models = client.models.list()
    embedding_model = next(m.identifier for m in models if m.model_type == "embedding")
    print(f"📌 Embedding Model: {embedding_model}")

    vector_db_id = f"vb_{uuid.uuid4().hex[:8]}"
    client.vector_dbs.register(vector_db_id=vector_db_id, embedding_model=embedding_model)
    print(f"🆕 Created new vector DB: {vector_db_id}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="create new vector")
    parser.add_argument("--base_url", default="http://localhost:8321", help="Llama Stack base URL")

    args = parser.parse_args()
    main(args.base_url)

