.PHONY: install parse test eval log

install:
	uv sync

parse:
	uv run python -m rulesagent.ingest.parser

test:
	uv run pytest

eval:
	uv run python evals/run_eval.py | tee /tmp/eval_out.txt
	@echo ""
	@echo "--- 30 seconds, raw answers, don't make it sound good ---"
	@read -p "What did you expect before this ran? " a; \
	 read -p "What surprised you? " b; \
	 printf "\n## %s -- eval\n- expected: %s\n- surprised: %s\n" \
	   "$$(date +%F\ %H:%M)" "$$a" "$$b" >> LOG.md

log:
	@read -p "What just happened? " a; \
	 printf "\n## %s\n- %s\n" "$$(date +%F\ %H:%M)" "$$a" >> LOG.md
