#!/usr/bin/env bash
# Nạp MỘT LẦN dữ liệu phiếu khảo sát scan của bệnh viện. Hướng dẫn đầy đủ:
# backend/scripts/hospital_ingest/README.md
#
#   bash backend/scripts/hospital_ingest.sh scan          # quét file, không gọi VLM, không ghi gì
#   bash backend/scripts/hospital_ingest.sh backup-wipe   # sao lưu rồi xoá dữ liệu bệnh nhân cũ (hỏi xác nhận)
#   bash backend/scripts/hospital_ingest.sh run [tuỳ chọn] # nạp; bị ngắt thì chạy lại đúng lệnh này
#   bash backend/scripts/hospital_ingest.sh purge-file "Phiếu 181 - 230"  # sao lưu, gỡ phiếu đã nạp từ một file để nạp lại
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
CONFIRM="XOA-DU-LIEU-BENH-NHAN"
PURGE_CONFIRM="GO-PHIEU-DA-NAP"

in_backend() {
  mkdir -p backups
  docker compose run --rm --no-deps -T \
    -v "$ROOT/data:/data:ro" \
    -v "$ROOT/backups:/backups:ro" \
    backend python -m scripts.hospital_ingest "$@"
}

backup() {
  BACKUP_DIR="backups/$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$BACKUP_DIR"
  echo "Sao lưu database -> $BACKUP_DIR/db.dump"
  docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' < /dev/null > "$BACKUP_DIR/db.dump"
  echo "Sao lưu storage (trừ storage/ingest) -> $BACKUP_DIR/storage.tgz"
  tar -czf "$BACKUP_DIR/storage.tgz" --exclude=storage/ingest storage
  # Bản sao lưu phải đọc lại được thì mới cho xoá.
  docker compose exec -T db pg_restore --list < "$BACKUP_DIR/db.dump" > /dev/null
  tar -tzf "$BACKUP_DIR/storage.tgz" > /dev/null
  echo "Sao lưu xong: $BACKUP_DIR"
}

case "${1:-}" in
  scan)
    shift
    in_backend scan "$@"
    ;;
  backup-wipe)
    backup
    echo
    echo "SẮP XOÁ toàn bộ dữ liệu bệnh nhân: phiếu khảo sát, đối tượng, hồ sơ bệnh nhân, file đã tải/xuất."
    echo "Giữ lại: tài khoản đăng nhập, storage/templates, kết quả VLM trong storage/ingest."
    # Xác nhận phải gõ từ bàn phím (không nhận từ pipe/nohup).
    answer=""
    read -r -p "Gõ $CONFIRM để xác nhận: " answer < /dev/tty || true
    if [ "$answer" != "$CONFIRM" ]; then
      echo "Đã huỷ, không xoá gì. Bản sao lưu vẫn ở $BACKUP_DIR."
      exit 1
    fi
    in_backend wipe --backup "/backups/${BACKUP_DIR#backups/}" --confirm "$CONFIRM"
    ;;
  run)
    shift
    in_backend run "$@"
    ;;
  purge-file)
    name="${2:-}"
    if [ -z "$name" ]; then
      echo "Thiếu tên file nguồn, ví dụ: bash $0 purge-file \"Phiếu 181 - 230\"" >&2
      exit 1
    fi
    backup
    echo
    echo "SẮP GỠ mọi phiếu đã nạp từ file có tên chứa \"$name\" (kèm file gốc tách ra, bản ghi OCR, đối tượng)."
    echo "Kết quả VLM giữ nguyên; sau đó chạy lại lệnh run để nạp lại file này."
    answer=""
    read -r -p "Gõ $PURGE_CONFIRM để xác nhận: " answer < /dev/tty || true
    if [ "$answer" != "$PURGE_CONFIRM" ]; then
      echo "Đã huỷ, không gỡ gì. Bản sao lưu vẫn ở $BACKUP_DIR."
      exit 1
    fi
    in_backend purge --file "$name" --confirm "$PURGE_CONFIRM"
    ;;
  *)
    sed -n '2,8p' "$0"
    exit 1
    ;;
esac
