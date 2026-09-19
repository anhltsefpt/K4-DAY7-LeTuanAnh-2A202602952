# Báo Cáo Cá Nhân — Lab 7: Embedding & Vector Store

**Họ tên:** Lê Tuấn Anh
**Nhóm:** G26
**Ngày:** 2026-09-19

> **Nộp 1 bản / sinh viên.** Phần nhóm (lựa chọn tài liệu, thiết kế chiến lược, bộ câu hỏi đánh giá, demo) nộp chung 1 bản trong `REPORT_NHOM.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần cá nhân: 60** = Khởi động (5) + Hướng tiếp cận (10) + Hoàn thiện code (30) + Dự đoán độ tương tự (5) + Kết quả truy xuất của tôi (10).

---

## 1. Khởi động (Warm-up) — Cá nhân (5 điểm)

### Độ tương tự Cosine (Cosine Similarity) (Bài tập 1.1)

**Độ tương tự cosine cao (High cosine similarity) nghĩa là gì?**
> hai đoạn text được model coi là CÙNG NGHĨA / CÙNG CHỦ ĐỀ

**Ví dụ có độ tương tự CAO:**
- Câu A: Sinh viên năm nhất được miễn học phí học kỳ đầu. 
- Câu B: Tân sinh viên không phải đóng tiền học cho kỳ một
- Tại sao tương đồng: Gần như không trùng từ nào ("miễn học phí" vs "không phải đóng tiền học", "năm nhất" vs "tân sinh viên") nhưng nghĩa y hệt. Nếu embedding cho similarity cao ở đây, nó chứng minh model hiểu nghĩa, không chỉ so khớp mặt chữ.

**Ví dụ có độ tương tự THẤP:**
- Câu A: Học bổng dành cho sinh viên có hoàn cảnh khó khăn.
- Câu B: Thư viện mở cửa đến 21 giờ mỗi ngày.
- Tại sao khác: Cùng "chủ thể trường đại học" nhưng khác hẳn chủ đề → góc lớn → similarity thấp.

**Tại sao độ tương tự cosine (cosine similarity) được ưu tiên hơn khoảng cách Euclid (Euclidean distance) cho text embeddings?**
> *
 cosine chỉ đo HƯỚNG của vector, còn Euclid đo cả hướng lẫn ĐỘ DÀI — mà với text embedding, nghĩa nằm ở hướng, còn độ dài thường là nhiễu.
### Bài toán tính toán Chunking (Bài tập 1.2)

**Tài liệu 10,000 ký tự, chunk_size=500, overlap=50. Bao nhiêu chunks?**
> **Phép tính:** Mỗi chunk mới chỉ tiến thêm `chunk_size − overlap = 500 − 50 = 450` ký tự (bước nhảy). Theo công thức trong `exercises.md`:
> `số chunk = ceil((độ_dài − overlap) / (chunk_size − overlap)) = ceil((10000 − 50) / (500 − 50)) = ceil(9950 / 450) = ceil(22.11) = 23`
> **Đáp án: 23 chunks.** Kiểm chứng bằng `FixedSizeChunker(chunk_size=500, overlap=50).chunk('a'*10000)` trong repo → trả về đúng `23`.

**Nếu độ chồng chéo (overlap) tăng lên 100, số lượng chunk thay đổi thế nào? Tại sao muốn độ chồng chéo nhiều hơn?**
> Tăng lên **25 chunks** (kiểm bằng chunker cho ra `25`): overlap lớn hơn làm bước nhảy giảm còn `500 − 100 = 400`, mỗi chunk tiến chậm hơn nên cần nhiều chunk hơn để phủ hết — `ceil((10000 − 100) / 400) = ceil(24.75) = 25`. Đôi khi vẫn muốn overlap lớn để **giữ ngữ cảnh nối giữa các chunk**: câu/thông tin nằm vắt qua ranh giới sẽ xuất hiện trọn vẹn ở ít nhất một chunk thay vì bị cắt đôi, giảm rủi ro chunk chứa đáp án bị mất nửa nội dung nên không lọt top-k — đánh đổi là tốn thêm bộ nhớ và chi phí embedding.

---

## 2. Hướng tiếp cận của tôi (My Approach) — Cá nhân (10 điểm)

Giải thích cách tiếp cận của bạn khi lập trình (implement) các phần chính trong gói `src`.

### Các hàm chia nhỏ (Chunking Functions)

**`SentenceChunker.chunk`** — hướng tiếp cận:
> Tôi tách câu bằng `re.split(r"(?<=[.!?])\s+", text)`: dùng lookbehind `(?<=[.!?])` để cắt ở khoảng trắng *đứng sau* dấu câu, nhờ vậy dấu `.`/`!`/`?` **ở lại với câu** thay vì bị nuốt mất như khi split trực tiếp trên `[.!?]\s+`. Sau đó gom mỗi `max_sentences_per_chunk` câu thành một chunk, `strip()` khoảng trắng thừa và bỏ chunk rỗng; text rỗng/toàn khoảng trắng trả `[]` để không crash. Edge case chưa xử lý được: chữ viết tắt (`TS.`, `v.v.`) và số thập phân (`3.5`) bị cắt nhầm vì mọi dấu `.` theo sau bởi khoảng trắng đều bị coi là hết câu.

**`RecursiveChunker.chunk` / `_split`** — hướng tiếp cận:
> Thuật toán chạy **hai chiều**. `_split` đệ quy *xuống sâu*: thử separator theo thứ tự `["\n\n", "\n", ". ", " ", ""]`, cắt bằng ranh giới "to" trước để giữ ngữ nghĩa, mảnh nào vẫn dài hơn `chunk_size` mới đệ quy với đuôi danh sách separator. `chunk` rồi *gom lên*: nối các mảnh nhỏ liền kề tới sát `chunk_size` để tránh sinh ra hàng trăm chunk vụn. Có **ba base case**: mảnh đã `≤ chunk_size` trả về chính nó; hết separator hoặc gặp separator rỗng `""` thì cắt cứng theo `chunk_size` (nhánh này xử lý `separators=[]`).

### Lớp EmbeddingStore

**`add_documents` + `search`** — hướng tiếp cận:
> Mỗi `Document` được chuẩn hoá qua helper `_make_record` thành 1 record `{id, content, embedding, metadata}` rồi `append` vào `self._store` — 1 `Document` = 1 record, **không tự chunk** (việc chunking làm ở tầng ngoài). `search` embed câu hỏi rồi tính độ tương tự bằng **dot product** giữa vector query và embedding từng record; dùng được dot product vì vector đã được chuẩn hoá `||v||=1` nên nó bằng đúng cosine. Cả hai gọi chung helper `_search_records` — hàm này sắp xếp giảm dần theo score, cắt lấy `top_k` và bỏ trường `embedding` khỏi kết quả cho gọn.

**`search_with_filter` + `delete_document`** — hướng tiếp cận:
> `search_with_filter` **lọc metadata TRƯỚC** (giữ record khớp mọi cặp key-value trong `metadata_filter`) rồi mới chạy `_search_records` trên tập ứng viên đã lọc — nếu search trước rồi mới bỏ cái không khớp thì k slot có thể bị tài liệu sai chiếm hết, còn 0 kết quả dù store vẫn còn tài liệu hợp lệ. Khi `metadata_filter` rỗng/`None` thì dùng cả store, nhờ đi chung một đường code với `search` nên kết quả không lệch. `delete_document` xoá mọi record có `metadata['doc_id']` khớp và trả `True`/`False` tuỳ có xoá được gì không; điều này phụ thuộc việc `_make_record` luôn gán sẵn `doc_id` (mặc định về `doc.id`).

### Tác tử KnowledgeBaseAgent

**`answer`** — hướng tiếp cận:
> Ba nhịp: (1) truy xuất top-k chunk qua `store.search`; (2) dựng ngữ cảnh đánh số `[1] [2] [3]` kèm `doc_id` nguồn để câu trả lời **truy vết được** về đúng chunk và đúng file (Source Traceability); (3) gọi `llm_fn` với prompt chứa ngữ cảnh đó. Prompt có thêm ràng buộc **chống bịa** — chỉ dùng thông tin trong ngữ cảnh, không có thì nói rõ là không tìm thấy, và yêu cầu trích dẫn số nguồn khi trả lời. Trường hợp store rỗng (không truy xuất được gì) thì trả thẳng câu thông báo, **không crash và không gọi LLM vô ích**.

---

## 3. Hoàn thiện code (Core Implementation) — Cá nhân (30 điểm)

Vượt qua bộ kiểm thử là điều kiện tính điểm phần này.

### Kết Quả Kiểm Thử (Test Results)

```
==================================== test session starts =====================================
platform darwin -- Python 3.11.6, pytest-9.1.1, pluggy-1.6.0 -- /Users/anh/Desktop/learn-ai/ai-thuc-chien/0.learn/7-day/lab/.venv/bin/python3.11
cachedir: .pytest_cache
rootdir: /Users/anh/Desktop/learn-ai/ai-thuc-chien/0.learn/7-day/lab
collected 42 items

tests/test_solution.py::TestProjectStructure::test_root_main_entrypoint_exists PASSED  [  2%]
tests/test_solution.py::TestProjectStructure::test_src_package_exists PASSED           [  4%]
tests/test_solution.py::TestClassBasedInterfaces::test_chunker_classes_exist PASSED    [  7%]
tests/test_solution.py::TestClassBasedInterfaces::test_mock_embedder_exists PASSED     [  9%]
tests/test_solution.py::TestFixedSizeChunker::test_chunks_respect_size PASSED          [ 11%]
tests/test_solution.py::TestFixedSizeChunker::test_correct_number_of_chunks_no_overlap PASSED [ 14%]
tests/test_solution.py::TestFixedSizeChunker::test_empty_text_returns_empty_list PASSED [ 16%]
tests/test_solution.py::TestFixedSizeChunker::test_no_overlap_no_shared_content PASSED [ 19%]
tests/test_solution.py::TestFixedSizeChunker::test_overlap_creates_shared_content PASSED [ 21%]
tests/test_solution.py::TestFixedSizeChunker::test_returns_list PASSED                 [ 23%]
tests/test_solution.py::TestFixedSizeChunker::test_single_chunk_if_text_shorter PASSED [ 26%]
tests/test_solution.py::TestSentenceChunker::test_chunks_are_strings PASSED            [ 28%]
tests/test_solution.py::TestSentenceChunker::test_respects_max_sentences PASSED        [ 30%]
tests/test_solution.py::TestSentenceChunker::test_returns_list PASSED                  [ 33%]
tests/test_solution.py::TestSentenceChunker::test_single_sentence_max_gives_many_chunks PASSED [ 35%]
tests/test_solution.py::TestRecursiveChunker::test_chunks_within_size_when_possible PASSED [ 38%]
tests/test_solution.py::TestRecursiveChunker::test_empty_separators_falls_back_gracefully PASSED [ 40%]
tests/test_solution.py::TestRecursiveChunker::test_handles_double_newline_separator PASSED [ 42%]
tests/test_solution.py::TestRecursiveChunker::test_returns_list PASSED                 [ 45%]
tests/test_solution.py::TestEmbeddingStore::test_add_documents_increases_size PASSED   [ 47%]
tests/test_solution.py::TestEmbeddingStore::test_add_more_increases_further PASSED     [ 50%]
tests/test_solution.py::TestEmbeddingStore::test_initial_size_is_zero PASSED           [ 52%]
tests/test_solution.py::TestEmbeddingStore::test_search_results_have_content_key PASSED [ 54%]
tests/test_solution.py::TestEmbeddingStore::test_search_results_have_score_key PASSED  [ 57%]
tests/test_solution.py::TestEmbeddingStore::test_search_results_sorted_by_score_descending PASSED [ 59%]
tests/test_solution.py::TestEmbeddingStore::test_search_returns_at_most_top_k PASSED   [ 61%]
tests/test_solution.py::TestEmbeddingStore::test_search_returns_list PASSED            [ 64%]
tests/test_solution.py::TestKnowledgeBaseAgent::test_answer_non_empty PASSED           [ 66%]
tests/test_solution.py::TestKnowledgeBaseAgent::test_answer_returns_string PASSED      [ 69%]
tests/test_solution.py::TestComputeSimilarity::test_identical_vectors_return_1 PASSED  [ 71%]
tests/test_solution.py::TestComputeSimilarity::test_opposite_vectors_return_minus_1 PASSED [ 73%]
tests/test_solution.py::TestComputeSimilarity::test_orthogonal_vectors_return_0 PASSED [ 76%]
tests/test_solution.py::TestComputeSimilarity::test_zero_vector_returns_0 PASSED       [ 78%]
tests/test_solution.py::TestCompareChunkingStrategies::test_counts_are_positive PASSED [ 80%]
tests/test_solution.py::TestCompareChunkingStrategies::test_each_strategy_has_count_and_avg_length PASSED [ 83%]
tests/test_solution.py::TestCompareChunkingStrategies::test_returns_three_strategies PASSED [ 85%]
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_filter_by_department PASSED [ 88%]
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_no_filter_returns_all_candidates PASSED [ 90%]
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_returns_at_most_top_k PASSED [ 92%]
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_reduces_collection_size PASSED [ 95%]
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_returns_false_for_nonexistent_doc PASSED [ 97%]
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_returns_true_for_existing_doc PASSED [100%]

===================================== 42 passed in 0.03s =====================================
```

**Số lượng bài test vượt qua (pass):** 42 / 42

---

## 4. Dự đoán độ tương tự (Similarity Predictions) — Cá nhân (5 điểm)

| Cặp | Câu A | Câu B | Dự đoán | Điểm thực tế | Đúng? |
|------|-----------|-----------|---------|--------------|-------|
| 1 | Sinh viên hộ nghèo được cấp học bổng toàn phần 100% học phí. | Học sinh thuộc gia đình nghèo được miễn toàn bộ tiền học nhờ học bổng. | cao | 0.683 | ✔ |
| 2 | Hồ sơ đăng ký nộp về Phòng 202, Nhà D7. | Giấy tờ đăng ký gửi tới phòng 202 tòa nhà D7. | cao | 0.936 | ✔ |
| 3 | Học bổng dành cho sinh viên có hoàn cảnh khó khăn. | Học phí chương trình tiên tiến khoảng 60 triệu đồng một năm. | thấp | 0.295 | ✔ |
| 4 | Đăng ký học bổng online tại trang tuyển sinh của trường. | Mức hỗ trợ 5.500.000 đồng mỗi tháng cho chương trình tài năng. | thấp | 0.316 | ✔ |
| 5 | Điều kiện xét học bổng dựa trên hoàn cảnh gia đình. | Tiêu chí cấp học bổng căn cứ vào hoàn cảnh của sinh viên. | cao | 0.610 | ✔ |

> Đo bằng `compute_similarity()` với embedder thật `paraphrase-multilingual-MiniLM-L12-v2`. Ngưỡng phân loại: ≥0.5 = cao, <0.5 = thấp. Cả 5/5 khớp dự đoán.

**Kết quả nào bất ngờ nhất? Điều này nói gì về cách embeddings biểu diễn ý nghĩa?**
> Bất ngờ nhất là chênh lệch giữa cặp 2 (0.936) và cặp 1 (0.683): cặp 2 gần như trùng mặt chữ ("Phòng 202, Nhà D7" ≈ "phòng 202 tòa nhà D7") nên điểm rất cao, còn cặp 1 diễn đạt lại hoàn toàn ("hộ nghèo... toàn phần 100% học phí" vs "gia đình nghèo... miễn toàn bộ tiền học") nên tuy vẫn cao nhưng thấp hơn hẳn. Điều này cho thấy model đúng là nắm được **ngữ nghĩa** (cặp 1 vẫn ~0.68 dù đổi từ), nhưng khi từ vựng trùng khít thì điểm bị đẩy lên gần cực đại — tức biểu diễn vẫn chịu ảnh hưởng một phần từ **hình thức bề mặt**, không thuần ngữ nghĩa 100%. Ngược lại, hai câu cùng "chủ thể trường đại học" nhưng khác chủ đề (cặp 3, 4) rơi xuống ~0.3, xác nhận khoảng cách được quyết định bởi chủ đề chứ không phải vài từ chung.

---

## 5. Kết quả truy xuất của tôi (Competition Results) — Cá nhân (10 điểm)

Chạy **5 câu hỏi đánh giá của nhóm** trên mã nguồn cá nhân của bạn trong gói `src`. **5 câu hỏi này phải trùng với các thành viên cùng nhóm** (xem `REPORT_NHOM.md`).

> Chiến lược của tôi: **HeadingChunker** (`chunk_size=500`), embedder thật `paraphrase-multilingual-MiniLM-L12-v2` (local), `top_k=3`, đo bằng `bench.py`. Cùng 5 câu với nhóm (REPORT_NHOM mục 3).

| # | Câu hỏi (Query) | Top-1 Chunk truy xuất được (tóm tắt) | Điểm Score | Có liên quan không? (Relevant) | Câu trả lời của Agent (tóm tắt) |
|---|-------|--------------------------------|-------|-----------|------------------------|
| 1 | Học phí IT-E10/năm? | "# Học phí Đại học 2022 — khoá K67..." (đúng bảng học phí) | 0.717 | Có (đúng tài liệu + có con số ~60tr trong top-3) | Trả đúng: ~60 triệu đồng/năm học |
| 2 | Nộp hồ sơ trực tuyến hay trực tiếp? (đã lọc `student`) | "# Tiêu chí xét học bổng hỗ trợ học tập..." | 0.702 | Có (đúng đối tượng student sau khi lọc) | Đúng tài liệu nhưng chunk "Phòng 202, Nhà D7" **không** lọt top-3 → trả lời còn chung chung, thiếu địa chỉ nộp |
| 3 | Học sinh lớp 12 đăng ký cách nào? | "# Mở đăng ký học bổng... cho học sinh năm cuối THPT" | 0.727 | Có (đúng tài liệu applicant) | Đúng tài liệu nhưng chunk chứa URL "đăng ký online" **không** lọt top-3 → thiếu link cụ thể |
| 4 | Hồ sơ gồm giấy tờ gì? (đã lọc `student`) | "## Hồ sơ đăng ký — Hồ sơ gồm: Đơn... sổ hộ khẩu..." | 0.774 | Có (đúng chunk liệt kê) | Trả đúng: liệt kê được danh sách giấy tờ |
| 5 | Mức/tháng theo NĐ179? | "## Tiêu chuẩn và điều kiện để được xét cấp học bổng..." | 0.771 | Có (đúng tài liệu NĐ179) | Đúng tài liệu nhưng chunk nêu "5.500.000 đồng/tháng" **không** lọt top-3 → thiếu con số |

**Bao nhiêu câu hỏi trả về chunk có liên quan trong top-3?** **5 / 5** (mức tài liệu — gold luôn ở #1). *Lưu ý:* ở **mức nội dung** (chunk chứa đúng đáp án nằm trong top-3) chỉ **2/5** (Q1, Q4) — Q2/Q3/Q5 truy xuất đúng tài liệu nhưng chunk chứa con số/địa chỉ/URL không lọt top-3.

**Điều hay nhất tôi học được từ thành viên khác / nhóm khác (qua demo):**
> Bài học lớn nhất là phải **chấm hai mức**, không chỉ đếm `doc_id` trong top-3. Chiến lược của tôi đạt 5/5 ở mức tài liệu nhưng chỉ 2/5 ở mức nội dung — nếu chỉ nhìn `doc_id` thì tưởng hoàn hảo, thực tế agent vẫn thiếu con số/địa chỉ để trả lời. So với bạn dùng FixedSize/Recursive (2/10 nội dung), HeadingChunker nhỉnh hơn nhờ mỗi chunk là một mục trọn vẹn kèm tiêu đề, nhưng cả nhóm đều thấy cần tăng `top_k` hoặc chunk theo mục nhỏ hơn để chunk chứa đáp án cụ thể lọt vào ngữ cảnh.

---

## Tự Đánh Giá (Phần Cá Nhân)

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Khởi động (Warm-up) | 5 / 5 |
| Hướng tiếp cận của tôi (My Approach) | 10 / 10 |
| Hoàn thiện code (Core Implementation — tests) | 30 / 30 |
| Dự đoán độ tương tự (Similarity Predictions) | 5 / 5 |
| Kết quả truy xuất của tôi (Competition Results) | 10 / 10 |
| **Tổng phần cá nhân** | **60 / 60** |

> Ghi chú tự đánh giá: mục Competition tính theo tiêu chí "chunk liên quan trong top-3" (`docs/SCORING.md`) — đạt 5/5. Đã nêu trung thực ở mục 5 rằng mức nội dung chỉ 2/5; đây là hạn chế đã phân tích, không giấu.
