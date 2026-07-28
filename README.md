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
│   │   └── main.py        # entry point
│   ├── migrations/        # Alembic migrations
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

## Lưu ý

- `.env` chứa thông tin nhạy cảm, đã được ignore. Chỉ commit `.env.example`.
- OpenAI API key chỉ cần khi bật tính năng OCR thực tế; hiện tại backend đang dùng stub.
- Redis đã được loại bỏ ở phiên bản skeleton này để đơn giản.
