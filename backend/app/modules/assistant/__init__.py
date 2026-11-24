"""Trợ lý dữ liệu: hỏi đáp bằng tiếng Việt về dữ liệu phiếu khảo sát.

LLM chọn công cụ phân tích định sẵn (``tools``) hoặc viết truy vấn dự phòng; mọi truy
vấn chạy trên ảnh chụp dữ liệu trong SQLite bộ nhớ (``snapshot``), không chạm database
thật. Họ tên, ngày sinh, quê quán chỉ hiển thị cho người dùng, không gửi cho LLM.
"""
