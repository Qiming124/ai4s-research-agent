# Task 06 — L3 Vector Memory (RAG)

Verify Chroma local vector store, document ingestion API, and RAG retrieval injected into literature/theory agents.

## Prerequisites

```bash
cd /home/agent
source .venv/bin/activate
pip install -e ".[dev]"
```

Ensure `.env` contains a valid `DEEPSEEK_API_KEY` for live chat smoke.

## Automated tests

```bash
pytest tests/ -q
pytest tests/test_rag.py -q
```

Expected: **78 passed** (default `ORCHESTRATION_BACKEND=legacy`).

With langgraph backend, `tests/test_api.py` mocks `GeneralAgent` only — run multi-agent + RAG tests explicitly:

```bash
ORCHESTRATION_BACKEND=langgraph pytest tests/test_multi_agent.py tests/test_rag.py -q
```

## Feature flags

RAG is active when:

```bash
ENABLE_RAG=true
RAG_CHROMA_PATH=./data/chroma
RAG_EMBEDDING_PROVIDER=chroma_default   # or openai, sentence_transformers, test
RAG_AGENTS=literature,theory
```

Literature/theory SubAgents retrieve local chunks before LLM calls. Session stores **doc_id + snippet preview** via `/v1/sessions/{id}/rag-refs`, not full RAG text in L2 messages.

## Architecture (Task 6)

| Component | Path |
|-----------|------|
| Chunking | `server/memory/rag/chunking.py` |
| Embeddings | `server/memory/rag/embeddings.py` |
| Chroma store + registry | `server/memory/rag/store.py` |
| Retrieval + prompt injection | `server/memory/rag/retrieval.py` |
| Session doc refs | `server/memory/rag/session_refs.py` |
| Document API | `server/api/documents.py` |
| Agent integration | `server/agents/subagent.py` |
| Config | `server/config.py`, `.env.example` |
| Schemas | `shared/schemas.py` |

## Embedding providers

| Provider | Use case |
|----------|----------|
| `chroma_default` | Local default (bundled ONNX mini model) |
| `sentence_transformers` | Optional: `pip install 'ai4s-research-agent[rag]'` |
| `openai` | OpenAI-compatible API (`RAG_EMBEDDING_BASE_URL` or `DEEPSEEK_BASE_URL`) |
| `test` | Deterministic vectors for pytest |

## API examples

```bash
# Upload / index markdown
curl -s -X POST http://127.0.0.1:8000/v1/documents \
  -H 'Content-Type: application/json' \
  -d '{"content":"# Adam\nAdam uses adaptive learning rates.","title":"Adam Notes","doc_id":"adam-notes"}'

# List indexed documents
curl -s http://127.0.0.1:8000/v1/documents

# Delete document
curl -s -X DELETE http://127.0.0.1:8000/v1/documents/adam-notes

# Session RAG refs (after chat with literature agent)
curl -s http://127.0.0.1:8000/v1/sessions/{session_id}/rag-refs
```

## Manual chat smoke (requires API key)

```bash
ENABLE_RAG=true ORCHESTRATION_BACKEND=langgraph uvicorn server.main:app --port 8000

curl -s -X POST http://127.0.0.1:8000/v1/documents \
  -H 'Content-Type: application/json' \
  -d '{"content":"The local doc mentions phrase RAG-SMOKE-OK for verification.","title":"Smoke","doc_id":"smoke"}'

curl -s -X POST http://127.0.0.1:8000/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"What phrase is in the local smoke document?","agent":"literature","auto_route":false}'
```

Expect answer referencing `RAG-SMOKE-OK` and rag-refs listing `smoke` doc_id.

## Optional: index MCP files at startup

```bash
ENABLE_RAG=true RAG_INDEX_MCP_FILES=true
```

Indexes `.md` / `.txt` under `MCP_ALLOWED_DIRS`.

## What is not in scope yet (Task 7/8)

- Docker / docker-compose
- Web RAG management UI

## Blockers / notes for Task 7 (Docker)

- Chroma data lives under `RAG_CHROMA_PATH` — mount as volume alongside `data/sessions.db` and `data/mcp_files`
- Default `chroma_default` embedding works in container without extra pip extras; `sentence_transformers` needs `[rag]` extra + model cache volume
- Chroma telemetry warnings in logs are harmless (chromadb 0.5.x)
- Plan optional separate Chroma service in compose; current design uses embedded PersistentClient (single container friendly)
