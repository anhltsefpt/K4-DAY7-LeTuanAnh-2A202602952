from __future__ import annotations

import math
import re


class FixedSizeChunker:
    """
    Split text into fixed-size chunks with optional overlap.

    Rules:
        - Each chunk is at most chunk_size characters long.
        - Consecutive chunks share overlap characters.
        - The last chunk contains whatever remains.
        - If text is shorter than chunk_size, return [text].
    """

    def __init__(self, chunk_size: int = 500, overlap: int = 50) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[str]:
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]

        step = self.chunk_size - self.overlap
        chunks: list[str] = []
        for start in range(0, len(text), step):
            chunk = text[start : start + self.chunk_size]
            chunks.append(chunk)
            if start + self.chunk_size >= len(text):
                break
        return chunks


class SentenceChunker:
    """
    Split text into chunks of at most max_sentences_per_chunk sentences.

    Sentence detection: split on ". ", "! ", "? " or ".\n".
    Strip extra whitespace from each chunk.
    """

    def __init__(self, max_sentences_per_chunk: int = 3) -> None:
        self.max_sentences_per_chunk = max(1, max_sentences_per_chunk)

    def chunk(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []

        # Tách câu ở khoảng trắng đứng SAU dấu ., !, ? — lookbehind giữ lại
        # dấu câu với câu (nếu split trực tiếp trên [.!?]\s+ thì dấu bị nuốt mất).
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]

        chunks: list[str] = []
        for i in range(0, len(sentences), self.max_sentences_per_chunk):
            group = sentences[i : i + self.max_sentences_per_chunk]
            chunk = " ".join(group).strip()
            if chunk:
                chunks.append(chunk)
        return chunks


class RecursiveChunker:
    """
    Recursively split text using separators in priority order.

    Default separator priority:
        ["\n\n", "\n", ". ", " ", ""]
    """

    DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

    def __init__(self, separators: list[str] | None = None, chunk_size: int = 500) -> None:
        self.separators = self.DEFAULT_SEPARATORS if separators is None else list(separators)
        self.chunk_size = chunk_size

    def chunk(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []

        # Chiều 1 — đệ quy xuống sâu: cắt bằng separator "to" trước, hạ dần.
        pieces = self._split(text, self.separators)

        # Chiều 2 — gom lên: nối các mảnh nhỏ liền kề cho tới sát chunk_size,
        # nếu không một file nhiều dòng ngắn sẽ ra hàng trăm chunk vụn.
        merged: list[str] = []
        current = ""
        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue
            if not current:
                current = piece
            elif len(current) + 1 + len(piece) <= self.chunk_size:
                current = f"{current} {piece}"
            else:
                merged.append(current)
                current = piece
        if current:
            merged.append(current)
        return merged

    def _split(self, current_text: str, remaining_separators: list[str]) -> list[str]:
        text = current_text
        # Base case 1: mảnh đã đủ nhỏ.
        if len(text) <= self.chunk_size:
            return [text] if text else []

        # Base case 2: hết separator, hoặc separator rỗng -> cắt cứng theo chunk_size.
        if not remaining_separators or remaining_separators[0] == "":
            return [text[i : i + self.chunk_size] for i in range(0, len(text), self.chunk_size)]

        sep = remaining_separators[0]
        rest = remaining_separators[1:]

        result: list[str] = []
        for part in text.split(sep):
            if not part:
                continue
            if len(part) <= self.chunk_size:
                result.append(part)
            else:
                # Mảnh vẫn quá dài -> hạ xuống separator nhỏ hơn.
                result.extend(self._split(part, rest))
        return result


class HeadingChunker:
    """
    Tách văn bản Markdown theo heading, mỗi section thành một chunk.

    Văn bản quy định được soạn theo mục ("## 1. ...", "## Điều 4 — ...", "### ...");
    mỗi mục đã là một đơn vị ngữ nghĩa trọn vẹn do người soạn chia sẵn. Ý tưởng:
      - Cắt trước mỗi dòng heading (mọi cấp #..######), mỗi section thành một chunk.
      - Section nào dài quá chunk_size thì hạ xuống RecursiveChunker.
      - Khi phải cắt nhỏ, GẮN LẠI tiêu đề vào từng mảnh con — nếu không, mảnh thứ
        hai trở đi mất ngữ cảnh "đây là mục nói về cái gì".

    Phần văn bản đứng trước heading đầu tiên (nếu có) được giữ làm một chunk riêng.
    """

    HEADING_RE = re.compile(r"^#{1,6}\s+\S")

    def __init__(self, chunk_size: int = 500, separators: list[str] | None = None) -> None:
        self.chunk_size = chunk_size
        # Dùng lại RecursiveChunker cho các section dài quá ngưỡng.
        self._recursive = RecursiveChunker(separators=separators, chunk_size=chunk_size)

    def chunk(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []

        chunks: list[str] = []
        for heading, body in self._split_sections(text):
            section = f"{heading}\n{body}".strip() if heading else body.strip()
            if not section:
                continue

            if len(section) <= self.chunk_size:
                chunks.append(section)
                continue

            # Section quá dài -> hạ xuống recursive trên phần thân, rồi gắn lại
            # tiêu đề vào từng mảnh con để không mảnh nào mất ngữ cảnh.
            for piece in self._recursive.chunk(body):
                piece = piece.strip()
                if not piece:
                    continue
                chunks.append(f"{heading}\n{piece}".strip() if heading else piece)
        return chunks

    def _split_sections(self, text: str) -> list[tuple[str | None, str]]:
        """Trả danh sách (heading | None, body). heading=None cho phần mở đầu."""
        sections: list[tuple[str | None, str]] = []
        heading: str | None = None
        body_lines: list[str] = []

        def flush() -> None:
            body = "\n".join(body_lines).strip()
            if heading is not None or body:
                sections.append((heading, body))

        for line in text.splitlines():
            if self.HEADING_RE.match(line):
                flush()
                heading = line.strip()
                body_lines = []
            else:
                body_lines.append(line)
        flush()
        return sections


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def compute_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    cosine_similarity = dot(a, b) / (||a|| * ||b||)

    Returns 0.0 if either vector has zero magnitude.
    """
    norm_a = math.sqrt(_dot(vec_a, vec_a))
    norm_b = math.sqrt(_dot(vec_b, vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return _dot(vec_a, vec_b) / (norm_a * norm_b)


class ChunkingStrategyComparator:
    """Run all built-in chunking strategies and compare their results."""

    def compare(self, text: str, chunk_size: int = 200) -> dict:
        strategies = {
            "fixed_size": FixedSizeChunker(chunk_size=chunk_size).chunk(text),
            "by_sentences": SentenceChunker().chunk(text),
            "recursive": RecursiveChunker(chunk_size=chunk_size).chunk(text),
        }

        result: dict = {}
        for name, chunks in strategies.items():
            count = len(chunks)
            avg_length = sum(len(c) for c in chunks) / count if count else 0.0
            result[name] = {
                "count": count,
                "avg_length": avg_length,
                "chunks": chunks,
            }
        return result
