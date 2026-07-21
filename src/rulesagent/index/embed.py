"""Voyage embedding wrapper. Phase B of retrieval. Reads VOYAGE_API_KEY from
the environment (loaded from .env). See docs/embedding-providers.md for why
Voyage.

Asymmetric embedding: the corpus is embedded with input_type="document" and
queries with input_type="query". Voyage embeds them into a shared space tuned
so a question lands near the passage that answers it, not near other questions
-- a real retrieval-quality lever, not a cosmetic setting.
"""

import numpy as np
import voyageai
from dotenv import load_dotenv

load_dotenv()

# Voyage accepts up to ~1000 texts per request, but also caps total tokens per
# batch. 128 is a safe, comfortably-under-the-limit batch for rules-length text.
BATCH = 128

_client = None


def _get_client() -> voyageai.Client:
    global _client
    if _client is None:
        _client = voyageai.Client()  # reads VOYAGE_API_KEY from env
    return _client


def _normalize(arr: np.ndarray) -> np.ndarray:
    """L2-normalize rows so cosine similarity is a plain dot product later."""
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


def embed_documents(texts: list[str], model: str) -> np.ndarray:
    """Embed corpus chunks. Returns an (N, dim) float32 array, L2-normalized."""
    client = _get_client()
    vectors: list[list[float]] = []
    for i in range(0, len(texts), BATCH):
        result = client.embed(texts[i : i + BATCH], model=model, input_type="document")
        vectors.extend(result.embeddings)
    return _normalize(np.array(vectors, dtype=np.float32))


def embed_query(text: str, model: str) -> np.ndarray:
    """Embed one query. Returns a (dim,) float32 vector, L2-normalized."""
    client = _get_client()
    result = client.embed([text], model=model, input_type="query")
    return _normalize(np.array(result.embeddings, dtype=np.float32))[0]
