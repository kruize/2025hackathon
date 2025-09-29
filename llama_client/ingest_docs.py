# ingest_docs.py

import os
import uuid
import json
import csv
import time
import threading
import argparse

from llama_stack_client import LlamaStackClient, Document


def load_documents_from_folder(folder_path):
    SUPPORTED_EXTENSIONS = [".txt", ".md", ".json", ".csv"]
    docs = []

    for root, _, files in os.walk(folder_path):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue

            path = os.path.join(root, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    if ext in [".txt", ".md"]:
                        content = f.read()
                    elif ext == ".json":
                        data = json.load(f)
                        content = json.dumps(data, indent=2)
                    elif ext == ".csv":
                        reader = csv.reader(f)
                        rows = [" | ".join(row) for row in reader]
                        content = "\n".join(rows)
                    else:
                        continue

                doc = Document(
                    document_id=os.path.relpath(path, folder_path),
                    content=content,
                    mime_type="text/plain",
                    metadata={"source": path}
                )
                docs.append(doc)
            except Exception as e:
                print(f"❌ Failed to load {path}: {e}")

    return docs


def start_document_refresher(client, vector_db_id, folder_path, interval_secs=100):
    known_docs = {}

    def refresh_loop():
        while True:
            try:
                new_docs = []
                for root, _, files in os.walk(folder_path):
                    for filename in files:
                        ext = os.path.splitext(filename)[1].lower()
                        if ext not in [".txt", ".md", ".json", ".csv"]:
                            continue

                        path = os.path.join(root, filename)
                        rel_path = os.path.relpath(path, folder_path)
                        last_modified = os.path.getmtime(path)

                        if known_docs.get(rel_path) == last_modified:
                            continue

                        try:
                            with open(path, "r", encoding="utf-8") as f:
                                if ext in [".txt", ".md"]:
                                    content = f.read()
                                elif ext == ".json":
                                    content = json.dumps(json.load(f), indent=2)
                                elif ext == ".csv":
                                    reader = csv.reader(f)
                                    content = "\n".join([" | ".join(row) for row in reader])
                                else:
                                    continue

                            doc = Document(
                                document_id=rel_path,
                                content=content,
                                mime_type="text/plain",
                                metadata={"source": path}
                            )
                            new_docs.append(doc)
                            known_docs[rel_path] = last_modified
                        except Exception as e:
                            print(f"⚠️ Skipped {rel_path}: {e}")

                if new_docs:
                    client.tool_runtime.rag_tool.insert(
                        documents=new_docs,
                        vector_db_id=vector_db_id,
                        chunk_size_in_tokens=500,
                    )
                    print(f"🔁 RAG Refresh: {len(new_docs)} new/updated documents added.")
                else:
                    print("⏳ No document updates found.")
            except Exception as e:
                print(f"[RAG Refresher Error] {e}")
            time.sleep(interval_secs)

    thread = threading.Thread(target=refresh_loop, daemon=True)
    thread.start()
    print("🌀 RAG document refresher started.")

def main(folder_path, base_url, start_refresher=False, tavily_api_key=None, vector_db_id=None):
    provider_data = {"tavily_search_api_key": tavily_api_key} if tavily_api_key else None
    client = LlamaStackClient(base_url=base_url, provider_data=provider_data)
    print(f"✅ Connected to Llama Stack at {base_url}")

    models = client.models.list()
    embedding_model = next(m.identifier for m in models if m.model_type == "embedding")
    print(f"📌 Embedding Model: {embedding_model}")

    documents = load_documents_from_folder(folder_path)
    if not documents:
        print("❌ No supported documents found in folder. Exiting.")
        return

    print(f"📄 Loaded {len(documents)} documents from '{folder_path}' ")


    # 👉 Get or create vector_db_id
    if not vector_db_id or not str(vector_db_id).strip():
        # Try loading from saved file first
        #if os.path.exists(".vector_db_id"):
        if os.path.exists(".vector_db_id") and (content := open(".vector_db_id").read().strip()):
            vector_db_id = content
            print(f"📂 Loaded vector DB ID from file: {vector_db_id}")
        else:
            # Try fetching existing vector DBs from client
            dbs = [db for db in client.vector_dbs.list() if db is not None]
            print(f"📚 Using existing vector dbs {dbs}")
            if dbs:
                vector_db_id = dbs[0].provider_resource_id #vector_db_name
                print(f"📚 Using existing vector DB from server: {vector_db_id}")
            else:
                # If no DBs exist, create a new one
                vector_db_id = f"vb_{uuid.uuid4().hex[:8]}"
                client.vector_dbs.register(vector_db_id=vector_db_id, embedding_model=embedding_model)
                print(f"🆕 Created new vector DB: {vector_db_id}")
    else:
        print(f"📚 Using provided vector DB ID: {vector_db_id}")

    # Save vector DB ID for reuse
    with open(".vector_db_id", "w") as f:
        f.write(vector_db_id)

    # Insert documents
    '''
    client.tool_runtime.rag_tool.insert(
        documents=documents,
        vector_db_id=vector_db_id,
        chunk_size_in_tokens=500,
    )
    print(f"✅ Inserted documents into vector DB: {vector_db_id}")
    '''
    for idx, doc in enumerate(documents):
        try:
            client.tool_runtime.rag_tool.insert(
                    documents=[doc],  # Insert one document at a time
                    vector_db_id=vector_db_id,
                    chunk_size_in_tokens=500,
                    )
            print(f"✅ Inserted document {idx+1}/{len(documents)} into vector DB")
        except Exception as e:
            print(f"❌ Failed to insert document {idx+1}: {e}")


    # Start refresher if enabled
    if start_refresher:
        start_document_refresher(client, vector_db_id, folder_path)

    print("🏁 Ingestion completed.")


def mainloop(folder_path, base_url, start_refresher=False, tavily_api_key=None, vector_db_id=None):
    provider_data = {"tavily_search_api_key": tavily_api_key} if tavily_api_key else None
    client = LlamaStackClient(base_url=base_url, provider_data=provider_data)
    print(f"✅ Connected to Llama Stack at {base_url}")

    models = client.models.list()
    embedding_model = next(m.identifier for m in models if m.model_type == "embedding")
    print(f"📌 Embedding Model: {embedding_model}")

    documents = load_documents_from_folder(folder_path)
    if not documents:
        print("❌ No supported documents found in folder. Exiting.")
        return

    print(f"📄 Loaded {len(documents)} documents from '{folder_path}'")

    if not vector_db_id:
        vector_db_id = f"vb_{uuid.uuid4().hex[:8]}"
        client.vector_dbs.register(vector_db_id=vector_db_id, embedding_model=embedding_model)
        print(f"🆕 Created new vector DB: {vector_db_id}")
    else:
        print(f"📚 Using existing vector DB: {vector_db_id}")

    '''
    client.tool_runtime.rag_tool.insert(
        documents=documents,
        vector_db_id=vector_db_id,
        chunk_size_in_tokens=500,
    )
    print(f"✅ Inserted documents into vector DB: {vector_db_id}")
    '''
    for idx, doc in enumerate(documents):
        try:
            client.tool_runtime.rag_tool.insert(
                    documents=[doc],
                    vector_db_id=vector_db_id,
                    chunk_size_in_tokens=500,
                    )
            print(f"✅ Inserted document {idx+1}/{len(documents)} into vector DB")
        except Exception as e:
            print(f"❌ Failed to insert document {idx+1}: {e}")

    # Save vector DB ID for reuse
    with open(".vector_db_id", "w") as f:
        f.write(vector_db_id)

    if start_refresher:
        print("refresher started")
        start_document_refresher(client, vector_db_id, folder_path)

    print("🏁 Ingestion completed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest documents into Llama Stack RAG vector DB")
    parser.add_argument("folder", help="Path to folder containing knowledge files")
    parser.add_argument("--base_url", default="http://localhost:8321", help="Llama Stack base URL")
    parser.add_argument("--vector_db_id", help="Reuse existing vector DB ID")
    parser.add_argument("--start_refresher", action="store_true", help="Start live refresher thread")
    parser.add_argument("--tavily_api_key", help="Optional Tavily API key")

    args = parser.parse_args()
    main(args.folder, args.base_url, args.start_refresher, args.tavily_api_key, args.vector_db_id)

