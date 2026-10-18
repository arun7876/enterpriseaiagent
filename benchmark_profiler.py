import time
import json
import sqlite3
import numpy as np
import httpx
from pathlib import Path

print("=== STARTING BENCHMARK PROFILER ===")

# 1. Embedding Model Cold vs Warm
print("\n--- 1. EMBEDDING MODEL INITIALIZATION & ENCODE ---")
t0 = time.perf_counter()
from sentence_transformers import SentenceTransformer
import_time = time.perf_counter() - t0
print(f"sentence_transformers library import: {import_time * 1000:.2f} ms")

t0 = time.perf_counter()
embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
load_time = time.perf_counter() - t0
print(f"Model initialization (cold load from disk): {load_time * 1000:.2f} ms")

# Warm encode 1 query
t0 = time.perf_counter()
q_emb = embedder.encode(["What are the key policy requirements?"], normalize_embeddings=True)
q_time = time.perf_counter() - t0
print(f"Single query encode (warm): {q_time * 1000:.2f} ms (shape: {q_emb.shape})")

# Warm encode batch of 5 chunks
chunks = [
    f"This is chunk number {i} containing corporate policy data and financial information."
    for i in range(5)
]
t0 = time.perf_counter()
batch_emb = embedder.encode(chunks, normalize_embeddings=True)
batch_time = time.perf_counter() - t0
print(f"Batch of 5 chunks encode: {batch_time * 1000:.2f} ms")

# 2. SQLite Vector Index Inspection & Search Latency
print("\n--- 2. SQLITE VECTOR INDEX SEARCH LATENCY ---")
from backend.app.config import settings
from backend.app.retriever import LocalVectorRetriever, SentenceTransformerEmbedder

wrapped_embedder = SentenceTransformerEmbedder()
wrapped_embedder._model = embedder  # reuse already warm model
retriever = LocalVectorRetriever(embedder=wrapped_embedder)
t0 = time.perf_counter()
chunk_count = retriever.count_chunks()
count_time = time.perf_counter() - t0
print(f"Vector index chunk count: {chunk_count} (counted in {count_time * 1000:.2f} ms)")

t0 = time.perf_counter()
results = retriever.search("annual leave policy", top_k=5)
search_time = time.perf_counter() - t0
print(f"Vector search 'annual leave policy' (top_k=5): {search_time * 1000:.2f} ms, retrieved {len(results)} chunks")

# 3. Ollama API Latency & Generation Breakdown
print("\n--- 3. OLLAMA API LATENCY & GENERATION ---")
ollama_url = settings.ollama_base_url.rstrip("/")
model_name = settings.ollama_model

t0 = time.perf_counter()
try:
    resp = httpx.get(f"{ollama_url}/api/tags", timeout=5.0)
    tags_time = time.perf_counter() - t0
    print(f"Ollama GET /api/tags: {tags_time * 1000:.2f} ms, status: {resp.status_code}")
except Exception as e:
    print(f"Ollama tags error: {e}")

# Test Ollama Generate
test_prompt = (
    "You are a document-grounded research assistant. Evidence JSON: [{\"source_id\": \"S1\", \"text\": \"Annual leave is 20 days per year.\"}]\n\n"
    "Question: \"What is the annual leave policy?\"\nGrounded answer:"
)
print("Testing Ollama generation...")
t0 = time.perf_counter()
try:
    resp = httpx.post(
        f"{ollama_url}/api/generate",
        json={
            "model": model_name,
            "prompt": test_prompt,
            "stream": False,
            "options": {"temperature": 0},
        },
        timeout=60.0,
    )
    gen_time = time.perf_counter() - t0
    data = resp.json()
    answer = data.get("response", "")
    total_duration_ns = data.get("total_duration", 0)
    load_duration_ns = data.get("load_duration", 0)
    prompt_eval_count = data.get("prompt_eval_count", 0)
    prompt_eval_duration_ns = data.get("prompt_eval_duration", 0)
    eval_count = data.get("eval_count", 0)
    eval_duration_ns = data.get("eval_duration", 0)

    print(f"Ollama generation total HTTP time: {gen_time * 1000:.2f} ms")
    print(f"  Model load duration: {load_duration_ns / 1e6:.2f} ms")
    print(f"  Prompt tokens: {prompt_eval_count} in {prompt_eval_duration_ns / 1e6:.2f} ms ({prompt_eval_count / (prompt_eval_duration_ns / 1e9 or 1):.1f} tok/s)")
    print(f"  Generated tokens: {eval_count} in {eval_duration_ns / 1e6:.2f} ms ({eval_count / (eval_duration_ns / 1e9 or 1):.1f} tok/s)")
    print(f"  Response: {answer[:80]}...")
except Exception as e:
    print(f"Ollama generate error: {e}")

# Second generation (Warm)
t0 = time.perf_counter()
try:
    resp = httpx.post(
        f"{ollama_url}/api/generate",
        json={
            "model": model_name,
            "prompt": test_prompt,
            "stream": False,
            "options": {"temperature": 0},
        },
        timeout=60.0,
    )
    gen_time_warm = time.perf_counter() - t0
    data = resp.json()
    print(f"Ollama second generation (warm) total HTTP time: {gen_time_warm * 1000:.2f} ms")
    print(f"  Model load duration (warm): {data.get('load_duration', 0) / 1e6:.2f} ms")
except Exception as e:
    print(f"Ollama warm generate error: {e}")

# 4. RAG Service End-to-End
print("\n--- 4. RAG SERVICE END-TO-END ---")
from backend.app.rag_service import get_default_rag_service
rag_service = get_default_rag_service()

t0 = time.perf_counter()
rag_ans = rag_service.ask("What is the annual leave policy?")
rag_time = time.perf_counter() - t0
print(f"RAG ask end-to-end: {rag_time * 1000:.2f} ms (internal processing_time_ms: {rag_ans.processing_time_ms:.2f} ms)")
print(f"  Answer: {rag_ans.answer[:80]}...")
print(f"  Citations: {len(rag_ans.citations)}")

# 5. Agent Workflow End-to-End
print("\n--- 5. AGENT WORKFLOW END-TO-END ---")
from backend.app.agent_api import get_default_agent
agent = get_default_agent()

# 5a. SQL tool query
t0 = time.perf_counter()
sql_ans = agent.ask("What were total sales from 2026-09-01 to 2026-09-30?")
sql_time = time.perf_counter() - t0
print(f"Agent SQL query 'total sales': {sql_time * 1000:.2f} ms (workflow: {sql_ans.workflow}, tools: {sql_ans.selected_tools})")

# 5b. Document query
t0 = time.perf_counter()
doc_ans = agent.ask("What is the annual leave policy?")
doc_time = time.perf_counter() - t0
print(f"Agent Doc query 'annual leave policy': {doc_time * 1000:.2f} ms (workflow: {doc_ans.workflow})")

# 5c. Combined query
t0 = time.perf_counter()
comb_ans = agent.ask("What were total sales in September 2026 and what does the policy say?")
comb_time = time.perf_counter() - t0
print(f"Agent Combined query: {comb_time * 1000:.2f} ms (workflow: {comb_ans.workflow})")

# 6. Database probe times
print("\n--- 6. DATABASE PROBE TIMES ---")
from backend.app.main import _sqlite_probe
t0 = time.perf_counter()
_sqlite_probe(settings.auth_db_path)
_sqlite_probe(settings.document_catalog_path)
_sqlite_probe(settings.business_db_path)
_sqlite_probe(settings.rag_index_path)
probe_time = time.perf_counter() - t0
print(f"4 SQLite file probes took: {probe_time * 1000:.2f} ms")

print("\n=== PROFILING COMPLETE ===")
