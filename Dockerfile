# Rulemancer gated demo container (docs/superpowers/plans/2026-07-27-gated-demo.md
# Task 13). Entrypoint is uvicorn on rulesagent.api.main:app directly --
# run.py is a LOCAL DEV launcher (kills stale processes on a port, opens a
# browser) and must never run inside a container.
FROM python:3.12-slim

WORKDIR /app

# System deps for building any C-extension wheels (numpy etc.) that don't
# ship a manylinux wheel for this base image; removed from the final layer
# isn't done here for simplicity -- this image is not size-sensitive (single
# always-on machine, pulled once per deploy).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
COPY frontend ./frontend
COPY scripts ./scripts

# uv installs from pyproject.toml's [project.dependencies] straight into the
# image's system Python -- no venv needed inside a container that only ever
# runs one thing. MUST be editable (-e): main.py derives REPO from
# Path(__file__).parent x4 to find data/ and scripts/ next to it (same
# convention the local .venv's editable install uses, per pyproject.toml's
# [tool.pytest.ini_options] comment above). A real (non-editable) install
# copies main.py into site-packages/rulesagent/api/main.py, four parents up
# from which is nowhere near /app -- that broke `import refresh_scryfall_bulk`
# (scripts/ not on sys.path) AND would have broken VectorStore.load's path
# the same way, discovered when Task 14's first deploy crash-looped on
# ModuleNotFoundError. Editable install leaves the package pointing at
# ./src, so __file__ still resolves under /app and REPO == /app, matching
# WORKDIR and where scripts/ and the data/ volume actually live.
RUN pip install --no-cache-dir uv \
    && uv pip install --system --no-cache -e .

ENV PYTHONIOENCODING=utf-8
ENV PYTHONUNBUFFERED=1

# data/ is NOT copied in -- the Fly volume is mounted at /app/data at
# runtime, seeded manually once (Task 14). Baking the vector pickle or CR
# text into the image would ship a redistribution problem in every image
# layer forever, not just at runtime (spec: "Not baked into the image --
# redistribution risk and rebuild cost").
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "rulesagent.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
