from typing import Callable

from .store import EmbeddingStore


class KnowledgeBaseAgent:
    """
    An agent that answers questions using a vector knowledge base.

    Retrieval-augmented generation (RAG) pattern:
        1. Retrieve top-k relevant chunks from the store.
        2. Build a prompt with the chunks as context.
        3. Call the LLM to generate an answer.
    """

    def __init__(self, store: EmbeddingStore, llm_fn: Callable[[str], str]) -> None:
        self.store = store
        self.llm_fn = llm_fn

    def answer(self, question: str, top_k: int = 3) -> str:
        # 1. Truy xuất top-k chunk liên quan.
        results = self.store.search(question, top_k=top_k)

        # Store rỗng / không có gì liên quan: trả thông báo, đừng gọi LLM vô ích.
        if not results:
            return "Không tìm thấy thông tin liên quan trong cơ sở tri thức."

        # 2. Dựng ngữ cảnh, đánh số [1] [2] [3] kèm nguồn để câu trả lời
        #    truy vết được về đúng chunk và đúng file (Source Traceability).
        context_blocks = []
        for i, r in enumerate(results, start=1):
            source = r.get("metadata", {}).get("doc_id", r.get("id", "?"))
            context_blocks.append(f"[{i}] (nguồn: {source}) {r['content']}")
        context = "\n".join(context_blocks)

        prompt = (
            "Bạn là trợ lý trả lời câu hỏi dựa trên ngữ cảnh được cung cấp.\n"
            "Chỉ dùng thông tin trong NGỮ CẢNH bên dưới; nếu ngữ cảnh không chứa "
            "câu trả lời, hãy nói rõ là không tìm thấy, không được bịa.\n"
            "Khi trả lời, trích dẫn số nguồn [1], [2], ... tương ứng.\n\n"
            f"NGỮ CẢNH:\n{context}\n\n"
            f"CÂU HỎI: {question}\n\n"
            "TRẢ LỜI:"
        )

        # 3. Gọi LLM sinh câu trả lời.
        return self.llm_fn(prompt)
