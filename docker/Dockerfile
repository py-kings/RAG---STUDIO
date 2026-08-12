# Enterprise KnowledgeOS - application image
# Includes the full RAG stack (sentence-transformers/torch, PyMuPDF,
# chromadb) so the image is sizeable - this is expected for an
# AI-heavy Flask app, not a build mistake.
FROM python:3.12-slim

# System deps:
# - build-essential: some chromadb/sentence-transformers deps compile from source
# - libgl1: PyMuPDF's rendering backend expects it on slim images
# - curl: used by the container healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libgl1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads parsed_cache chroma_store logs

RUN chmod +x docker/entrypoint.sh

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

ENTRYPOINT ["docker/entrypoint.sh"]
