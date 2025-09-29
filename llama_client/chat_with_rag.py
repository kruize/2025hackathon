# chat_with_rag.py

import os
import uuid
import time
import argparse

from llama_stack_client import LlamaStackClient, Agent


def create_agent(client, llm_model, vector_db_id):
    tools = [
        {
            "name": "builtin::rag/knowledge_search",
            "args": {"vector_db_ids": [vector_db_id], "max_chunks_returned": 3},
        },
        {
            "name": "builtin::websearch",
            "args": {"max_results": 3},
        },
    ]

    return Agent(
        client,
        model=llm_model,
        instructions="You are a helpful assistant. Use retrieved knowledge or web search results to answer questions.",
        tools=tools,
        sampling_params={"max_tokens": 1024, "temperature": 0.7},
        tool_config={"tool_choice": "auto", "fallback_behavior": "continue_without_tools"}
    )


def main(base_url, folder_path=None, questions_file=None, tavily_api_key=None, vector_db_id=None):
    if not vector_db_id or not str(vector_db_id).strip():
        if os.path.exists(".vector_db_id") and (content := open(".vector_db_id").read().strip()):
            vector_db_id = content
            print(f"📂 Loaded vector DB ID from file: {vector_db_id}")
        else:
            # Try fetching existing vector DBs from client
            dbs = [db for db in client.vector_dbs.list() if db is not None]
            if dbs:
                vector_db_id = dbs[0].provider_resource_id #vector_db_name
                print(f"📚 Using existing vector DB from server: {vector_db_id}")
            else:
                # If no DBs exist
                print("❌ No vector DB ID provided or found. Run ingestion first.")
                return
    else:
        print(f"📚 Using vector DB ID provided: {vector_db_id}")

    provider_data = {"tavily_search_api_key": tavily_api_key} if tavily_api_key else None
    client = LlamaStackClient(base_url=base_url, provider_data=provider_data)
    print(f"✅ Connected to Llama Stack at {base_url}")

    models = client.models.list()
    llm_model = next(m.identifier for m in models if m.model_type == "llm")
    print(f"📌 LLM Model: {llm_model}")

    agent = create_agent(client, llm_model, vector_db_id)
    session_id = agent.create_session(session_name=f"rag_chat_{uuid.uuid4().hex[:6]}")
    print(f"🧠 Session created: {session_id}")

    if questions_file:
        print(f"\n📜 Running scripted questions from: {questions_file}")
        with open(questions_file, "r", encoding="utf-8") as qf:
            questions = [line.strip() for line in qf if line.strip()]

        for idx, question in enumerate(questions, 1):
            print(f"\nQ{idx}: {question}")
            try:
                resp = agent.create_turn(
                    messages=[{"role": "user", "content": question}],
                    session_id=session_id,
                    stream=False,
                )
                answer = resp.output_message.content if resp.output_message else "(no response)"
            except Exception as e:
                answer = f"(Error: {e})"
            print(f"🤖 Assistant: {answer}")

            if idx != len(questions):
                print("⏳ Waiting 10 secs before the next question...\n")
                time.sleep(10)

    # Mode 2: Interactive
    else:
        print("\n💬 Interactive mode. Type your questions (or 'exit' to quit):")
        while True:
            try:
                query = input("\nYou: ").strip()
                if query.lower() in ("exit", "quit"):
                    print("👋 Exiting. Goodbye!")
                    break

                resp = agent.create_turn(
                    messages=[{"role": "user", "content": query}],
                    session_id=session_id,
                    stream=False,
                )
                answer = resp.output_message.content if resp.output_message else "(no response)"
                print(f"🤖 Assistant: {answer}")
            except Exception as e:
                print(f"(Error: {e})")

# 🚀 Entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Multi-file RAG + Websearch Chat")
    parser.add_argument("folder", nargs="?", default=None, help="Optinal Path to folder containing knowledge files")
    parser.add_argument("--base_url", default="http://localhost:8321", help="Llama Stack base URL")
    parser.add_argument("--questions_file", help="Optional file with one question per line")
    parser.add_argument("--tavily_api_key", help="Tavily Search API key")
    parser.add_argument("--vector_db_id", help="Reuse existing vector DB ID")

    args = parser.parse_args()
    main(args.base_url, args.folder, args.questions_file, args.tavily_api_key, args.vector_db_id)


