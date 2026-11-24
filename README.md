# Hệ thống quản lý và phân tích dữ liệu sức khỏe tâm thần

Ứng dụng của Bệnh viện Quân y 103 quản lý phiếu khảo sát của thanh niên và quân nhân. Frontend sử dụng React, TypeScript, Vite và TanStack. Backend sử dụng FastAPI, SQLAlchemy và PostgreSQL. Docker Compose phục vụ frontend qua Nginx.

## Khởi động

Tạo `.env` từ `.env.example` khi cài mới và cấu hình tài khoản, khóa JWT, thông tin PostgreSQL. Dùng tài khoản hiện có để đăng nhập. Với cơ sở dữ liệu mới, API tạo tài khoản cấu hình bằng `DEFAULT_USER_EMAIL` và `DEFAULT_USER_PASSWORD`.

```bash
docker compose up -d --build
```

Truy cập cổng `FRONTEND_PORT` đã cấu hình. API cung cấp `/api/health` và OpenAPI tại cổng `BACKEND_PORT`. API tự tạo bảng khảo sát còn thiếu khi khởi động. Môi trường quản lý schema bằng Alembic có thể áp dụng các revision đến `20261120_survey_documents` thông qua `alembic upgrade head`.

Khi chạy frontend riêng, vào `frontend/`, chạy `npm ci` và `npm run dev`. Vite chuyển tiếp `/api` đến cổng backend cấu hình trong `frontend/vite.config.ts`.

## Phiếu khảo sát

- Dashboard tổng hợp số phiếu, đối tượng, tiến độ và phân bố câu trả lời của phiếu đã hoàn tất.
- Danh sách Thanh niên có hai biểu mẫu F08–F09. Danh sách Quân nhân có bảy biểu mẫu F01–F07. Danh mục, câu hỏi, chỉ dẫn chuyển câu (`skipIf`) và nội dung xem trước Word nằm trong `backend/app/modules/surveys/forms.json`. Chuyển câu: F01 theo Câu 5, 7a, 8, 16 (câu được chuyển qua bị bỏ câu trả lời); F09 phần D — D0 = Không thì D1–D4 không bắt buộc nhưng câu trả lời đã đánh vẫn được giữ.
- Có thể nhập thủ công, nhập Excel hoặc tải file phiếu đã điền. Luồng Excel xem trước các hàng hợp lệ trước khi lưu.
- Nút "Tải file khảo sát" nhận ảnh JPG, PNG, WebP, PDF scan hoặc PDF (tối đa 40 MB). Mỗi lượt tải là phiếu của **một người**: chọn một mẫu cụ thể, hoặc chọn "Nhiều phiếu của một người — tự tách theo mẫu" khi file gồm nhiều mẫu (ví dụ bộ thanh niên F08 + F09, bộ quân nhân F01–F07). Ở chế độ tự tách, model nhận diện mẫu của từng trang qua phần đầu trang (mã mẫu in ở góc, tiêu đề), gom trang theo mẫu rồi đọc từng phiếu song song; trang trắng và mẫu chưa có trong hệ thống được bỏ qua; cùng một mẫu xuất hiện hai lần thì cả file bị từ chối vì có phiếu của nhiều người. Mỗi phiếu được lưu một file gốc riêng chỉ gồm các trang của phiếu đó.
- Mã đối tượng được chuẩn hoá về một dạng: chữ in hoa, các phần ngăn cách bằng dấu chấm (`PT.CK 001` → `PT.CK.001`, `QK1. 02` → `QK1.02`); mã nhập tay khớp mã đã có (không phân biệt hoa thường, dấu ngăn cách, số 0 đứng đầu) thì dùng lại mã đã có. Khi tự tách, mã được đọc hai lần độc lập (lúc nhận diện trang và lúc đọc phiếu); hai lần lệch nhau, mã viết tay không rõ hoặc phiếu không ghi mã thì hệ thống hỏi xác nhận mã trước khi lưu. Đóng hộp thoại mà không lưu thì file đã tải lên bị xoá.
- Backend render từng trang thành ảnh, bỏ trang trắng, rồi gửi model thị giác `OCR_MODEL` (mặc định `gpt-5.6-luna`, mức suy luận `EXTRACTION_REASONING_EFFORT`) kèm JSON schema chặt sinh từ câu hỏi của biểu mẫu, sau đó kiểm lại mọi đáp án. Dấu bị khoanh tròn hay gạch xoá được coi là đã huỷ. Câu có dấu sửa, chữ viết tay khó đọc hoặc không chắc chắn được liệt kê để đối soát; phiếu chỉ ở trạng thái "Chờ đối soát" khi đủ câu và không còn mục nghi vấn, còn lại là "Bản nháp". Không có `OPENAI_API_KEY` thì chạy chế độ giả lập.
- File gốc lưu trong `storage/surveys`. Bảng danh sách có cột "Phiếu gốc", chi tiết phiếu có nút "Xem phiếu gốc" để mở ảnh/PDF ngay trong ứng dụng. Xoá phiếu thì xoá luôn file gốc.
- Thông tin đối tượng dùng chung giữa các phiếu có cùng mã đối tượng trong một nhóm. Phiếu lưu trên PostgreSQL; giao diện chỉ hiển thị dữ liệu thật (không còn phiếu mẫu giả lập) và chưa hiện số liệu cho tới khi tải xong.
- Dữ liệu bệnh án và lần khám của phiên bản trước vẫn lưu trong các bảng cũ. API tương thích tiếp tục phục vụ dữ liệu đó. Việc chuyển hồ sơ cũ sang một trong chín mẫu khảo sát cần quy tắc ánh xạ nghiệp vụ riêng.

## Bệnh án

Menu "Bệnh án" có hai trang: **Tâm thần phân liệt (F20)** và **Trầm cảm (F32)**. Giao diện dựng theo bản thiết kế `103_design_v2` (CSS `clinical.css` sao nguyên văn).

- **Danh sách bệnh nhân:** tìm theo mã, họ tên, chẩn đoán; xem hoặc xoá bệnh nhân (xoá luôn mọi lần khám). Cột chẩn đoán lấy từ lần khám gần nhất.
- **Thêm bệnh nhân:** mã (duy nhất, không phân biệt hoa thường), họ tên, tuổi, giới tính và bệnh án lần khám đầu tiên. Các mục chuyên môn bổ sung sau.
- **Trang bệnh án:**
  - lịch sử khám dạng timeline ngang, bấm từng ngày để xem/sửa lần khám đó;
  - "Thêm lần khám" tạo biểu mẫu trống mới;
  - mục lục các phần bên trái, thanh lưu cố định ở đáy;
  - rời trang khi chưa lưu thì hỏi xác nhận.
- **Lưu đồng thời:** dùng khoá lạc quan (`revision`). Hai người cùng sửa thì người lưu sau được báo tải lại, không ghi đè.
- **Tải bệnh án:**
  - Ảnh JPG/PNG/WebP hoặc PDF, tối đa 40 MB (`EXTRACTION_MAX_FILE_MB`), đọc tối đa 30 trang.
  - Model thị giác `OCR_MODEL` đọc theo JSON schema chặt của biểu mẫu, rồi lưu thành **một bệnh nhân mới** (nguồn OCR, cần đối soát). File gốc và tóm tắt lần đọc được giữ để đối chiếu.
  - Không đọc được mã thì sinh mã `OCR-…`; không đọc được ngày khám thì dùng ngày vào viện, rồi mới đến ngày tải lên.
  - Mã trùng hồ sơ có sẵn thì từ chối, không tạo hồ sơ khác và không ghi đè.
- **Biểu mẫu** nằm trong `backend/app/modules/clinical/forms.json`, chuyển từ mẫu Word nghiên cứu. Mẫu Word gốc tải được tại trang bệnh án (`frontend/public/clinical/`).
- **Lưu trữ:**
  - API `/api/v1/clinical`;
  - bảng `clinical_patients`, `clinical_visits`;
  - file trong `storage/clinical`.
- **Trợ lý dữ liệu:** hỏi được về bệnh án (thống kê, phân bố một trường, tìm bệnh nhân theo điều kiện). Họ tên, quê quán, nơi ở của bệnh nhân không gửi cho LLM.

## Trợ lý dữ liệu

Nút tròn góc dưới bên phải mở khung hỏi đáp. Người dùng gõ câu hỏi tiếng Việt, ví dụ "Quân nhân trả lời thế nào về ý định tự sát hiện tại?" hoặc "Liệt kê thanh niên có nghĩ đến tự sát trong tháng qua". Trợ lý trả lời ngắn gọn, kèm bảng hoặc biểu đồ, có nút tải CSV và dòng "Cách tính". Bấm mã đối tượng trong bảng để mở phiếu của người đó. Khung có các thẻ gợi ý theo từng loại phân tích, và hội thoại được giữ trong phiên đăng nhập.

- **Backend** (`backend/app/modules/assistant/`, API `/api/v1/assistant`):
  - LLM chọn một trong các công cụ phân tích định sẵn: tổng quan, phân bố câu trả lời, so sánh theo nhóm (giới tính, nhóm tuổi, đầu mã, hai câu hỏi), tìm đối tượng theo câu trả lời, hồ sơ một đối tượng, tiến độ đối soát, xu hướng theo thời gian.
  - Câu hỏi ngoài các công cụ đó thì LLM tự viết một câu SELECT (truy vấn nâng cao).
  - Mọi truy vấn chạy trên ảnh chụp dữ liệu trong SQLite bộ nhớ: chỉ đọc, giới hạn thời gian và số dòng, không chạm database thật.
- **Hiển thị và nhật ký:** người dùng không thấy SQL. SQL, tham số công cụ, người hỏi và câu trả lời được ghi vào bảng `assistant_logs`.
- **Quyền riêng tư:** họ tên, ngày sinh, quê quán chỉ hiển thị cho người dùng, không gửi cho LLM. Hệ thống lọc theo cột và theo giá trị, kể cả khi bị ghép trong chuỗi.
- **Cấu hình:**
  - `ASSISTANT_MODEL`: để trống thì dùng `OCR_MODEL`. Gọi qua OpenAI Responses API với `store=false`.
  - `ASSISTANT_REASONING_EFFORT`, `ASSISTANT_MAX_STEPS`, `ASSISTANT_RATE_PER_MINUTE` (mặc định 12 câu/phút/người).
  - Không có `OPENAI_API_KEY` thì trợ lý báo chưa cấu hình.
- **Chi phí:** khoảng 20 nghìn token đầu vào mỗi câu hỏi (dưới $0,01 với `gpt-5.6-luna`). Mỗi câu mất khoảng 3–9 giây.

## Nạp một lần dữ liệu scan của bệnh viện

`backend/scripts/hospital_ingest.sh` sao lưu, xoá dữ liệu bệnh nhân cũ rồi nạp toàn bộ phiếu trong `data/Đối tượng thanh niên` và `data/Đối tượng nhập ngũ ` (mỗi file chứa phiếu của nhiều người, xếp theo mã). Chạy lại được khi bị ngắt mà không gọi lại VLM. Xem `backend/scripts/hospital_ingest/README.md`.

## Kiểm tra

```bash
cd frontend
npm run build
```

```bash
cd backend
pytest -q
```
