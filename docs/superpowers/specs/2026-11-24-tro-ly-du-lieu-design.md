# Trợ lý dữ liệu — thiết kế

## Mục đích
Cán bộ hỏi bằng tiếng Việt về dữ liệu phiếu khảo sát sức khỏe tâm thần (thanh niên F08–F09, quân nhân F01–F07) và nhận câu trả lời ngắn kèm bảng/biểu đồ. Ví dụ: "Có bao nhiêu quân nhân trả lời có ý định tự sát?", "Uống rượu theo giới tính", "Liệt kê thanh niên PT.CK có ý nghĩ tự sát".

## Đã chốt với người dùng
- Cách C: ưu tiên công cụ phân tích định sẵn (function calling); câu hỏi ngoài phạm vi thì LLM tự viết truy vấn dự phòng trên dữ liệu an toàn.
- Người dùng gõ câu hỏi tự do, trợ lý tự chọn công cụ. Công cụ chỉ hiện trên giao diện dưới dạng thẻ gợi ý với tên thân thiện.
- Không hiện SQL cho người dùng. Thay bằng dòng "Cách tính" bằng lời thường. SQL và tham số công cụ ghi vào nhật ký phía máy chủ.
- Giao diện: nút tròn góc dưới phải, bấm mở khung chat nhỏ; UI/UX đẹp, thân thiện.

## Quyết định của người xây dựng (đề xuất đã nêu, người dùng cho bắt đầu)
- Trả danh sách có họ tên cho người đã đăng nhập, chỉ hiển thị trong khung chat; họ tên, ngày sinh, quê quán không bao giờ gửi cho LLM (lọc theo cột và theo giá trị).
- Không tính điểm/kết luận sàng lọc: chưa có quy tắc chấm điểm; trợ lý không chẩn đoán.
- Mọi số liệu nêu rõ đã tính trên trạng thái phiếu nào (phần lớn phiếu chưa đối soát).

## Kiến trúc
- Backend `app/modules/assistant/`:
  - `snapshot`: ảnh chụp dữ liệu vào SQLite trong bộ nhớ (bảng `records`, `answers`, `questions`, `subjects`), làm mới khi dữ liệu đổi. Câu trả lời định danh (họ tên, địa chỉ) không đưa vào `answers`. Truy vấn chạy với `query_only`, authorizer chỉ cho đọc, giới hạn thời gian và số dòng. LLM không bao giờ chạm database thật.
  - `tools`: 9 công cụ — tra cứu câu hỏi, tổng quan, phân bố đáp án, so sánh theo nhóm, tìm đối tượng, hồ sơ đối tượng, tiến độ đối soát, xu hướng theo thời gian, truy vấn nâng cao. Mỗi công cụ trả phần tóm tắt cho LLM (không định danh) và các khối hiển thị (thẻ số, bảng, thanh) cho giao diện, kèm "Cách tính".
  - `agent`: vòng lặp function calling (`chat.completions` + `tools`, tối đa vài bước), model mặc định như OCR.
  - `router`: `POST /api/v1/assistant/chat`, `GET /api/v1/assistant/suggestions`; cần đăng nhập; giới hạn tần suất theo người dùng; nhật ký `assistant_logs`.
- Frontend `features/assistant/`: nút nổi + khung chat, thẻ gợi ý theo công cụ, bong bóng hội thoại, bảng (xuất CSV, mở hồ sơ đối tượng), thanh phân bố, trạng thái đang xử lý, lưu hội thoại trong phiên.

## Kiểm thử
- Backend: snapshot, từng công cụ trên dữ liệu mẫu, chặn truy vấn ghi/nguy hiểm, lọc định danh trước khi gửi LLM, vòng lặp agent với LLM giả, API (xác thực, giới hạn, nhật ký, không trả SQL).
- Frontend: build/typecheck và kiểm tra giao diện bằng trình duyệt headless.
