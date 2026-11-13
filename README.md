# Hệ thống quản lý và phân tích dữ liệu sức khỏe tâm thần

Ứng dụng của Bệnh viện Quân y 103 quản lý phiếu khảo sát của thanh niên và quân nhân. Frontend sử dụng React, TypeScript, Vite và TanStack. Backend sử dụng FastAPI, SQLAlchemy và PostgreSQL. Docker Compose phục vụ frontend qua Nginx.

## Khởi động

Tạo `.env` từ `.env.example` khi cài mới và cấu hình tài khoản, khóa JWT, thông tin PostgreSQL. Dùng tài khoản hiện có để đăng nhập. Với cơ sở dữ liệu mới, API tạo tài khoản cấu hình bằng `DEFAULT_USER_EMAIL` và `DEFAULT_USER_PASSWORD`.

```bash
docker compose up -d --build
```

Truy cập cổng `FRONTEND_PORT` đã cấu hình. API cung cấp `/api/health` và OpenAPI tại cổng `BACKEND_PORT`. API tự tạo bảng khảo sát còn thiếu khi khởi động. Môi trường quản lý schema bằng Alembic có thể áp dụng revision `20261113_surveys` thông qua `alembic upgrade head`.

Khi chạy frontend riêng, vào `frontend/`, chạy `npm ci` và `npm run dev`. Vite chuyển tiếp `/api` đến cổng backend cấu hình trong `frontend/vite.config.ts`.

## Phiếu khảo sát

- Dashboard tổng hợp số phiếu, đối tượng, tiến độ và phân bố câu trả lời của phiếu đã hoàn tất.
- Danh sách Thanh niên có hai biểu mẫu F08–F09. Danh sách Quân nhân có bảy biểu mẫu F01–F07. Danh mục, câu hỏi và nội dung xem trước Word nằm trong `backend/app/modules/surveys/forms.json`.
- Có thể nhập thủ công, nhập Excel hoặc trích xuất ảnh JPG, PNG, WebP. Luồng Excel xem trước các hàng hợp lệ trước khi lưu. Luồng OCR chạy trong trình duyệt và lần đầu cần tải lõi OCR và mô hình tiếng Việt, tiếng Anh. Phiếu từ OCR lưu kèm ảnh đã nén và văn bản nhận dạng để đối soát.
- Thông tin đối tượng dùng chung giữa các phiếu có cùng mã đối tượng trong một nhóm. Phiếu thật lưu trên PostgreSQL. 88 phiếu mẫu lưu riêng trong trình duyệt và được đánh dấu khi xuất Excel.
- Dữ liệu bệnh án và lần khám của phiên bản trước vẫn lưu trong các bảng cũ. API tương thích tiếp tục phục vụ dữ liệu đó. Việc chuyển hồ sơ cũ sang một trong chín mẫu khảo sát cần quy tắc ánh xạ nghiệp vụ riêng.

## Kiểm tra

```bash
cd frontend
npm run build
```

```bash
cd backend
pytest -q
```
