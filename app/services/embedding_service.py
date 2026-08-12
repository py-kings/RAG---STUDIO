"""
Embedding service - Phase 7.

Generates embeddings for a document's parsed chunks (Sentence
Transformers, BAAI BGE model) and stores the vectors in ChromaDB.
Per project requirements, vector embeddings live ONLY in ChromaDB —
MySQL (Document.status/chunk_count) only tracks that indexing
happened, never the vectors themselves.

The model loader (_get_model) and the ChromaDB client are both lazy
and module-level singletons so the (large, slow-to-load) embedding
model is only loaded once per process. embed_texts() is the single
seam tests stub out, so the rest of this module can be exercised
without needing the actual model weights downloaded.
"""
import logging

import chromadb
from flask import current_app

from app import db
from app.services import parsing_service

logger = logging.getLogger(__name__)

_model = None
_chroma_client = None

COLLECTION_NAME = "document_chunks"


class EmbeddingError(Exception):
    """Raised when embedding or vector storage fails."""


# --- Model / client singletons --------------------------------------

def _get_model():
    global _model

    if _model is None:
        from sentence_transformers import SentenceTransformer

        model_name = current_app.config["EMBEDDING_MODEL_NAME"]
        logger.info("Loading embedding model %s", model_name)

        _model = SentenceTransformer(
            model_name,
            device="cpu"
        )

    return _model


def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=current_app.config["CHROMA_PERSIST_DIR"]
        )
    return _chroma_client


def get_collection():
    return get_chroma_client().get_or_create_collection(name=COLLECTION_NAME)


# --- Embedding --------------------------------------------------------

def embed_texts(texts: list) -> list:
    """Encode a batch of texts to normalized embedding vectors."""
    model = _get_model()
    return model.encode(
    texts,
    normalize_embeddings=True,
    batch_size=32,
    show_progress_bar=False
    ).tolist()


def embed_query(query_text: str) -> list:
    return embed_texts([query_text])[0]


# --- Vector storage ----------------------------------------------------

def _chunk_ids(document_id: int, chunks: list) -> list:
    return [f"doc{document_id}_chunk{c['chunk_index']}" for c in chunks]


def delete_document_embeddings(document_id: int) -> None:
    """Remove all vectors for a document (idempotent re-embed, or on delete)."""
    collection = get_collection()
    try:
        collection.delete(where={"document_id": document_id})
    except Exception:  # noqa: BLE001 - deleting a non-existent id set is fine
        logger.debug("No existing embeddings to delete for document %s", document_id)


def embed_document(document) -> dict:
    """
    Embed and store every cached chunk for `document` in ChromaDB.
    Requires the document to have already been parsed (Phase 6) —
    i.e. a parsed_cache/<id>.json file must exist.
    """
    chunks = parsing_service.load_cached_chunks(document)
    if not chunks:
        raise EmbeddingError(
            "No parsed chunks found for this document — parse it first."
        )

    texts = [c["text"] for c in chunks]
    try:
        vectors = embed_texts(texts)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Embedding failed for document %s", document.id)
        raise EmbeddingError(str(exc)) from exc

    ids = _chunk_ids(document.id, chunks)
    metadatas = [
        {
            "document_id": document.id,
            "chunk_index": c["chunk_index"],
            # Chroma metadata can't store None - use -1 for "no page" (DOCX/TXT)
            "page": c["page"] if c["page"] is not None else -1,
            "title": document.title,
        }
        for c in chunks
    ]

    # Re-embedding (e.g. after re-index) should replace, not duplicate.
    delete_document_embeddings(document.id)

    collection = get_collection()
    collection.add(ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas)

    document.status = "indexed"
    db.session.commit()

    return {"chunks_embedded": len(ids)}


def search_similar_chunks(query_text: str, top_k: int = 5, document_id: int = None):
    """
    Semantic search over stored chunks. Used to verify the embedding
    pipeline end-to-end in this phase; the AI Knowledge Assistant
    (Phase 9) will call this as part of the full RAG flow.
    """
    query_vector = embed_query(query_text)
    collection = get_collection()

    kwargs = {"query_embeddings": [query_vector], "n_results": top_k}
    if document_id is not None:
        kwargs["where"] = {"document_id": document_id}

    results = collection.query(**kwargs)

    hits = []
    for doc_text, metadata, distance in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        hits.append({"text": doc_text, "metadata": metadata, "distance": distance})
    return hits
