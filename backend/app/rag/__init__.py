"""
MediSense RAG Pipeline — Hybrid MCP-RAG Architecture.

Modules:
    language        Language detection (FR / AR / Darija)
    normalizer      Query translation to clinical French
    embedder        multilingual-e5-base embeddings (768-dim)
    vectorstore     Qdrant hybrid search (Dense + BM25 + RRF)
    medical_entities ICD-10 entity extraction + payload boost
    reranker        mmarco cross-encoder (evaluation mode)
    safety          Confidence gate + drug warnings + allergy check
    llm             Mistral 7B via Ollama (SSE streaming)
    pipeline        Full orchestrator (steps 1-7)
"""
