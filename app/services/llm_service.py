"""
LLM service - Phase 8.

Wraps Google Gemini via LangChain's ChatGoogleGenerativeAI behind a
small, testable seam (get_llm()) and a LangChain Expression Language
(LCEL) chain: prompt | llm | StrOutputParser.

This phase wires up the model + prompt + chain in isolation, using
manually-supplied context so the integration can be verified without
depending on the embedding search. Phase 9 connects
embedding_service.search_similar_chunks() as the context source to
complete the full RAG pipeline.
"""
import logging

from flask import current_app
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)

_llm = None

SYSTEM_PROMPT = (
    "You are the Enterprise KnowledgeOS AI Knowledge Assistant. "
    "Answer the user's question using ONLY the provided context. "
    "The context may contain information from internal documents "
    "and external web sources.\n\n"

    "For internal-document information, rely only on the supplied "
    "document context.\n"

    "For web information, rely only on the supplied web-search "
    "context.\n\n"

    "If the required information is not present in the context, "
    "clearly say that you do not have enough information. "
    "Do not invent facts.\n\n"

    "When comparing internal documents with web information, "
    "clearly distinguish the user's existing skills from "
    "externally identified requirements.\n\n"

    "Keep answers concise, structured, and professional.\n\n"

    "Context:\n{context}"
)


class LLMError(Exception):
    """Raised when the Gemini call fails (bad/missing API key, network, etc)."""


def get_llm():
    """Lazily construct the ChatGoogleGenerativeAI client (module singleton)."""
    global _llm
    if _llm is None:
        from langchain_google_genai import ChatGoogleGenerativeAI

        api_key = current_app.config["GEMINI_API_KEY"]
        if not api_key:
            raise LLMError(
                "GEMINI_API_KEY is not set. Add it to your .env file to "
                "enable the AI Knowledge Assistant."
            )
        _llm = ChatGoogleGenerativeAI(
            model=current_app.config["GEMINI_MODEL_NAME"],
            google_api_key=api_key,
            temperature=current_app.config["GEMINI_TEMPERATURE"],
        )
    return _llm


def _build_chain():
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{question}"),
    ])
    return prompt | get_llm() | StrOutputParser()


def generate_answer(question: str, context: str) -> str:
    """
    Ask Gemini a question grounded in `context` (plain text, typically
    the concatenation of retrieved chunk texts). Returns the answer
    text. Raises LLMError on any failure so callers can show a clean
    message instead of a stack trace.
    """
    chain = _build_chain()
    try:
        return chain.invoke({"question": question, "context": context or "(no context provided)"})
    except LLMError:
        raise
    except Exception as exc:  # noqa: BLE001 - normalize all provider/network errors
        logger.exception("Gemini call failed")
        raise LLMError(str(exc)) from exc
