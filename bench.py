"""
bench.py — Công cụ đo benchmark của nhóm (CHECKPOINT 5).

KHÔNG phải bài tập được chấm bằng test. Nó làm bốn việc:
  1. Đọc từng file .md, tách frontmatter -> metadata và phần thân -> content.
  2. Chunk phần thân, mỗi chunk thành một Document
     (id="file#i", metadata={**frontmatter, "doc_id": file, ...}).
  3. Nạp vào EmbeddingStore, chạy 5 query qua search_with_filter().
  4. In top-3 kèm score và doc_id để đối chiếu với gold answer.

Cách dùng:
    python bench.py                 # chạy mock embedder (mặc định)
    EMBEDDING_PROVIDER=local  python bench.py
    EMBEDDING_PROVIDER=openai python bench.py
    EMBEDDING_PROVIDER=gemini python bench.py
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from src.chunking import FixedSizeChunker, HeadingChunker, RecursiveChunker, SentenceChunker
from src.embeddings import (
    EMBEDDING_PROVIDER_ENV,
    GEMINI_EMBEDDING_MODEL,
    LOCAL_EMBEDDING_MODEL,
    OPENAI_EMBEDDING_MODEL,
    GeminiEmbedder,
    LocalEmbedder,
    OpenAIEmbedder,
    _mock_embed,
)
from src.models import Document
from src.store import EmbeddingStore

# ─────────────────────────────────────────────────────────────────────────────
# ĐỔI CHIẾN LƯỢC CHUNKING Ở ĐÂY — CHỈ MỘT DÒNG.
# Mọi người dùng CHUNG bộ query + CHUNG mọi thứ khác; mỗi người chỉ đổi dòng này
# sang chiến lược của mình để so sánh mới công bằng.
CHUNKER = HeadingChunker(chunk_size=500)
# CHUNKER = RecursiveChunker(chunk_size=500)
# CHUNKER = FixedSizeChunker(chunk_size=500, overlap=50)
# CHUNKER = SentenceChunker(max_sentences_per_chunk=3)
# ─────────────────────────────────────────────────────────────────────────────

# Thư mục corpus cần nạp. Chỉ lấy tài liệu HUST thật (bỏ template university/*).
DOC_DIRS = ["data/hoc-bong-hoc-phi"]

# 5 câu benchmark dùng chung (khớp REPORT_NHOM mục 3).
# signature = "chuỗi đặc trưng" phải xuất hiện trong ngữ cảnh truy xuất -> chấm mức nội dung (mục 7).
QUERIES = [
    {
        "id": "Q1",
        "type": "tra số liệu",
        "question": "Học phí chương trình Khoa học dữ liệu và Trí tuệ nhân tạo (IT-E10) khoảng bao nhiêu một năm?",
        "gold_doc_id": "hoc-phi-dai-hoc-2022",
        "signature": "khoảng 60 triệu đồng/năm học",
        "filter": None,
    },
    {
        # Câu nhập nhằng đối tượng: student nộp trực tiếp (Phòng 202, Nhà D7),
        # applicant nộp online. Không lọc -> applicant thắng top-1 (sai đối tượng);
        # lọc audience=student -> lật về đáp án student. Đây là câu CẦN FILTER.
        "id": "Q2",
        "type": "nộp hồ sơ ở đâu — CẦN FILTER (nhập nhằng đối tượng)",
        "question": "Hồ sơ học bổng hỗ trợ học tập nộp trực tuyến hay nộp trực tiếp?",
        "gold_doc_id": "tieu-chi-xet-hoc-bong-ho-tro-hoc-tap",
        "signature": "Phòng 202, Nhà D7",
        "filter": {"audience": "student"},
    },
    {
        "id": "Q3",
        "type": "hỏi quy trình",
        "question": "Học sinh lớp 12 muốn đăng ký học bổng hỗ trợ học tập thì đăng ký bằng cách nào?",
        "gold_doc_id": "mo-dang-ky-hoc-bong-ho-tro-hoc-tap-cho-hoc-sinh-nam-cuoi-thpt",
        "signature": "Đăng ký online tại địa chỉ https://ts.hust.edu.vn/dang-ky-hoc-bong",
        "filter": None,
    },
    {
        "id": "Q4",
        "type": "liệt kê",
        "question": "Hồ sơ đăng ký học bổng hỗ trợ học tập (bản cho sinh viên) gồm những giấy tờ gì?",
        "gold_doc_id": "tieu-chi-xet-hoc-bong-ho-tro-hoc-tap",
        "signature": "Bản sao học bạ THPT (có xác nhận của trường THPT)",
        "filter": {"audience": "student"},
    },
    {
        "id": "Q5",
        "type": "tự chọn — số liệu",
        "question": "Sinh viên chương trình đào tạo tài năng nhận học bổng Chính phủ mức bao nhiêu mỗi tháng theo Nghị định 179?",
        "gold_doc_id": "nghi-dinh-55-nhan-hoc-bong",
        "signature": "Mức 5.500.000 đồng/tháng",
        "filter": None,
    },
]


def parse_frontmatter(raw: str) -> tuple[dict, str]:
    """Tách khối frontmatter YAML đơn giản (--- ... ---) thành (metadata, body).

    Chỉ xử lý các cặp `key: value` một dòng — đủ cho corpus của lab (không có
    PyYAML). Không có frontmatter thì trả metadata rỗng và toàn bộ text làm body.
    """
    if not raw.startswith("---"):
        return {}, raw

    lines = raw.splitlines()
    # Dòng 0 là "---". Tìm "---" đóng.
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, raw

    metadata: dict = {}
    for line in lines[1:end]:
        if not line.strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        # Bỏ comment nội dòng kiểu "student   # student | faculty | ...".
        if " #" in value:
            value = value.split(" #", 1)[0].strip()
        # Bỏ dấu nháy bao quanh ("2026.1").
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        metadata[key] = value

    body = "\n".join(lines[end + 1 :]).strip()
    return metadata, body


def build_documents(chunker) -> list[Document]:
    """Đọc mọi .md trong DOC_DIRS, chunk phần thân, trả danh sách Document.

    Bốn chỗ dễ sai (đã tránh):
      - Chunk XẢY RA Ở ĐÂY, ngoài store (không nạp cả file làm một Document).
      - doc_id trỏ về tên file gốc; Document.id mới là "file#i".
      - Frontmatter được trải vào MỌI chunk (để search_with_filter có cái lọc).
      - Bỏ frontmatter trước khi chunk (không đo cả khối YAML).
    """
    documents: list[Document] = []
    for doc_dir in DOC_DIRS:
        for path in sorted(Path(doc_dir).glob("*.md")):
            raw = path.read_text(encoding="utf-8")
            frontmatter, body = parse_frontmatter(raw)
            chunks = chunker.chunk(body)
            for i, chunk in enumerate(chunks):
                documents.append(
                    Document(
                        id=f"{path.stem}#{i}",
                        content=chunk,
                        metadata={
                            **frontmatter,
                            "doc_id": path.stem,
                            "source": str(path),
                            "chunk_index": i,
                        },
                    )
                )
    return documents


class CachingEmbedder:
    """Bọc một embedder thật, cache theo hash nội dung ra file JSON.

    Chạy lại benchmark không gọi lại API (không tốn thêm tiền với OpenAI/Gemini).
    """

    def __init__(self, inner, cache_path: str = ".bench_embed_cache.json") -> None:
        self._inner = inner
        self._backend_name = getattr(inner, "_backend_name", inner.__class__.__name__)
        self._cache_path = Path(cache_path)
        self._cache: dict[str, list[float]] = {}
        if self._cache_path.exists():
            try:
                self._cache = json.loads(self._cache_path.read_text(encoding="utf-8"))
            except Exception:
                self._cache = {}

    def __call__(self, text: str) -> list[float]:
        key = hashlib.md5(text.encode("utf-8")).hexdigest()
        if key not in self._cache:
            self._cache[key] = self._inner(text)
            self._cache_path.write_text(json.dumps(self._cache), encoding="utf-8")
        return self._cache[key]


def select_embedder():
    """Chọn embedder theo EMBEDDING_PROVIDER (giống main.py). Mock là mặc định.

    Backend gọi API (openai/gemini) được bọc cache theo hash nội dung.
    """
    load_dotenv(override=False)
    provider = os.getenv(EMBEDDING_PROVIDER_ENV, "mock").strip().lower()

    if provider == "local":
        try:
            return LocalEmbedder(model_name=os.getenv("LOCAL_EMBEDDING_MODEL", LOCAL_EMBEDDING_MODEL))
        except Exception:
            return _mock_embed
    if provider == "openai":
        try:
            return CachingEmbedder(OpenAIEmbedder(model_name=os.getenv("OPENAI_EMBEDDING_MODEL", OPENAI_EMBEDDING_MODEL)))
        except Exception:
            return _mock_embed
    if provider == "gemini":
        try:
            return CachingEmbedder(GeminiEmbedder(model_name=os.getenv("GEMINI_EMBEDDING_MODEL", GEMINI_EMBEDDING_MODEL)))
        except Exception:
            return _mock_embed
    return _mock_embed


def print_results(store: EmbeddingStore, query: dict, metadata_filter, label: str = "") -> None:
    """Chạy một query và in top-3 kèm score, doc_id, và có/không chứa signature."""
    results = store.search_with_filter(query["question"], top_k=3, metadata_filter=metadata_filter)
    tag = f" [{label}]" if label else ""
    filt = metadata_filter if metadata_filter else "(không lọc)"
    print(f"\n  filter={filt}{tag}")
    if not results:
        print("    (không có kết quả — store rỗng sau khi lọc?)")
        return
    for rank, r in enumerate(results, start=1):
        doc_id = r["metadata"].get("doc_id")
        hit = "✔ gold" if doc_id == query["gold_doc_id"] else "      "
        preview = r["content"][:80].replace("\n", " ")
        print(f"    {rank}. score={r['score']:+.3f} {hit} doc_id={doc_id}  id={r['id']}")
        print(f"       {preview}...")
    # Chấm mức nội dung: signature có nằm trong ngữ cảnh top-3 không?
    context = " ".join(r["content"] for r in results)
    has_sig = query["signature"] in context
    print(f"    signature {'CÓ' if has_sig else 'KHÔNG'} trong ngữ cảnh top-3: {query['signature']!r}")


def main() -> int:
    embedder = select_embedder()
    backend = getattr(embedder, "_backend_name", embedder.__class__.__name__)

    documents = build_documents(CHUNKER)
    store = EmbeddingStore(collection_name="bench", embedding_fn=embedder)
    store.add_documents(documents)

    print("=== bench.py — CHECKPOINT 5 ===")
    print(f"Chunker      : {CHUNKER.__class__.__name__}")
    print(f"Embedder     : {backend}")
    print(f"Số file      : {sum(len(list(Path(d).glob('*.md'))) for d in DOC_DIRS)}")
    print(f"Số chunk nạp : {store.get_collection_size()}")
    if backend.startswith("mock"):
        print("LƯU Ý: MockEmbedder không mã hoá ngữ nghĩa — số liệu retrieval là nhiễu (xem mục 7).")

    for query in QUERIES:
        print(f"\n{'─' * 78}")
        print(f"{query['id']} ({query['type']})")
        print(f"  Q: {query['question']}")
        print(f"  gold doc_id: {query['gold_doc_id']}")
        print_results(store, query, query["filter"])

    # A/B bắt buộc cho câu cần filter: chạy hai lần (có / không filter).
    ab = next((q for q in QUERIES if q["filter"]), None)
    if ab:
        print(f"\n{'═' * 78}")
        print(f"A/B — câu cần filter ({ab['id']}): {ab['question']}")
        print_results(store, ab, None, label="A: không filter")
        print_results(store, ab, ab["filter"], label="B: có filter")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
