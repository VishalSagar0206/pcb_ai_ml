# Backend image: FastAPI app (src/pcb_ai/api/app.py) serving the deterministic
# DRC + RAG + LLM diagnosis pipeline. Deliberately does NOT install KiCad --
# this project treats a missing `kicad-cli` as a fully supported state
# (kicad_available=false, DRC falls back to recorded fixtures for the bundled
# sample boards; see DEVELOPMENT.md "KiCad availability"). Install KiCad
# yourself and mount `kicad-cli` in if you need live DRC against your own
# boards inside the container.
FROM python:3.11-slim

WORKDIR /app

# Install the package first (separate layer) so `docker build` doesn't
# reinstall all dependencies every time only data/ or pcb_qa-4FEE/ changes.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Bundled demo/sample boards, curated real datasheets for the Knowledge Base
# showcase, and the pcb_qa-4FEE reference benchmark (Research Lineage tab).
COPY data ./data
COPY pcb_qa-4FEE ./pcb_qa-4FEE

RUN mkdir -p /app/results /app/data/knowledge /app/data/datasheets /app/data/pcb_uploads

ENV API_HOST=0.0.0.0 \
    API_PORT=8000 \
    CAF_MODEL_PROVIDER=mock

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "pcb_ai.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
