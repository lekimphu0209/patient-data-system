# Nạp một lần dữ liệu phiếu scan của bệnh viện

Dùng **một lần** để đưa toàn bộ phiếu khảo sát scan bệnh viện gửi (`data/Đối tượng thanh niên`,
`data/Đối tượng nhập ngũ `) vào hệ thống. Không thay đổi cách hệ thống hoạt động: sau khi nạp,
người dùng vẫn tải file theo nguyên tắc một lượt một người như cũ.

Các thư mục khác trong `data/` (hai thư mục `scan trạm y tế …` là bản trùng, `ocr-samples`) bị bỏ qua.

## Lệnh

Chạy từ thư mục gốc repo, khi `docker compose` đang chạy (db + backend):

```bash
# 1. (tuỳ chọn) Quét file: số trang, trang trắng, file hỏng. Không gọi VLM, không ghi gì.
bash backend/scripts/hospital_ingest.sh scan

# 2. Sao lưu rồi xoá dữ liệu bệnh nhân cũ (hỏi gõ xác nhận). Chỉ làm MỘT lần.
bash backend/scripts/hospital_ingest.sh backup-wipe

# 3. Nạp. Nên chạy trong tmux/screen hoặc nohup để mất kết nối SSH không làm dừng.
nohup bash backend/scripts/hospital_ingest.sh run > hospital-ingest.log 2>&1 &
tail -F hospital-ingest.log   # -F: chờ file log được tạo
```

Bị ngắt (mất điện, mất mạng, Ctrl+C, hết ngân sách…) thì **chạy lại đúng lệnh bước 3**:

- phần đã có kết quả VLM không gọi lại;
- phiếu đã ghi không ghi lại;
- file tách dở của lần trước được tự dọn.

Lệnh kết thúc với mã thoát 2 nếu còn file chưa xong. Khi đó chạy lại cho tới khi báo `đã nạp` cho mọi file đọc được.

**Không chạy lại bước 2 sau khi đã nạp.** Bước 2 sẽ xoá dữ liệu vừa nạp. Nếu lỡ chạy, nạp lại từ kết quả đã lưu không tốn tiền VLM, nhưng mọi chỉnh sửa người dùng đã làm sẽ mất.

### Nạp lại một file

Dùng khi một file đã nạp nhưng cần nạp lại, ví dụ sau khi sửa cách tách người:

```bash
bash backend/scripts/hospital_ingest.sh purge-file "Phiếu 181 - 230"   # sao lưu, hỏi gõ GO-PHIEU-DA-NAP
nohup bash backend/scripts/hospital_ingest.sh run > hospital-ingest.log 2>&1 &
tail -F hospital-ingest.log
```

- `purge-file` sao lưu như bước 2, rồi gỡ mọi phiếu đã nạp từ đúng một file nguồn có tên chứa chuỗi đã cho, kèm file gốc tách ra, bản ghi OCR, đối tượng không còn phiếu nào và các dòng tương ứng trong `ledger.jsonl` (bản cũ giữ ở `ledger-truoc-khi-go-*.jsonl`).
- Lệnh từ chối khi tên khớp nhiều file, không khớp file nào, hoặc có phiếu người dùng đã sửa sau khi nạp.
- `run` sau đó chỉ gọi VLM cho những trang mới ghép thành phiếu khác trước; phần còn lại lấy từ cache. Các file khác giữ nguyên.

Tuỳ chọn của `run`:

| Tuỳ chọn | Ý nghĩa |
|---|---|
| `--max-cost 40` | Ngân sách VLM (USD) cho mỗi lần chạy. Chạm ngưỡng thì dừng gọi; chạy lại để tiếp. |
| `--workers 24` | Số lượt gọi VLM song song. |
| `--processes 16` | Số tiến trình render trang PDF. |
| `--retry-failed` | Đọc lại các phiếu VLM đã trả lỗi ở lần trước (mặc định không gọi lại). |
| `--only "PT.CK 01"` | Chỉ xử lý file có tên chứa chuỗi này. Có thể lặp lại. |
| `--max-pages N --dry-run` | Chạy thử N trang đầu mỗi file. Có gọi VLM nhưng không ghi database. |

## Cách hoạt động

1. **Quét file** (chỉ dùng máy): đếm số trang, nhận trang trắng, đọc dải mã trên tên file (`PT.CK 01 - 80`, `QK1. 01 - 180/phieu 01- 41`). File không mở được (ví dụ `phieu 132 - 180.pdf` đang toàn byte 0) bị bỏ qua và ghi vào báo cáo.
2. **Nhận diện trang:** VLM nhận diện mẫu của từng trang qua phần đầu trang, mỗi lượt 10 trang. Cách này giống luồng "Nhiều phiếu của một người" trên giao diện.
3. **Tách người:**
   - Mã viết tay chỉ có ở trang đầu bộ phiếu: F02 với quân nhân, F08 với thanh niên. Trang đầu của mẫu này luôn mở sang người mới.
   - Mẫu đã có của người hiện tại xuất hiện lại ở trang đầu mẫu cũng mở sang người mới. Trường hợp này xảy ra khi người sau mất trang tiêu đề.
   - Trang tiếp nối bị đọc nhầm số mẫu (ví dụ trang 2 của Mẫu 06 đọc thành "Mẫu 05") được giữ với phiếu đang đọc, không tách người. Nếu tách ở đó, mọi ranh giới phía sau trong file sẽ lệch nửa người.
   - Mẫu 02 của quân nhân không có trong hệ thống nên bị bỏ qua.
4. **Đọc phiếu:** VLM đọc từng phiếu với cùng prompt, model, độ phân giải như khi tải trên giao diện.
5. **Gán mã đối tượng:**
   - **Số người khớp dải mã trên tên file:** gán theo thứ tự trong file. Mã viết tay chỉ dùng để đối chiếu; lệch thì phiếu được đánh dấu "cần đối soát mã".
   - **Số người không khớp** (thiếu hoặc thừa người): neo theo mã viết tay đọc chắc chắn (ít nhất 2 lần đọc ra cùng số). Mọi mã của file đó đều được đánh dấu cần đối soát.
   - **Tiền tố mã:** lấy theo cách viết trên phiếu khi đa số người trong file viết giống nhau. Ví dụ file tên `PT.PL …` nhưng trên phiếu viết `PT.TL`, nên mã là `PT.TL.001`.
   - **Số chữ số:** theo cách người điền viết (`PT.CK.001`, `QK1.01`, `QK1.181`). Quyết định này lưu ở `decisions.json` để các lần chạy sau thống nhất.
6. **Ghi:** mỗi phiếu thành một bản ghi.
   - Nguồn "OCR", mã phiếu `OCR-<mã đối tượng>-<mẫu>`.
   - File gốc riêng chỉ gồm các trang của phiếu đó, kèm bản ghi OCR như khi tải qua giao diện.
   - Trạng thái theo đúng quy tắc giao diện: đủ câu và không có mục nghi vấn thì "Chờ đối soát"; ngược lại là "Bản nháp".
   - Ghi chú của phiếu nêu file nguồn, các trang, cách gán mã và các mục cần đối soát.

**Không đoán khi không chắc.** Không xác định chắc mã, hoặc các phiếu của một người ghi hai mã khác nhau, thì người đó không được nạp. Thay vào đó PDF của người đó được xuất ra để nạp tay qua giao diện (mục "Nhiều phiếu của một người"). Phiếu VLM không đọc được cũng được xuất PDF riêng để nạp tay ("Tải file khảo sát", chọn đúng mẫu).

## Kết quả nằm ở đâu (`storage/ingest/`)

| Đường dẫn | Nội dung |
|---|---|
| `report/tom-tat.txt` | Tóm tắt theo file: số người, cách gán mã, số phiếu mới, phiếu lỗi, người cần nạp tay, chi phí. |
| `report/nguoi.csv` | Từng người: trang, mã gán, mã đọc được, phiếu đã nạp, lỗi, lý do nạp tay. |
| `manual/<nhóm>/<file>/` | PDF cần nạp tay qua giao diện. |
| `cache/` | Kết quả VLM; **giữ lại** để chạy lại không tốn tiền. |
| `ledger.jsonl` | Các phiếu đã nạp. Chạy lại không tạo lại phiếu người dùng đã chủ động xoá. |

Thư mục này chứa dữ liệu thật (họ tên…) và không được commit (`storage/*` đã có trong `.gitignore`).

## Chi phí và thời gian

Ước tính từ lần chạy thử 28 người thật với `gpt-5.6-luna` ($0,20 / 1 triệu token vào, $1,20 / 1 triệu token ra):

- khoảng 3.100 lượt gọi, 41 triệu token, **khoảng $10** cho 566 người;
- khoảng 30–45 phút máy chạy.

Sau đó mỗi phiếu ở trạng thái "Chờ đối soát" hoặc "Bản nháp" cần người đối chiếu với file gốc.

## Khôi phục từ bản sao lưu

Bước 2 tạo `backups/<thời điểm>/db.dump` và `storage.tgz`. Để quay lại trạng thái trước khi nạp:

```bash
B=backups/<thời điểm>
docker compose exec -T db sh -c 'pg_restore --clean --if-exists -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < $B/db.dump
docker compose run --rm --no-deps -T -v "$PWD/$B:/restore:ro" backend sh -c \
  'rm -rf storage/surveys/* storage/uploads/* storage/exports/* storage/imports/* && tar -xzf /restore/storage.tgz -C /app'
```

Các lệnh trên đã được chạy thử trên bản sao database: khôi phục đúng số tài khoản, phiếu, bệnh nhân và file.
