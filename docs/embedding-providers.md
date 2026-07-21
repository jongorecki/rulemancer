# Embedding provider comparison (for Phase B — vector retrieval)

Research done 2026-07-21 to decide which embedding API to use once we move
past BM25. Not yet decided — this is the decision aid. All pricing/specs
verified against 2026 sources (cited inline). Anthropic offers no embeddings
API, so "stick to Claude" doesn't cover this layer; embeddings are billed
separately from the OpenRouter LLM layer.

Use case that should drive the choice: a tiny corpus (~3,617 chunks, so
indexing cost is trivial), jargon-heavy rules text, natural-language
queries. Priority is **retrieval quality on specialized vocabulary**, then
integration ease. A later phase also needs a **reranker**, so a provider
that offers both under one account is a plus.

## Comparison

| Provider | Flagship model | $/1M tokens (input) | Max dims (configurable?) | Max context/doc | Reranker in-house? | Integration |
|---|---|---|---|---|---|---|
| **Voyage AI** | voyage-4 / voyage-4-large | $0.06 / $0.12 (lite $0.02) | 2048, Matryoshka (256/512/1024/2048) | 32K | **Yes** — rerank-2.5 ($0.05/M), lite ($0.02/M) | Python SDK, REST, LangChain/LlamaIndex |
| **OpenAI** | text-embedding-3-large | $0.13 std / $0.065 batch | 3072, configurable | 8,191 | **No** | De-facto reference SDK; simplest |
| **Cohere** | embed-v4 | $0.12 text | 1536, configurable 256–1536 | **128K** | **Yes** — Rerank 3.5/4 (signature product) | SDK, REST, LangChain |
| Google (Gemini) | gemini-embedding-001 | $0.15 (batch $0.075) | 3072, MRL | 2,048 | No hobby-tier reranker | Gemini API / Vertex AI SDK |
| Jina AI | jina-embeddings-v4 | ~$0.02 (v3 confirmed) | 2048, truncatable | Very long (late chunking) | Yes — jina-reranker-v2 | REST/SDK |
| Nomic | nomic-embed-text-v2 | Free (open-weight, self-host) | 768, Matryoshka | 8,192 | No managed rerank | Self-host only — not plug-and-play |

## Tradeoffs

- **Voyage AI** — Built domain-specialized models from the start; general
  voyage-4 is benchmarked to beat OpenAI's large model on specialized-domain
  retrieval, which maps directly onto jargon-heavy rules text. Ships its own
  reranker under the same account/SDK. 200M-token free tier covers a
  3,600-chunk hobby project effectively forever.
- **OpenAI** — Easiest integration (most tooling assumes its format), but
  text-embedding-3-large is now visibly behind on 2026 MTEB (64.6, lowest of
  this group), has no embeddings free tier, and zero reranking story — you'd
  need a second vendor for the rerank phase regardless.
- **Cohere** — Rerank is genuinely best-in-class and used even by teams who
  embed elsewhere; embed-v4's 128K context is generous. But raw embedding
  retrieval quality (65.2 MTEB) trails Voyage/Gemini, and the free trial
  (1,000 calls/mo, no production) is thin for iterating.

## Recommendation

**Voyage AI** (voyage-4 or voyage-4-large for embeddings; rerank-2.5 for the
later rerank phase). Single biggest reason: it's the only option here that
pairs top-tier domain/jargon retrieval quality with a bundled reranker in
the same account/SDK, and the 200M-token free tier makes this corpus
effectively free — so we optimize purely for quality without onboarding a
second vendor for reranking later. Cohere is the strong second choice if
reranking ends up mattering more than raw embedding quality.

## Time-sensitive flags

- Voyage voyage-3.x was replaced by voyage-4 (Jan 2026), and voyage-3.x no
  longer carries the free tier — target `voyage-4`/`voyage-4-large`, not a
  voyage-3 name from an older tutorial.
- Open-weight models now top raw MTEB (Qwen3-Embedding-8B 70.6 vs Gemini
  68.3, OpenAI 64.6) — irrelevant for "no infra to manage," but worth
  knowing if self-hosting ever comes up.
- OpenAI embeddings have no free tier at all now; Tier 1 needs a funded
  account before any allowance.

Sources: docs.voyageai.com/docs/pricing · blog.voyageai.com/2025/01/07/voyage-3-large ·
docs.voyageai.com/docs/reranker · openai.com/index/new-embedding-models-and-api-updates ·
developers.openai.com/api/docs/guides/rate-limits · cohere.com/pricing ·
docs.cohere.com/docs/cohere-embed · developers.googleblog.com/gemini-embedding-available-gemini-api ·
awesomeagents.ai/leaderboards/embedding-model-leaderboard-mteb-april-2026 ·
jina.ai/models/jina-embeddings-v4
