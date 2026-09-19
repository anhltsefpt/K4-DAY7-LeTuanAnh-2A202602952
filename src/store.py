from __future__ import annotations

from typing import Any, Callable

from .chunking import _dot
from .embeddings import _mock_embed
from .models import Document


class EmbeddingStore:
    """
    A vector store for text chunks.

    Tries to use ChromaDB if available; falls back to an in-memory store.
    The embedding_fn parameter allows injection of mock embeddings for tests.
    """

    def __init__(
        self,
        collection_name: str = "documents",
        embedding_fn: Callable[[str], list[float]] | None = None,
    ) -> None:
        self._embedding_fn = embedding_fn or _mock_embed
        self._collection_name = collection_name
        self._use_chroma = False
        self._store: list[dict[str, Any]] = []
        self._collection = None
        self._next_index = 0

        try:
            import chromadb  # noqa: F401

            # TODO: initialize chromadb client + collection
            self._use_chroma = False
        except Exception:
            self._use_chroma = False
            self._collection = None

    def _make_record(self, doc: Document) -> dict[str, Any]:
        # Copy metadata để không sửa nhầm object của người gọi.
        metadata = dict(doc.metadata)
        # delete_document lọc theo doc_id -> luôn bảo đảm có khoá này.
        # Ở CP5 nhiều chunk chung một file dùng id "file#0", "file#1" nhưng
        # doc_id trỏ về file gốc; nếu chưa có thì mặc định về chính doc.id.
        metadata.setdefault("doc_id", doc.id)
        return {
            "id": doc.id,
            "content": doc.content,
            "embedding": self._embedding_fn(doc.content),
            "metadata": metadata,
        }

    def _search_records(self, query: str, records: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        query_vec = self._embedding_fn(query)
        scored = []
        for rec in records:
            # Trả bản sao bỏ 'embedding' (vector dài làm bẩn output khi in).
            scored.append({
                "id": rec["id"],
                "content": rec["content"],
                "metadata": rec["metadata"],
                "score": _dot(query_vec, rec["embedding"]),
            })
        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:top_k]

    def add_documents(self, docs: list[Document]) -> None:
        """
        Embed each document's content and store it.

        For ChromaDB: use collection.add(ids=[...], documents=[...], embeddings=[...])
        For in-memory: append dicts to self._store
        """
        for doc in docs:
            self._store.append(self._make_record(doc))

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """
        Find the top_k most similar documents to query.

        For in-memory: compute dot product of query embedding vs all stored embeddings.
        """
        return self._search_records(query, self._store, top_k)

    def get_collection_size(self) -> int:
        """Return the total number of stored chunks."""
        return len(self._store)

    def search_with_filter(self, query: str, top_k: int = 3, metadata_filter: dict = None) -> list[dict]:
        """
        Search with optional metadata pre-filtering.

        First filter stored chunks by metadata_filter, then run similarity search.
        """
        # Lọc TRƯỚC rồi mới search: nếu search trước rồi bỏ cái không khớp,
        # k slot có thể bị tài liệu sai chiếm hết -> còn 0 kết quả dù store còn hợp lệ.
        if metadata_filter:
            candidates = [
                rec for rec in self._store
                if all(rec["metadata"].get(k) == v for k, v in metadata_filter.items())
            ]
        else:
            candidates = self._store
        return self._search_records(query, candidates, top_k)

    def delete_document(self, doc_id: str) -> bool:
        """
        Remove all chunks belonging to a document.

        Returns True if any chunks were removed, False otherwise.
        """
        before = len(self._store)
        self._store = [rec for rec in self._store if rec["metadata"].get("doc_id") != doc_id]
        return len(self._store) < before
