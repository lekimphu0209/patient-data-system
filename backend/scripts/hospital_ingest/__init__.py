"""Nạp một lần toàn bộ phiếu khảo sát scan của bệnh viện vào hệ thống.

Mỗi file PDF của bệnh viện chứa phiếu của NHIỀU người, xếp liên tiếp theo mã
(tên file ghi dải mã, ví dụ "PT.CK 01 - 80"). Luồng xử lý:

    quét file (chỉ máy, không gọi VLM): số trang, trang trắng, dải mã trên tên file
    -> VLM nhận diện mẫu của từng trang (phần đầu trang)
    -> tách thành từng người: một mẫu xuất hiện lại = sang người mới
    -> VLM đọc từng phiếu
    -> gán mã đối tượng theo thứ tự người trong file, đối chiếu với mã viết tay đọc được
    -> ghi bản ghi + file gốc của từng phiếu (giống hệt luồng tải file trên giao diện)

Mọi kết quả VLM được lưu vào thư mục làm việc; chạy lại (sau khi bị ngắt) chỉ gọi
VLM cho phần còn thiếu, và chỉ ghi các phiếu chưa có. Trường hợp không xác định chắc
mã đối tượng thì không đoán: xuất PDF của người đó để tải tay qua giao diện.
"""
