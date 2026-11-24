# Bệnh án F20/F32 — thiết kế

## Yêu cầu
- Thêm menu "Bệnh án" và hai trang **Tâm thần phân liệt (F20)**, **Trầm cảm (F32)**.
- Nội dung, bố cục và hành vi giống bản thiết kế `103_design_v2` (`clinical.js`, `clinical.css`, `clinical-schema.js`); chỉ quan tâm hai trang này.
- Được sửa database, backend, trợ lý nếu cần.
- Dữ liệu tạo ra khi kiểm thử phải được xoá sau khi xong.

## Quyết định
- **Lưu trên máy chủ:** API `/api/v1/clinical`, bảng `clinical_patients` + `clinical_visits`. Bản HTML của thiết kế lưu trong IndexedDB của trình duyệt; ở đây lưu trên máy chủ.
- **Biểu mẫu:** chuyển nguyên văn `CLINICAL_IDENTITY` + `CLINICAL_FORMS` thành `forms.json` (F20: 14 phần, 107 trường; F32: 16 phần, 160 trường).
- **Không nạp 24 hồ sơ giả lập (MAU-) của thiết kế**, theo yêu cầu trước đó của người dùng là không hiển thị dữ liệu mock.
- **Tải bệnh án:**
  - Dùng model thị giác của hệ thống (structured output theo schema biểu mẫu) thay cho Tesseract chạy trên trình duyệt.
  - Nhận thêm PDF, vì bệnh án thường nhiều trang.
  - Khung "Ảnh bệnh án và nội dung OCR" hiển thị file gốc kèm tóm tắt lần đọc (số trường, mục cần đối soát, ghi chú) thay cho văn bản OCR thô.
- **Giao diện:**
  - `clinical.css` sao nguyên văn, markup/class giữ như `clinical.js`, chỉ thêm hiệu ứng thanh tiến trình khi chờ model.
  - Khi ở trang bệnh án, hai nhóm menu khảo sát thu gọn như thiết kế.
  - Nút trợ lý được đẩy lên trên thanh lưu.
- **Trợ lý dữ liệu:** thêm bảng `clinical_patients`, `clinical_fields` vào ảnh chụp dữ liệu, cùng 3 công cụ (tra cứu trường, thống kê/phân bố, tìm bệnh nhân). Họ tên, quê quán, nơi ở và người làm bệnh án không gửi cho LLM.

## Kiểm thử
- **Backend:** `tests/test_clinical.py` gồm kiểm tra dữ liệu, revision, trùng mã, xoá, tải bệnh án với model giả (đúng/sai loại/rỗng/file sai/lỗi dịch vụ) và công cụ trợ lý.
- **Giao diện:** kiểm thử đầu-cuối bằng Chrome headless với backend và model thật; dữ liệu `UITEST-` tạo ra được xoá hết sau khi chạy.
