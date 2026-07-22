.PHONY: install index run test eval answers ablate log

install:
	uv sync

# Parse + chunk the CR and embed the corpus (one-time; needs VOYAGE_API_KEY
# and the CR txt in data/raw/ -- see README "Run it").
index:
	uv run python evals/build_vector_indexes.py

run:
	uv run python run.py

test:
	uv run pytest

# Retrieval eval (recall@k over the rules questions).
eval:
	uv run python evals/run_eval.py

# Answer eval (generation + grading pre-scores; costs API calls).
answers:
	uv run python evals/run_answer_eval.py

# Gold-by-ablation over the card questions (costs API calls).
ablate:
	uv run python evals/ablate_gold.py

# Quick raw note into LOG.md (bash-only; the 10-second capture habit).
log:
	@read -p "What just happened? " a; \
	 printf "\n## %s\n- %s\n" "$$(date +%F\ %H:%M)" "$$a" >> LOG.md
