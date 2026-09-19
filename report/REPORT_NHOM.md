# Báo Cáo Nhóm — Lab 7: Embedding & Vector Store

**Nhóm:** G26
**Thành viên:** Lê Tuấn Anh, Nguyễn Sơn Giang, Vũ Thường Tín, Nguyễn Ngọc Thái An
**Ngày:** 2026-09-19

> **Nộp 1 bản / nhóm.** Phần cá nhân (hướng tiếp cận, kết quả riêng, dự đoán…) mỗi thành viên nộp riêng trong `REPORT_CANHAN.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần nhóm: 40** = Lựa chọn tài liệu (10) + Thiết kế chiến lược (15) + Chất lượng truy xuất (10) + Thuyết trình (5).

---

## 1. Lựa chọn tài liệu (Document Set Quality) — Nhóm (10 điểm)

### Chủ đề (Domain) & Lý Do Chọn

**Chủ đề:** Học bổng & học phí Đại học Bách khoa Hà Nội (HUST) — dịch vụ/quy định đại học (chủ đề bắt buộc lớp L3A).

**Tại sao nhóm chọn chủ đề này?**
> Đây là thông tin công khai trên cổng tuyển sinh HUST (`ts.hust.edu.vn`), phù hợp chuẩn provenance và không đụng dữ liệu cá nhân. Chủ đề có sẵn hai đối tượng khác nhau — `student` (sinh viên đang học) và `applicant` (học sinh THPT đăng ký) — nên `audience` là chiều lọc metadata có việc thật, đúng yêu cầu bài lab.

### Danh sách tài liệu (Data Inventory)

| # | Tên tài liệu | Nguồn (Source URL) | Ngày lấy / Phiên bản | Số ký tự | Metadata đã gán |
|---|--------------|------------|--------------------|----------|-----------------|
| 1 | Hỗ trợ tài chính cho sinh viên | https://ts.hust.edu.vn/tin-tuc/ho-tro-tai-chinh-cho-sinh-vien | 2026-09-19 / 2025-02-28 | ~3.0K | audience=student, department=academic-affairs, category=financial-aid, language=vi |
| 2 | Học phí Đại học 2022 | https://ts.hust.edu.vn/tin-tuc/hoc-phi-dai-hoc-2022 | 2026-09-19 / 2022-06-29 | ~0.9K | audience=student, department=academic-affairs, category=tuition, language=vi |
| 3 | Mở đăng ký học bổng hỗ trợ học tập cho học sinh năm cuối THPT | https://ts.hust.edu.vn/tin-tuc/mo-dang-ky-hoc-bong-ho-tro-hoc-tap-cho-hoc-sinh-nam-cuoi-thpt | 2026-09-19 / 2020-09-22 | ~2.7K | audience=applicant, department=student-affairs, category=scholarship, language=vi |
| 4 | Chi tiết 55 CTĐT tại Bách khoa HN nhận Học bổng Chính phủ theo Nghị định 179 | https://ts.hust.edu.vn/tin-tuc/chi-tiet-55-chuong-trinh-dao-tao-tai-bach-khoa-ha-noi-nhan-hoc-bong-chinh-phu-theo-nghi-dinh-179 | 2026-09-19 / 2026-07-01 | ~6.3K | audience=student, department=academic-affairs, category=scholarship, language=vi |
| 5 | Tiêu chí xét học bổng hỗ trợ học tập | https://ts.hust.edu.vn/tin-tuc/tieu-chi-xet-hoc-bong-ho-tro-hoc-tap | 2026-09-19 / 2019-09-25 | ~3.3K | audience=student, department=student-affairs, category=scholarship, language=vi |

> **Tổng:** 5 tài liệu · phân bố `audience`: student=4, applicant=1 (≥2 giá trị → filter có việc để lọc) · `category`: scholarship=3, financial-aid=1, tuition=1 · toàn bộ tiếng Việt, nguồn công khai `ts.hust.edu.vn`. `sources.csv` khớp 1-1 với 5 file `.md`.

**Danh sách kiểm tra quản trị dữ liệu (Data governance checklist):**
- [x] Tập tài liệu (Corpus) chỉ chứa nguồn công khai/được phép dùng và không chứa dữ liệu cá nhân, thông tin đăng nhập hoặc tài liệu nội bộ. *(5 tin công khai trên cổng tuyển sinh HUST, `license_or_permission=public-source`.)*
- [x] Mỗi tài liệu có `source_url`, `retrieved_at`, `document_version` (hoặc ngày hiệu lực) trong metadata. *(Đủ ở cả frontmatter `.md` lẫn `sources.csv`.)*

### Cấu trúc Metadata (Metadata Schema)

| Trường metadata | Kiểu | Ví dụ giá trị | Tại sao hữu ích cho truy xuất (retrieval)? |
|----------------|------|---------------|-------------------------------|
| `doc_id` | string | `nghi-dinh-55-nhan-hoc-bong` | Định danh tài liệu gốc; `delete_document` và chấm benchmark theo doc_id đều dựa vào nó (mỗi chunk mang `doc_id` trỏ về file gốc). |
| `audience` | enum(student/applicant/faculty/staff/all) | `student` | Chiều lọc chính: tách câu hỏi của sinh viên đang học vs. học sinh THPT đăng ký — dùng cho `metadata_filter={"audience":"student"}`. |
| `category` | enum(scholarship/tuition/financial-aid) | `scholarship` | Thu hẹp theo loại nội dung, tránh lẫn chunk học phí vào câu hỏi học bổng. |
| `department` | string | `academic-affairs` | Lọc theo đơn vị ban hành; phân biệt nguồn học vụ vs. công tác sinh viên. |
| `source_url` | url | `https://ts.hust.edu.vn/...` | Truy vết nguồn (Source Traceability) — cho phép trích dẫn về đúng trang gốc trong câu trả lời. |
| `document_version` | date/string | `2026-07-01` (hoặc `not-stated`) | Phân biệt phiên bản/ngày hiệu lực; quan trọng với quy định thay đổi theo năm (vd học phí 2022 vs. nghị định 2026). |
| `retrieved_at` | date | `2026-09-19` | Ghi mốc thu thập để đánh giá độ mới của dữ liệu. |
| `language` | enum(vi/en) | `vi` | Xác nhận corpus tiếng Việt, tránh nhiễu ngôn ngữ và chọn embedder phù hợp. |

---

## 2. Thiết kế chiến lược (Strategy Design) — Nhóm (15 điểm)

> Mỗi thành viên thử **một chiến lược khác nhau** trên cùng bộ tài liệu; nhóm tổng hợp và so sánh ở đây.

### Phân tích đường cơ sở (Baseline Analysis)

Chạy `ChunkingStrategyComparator().compare()` trên 3 tài liệu (`chunk_size=500`, đã **bỏ frontmatter** trước khi so sánh để không đo cả khối YAML):

| Tài liệu | Chiến lược (Strategy) | Số lượng Chunk | Độ dài trung bình | Giữ được ngữ cảnh không? |
|-----------|----------|-------------|------------|-------------------|
| `nghi-dinh-55-nhan-hoc-bong` (6310 ký tự) | FixedSizeChunker (`fixed_size`) | 14 | 497.1 | Kém — cắt cứng theo ký tự, dễ đứt giữa dòng/mục |
| `nghi-dinh-55-nhan-hoc-bong` | SentenceChunker (`by_sentences`) | 13 | 483.7 | Trung bình — trọn câu nhưng bỏ qua ranh giới mục |
| `nghi-dinh-55-nhan-hoc-bong` | RecursiveChunker (`recursive`) | 16 | 392.1 | Tốt hơn — ưu tiên tách ở `\n\n`/`\n` nên bám cấu trúc |
| `tieu-chi-xet-hoc-bong-ho-tro-hoc-tap` (3276 ký tự) | FixedSizeChunker (`fixed_size`) | 8 | 453.2 | Kém — cắt cứng theo ký tự |
| `tieu-chi-xet-hoc-bong-ho-tro-hoc-tap` | SentenceChunker (`by_sentences`) | 7 | 466.3 | Trung bình — mất ranh giới mục "Hồ sơ đăng ký" |
| `tieu-chi-xet-hoc-bong-ho-tro-hoc-tap` | RecursiveChunker (`recursive`) | 9 | 361.3 | Tốt hơn — chunk nhỏ, bám xuống dòng |
| `hoc-phi-dai-hoc-2022` (933 ký tự) | FixedSizeChunker (`fixed_size`) | 2 | 491.5 | Kém — có thể cắt ngang bảng học phí |
| `hoc-phi-dai-hoc-2022` | SentenceChunker (`by_sentences`) | 2 | 465.5 | Trung bình |
| `hoc-phi-dai-hoc-2022` | RecursiveChunker (`recursive`) | 3 | 309.0 | Tốt hơn — tài liệu ngắn, tách gọn |

> Nhận xét chung: `recursive` luôn tạo nhiều chunk hơn nhưng độ dài trung bình nhỏ hơn (~310–390) → chunk cô đọng, ít lẫn chủ đề. `fixed_size` cho độ dài đều (~490–500) nhưng cắt cứng theo ký tự nên hay đứt giữa mục/dòng. Với văn bản quy định soạn theo mục, `HeadingChunker` (chiến lược riêng của nhóm) bám ranh giới `##`/`###` sẵn có nên giữ ngữ cảnh tốt nhất — xem phần "Chiến lược của từng thành viên".

### Chiến lược của từng thành viên

> Mỗi thành viên điền một khối dưới đây (copy thêm nếu nhóm có nhiều hơn 3 người).

> Phân công: mỗi người đổi đúng **một dòng** `CHUNKER = ...` trong `bench.py` sang chiến lược của mình, giữ nguyên mọi thứ khác để so sánh công bằng.

**Thành viên 1 — Vũ Thường Tín**
- **Loại chiến lược:** FixedSizeChunker (`fixed_size`) — đường cơ sở ngây thơ
- **Mô tả & lý do chọn cho chủ đề này:** Cắt văn bản thành khối cố định 500 ký tự, chồng lấn 50 ký tự. Chọn làm mốc đối chứng: nó không hiểu cấu trúc tài liệu nên hay cắt ngang câu/mục (ví dụ đứt giữa bảng học phí hay giữa danh sách hồ sơ), qua đó làm nổi bật giá trị của các chiến lược bám cấu trúc.
- **Dòng đổi trong `bench.py`:**
```python
CHUNKER = FixedSizeChunker(chunk_size=500, overlap=50)
```

**Thành viên 2 — Nguyễn Sơn Giang**
- **Loại chiến lược:** RecursiveChunker (`recursive`)
- **Mô tả & lý do chọn:** Tách đệ quy theo thứ tự ưu tiên `["\n\n", "\n", ". ", " ", ""]`, rồi gom các mảnh nhỏ liền kề tới sát 500 ký tự. Với văn bản có nhiều đoạn/danh sách, nó bám ranh giới `\n\n`/`\n` nên chunk cô đọng hơn (Baseline: ~310–390 ký tự) và ít lẫn chủ đề hơn `fixed_size`.
- **Dòng đổi trong `bench.py`:**
```python
CHUNKER = RecursiveChunker(chunk_size=500)
```

**Thành viên 3 — Lê Tuấn Anh**
- **Loại chiến lược:** HeadingChunker (`custom`) — bám heading Markdown
- **Mô tả & lý do chọn:** Văn bản quy định được soạn theo mục (`## 1. ...`, `## Điều 4 — ...`, `### ...`); mỗi mục đã là một đơn vị ngữ nghĩa trọn vẹn. Chiến lược tách trước mỗi dòng heading, mỗi section thành một chunk; section dài quá ngưỡng thì hạ xuống recursive và **gắn lại tiêu đề vào từng mảnh con** để không mảnh nào mất ngữ cảnh "đây là mục nói về cái gì". Kỳ vọng giữ ngữ cảnh tốt nhất cho corpus học bổng/học phí.
- **Code snippet (custom — đặt trong `src/chunking.py`):**
```python
class HeadingChunker:
    """Tách theo heading Markdown; section dài thì hạ xuống recursive và
    gắn lại tiêu đề vào từng mảnh con."""

    HEADING_RE = re.compile(r"^#{1,6}\s+\S")

    def __init__(self, chunk_size: int = 500, separators: list[str] | None = None) -> None:
        self.chunk_size = chunk_size
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
            for piece in self._recursive.chunk(body):
                piece = piece.strip()
                if piece:
                    chunks.append(f"{heading}\n{piece}".strip() if heading else piece)
        return chunks

    def _split_sections(self, text: str) -> list[tuple[str | None, str]]:
        sections, heading, body_lines = [], None, []
        def flush():
            body = "\n".join(body_lines).strip()
            if heading is not None or body:
                sections.append((heading, body))
        for line in text.splitlines():
            if self.HEADING_RE.match(line):
                flush(); heading = line.strip(); body_lines = []
            else:
                body_lines.append(line)
        flush()
        return sections
```
- **Dòng đổi trong `bench.py`:**
```python
CHUNKER = HeadingChunker(chunk_size=500)
```

**Thành viên 4 — Nguyễn Ngọc Thái An**
- **Loại chiến lược:** SentenceChunker (`by_sentences`)
- **Mô tả & lý do chọn:** Tách câu bằng lookbehind `(?<=[.!?])\s+` (giữ dấu câu ở lại), rồi gom mỗi 3 câu thành một chunk. Ưu điểm là **không bao giờ cắt giữa câu** nên chunk chứa con số/định nghĩa được giữ trọn — nhờ vậy bắt đúng Q5 ("Mức 5.500.000 đồng/tháng" nằm gọn trong một chunk). Hạn chế: bỏ qua ranh giới mục/heading, và dễ cắt nhầm ở chữ viết tắt (`TS.`) hay số thập phân (`3.5`).
- **Dòng đổi trong `bench.py`:**
```python
CHUNKER = SentenceChunker(max_sentences_per_chunk=3)
```

### So Sánh Giữa Các Thành Viên

> Điểm truy xuất đo bằng `bench.py`, embedder thật `paraphrase-multilingual-MiniLM-L12-v2` (local), `top_k=3`, trên 5 query mục 3. Ghi **hai mức**: *tài liệu* (gold ở top-3) / *nội dung* (ngữ cảnh chứa đáp án). Số chunk là toàn bộ corpus `data/hoc-bong-hoc-phi/` (5 file), `chunk_size=500`.

| Thành viên | Chiến lược (Strategy) | Điểm truy xuất — tài liệu / nội dung | Điểm mạnh | Điểm yếu |
|-----------|----------|----------------------|-----------|----------|
| Vũ Thường Tín | FixedSizeChunker (37 chunk) | 6/10 · 2/10 | Đơn giản, độ dài đều (~490); chồng lấn giảm mất mát ở mép cắt | Cắt cứng theo ký tự → đứt ngang câu/mục/bảng, chunk lẫn hai chủ đề |
| Nguyễn Sơn Giang | RecursiveChunker (42 chunk) | 8/10 · 2/10 | Bám ranh giới đoạn/dòng, chunk cô đọng (~310–390), ít lẫn chủ đề | Không nhận biết heading; tài liệu phẳng (ít `\n\n`) thì suy về gần cắt cứng |
| Nguyễn Ngọc Thái An | SentenceChunker (45 chunk) | 8/10 · 4/10 | Không cắt giữa câu → chunk chứa con số/định nghĩa trọn vẹn (bắt đúng Q5) | Bỏ qua ranh giới mục; cắt nhầm ở viết tắt/số thập phân |
| **Lê Tuấn Anh** | **HeadingChunker (43 chunk)** | **10/10 · 4/10** | Mỗi chunk là một mục trọn vẹn, giữ tiêu đề khi cắt nhỏ → ngữ cảnh rõ, gold luôn ở #1 | Phụ thuộc chất lượng heading; tài liệu không có `##` (vd hoc-phi) suy về recursive |

**Chiến lược nào tốt nhất cho chủ đề này? Tại sao?**
> **HeadingChunker** (Lê Tuấn Anh) — đã xác nhận bằng số liệu: đứng đầu ở mức tài liệu (10/10, gold luôn ở #1) và đồng hạng cao nhất ở mức nội dung (4/10). Corpus học bổng/học phí được soạn theo mục sẵn (`## 1.`, `## Điều...`, `### ...`) nên mỗi chunk trùng khít một đơn vị ngữ nghĩa và giữ tiêu đề làm ngữ cảnh. SentenceChunker (Thái An) cũng đạt 4/10 nội dung nhờ giữ trọn câu chứa con số — cho thấy "giữ đơn vị ngữ nghĩa nguyên vẹn" (dù là mục hay câu) mới là yếu tố quyết định, chứ không phải độ dài chunk. RecursiveChunker (8/10 tài liệu) bám cấu trúc khá tốt, là dự phòng cho tài liệu ít heading; FixedSizeChunker (6/10) làm mốc đối chứng cho thấy cái giá của việc bỏ qua cấu trúc. Lưu ý chung: cả bốn đều tụt ở mức nội dung (2–4/10) — bám đúng tài liệu chưa đủ, chunk chứa con số/địa chỉ đáp án thường không lọt top-3; hướng cải thiện là tăng `top_k` hoặc chunk theo mục nhỏ hơn.

---

## 3. Câu hỏi đánh giá & Chất lượng truy xuất (Retrieval Quality) — Nhóm (10 điểm)

### Câu hỏi đánh giá & Câu trả lời chuẩn (nhóm thống nhất)

> **Đúng 5 câu hỏi**, đa dạng, có thể kiểm chứng; **ít nhất 1 câu** cần lọc metadata mới trả lời tốt. Đây là bộ câu hỏi chung cho mọi thành viên chạy.

| # | Câu hỏi (Query) | Câu trả lời chuẩn (Gold Answer) | Chunk nào chứa thông tin? |
|---|-------|-------------------------------|--------------------------|
| 1 | *(Tra số liệu)* Học phí chương trình Khoa học dữ liệu và Trí tuệ nhân tạo (IT-E10) khoảng bao nhiêu một năm? | Khoảng 60 triệu đồng/năm học. | `hoc-phi-dai-hoc-2022` — chuỗi đặc trưng: `khoảng 60 triệu đồng/năm học` |
| 2 | *(Nộp hồ sơ ở đâu — **CẦN FILTER**, nhập nhằng đối tượng)* Hồ sơ học bổng hỗ trợ học tập nộp trực tuyến hay nộp trực tiếp? | Sinh viên nộp **trực tiếp**: gửi về Phòng Tuyển sinh, Phòng 202, Nhà D7, ĐHBK Hà Nội. (Học sinh THPT thì đăng ký online — tài liệu applicant.) | `tieu-chi-xet-hoc-bong-ho-tro-hoc-tap` (`audience:student`) — chuỗi đặc trưng: `Phòng 202, Nhà D7` |
| 3 | *(Hỏi quy trình)* Học sinh lớp 12 muốn đăng ký học bổng hỗ trợ học tập thì đăng ký bằng cách nào? | Đăng ký online tại https://ts.hust.edu.vn/dang-ky-hoc-bong | `mo-dang-ky-hoc-bong-ho-tro-hoc-tap-cho-hoc-sinh-nam-cuoi-thpt` (`audience:applicant`) — chuỗi đặc trưng: `Đăng ký online tại địa chỉ https://ts.hust.edu.vn/dang-ky-hoc-bong` |
| 4 | *(Liệt kê)* Hồ sơ đăng ký học bổng hỗ trợ học tập (bản cho sinh viên) gồm những giấy tờ gì? | Đơn theo mẫu; sổ hộ khẩu; CMND/CCCD; giấy hộ nghèo/cận nghèo; giấy tờ khó khăn khác; bệnh án (nếu có); học bạ THPT có xác nhận; thư giới thiệu của GV THPT. | `tieu-chi-xet-hoc-bong-ho-tro-hoc-tap` (`audience:student`) — chuỗi đặc trưng: `Bản sao học bạ THPT (có xác nhận của trường THPT)` |
| 5 | *(Tự chọn — số liệu)* Sinh viên chương trình đào tạo tài năng nhận học bổng Chính phủ mức bao nhiêu/tháng theo Nghị định 179? | 5.500.000 đồng/tháng. | `nghi-dinh-55-nhan-hoc-bong` — chuỗi đặc trưng: `Mức 5.500.000 đồng/tháng` |

### Tổng hợp chất lượng truy xuất của nhóm

> Đo bằng `bench.py`, embedder thật `paraphrase-multilingual-MiniLM-L12-v2` (local), `top_k=3`, chiến lược tốt nhất **HeadingChunker**. **Chấm hai mức** (theo mục 7 lab): (a) *mức tài liệu* — gold có ở top-3 không; (b) *mức nội dung* — ngữ cảnh top-3 có chứa "chuỗi đặc trưng" trả lời được câu hỏi không.

| # | Câu hỏi | Chiến lược tốt nhất | Gold rank (top-3?) | Đáp án có trong ngữ cảnh? | Điểm nội dung |
|---|---------|-------------------------------|-------------------------------|--------------------------|---------------|
| 1 | Học phí IT-E10 | HeadingChunker | #1 ✔ | Có | 2 |
| 2 | Nộp hồ sơ (cần filter) | HeadingChunker | #1 ✔ (sau khi lọc `student`) | Không — chunk chứa "Phòng 202" không lọt top-3 | 0 |
| 3 | Cách đăng ký (applicant) | HeadingChunker | #1 ✔ | Không — chunk chứa URL đăng ký không lọt top-3 | 0 |
| 4 | Hồ sơ gồm gì | HeadingChunker | #1 ✔ | Có | 2 |
| 5 | Mức 5.5tr/tháng (NĐ179) | HeadingChunker | #1 ✔ | Không — lấy chunk mở đầu, không phải chunk nêu con số | 0 |

**Phát hiện quan trọng — chênh lệch hai cách chấm:** với HeadingChunker, **mức tài liệu = 10/10** (cả 5 câu gold đều ở #1) nhưng **mức nội dung chỉ 4/10**. Nghĩa là retrieval bám đúng tài liệu rất tốt, nhưng chunk cụ thể chứa con số/địa chỉ/URL đáp án thường **không** lọt top-3 — nếu chỉ chấm bằng `doc_id` thì kết quả bị thổi phồng. Đây là lý do phải kiểm ở mức nội dung. (fixed_size: 6/10 vs 2/10 · recursive: 8/10 vs 2/10 · heading: 10/10 vs 4/10.)

**Lọc bằng metadata có giúp ích không? Ở câu hỏi nào?**
> Có — rõ nhất ở **câu 2**. Corpus có hai tài liệu cùng chủ đề "học bổng hỗ trợ học tập" nhưng khác đối tượng và khác đáp án về nơi nộp: `tieu-chi-xet-hoc-bong-ho-tro-hoc-tap` (`audience:student` → nộp **trực tiếp** tại Phòng 202, Nhà D7) và `mo-dang-ky-...-thpt` (`audience:applicant` → **đăng ký online**). Câu hỏi không nêu người hỏi là ai. **A/B thật (HeadingChunker, embedder local):**
>
> | Nhánh | top-1 | top-2 | top-3 |
> |---|---|---|---|
> | A — không lọc | **APPLICANT** (0.708) | STUDENT (0.702) | ho-tro-tai-chinh (0.690) |
> | B — lọc `audience:student` | **STUDENT** (0.702) | ho-tro-tai-chinh | ho-tro-tai-chinh |
>
> Không lọc → top-1 là tài liệu applicant, agent sẽ trả "đăng ký online" — **sai đối tượng** với một sinh viên đang học. Lọc `audience:student` → top-1 lật về tài liệu student. Đây là bằng chứng metadata filter thay đổi câu trả lời.
>
> *Ghi chú quá trình:* câu Q2 ban đầu ("Điều kiện xét học bổng là gì?") cho A/B **giống hệt nhau** vì tài liệu student áp đảo (applicant chỉ hạng 6) — đúng cảnh báo của lab "A/B giống nhau ⇒ câu chưa thực sự cần filter". Nhóm đã **sửa câu hỏi** sang câu nộp hồ sơ (nơi nộp khác nhau theo đối tượng) thì filter mới cắn.

---

## 4. Thuyết trình (Demo) & Bài học nhóm — Nhóm (5 điểm)

**Những phân tích (insights) hay nhất nhóm sẽ trình bày:**
> 1. **Chấm hai mức phơi bày sự thật:** HeadingChunker đạt 10/10 ở mức tài liệu (gold luôn ở #1) nhưng chỉ 4/10 ở mức nội dung — nếu chỉ đếm `doc_id` trong top-3 thì kết quả bị thổi phồng ~2,5 lần, vì chunk chứa con số/địa chỉ/URL đáp án thường không lọt top-3.
> 2. **Metadata filter chỉ "cắn" khi câu hỏi thực sự nhập nhằng đối tượng:** câu Q2 ban đầu ("điều kiện xét học bổng") cho A/B giống hệt vì tài liệu student áp đảo; phải đổi sang câu "nộp trực tuyến hay trực tiếp" (đáp án khác nhau theo audience) thì filter mới lật top-1 từ APPLICANT→STUDENT.
> 3. **Mock vs embedder thật khác một trời vực:** cùng bộ query, MockEmbedder cho gold xếp hạng 2–3 với score âm (nhiễu MD5), embedder thật đưa gold lên #1 (score 0.7–0.8).

**Bài học rút ra khi so sánh trong nhóm:**
> Cùng 5 câu và cùng corpus, bốn chiến lược cho kết quả khác nhau rõ ở mức tài liệu: Heading 10/10, Sentence & Recursive 8/10, Fixed 6/10. Điểm mấu chốt không phải độ dài chunk mà là **giữ nguyên vẹn đơn vị ngữ nghĩa**: Heading giữ trọn từng mục, Sentence giữ trọn từng câu (nên cùng đạt 4/10 nội dung), còn Fixed cắt cứng theo ký tự làm đứt ngang câu/mục nên rơi điểm cả hai mức.

**Nếu làm lại, nhóm sẽ thay đổi gì trong chiến lược dữ liệu (data strategy)?**
> Ba điều: (1) tăng `top_k` (3→5) hoặc chunk theo mục nhỏ hơn để chunk chứa con số/địa chỉ đáp án lọt vào ngữ cảnh, kéo điểm mức nội dung lên; (2) bổ sung tài liệu cho cân bằng `audience` (hiện applicant chỉ có 1 file) và cân nhắc gắn `audience` ở cấp section thay vì cả tài liệu; (3) thiết kế câu hỏi đánh giá ngay từ đầu xoay quanh điểm nhập nhằng đối tượng để chứng minh giá trị của metadata filter thay vì phát hiện muộn rồi phải sửa câu hỏi.

---

## Tự Đánh Giá (Phần Nhóm)

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Lựa chọn tài liệu (Document Set Quality) | 10 / 10 |
| Thiết kế chiến lược (Strategy Design) | 15 / 15 |
| Chất lượng truy xuất (Retrieval Quality) | 10 / 10 |
| Thuyết trình (Demo) | 5 / 5 |
| **Tổng phần nhóm** | **40 / 40** |

> Ghi chú: điểm Demo là tự đánh giá dự kiến — điều chỉnh sau khi trình bày thực tế ở mục 8.
