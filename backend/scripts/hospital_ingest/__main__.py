"""Dòng lệnh. Chạy trong container backend (thư mục làm việc /app):

    python -m scripts.hospital_ingest scan                 # chỉ quét file, không gọi VLM
    python -m scripts.hospital_ingest run [--max-pages N]  # nạp (chạy lại được, không gọi lại VLM)
    python -m scripts.hospital_ingest wipe --backup DIR --confirm XOA-DU-LIEU-BENH-NHAN
    python -m scripts.hospital_ingest purge --file "Phiếu 181 - 230" --confirm GO-PHIEU-DA-NAP   # gỡ để nạp lại

Cách dùng đầy đủ (kèm sao lưu): xem README.md cùng thư mục, hoặc scripts/hospital_ingest.sh.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

CONFIRM = "XOA-DU-LIEU-BENH-NHAN"
PURGE_CONFIRM = "GO-PHIEU-DA-NAP"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.hospital_ingest")
    parser.add_argument("--data", type=Path, default=Path("/data"), help="thư mục dữ liệu bệnh viện")
    parser.add_argument("--work", type=Path, default=Path("storage/ingest"),
                        help="thư mục lưu kết quả VLM, báo cáo, PDF cần nạp tay")
    commands = parser.add_subparsers(dest="command", required=True)

    scan = commands.add_parser("scan", help="quét file: số trang, trang trắng, file hỏng (không gọi VLM)")
    scan.add_argument("--processes", type=int, default=16)
    scan.add_argument("--only", action="append", default=[], help="chỉ xử lý file có tên chứa chuỗi này")

    run = commands.add_parser("run", help="nạp dữ liệu")
    run.add_argument("--workers", type=int, default=24, help="số lượt gọi VLM song song")
    run.add_argument("--processes", type=int, default=16, help="số tiến trình đọc trang PDF")
    run.add_argument("--max-pages", type=int, help="chạy thử: chỉ xử lý N trang đầu mỗi file")
    run.add_argument("--only", action="append", default=[], help="chỉ xử lý file có tên chứa chuỗi này")
    run.add_argument("--max-cost", type=float, default=40.0, help="ngân sách VLM (USD) cho lần chạy này")
    run.add_argument("--retry-failed", action="store_true", help="đọc lại các phần VLM đã lỗi ở lần trước")
    run.add_argument("--dry-run", action="store_true", help="gọi VLM, tách, gán mã, báo cáo nhưng không ghi database")
    run.add_argument("--allow-existing", action="store_true", help="cho nạp khi database còn dữ liệu cũ")

    wipe = commands.add_parser("wipe", help="xoá toàn bộ dữ liệu bệnh nhân (giữ tài khoản, file mẫu)")
    wipe.add_argument("--backup", type=Path, required=True, help="thư mục sao lưu vừa tạo (db.dump, storage.tgz)")
    wipe.add_argument("--confirm", required=True, help=f"gõ đúng {CONFIRM}")

    purge = commands.add_parser("purge", help="gỡ các phiếu đã nạp từ một file nguồn để nạp lại file đó")
    purge.add_argument("--file", required=True, help="tên (một phần) của file nguồn, phải khớp đúng một file")
    purge.add_argument("--confirm", required=True, help=f"gõ đúng {PURGE_CONFIRM}")

    args = parser.parse_args(argv)
    if args.command == "wipe":
        return _wipe(args)
    if args.command == "purge":
        return _purge(args)

    from .pipeline import Options, Runner

    options = Options(data=args.data, work=args.work, processes=args.processes, only=args.only)
    if args.command == "scan":
        return _scan(Runner(options))
    options.workers = args.workers
    options.max_pages = args.max_pages
    options.max_cost = args.max_cost
    options.retry_failed = args.retry_failed
    options.dry_run = args.dry_run
    options.allow_existing = args.allow_existing
    states = Runner(options).run()
    unfinished = [state for state in states if state.error is None and state.status not in ("đã nạp", "đã xử lý (chạy thử, chưa ghi)")]
    return 2 if unfinished else 0


def _scan(runner) -> int:
    from .pipeline import GROUP_LABEL

    states = runner.scan()
    total = people = 0
    for state in states:
        source = state.source
        if state.error:
            print(f"[HỎNG] {source.label}: {state.error}")
            continue
        content = state.total_pages - len(state.blank)
        expected = source.expected
        per = f"{content / expected:.1f}" if expected else "?"
        print(f"{GROUP_LABEL[source.group]:10} {source.label}: {state.total_pages} trang, {len(state.blank)} trắng, "
              f"{content} có nội dung; dải mã {source.hint or '?'} {source.start}–{source.end} "
              f"({expected or '?'} người, ~{per} trang nội dung/người)")
        total += state.total_pages
        people += expected or 0
    print(f"Tổng: {total} trang, khoảng {people} người trong các file đọc được.")
    return 0


def _wipe(args) -> int:
    from app.core.database import SessionLocal

    from .store import Ledger, wipe

    if args.confirm != CONFIRM:
        print(f"Từ chối: --confirm phải là {CONFIRM}.", file=sys.stderr)
        return 1
    dump, archive = args.backup / "db.dump", args.backup / "storage.tgz"
    if not (dump.is_file() and dump.stat().st_size > 0 and archive.is_file() and archive.stat().st_size > 0):
        print(f"Từ chối: chưa thấy bản sao lưu đầy đủ trong {args.backup} (cần db.dump và storage.tgz).",
              file=sys.stderr)
        return 1
    with SessionLocal() as db:
        counts = wipe(db, Path("storage"))
    Ledger(args.work / "ledger.jsonl").reset()
    print("Đã xoá: " + ", ".join(f"{name} {count}" for name, count in counts.items()))
    print("Giữ nguyên: bảng users (tài khoản), storage/templates (file mẫu), storage/ingest (kết quả VLM).")
    return 0


def _purge(args) -> int:
    from app.core.database import SessionLocal

    from .store import Ledger, PurgeRefused, ingested_from, purge

    if args.confirm != PURGE_CONFIRM:
        print(f"Từ chối: --confirm phải là {PURGE_CONFIRM}.", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        try:
            label, ids = ingested_from(db, args.file)
        except PurgeRefused as error:
            print(f"Từ chối: {error}.", file=sys.stderr)
            return 1
        counts = purge(db, ids, Ledger(args.work / "ledger.jsonl"))
    print(f"Đã gỡ các phiếu nạp từ {label}: " + ", ".join(f"{name} {count}" for name, count in counts.items()))
    print("Kết quả VLM vẫn giữ trong storage/ingest/cache. Chạy lại lệnh nạp (run) để nạp lại file này.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
