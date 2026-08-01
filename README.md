# Hệ thống quản lý dữ liệu bệnh nhân

Dự án xây dựng nền tảng quản lý dữ liệu bệnh nhân cho bác sĩ, hỗ trợ nhập/xuất dữ liệu và quản lý hồ sơ cơ bản.

## Công nghệ

- **Backend**: FastAPI + SQLAlchemy + Alembic + PostgreSQL
- **Frontend**: React + TypeScript + Vite + Tailwind CSS + TanStack Query/Router
- **Triển khai**: Docker Compose

## Cấu trúc thư mục

```
patient-data-system/
├── backend/               # API FastAPI
│   ├── app/
│   │   ├── core/          # config, database, security, dependencies
│   │   ├── modules/       # auth, patients, documents, import_export
│   │   │   └── patients/
│   │   │       └── form_schema.json   # Định nghĩa biểu mẫu bệnh án (xem bên dưới)
│   │   └── main.py        # entry point
│   ├── migrations/        # Alembic migrations
│   ├── scripts/           # Sinh & nạp dữ liệu mẫu
│   │   └── mock_data/     # CSV dữ liệu mẫu
│   └── tests/             # unit test cơ bản
├── frontend/              # Giao diện React
│   └── src/
│       ├── app/           # router, providers, auth context
│       ├── features/      # API wrappers
│       └── routes/        # pages: login, patients, new patient
├── docker/                # Dockerfile
├── reports/               # File báo cáo .docx/.pdf/.pptx (không commit)
├── storage/               # File upload (không commit)
├── docker-compose.yml     # Postgres + backend
└── .env.example           # Mẫu biến môi trường
```

## Cài đặt nhanh

### 1. Chuẩn bị môi trường

Copy file môi trường:

```bash
cp .env.example .env
```

### 2. Chạy bằng Docker Compose

Chỉ cần chạy lệnh duy nhất để khởi động Postgres và backend:

```bash
docker compose up -d --build
```

Sau khi khởi động xong:

- **API docs**: http://localhost:8000/docs
- **Backend health**: http://localhost:8000/api/health

### 3. Chạy frontend riêng

Nếu muốn xem giao diện, mở terminal khác:

```bash
cd frontend
npm install
npm run dev
```

Frontend sẽ chạy tại: http://localhost:5173

## Tài khoản thử nghiệm

Hệ thống tự động tạo sẵn tài khoản khi khởi động:

- **Email**: `doctor@example.com`
- **Mật khẩu**: `password123`

Có thể thay đổi trong `.env` qua các biến:

```env
DEFAULT_USER_EMAIL=doctor@example.com
DEFAULT_USER_PASSWORD=password123
```

## Biểu mẫu bệnh án (form động)

Toàn bộ cấu trúc bệnh án nằm ở một chỗ duy nhất:
`backend/app/modules/patients/form_schema.json`, dựng theo hai template
`docs/F20. BỆNH ÁN NC BỆNH TTPL.docx` và `docs/F32, BỆNH ÁN NC TRẦM CẢM.docx`.

- **Phân cấp**: `blocks → groups → subgroups → fields`, tương ứng 3 khối trên giao
  diện: `administrative` (PHẦN 1), `medical_history` (PHẦN 2), `examination`
  (PHẦN 3 → PHẦN 7).
- **Kiểu nhập**: `text`, `textarea`, `number` (kèm `unit`), `date`, `radio`,
  `checkbox_group`, `matrix` (bảng Có/Không, bảng Ý thức).
- **Chung / riêng theo bệnh**: node không khai `applies_to` thì áp dụng cho mọi
  loại bệnh; khai `applies_to: ["f20"]` thì chỉ hiện với Tâm thần phân liệt.
  Áp dụng được xuống tận từng option.
- **Điều kiện hiển thị**: `show_if` — ví dụ ô "Cụ thể…" chỉ hiện khi đã tick "Khác".

Frontend không hard-code field nào, chỉ gọi `GET /api/v1/patients/{id}/form-schema`
rồi render. **Muốn thêm/bớt mục trong bệnh án thì sửa file JSON này, không cần
đụng vào code frontend.**

Mã bệnh: `f20` (Tâm thần phân liệt), `f32` (Trầm cảm), `normal` (Bình thường —
không có khối hỏi bệnh và khám tâm thần). Hệ thống tự suy ra từ chẩn đoán của
bệnh nhân qua danh sách `aliases` trong JSON.

## Dữ liệu mẫu (mock data)

Có sẵn 20 bệnh nhân (10 Tâm thần phân liệt + 8 Trầm cảm + 2 Bình thường), mỗi
người 10 lần khám với dữ liệu đầy đủ mọi trường trong template.

### Nạp vào database

```bash
docker compose exec backend python scripts/load_mock_data.py
```

Lệnh này chạy lại được nhiều lần: bệnh nhân trùng mã hồ sơ sẽ được cập nhật chứ
không nhân bản. Muốn xoá hẳn rồi nạp lại từ đầu:

```bash
docker compose exec backend python scripts/load_mock_data.py --replace
```

Chạy ngoài Docker (cần `DATABASE_URL` trỏ đúng database):

```bash
cd backend && python scripts/load_mock_data.py
```

### Sinh lại bộ dữ liệu khác

```bash
docker compose exec --user "$(id -u):$(id -g)" backend python scripts/generate_mock_csv.py
```

> Nhớ cờ `--user`: container chạy bằng `root`, thiếu cờ này thì 2 file CSV sinh ra
> sẽ thuộc quyền `root` trên máy bạn, sau đó không sửa/xoá được và `git pull` sẽ
> báo *permission denied*.

Script đọc `form_schema.json` nên dữ liệu sinh ra luôn khớp template hiện tại —
thêm trường mới vào JSON thì chạy lại là có ngay dữ liệu cho trường đó. Đổi hằng
`SEED` trong `scripts/generate_mock_csv.py` để ra bộ khác, `EXAMS_PER_PATIENT` để
đổi số lần khám mỗi bệnh nhân.

### Định dạng CSV

| File | Nội dung |
| --- | --- |
| `backend/scripts/mock_data/patients.csv` | Mỗi dòng 1 bệnh nhân — khối hành chính + khối hỏi bệnh |
| `backend/scripts/mock_data/examinations.csv` | Mỗi dòng 1 lần khám — khối khám bệnh, nối với bệnh nhân qua `patient_code` |

Tên cột chính là **đường dẫn trong schema**, ví dụ:

```text
examination.general.weight
examination.mental_exam.emotion.symptoms.depressed_mood
medical_history.disease_history.onset_age
```

Trường nhiều lựa chọn ghi nhiều giá trị ngăn bằng dấu `|`
(`bizarre|agitated|other`). Nhờ quy ước này, loader chỉ cần tách theo dấu chấm là
dựng lại được cấu trúc lồng nhau, và bạn có thể mở file bằng Excel để sửa tay rồi
nạp lại.

Ngoài các cột theo schema, `patients.csv` còn có `patient_code`, `birth_date`,
`diagnosis`, `disease_type`, `disease_code` để xác định danh tính và loại biểu mẫu.

Cột `diagnosis` chỉ nhận đúng 3 nhãn — `Bình thường`, `Trầm cảm`,
`Tâm thần phân liệt` — để khớp bộ lọc chẩn đoán ở danh sách bệnh nhân. Mã ICD chi
tiết (`F20.1 - ... thể thanh xuân`) nằm ở *Chẩn đoán xác định* của từng lần khám
trong `examinations.csv`.

## Phát triển

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Chạy migration:

```bash
alembic upgrade head
```

Chạy test:

```bash
python -m pytest
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Build kiểm tra TypeScript:

```bash
npm run build
```

## Số hoá phiếu khám (OCR & đọc file digital)

Ở khối **KHÁM BỆNH** có hai nút, cùng đi chung một quy trình:

| Nút | Dùng cho | Cách đọc |
| --- | --- | --- |
| **OCR** | Ảnh chụp, bản scan (JPG/PNG/TIFF, PDF scan) | Đưa thẳng ảnh cho vision model |
| **Upload phiếu khám** | File Word `.docx`, PDF xuất từ văn bản | Trích text rồi cho model đọc — nhanh và rẻ hơn |

Quy trình: **chọn file → AI bóc tách → màn hình soát (trái: bản gốc, phải: biểu
mẫu đã điền sẵn) → sửa chỗ sai → Lưu**. Chỉ khi bấm Lưu mới tạo lần khám thật,
nên upload nhầm file không làm bẩn hồ sơ.

Hệ thống chỉ bóc **PHẦN 3 → PHẦN 7**; phần hành chính và hỏi bệnh giữ nguyên
theo dữ liệu đã có trong hệ thống.

**Tự nhận dạng file**: PDF không tự nói nó là bản scan hay văn bản. Hệ thống dò
lớp text thật trong file rồi tự chọn cách đọc — bấm nhầm nút vẫn ra kết quả
đúng, và có dòng ghi chú giải thích đã chuyển chế độ.

**Không bao giờ đoán**: model được yêu cầu bỏ trống thay vì suy diễn, và mọi giá
trị trả về đều phải khớp danh sách lựa chọn trong `form_schema.json` mới được
ghi nhận. Giá trị lạ bị loại và liệt kê ở mục cảnh báo để bác sĩ tự điền. Riêng
phủ định được chặn cứng: "không bình thường" không bao giờ bị hiểu thành
"Bình thường".

Mỗi lần khám lưu kèm nguồn gốc (`manual` / `ocr` / `upload`) và id file gốc;
bảng khám bệnh hiển thị nhãn tương ứng. Bản model đọc (`raw_result`) và bản bác
sĩ đã sửa (`reviewed_result`) đều được giữ trong `ocr_extractions` để về sau còn
đánh giá độ chính xác của model.

### Cấu hình

```env
OPENAI_API_KEY=            # để trống -> chạy chế độ giả lập, không gọi ra ngoài
OPENAI_BASE_URL=https://api.openai.com/v1
OCR_PROVIDER=openai        # openai | stub
OCR_MODEL=gpt-4o
DOC_PARSER_PROVIDER=openai
DOC_PARSER_MODEL=gpt-4o-mini
EXTRACTION_MAX_PAGES=10
EXTRACTION_TIMEOUT_SECONDS=180
EXTRACTION_MAX_FILE_MB=20
EXTRACTION_PDF_DPI=200     # tăng nếu chữ viết tay khó đọc
```

Chưa có key thì toàn bộ luồng vẫn chạy được với dữ liệu giả — tiện để thử giao
diện và chạy test tự động.

### Thay nhà cung cấp

Khi team có model OCR riêng: viết một lớp con của `ExamExtractor`
(`backend/app/modules/documents/extractor/base.py`), khai báo thêm một nhánh
trong `extractor/factory.py`, rồi đổi `OCR_PROVIDER`. Phần đặc tả trường, kiểm
tra dữ liệu, màn hình soát và lưu trữ dùng lại nguyên vẹn.

## Xuất dữ liệu khám bệnh

Trong trang chi tiết bệnh nhân, khối **KHÁM BỆNH** có nút **Xuất Excel**. File tải
về gồm 2 sheet:

- **Bảng khám bệnh** — đúng các cột đang hiển thị trên giao diện, mỗi ô là bản
  tóm tắt của một khối.
- **Chi tiết** — mỗi trường trong template là một cột riêng (mỗi dòng của bảng
  Có/Không cũng thành một cột), dạng bảng phẳng để đưa thẳng vào phân tích thống kê.

Nhãn cột lấy từ `form_schema.json` nên thêm mục vào template là file xuất tự có
thêm cột. API tương ứng: `GET /api/v1/patients/{id}/exams/export`.

## Lưu ý

- `.env` chứa thông tin nhạy cảm, đã được ignore. Chỉ commit `.env.example`.
- OpenAI API key chỉ cần khi bật tính năng OCR thực tế; hiện tại backend đang dùng stub.
- Redis đã được loại bỏ ở phiên bản skeleton này để đơn giản.
