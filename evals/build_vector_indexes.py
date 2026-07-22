"""One-time (per model) embedding of the corpus, persisted to data/parsed/.

Embeddings cost API calls, so we build once and reuse. Run this after any
change to chunking, or to add a model. Run: `uv run python evals/build_vector_indexes.py`
"""

import time
from pathlib import Path

from rulesagent.ingest.parser import parse_comprehensive_rules
from rulesagent.ingest.chunker import chunk_rules
from rulesagent.index.store import VectorStore

REPO = Path(__file__).parent.parent
CR_PATH = REPO / "data" / "raw" / "MagicCompRules 20260619.txt"
OUT_DIR = REPO / "data" / "parsed"

# Default = the shipped model only, so a fresh clone doesn't pay to embed a
# model the app never loads. Pass --models to build others (e.g. the
# voyage-4 A/B column from the Phase B eval).
DEFAULT_MODELS = ["voyage-4-large"]


def store_path(model: str) -> Path:
    return OUT_DIR / f"vector_{model}.pkl"


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS,
                    help="embedding models to build indexes for "
                         f"(default: {' '.join(DEFAULT_MODELS)})")
    models = ap.parse_args().models
    rules, glossary = parse_comprehensive_rules(CR_PATH)
    chunks = chunk_rules(rules, glossary)
    print(f"{len(chunks)} chunks to embed\n")
    for model in models:
        start = time.time()
        store = VectorStore.build(chunks, model)
        store.save(store_path(model))
        print(f"  {model}: embedded {len(chunks)} chunks in {time.time() - start:.1f}s "
              f"-> {store_path(model).name}")


if __name__ == "__main__":
    main()
